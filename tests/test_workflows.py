"""НОУС · воркфлоу-гейты: пины по SHA (ADR-0004), права, опасные триггеры."""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class TestWorkflows(unittest.TestCase):
    def setUp(self):
        self.files = sorted(WF.glob("*.yml"))
        self.assertTrue(self.files, "workflows не найдены")

    def test_every_uses_pinned_by_full_sha(self):
        uses_line = re.compile(
            r"uses:\s*[\w./-]+@[0-9a-f]{40}\s+#\s+v[\w.-]+"
        )
        for path in self.files:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            jobs = data.get("jobs", {})
            self.assertTrue(jobs, f"{path.name}: нет jobs")
            for job_name, job in jobs.items():
                for i, step in enumerate(job.get("steps", [])):
                    uses = step.get("uses", "")
                    if not uses:
                        continue
                    ref = uses.split("@", 1)[1] if "@" in uses else ""
                    self.assertRegex(
                        ref, SHA_RE,
                        f"{path.name}:{job_name}: шаг {i} ({uses}) не пинован полным SHA",
                    )
            # комментарий версии проверяем по сырому тексту (YAML его съедает)
            for line in path.read_text(encoding="utf-8").splitlines():
                if "uses:" in line and "@" in line.split("uses:", 1)[1].split()[0]:
                    self.assertRegex(
                        line, uses_line,
                        f"{path.name}: строка без комментария версии: {line.strip()}",
                    )

    def test_permissions_declared_and_minimal(self):
        for path in self.files:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIn("permissions", data, f"{path.name}: нет верхнеуровневых permissions")
            self.assertEqual(data["permissions"].get("contents"), "read",
                             f"{path.name}: верхний уровень обязан быть contents: read")

    def test_no_dangerous_triggers(self):
        forbidden = ("pull_request_target", "workflow_run")
        for path in self.files:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            triggers = data.get(True, {}) or data.get("on", {}) or {}
            used = set(triggers.keys())
            clash = used & set(forbidden)
            self.assertFalse(clash, f"{path.name}: запрещённые триггеры {clash}")

    def test_checkout_disables_persist_credentials(self):
        for path in self.files:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            found = False
            for job in data.get("jobs", {}).values():
                for step in job.get("steps", []):
                    if "actions/checkout" in step.get("uses", ""):
                        found = True
                        self.assertIs(
                            step.get("with", {}).get("persist-credentials"), False,
                            f"{path.name}: checkout без persist-credentials: false",
                        )
            self.assertTrue(found, f"{path.name}: не найден checkout")

    def test_release_is_separate_and_gated(self):
        data = yaml.safe_load((WF / "release.yml").read_text(encoding="utf-8"))
        triggers = data.get(True, {}) or data.get("on", {}) or {}
        self.assertIn("push", triggers, "release обязан запускаться по тегу")
        self.assertIn("tags", triggers["push"], "release обязан быть за тегом v*")
        blob = (WF / "release.yml").read_text(encoding="utf-8")
        self.assertIn("ENABLE_ATTESTATION", blob, "аттестация обязана быть за гейтом")


if __name__ == "__main__":
    unittest.main()
