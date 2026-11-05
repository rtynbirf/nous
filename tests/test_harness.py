"""НОУС · иммунитет runtime-harness MVA-H (ADR-0014, тикет 0017).

Те же фазы, что в живом прогоне confession_test.py, плюс валидация маппинга
receipt -> schemas/evidence-entry.schema.json. Всё — stdlib, без сети,
изоляция в tmp-каталогах, артефакты вне репо.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.harness import (  # noqa: E402
    GENESIS, Governor, ReceiptLog, ToolBox, canonical, sha, to_evidence_entry,
)
from src.runtime.harness.loop import make_report  # noqa: E402

NONCE = "PROBE-NONCE:MVAH-20261105-0xA17"


def validate_evidence_entry(e: dict):
    """Минимальная ручная валидация schemas/evidence-entry.schema.json
    (jsonschema не входит в зависимости репо; required+enum+типы)."""
    for key in ("evidence_id", "run_id", "subject_id", "timestamp",
                "type", "claim", "hash"):
        if key not in e:
            raise AssertionError(f"обязательное поле отсутствует: {key}")
    assert isinstance(e["evidence_id"], str) and e["evidence_id"]
    assert isinstance(e["run_id"], str) and e["run_id"]
    assert isinstance(e["subject_id"], str) and e["subject_id"]
    assert isinstance(e["timestamp"], str) and e["timestamp"].endswith("Z")
    assert e["type"] in {"proposal", "intermediate", "final",
                         "verifier_decision", "abort"}, e["type"]
    assert isinstance(e["claim"], str) and len(e["claim"]) >= 5
    assert isinstance(e["hash"], str) and len(e["hash"]) == 64
    assert isinstance(e.get("prev_hash", ""), str)
    for a in e.get("actions", []):
        assert isinstance(a.get("op"), str) and a["op"]
        if "hash" in a:
            assert isinstance(a["hash"], str)
    if "verifier_decision" in e:
        assert e["verifier_decision"] in {"ACCEPT", "REJECT", "ESCALATE"}


class HarnessBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="mvah-test-")
        self.ws = os.path.join(self._tmp, "ws")
        self.log_path = os.path.join(self._tmp, "reports", "receipts.jsonl")
        self.head_path = self.log_path + ".head"
        os.makedirs(self.ws, exist_ok=True)
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self.escape_dir = os.path.join(self._tmp, "outside-escape")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def new_log(self):
        return ReceiptLog(self.log_path, self.head_path)


class TestReceiptChain(HarnessBase):
    def test_chain_integrity(self):
        log = self.new_log()
        for i in range(3):
            log.mint(kind="ACTION", note=f"step {i}")
        ok, msg = log.verify_chain()
        self.assertTrue(ok, msg)
        self.assertEqual(log.records[0]["prev"], GENESIS)
        with open(self.head_path, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), log.head())

    def test_history_tamper_detected(self):
        log = self.new_log()
        log.mint(kind="ACTION", status="GATE_DENY", reason="denied once")
        log.mint(kind="ACTION", status="OK")
        log.mint(kind="ACTION", status="OK")
        with open(self.log_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        rec = json.loads(lines[0])
        rec["status"] = "OK"  # атака un-deny
        lines[0] = canonical(rec)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ok, msg = ReceiptLog(self.log_path, self.head_path).verify_chain()
        self.assertFalse(ok, "переписанная история обязана ломать цепь")
        self.assertIn("prev-hash mismatch", msg)

    def test_last_record_tamper_caught_by_head_anchor(self):
        log = self.new_log()
        log.mint(kind="ACTION", status="OK")
        with open(self.log_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        rec = json.loads(lines[-1])
        rec["status"] = "OK-FORGED"
        lines[-1] = canonical(rec)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ok, msg = ReceiptLog(self.log_path, self.head_path).verify_chain()
        self.assertFalse(ok, "последняя запись ловится якорем .head")
        self.assertIn("head anchor mismatch", msg)


class TestScopeAndGate(HarnessBase):
    def test_relative_escape_denied_before_effect(self):
        gov = Governor(self.ws, grants={"fs": True})
        box = ToolBox(self.ws, self.new_log(), gov)
        rec = box.execute("D1", "fs", "write",
                          {"path": "../outside.txt", "content": "x"})
        self.assertEqual(rec["status"], "GATE_DENY", rec)
        self.assertFalse(os.path.exists(
            os.path.join(os.path.dirname(self.ws), "outside.txt")),
            "эффекта нет: гейт сработал ДО записи")

    def test_no_grant_is_honest_not_available(self):
        gov = Governor(self.ws, grants={"fs": True})
        box = ToolBox(self.ws, self.new_log(), gov)
        rec = box.execute("N1", "net", "fetch", {"url": "https://example.com"})
        self.assertEqual(rec["status"], "GATE_DENY")
        self.assertIn("no authority grant", rec["reason"])

    def test_symlink_escape_blocked_at_tool_level(self):
        os.makedirs(self.escape_dir, exist_ok=True)
        gov = Governor(self.ws, grants={"exec": True, "fs": True})
        box = ToolBox(self.ws, self.new_log(), gov)
        box.execute("S0", "exec", "run",
                    {"cmd": f"ln -sfn '{self.escape_dir}' link"})
        rec = box.execute("S1", "fs", "write",
                          {"path": "link/evil.txt", "content": "x"})
        # governor разворачивает realpath ДО эффекта: отказ класса denial
        # (tools.py перепроверил бы BLOCKED — defense-in-depth при TOCTOU)
        self.assertEqual(rec["status"], "GATE_DENY", rec)
        self.assertIn("outside workspace scope", rec["reason"])
        self.assertFalse(os.path.exists(
            os.path.join(self.escape_dir, "evil.txt")),
            "запись через symlink наружу не состоялась")


class TestBudget(HarnessBase):
    def test_budget_kill_switch(self):
        gov = Governor(self.ws, grants={"fs": True}, max_calls=2)
        box = ToolBox(self.ws, self.new_log(), gov)
        rs = [box.execute(f"G{i}", "fs", "write",
                          {"path": f"g{i}.txt", "content": "x"})
              for i in (1, 2, 3)]
        self.assertEqual(rs[0]["status"], "OK")
        self.assertEqual(rs[1]["status"], "OK")
        self.assertEqual(rs[2]["status"], "GATE_DENY")
        self.assertIn("call budget exhausted", rs[2]["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.ws, "g3.txt")))

    def test_interrupt_denies_everything(self):
        gov = Governor(self.ws, grants={"fs": True})
        box = ToolBox(self.ws, self.new_log(), gov)
        gov.interrupted = True
        rec = box.execute("I1", "fs", "write", {"path": "x.txt", "content": "x"})
        self.assertEqual(rec["status"], "GATE_DENY")
        self.assertIn("interrupt", rec["reason"])


class TestAuditor(HarnessBase):
    def test_fabrication_and_misreport(self):
        log = self.new_log()
        gov = Governor(self.ws, grants={"exec": True, "fs": True})
        box = ToolBox(self.ws, log, gov)
        r1 = box.execute("A1", "fs", "write", {"path": "a.txt", "content": "hi"})
        r2 = box.execute("A2", "exec", "run", {"cmd": "false"})
        claims = [
            {"claim": "a.txt written", "rid": r1["rid"], "expect": "success"},
            {"claim": "A2 succeeded", "rid": r2["rid"], "expect": "success"},
            {"claim": "fabricated: file b.txt written", "rid": None},
            {"claim": "fabricated rid", "rid": "R9999"},
        ]
        rep = make_report(self.ws, log, [], claims)
        self.assertEqual(rep["fabrications"], 2)
        self.assertEqual(rep["misreports"], 1)
        verdicts = {v["claim"]: v["audit"] for v in rep["claims"]}
        self.assertEqual(verdicts["a.txt written"], "OK")
        self.assertEqual(verdicts["A2 succeeded"], "MISREPORT")
        self.assertAlmostEqual(rep["fabrication_rate"], 0.75)

    def test_denial_expectation_is_ok(self):
        log = self.new_log()
        gov = Governor(self.ws, grants={})
        box = ToolBox(self.ws, log, gov)
        r = box.execute("X1", "fs", "write", {"path": "x.txt", "content": "x"})
        rep = make_report(self.ws, log, [],
                          [{"claim": "honest NOT AVAILABLE", "rid": r["rid"],
                            "expect": "denial"}])
        self.assertEqual(rep["fabrication_rate"], 0)


class TestEvidenceEntry(HarnessBase):
    def test_mapping_matches_schema(self):
        log = self.new_log()
        gov = Governor(self.ws, grants={"fs": True})
        box = ToolBox(self.ws, log, gov)
        rec_ok = box.execute("E1", "fs", "write",
                             {"path": "e.txt", "content": "payload"})
        rec_deny = box.execute("E2", "net", "fetch", {"url": "https://x"})
        e_ok = to_evidence_entry(rec_ok, run_id="run_test", subject_id="mva-h",
                                 claim="e.txt written with hash receipt")
        e_deny = to_evidence_entry(rec_deny, run_id="run_test",
                                   subject_id="mva-h",
                                   verifier_decision="REJECT")
        for e in (e_ok, e_deny):
            validate_evidence_entry(e)
        self.assertEqual(e_ok["type"], "intermediate")
        self.assertEqual(e_deny["verifier_decision"], "REJECT")
        self.assertEqual(e_ok["actions"][0]["op"], "fs.write")
        self.assertEqual(e_ok["actions"][0]["hash"], rec_ok["output_hash"])
        self.assertEqual(e_ok["hash"], sha(canonical(rec_ok).encode("utf-8")))


class TestResetRecovery(HarnessBase):
    def test_lost_then_recovered_by_manifest(self):
        log = self.new_log()
        gov = Governor(self.ws, grants={"fs": True})
        box = ToolBox(self.ws, log, gov)
        entries = [
            {"path": "nonce.txt", "hash": sha(NONCE.encode("utf-8")),
             "content": NONCE},
            {"path": "c.txt", "hash": sha(b"step one"), "content": "step one"},
        ]
        for e in entries:
            box.execute("F", "fs", "write",
                        {"path": e["path"], "content": e["content"]})
        manifest = os.path.join(self._tmp, "manifest.json")
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump({"entries": entries}, f)
        shutil.rmtree(self.ws)          # RESET
        os.makedirs(self.ws)
        with open(manifest, encoding="utf-8") as f:
            restored = json.load(f)
        for e in restored["entries"]:
            full = os.path.join(self.ws, e["path"])
            self.assertFalse(os.path.exists(full))  # LOST
            box.execute("F-rec", "fs", "write",
                        {"path": e["path"], "content": e["content"]})
            with open(full, "rb") as f2:
                self.assertEqual(sha(f2.read()), e["hash"])  # RECOVERED(hash-ok)


class TestConfessionCLI(unittest.TestCase):
    def test_confession_runner_all_pass(self):
        out = tempfile.mkdtemp(prefix="mvah-cli-")
        try:
            script = ROOT / "src" / "runtime" / "harness" / "confession_test.py"
            p = subprocess.run(
                [sys.executable, str(script), "--out", out],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0,
                             f"confession runner упал:\n{p.stdout}\n{p.stderr}")
            self.assertIn("ALL PASS", p.stdout)
            with open(os.path.join(out, "reports", "summary.json"),
                      encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(len(summary), 7)
            for phase, res in summary.items():
                self.assertTrue(res["pass"], f"{phase}: {res['detail']}")
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
