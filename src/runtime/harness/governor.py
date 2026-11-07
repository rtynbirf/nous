"""src/runtime/harness · governor: детерминированный слой политики.

decide() считает ЗДЕСЬ, кодом, а не моделью. На вход — описание действия,
гранты и бюджеты; на выход — ALLOW | DENY | ASK. Модель не может расширить
свои права: их меняет владелец в конфиге грантов, не в надежде (аксиома
N=СУБЪЕКТ≠ИНДИВИД; A8-кандидат: budget-закон).
"""
from __future__ import annotations

import os
import time

ALLOW, DENY, ASK = "ALLOW", "DENY", "ASK"


class Governor:
    def __init__(self, workspace: str, grants: dict,
                 max_calls: int = 1000, max_seconds: int = 300):
        self.workspace = os.path.realpath(workspace)
        self.grants = grants  # например {"exec": True, "fs": True, "net": False}
        self.max_calls = max_calls
        self.deadline = time.time() + max_seconds
        self.calls = 0
        self.interrupted = False

    def within_scope(self, path: str) -> bool:
        """realpath-сверка: symlinks и относительные пути разворачиваются до проверки."""
        rp = os.path.realpath(path)
        return rp == self.workspace or rp.startswith(self.workspace + os.sep)

    def decide(self, action: dict):
        tool, op = action["tool"], action["op"]
        if self.interrupted:
            return DENY, "interrupt: goal changed by user"
        if time.time() > self.deadline:
            return DENY, "time budget exhausted"
        if self.calls >= self.max_calls:
            return DENY, "call budget exhausted"
        risk = action.get("risk_class", 1)
        if risk >= 3 and not action.get("approved"):
            return ASK, (f"risk_class={risk} requires explicit user consent "
                         f"(irreversible/external)")
        if not self.grants.get(tool):
            return DENY, (f"no authority grant for tool '{tool}' "
                          f"(NOT AUTHORIZED / NOT AVAILABLE)")
        if tool == "fs" and op in ("write", "delete"):
            p = action["args"].get("path", "")
            full = p if os.path.isabs(p) else os.path.join(self.workspace, p)
            if not self.within_scope(full):
                return DENY, f"path outside workspace scope: {p}"
        return ALLOW, "ok"
