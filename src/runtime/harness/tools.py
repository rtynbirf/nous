"""src/runtime/harness · tools: доверенные обёртки над сырыми возможностями.

Каждое действие — включая отказ гейта — чеканит receipt. Предусловие
(sleep-реалм: realpath) перепроверяется непосредственно перед эффектом
(защита от TOCTOU, defense-in-depth поверх governor.decide()).
"""
from __future__ import annotations

import json
import os
import subprocess

try:
    from .receipts import sha
except ImportError:  # автономный запуск модуля без пакета
    from receipts import sha


class ToolBox:
    def __init__(self, workspace: str, log, gov):
        self.ws = os.path.realpath(workspace)
        os.makedirs(self.ws, exist_ok=True)
        self.log = log
        self.gov = gov

    def execute(self, action_id, tool, op, args=None, risk_class=1,
                approved=False, idem_key=None):
        args = args or {}
        action = {"action_id": action_id, "tool": tool, "op": op, "args": args,
                  "risk_class": risk_class, "approved": approved,
                  "idem_key": idem_key}
        args_hash = sha(json.dumps(args, sort_keys=True,
                                   ensure_ascii=False).encode("utf-8"))
        decision, reason = self.gov.decide(action)
        self.gov.calls += 1
        base = dict(kind="ACTION", action_id=action_id, tool=tool, op=op,
                    args_hash=args_hash)
        if decision != "ALLOW":
            # гейт ДО эффекта: отказ тоже получает receipt (replay-able)
            return self.log.mint(**base, status=f"GATE_{decision}", reason=reason)
        try:
            if tool == "fs":
                return self._fs(action, base)
            if tool == "exec":
                return self._exec(action, base)
            return self.log.mint(**base, status="ERROR", error="unknown tool")
        except Exception as e:  # noqa: BLE001 — ошибка тоже journalируется честно
            return self.log.mint(**base, status="ERROR",
                                 error=f"{type(e).__name__}: {e}")

    def _resolve(self, relpath):
        full = relpath if os.path.isabs(relpath) else os.path.join(self.ws, relpath)
        return os.path.realpath(full)  # канонизация: убивает symlink/относительные эскейпы

    def _fs(self, action, base):
        op, args = action["op"], action["args"]
        full = self._resolve(args["path"])
        if not (full == self.ws or full.startswith(self.ws + os.sep)):
            return self.log.mint(**base, status="BLOCKED",
                                 reason="realpath outside workspace "
                                        "(symlink/relative escape)")
        rel = os.path.relpath(full, self.ws)
        if op == "write":
            os.makedirs(os.path.dirname(full), exist_ok=True)
            data = str(args.get("content", "")).encode("utf-8")
            with open(full, "wb") as f:
                f.write(data)
            return self.log.mint(**base, status="OK", path=rel,
                                 output_hash=sha(data), size=len(data))
        if op == "read":
            with open(full, "rb") as f:
                data = f.read()
            return self.log.mint(**base, status="OK", path=rel,
                                 output_hash=sha(data), size=len(data))
        if op == "delete":
            existed = os.path.exists(full)
            if existed:
                os.remove(full)
            return self.log.mint(**base, status="OK" if existed else "ERROR",
                                 path=rel, existed=existed,
                                 **({} if existed else {"error": "file not found"}))
        return self.log.mint(**base, status="ERROR", error=f"unknown fs op '{op}'")

    def _exec(self, action, base):
        cmd = action["args"].get("cmd", "")
        timeout = action["args"].get("timeout", 10)
        p = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           timeout=timeout, cwd=self.ws)
        out, err = p.stdout, p.stderr
        return self.log.mint(**base, status="OK" if p.returncode == 0 else "FAIL",
                             cmd=cmd, exit_code=p.returncode,
                             stdout_hash=sha(out), stderr_hash=sha(err),
                             stdout_ref=out.decode("utf-8", "replace")[:4000],
                             stderr_ref=err.decode("utf-8", "replace")[:4000])
