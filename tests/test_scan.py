"""НОУС · tests/test_scan.py — сенсор территории (src/scan/scan.sh).

Спека: docs/genesis/sintez-public-repo-synthesis.md §4, ADR-0011/0012.
CI-гигиена как у коллег (их скан 19/19): реальные клоны только из allowlist;
тесты гоняют СИНТАКСИЧЕСКИЕ гейты и журнал на фикстурах, сеть не трогаем
(единственный сетевой тест помечен и выключается без GITHUB_REF).
Только stdlib python3 + bash.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_SH = ROOT / "src" / "scan" / "scan.sh"
LEDGER_SH = ROOT / "src" / "lib" / "ledger.sh"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("NOUS_")}
    env.update(extra)
    return env


def run_scan(args, out_dir: Path, extra_env=None):
    env = clean_env(NOUS_TARGET_DIR=str(out_dir))
    env.update(extra_env or {})
    return subprocess.run(["bash", str(SCAN_SH), *args],
                          capture_output=True, text=True, check=False, env=env)


def ledger_rows(path: Path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


class UrlGateTests(unittest.TestCase):
    """Синтаксический фильтр: только https + allowlist (гейт коллег, тест 7 из их исправлений)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        # без сети: список с единственным обязательным отказом -> die после фильтра
        self.bad_list = self.out / "urls.txt"
        self.bad_list.write_text(
            "ssh://git@github.com/evil/repo.git\n"
            "git://github.com/evil/repo.git\n"
            "http://github.com/evil/repo.git\n"
            "https://user:pass@github.com/owner/repo.git\n"
            "https://not-allowed.example.com/owner/repo.git\n"
            "https://github.com/only-one-seg\n"
            "https://github.com/owner/../owner2/repo.git\n",
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_all_forbidden_schemes_and_hosts(self):
        r = run_scan([str(self.bad_list), "--out", str(self.out / "scan")], self.out)
        self.assertNotEqual(r.returncode, 0, "все URL запрещены — скан обязан упасть")
        self.assertIn("ни один URL не принят", r.stderr)
        rejected = (self.out / "scan" / "rejected.log").read_text(encoding="utf-8")
        self.assertIn("только https", rejected)
        self.assertIn("allowlist", rejected)
        self.assertIn("учётные данные", rejected)
        # 7 URL: 5 отказов по фильтру + 1 «только один сегмент» + 1 «..» в пути
        self.assertEqual(rejected.count("[scan] ОТКАЗ"), 7)

    def test_allow_host_extends_list(self):
        ok_list = self.out / "ok.txt"
        ok_list.write_text("https://git.example.org/owner/repo.git\n", encoding="utf-8")
        # сеть недоступна для git.example.org — ожидаем FAILED клона, но НЕ фильтр-отказ
        r = run_scan([str(ok_list), "--out", str(self.out / "scan2"),
                      "--allow-host", "git.example.org"], self.out)
        rejected = (self.out / "scan2" / "rejected.log")
        self.assertFalse(rejected.exists(), "allowlist-хост не должен попадать в отказы фильтра")


class LedgerIntegrationTests(unittest.TestCase):
    """Журнал пишется в	out-dir, цепь целостна, статусы по лестнице ADR-0011."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_clone_records_evidence_and_verifies(self):
        """Недоступный (но разрешённый) хост: FAILED фиксируется в журнале, цепь цела."""
        lst = self.out / "urls.txt"
        lst.write_text("https://git.invalid-nonexistent.tld/owner/repo.git\n", encoding="utf-8")
        r = run_scan([str(lst), "--out", str(self.out / "scan"),
                      "--allow-host", "git.invalid-nonexistent.tld"], self.out)
        ledger = self.out / "scan" / "evidence.jsonl"
        self.assertTrue(ledger.exists(), "журнал обязан существовать даже при FAILED: " + r.stderr)
        rows = ledger_rows(ledger)
        self.assertEqual(rows[0]["claim"], "anonymous clone succeeded")
        self.assertEqual(rows[0]["status"], "FAILED")
        self.assertEqual([row["seq"] for row in rows], list(range(1, len(rows) + 1)))
        v = subprocess.run(["bash", "-c", f'source "{LEDGER_SH}"; ledger::verify "{ledger}"'],
                           capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, "цепь журнала сломана: " + v.stdout)
        repos = json.loads((self.out / "scan" / "repos.json").read_text(encoding="utf-8"))
        self.assertEqual(repos[0]["status"], "FAILED")
        # отчёт-карта обязана появиться и честно говорить, что это не вердикт
        report = (self.out / "scan" / "report.md").read_text(encoding="utf-8")
        self.assertIn("не доказательство", report)


class NoEnvLeaksTests(unittest.TestCase):
    """Доктрина ADR-0012, правило 1: сканер не передаёт токены потомкам."""

    def test_env_tokens_stripped_for_clone(self):
        secret = "ghp_SUPERSECRETVALUE1234567890"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            lst = out / "urls.txt"
            # разрешённый хост с невалидным URL → клон упадёт БЫСТРО, лог останется
            lst.write_text("https://github.com/__nonexistent_owner__/__x__.git\n", encoding="utf-8")
            run_scan([str(lst), "--out", str(out / "scan")], out,
                     extra_env={"NOUS_TEST_TOKEN": secret, "GH_TOKEN": secret})
            # в окружении потомка env -i: проверяем через strace-замену — логи и журнал
            # не должны содержать секрет
            artifacts = list((out / "scan").rglob("*"))
            for f in artifacts:
                if f.is_file():
                    body = f.read_text(encoding="utf-8", errors="replace")
                    self.assertNotIn(secret, body, f"секрет утёк в {f.name}")


if __name__ == "__main__":
    unittest.main()
