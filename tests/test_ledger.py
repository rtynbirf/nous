"""НОУС · tests/test_ledger.py — механика журнала доказательств (ADR-0011).

Спека: docs/decisions/0011-evidence-ledger.md. Тесты гоняют ledger.sh в
TemporaryDirectory; совместимость формата с журналом коллег проверяется
сверкой канонического хеша (sort_keys + компактный JSON), как у них.
Только stdlib python3 + bash (уже требование каркаса).
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_SH = ROOT / "src" / "lib" / "ledger.sh"
GENESIS = "0" * 64


def bash(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "{LEDGER_SH}"; ' + " ".join(args)],
        capture_output=True, text=True, check=False,
    )


def canon_hash(row: dict) -> str:
    import hashlib
    body = {k: v for k, v in row.items() if k != "hash"}
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = str(Path(self.tmp.name) / "evidence.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        return [json.loads(l) for l in Path(self.ledger).read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_append_creates_chain(self):
        r = bash("ledger::append", f'"{self.ledger}"', "'первая запись'", PARTIAL := "PARTIAL",
                 "'curl+grep'", "'{\"n\":1}'", "'лимиты'")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = bash("ledger::append", f'"{self.ledger}"', "'вторая запись'", "CONFIRMED",
                 "'TOFU-сверка'", "'хеш сошёлся'")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.rows()
        self.assertEqual([row["seq"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["prev"], GENESIS)
        self.assertEqual(rows[1]["prev"], rows[0]["hash"])
        self.assertEqual(rows[0]["status"], PARTIAL)
        self.assertEqual(rows[1]["status"], "CONFIRMED")

    def test_hash_matches_canonical_format(self):
        """Совместимость с форматом коллег: hash = sha256(канонический JSON без hash)."""
        bash("ledger::append", f'"{self.ledger}"', "'claim'", "PARTIAL", "'method'", "'d'", "'lim'")
        row = self.rows()[0]
        self.assertEqual(row["hash"], canon_hash(row))

    def test_verify_clean_chain(self):
        for i in range(3):
            bash("ledger::append", f'"{self.ledger}"', f"'запись {i}'", "UNKNOWN", "'m'", "'d'")
        r = bash("ledger::verify", f'"{self.ledger}"')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("целостна", r.stdout)

    def test_verify_detects_tamper(self):
        """Правка старой строки ломает цепь — тест коллег, у нас обязателен."""
        bash("ledger::append", f'"{self.ledger}"', "'claim-1'", "PARTIAL", "'m'", "'d'")
        bash("ledger::append", f'"{self.ledger}"', "'claim-2'", "PARTIAL", "'m'", "'d'")
        text = Path(self.ledger).read_text(encoding="utf-8")
        Path(self.ledger).write_text(text.replace("claim-1", "ВЗЛОМ"), encoding="utf-8")
        r = bash("ledger::verify", f'"{self.ledger}"')
        self.assertNotEqual(r.returncode, 0, "подделка не обнаружена!")
        self.assertIn("изменено", r.stdout + r.stderr)

    def test_verify_detects_deletion(self):
        """Удаление строки ломает seq — вторая проверка коллег."""
        for i in range(3):
            bash("ledger::append", f'"{self.ledger}"', f"'запись {i}'", "PARTIAL", "'m'", "'d'")
        lines = Path(self.ledger).read_text(encoding="utf-8").splitlines()
        del lines[0]
        Path(self.ledger).write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = bash("ledger::verify", f'"{self.ledger}"')
        self.assertNotEqual(r.returncode, 0, "удаление не обнаружено!")

    def test_invalid_status_rejected(self):
        r = bash("ledger::append", f'"{self.ledger}"', "'claim'", "ПРОВЕРЕНО", "'m'", "'d'")
        self.assertNotEqual(r.returncode, 0, "недопустимый статус должен отклоняться")
        self.assertFalse(Path(self.ledger).exists(), "журнал не должен создаваться битой записью")

    def test_weakest_link(self):
        r = bash("ledger::weakest CONFIRMED PARTIAL UNKNOWN GAP CONFIRMED")
        self.assertEqual(r.stdout.strip(), "GAP")
        r = bash("ledger::weakest CONFIRMED PARTIAL")
        self.assertEqual(r.stdout.strip(), "PARTIAL")
        r = bash("ledger::weakest CONFIRMED FAILED CONFIRMED")
        self.assertEqual(r.stdout.strip(), "FAILED")
        r = bash("ledger::weakest CONFIRMED CONFIRMED")
        self.assertEqual(r.stdout.strip(), "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
