"""НОУС · tests/test_forge_probe.py — карта модуля probe и точки входа forge.sh.

Спека: docs/spec/implementation/02-probe.md (02-probe), ТЗ §1, тикет 0002.
CI (ubuntu-latest) гоняет тесты на ФИКСТУРАХ: реальное железо не трогается,
все записи — только в TemporaryDirectory (приёмка тикета: ни одной записи вне temp).
Только stdlib python3 — без внешних зависимостей.
"""
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE_SH = ROOT / "src" / "forge" / "probe" / "probe.sh"
FORGE_SH = ROOT / "src" / "forge" / "forge.sh"

FIXTURE_OS_RELEASE = (
    'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n'
    'NAME="Debian GNU/Linux"\n'
    'VERSION_ID="12"\n'
    'VERSION="12 (bookworm)"\n'
    'ID=debian\n'
)
FIXTURE_CPUINFO = (
    "processor\t: 0\n"
    "model name\t: Fixture CPU Model @ 3.00GHz\n"
    "cpu cores\t: 2\n"
    "\n"
    "processor\t: 1\n"
    "model name\t: Fixture CPU Model @ 3.00GHz\n"
    "cpu cores\t: 2\n"
)
FIXTURE_MEMINFO = "MemTotal:       16000000 kB\nMemFree:         8000000 kB\n"
FIXTURE_OSRELEASE = "6.1.0-fixture-amd64\n"


def clean_env(**extra):
    """Окружение без NOUS_*: тест не зависит от среды запускающего."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("NOUS_")}
    env.update(extra)
    return env


def make_fixtures(root: Path, empty: bool = False) -> None:
    """Фикстуры CI: подставные /etc и /proc; /sys/firmware/efi отсутствует сознательно → BIOS.

    empty=True — пустая фикстура: все домены отсутствуют (спека 02, приёмка п.3:
    отсутствующие домены → unknown, не ошибка).
    """
    root.mkdir(parents=True, exist_ok=True)
    if empty:
        return
    (root / "etc").mkdir()
    (root / "etc" / "os-release").write_text(FIXTURE_OS_RELEASE, encoding="utf-8")
    (root / "proc").mkdir()
    (root / "proc" / "cpuinfo").write_text(FIXTURE_CPUINFO, encoding="utf-8")
    (root / "proc" / "meminfo").write_text(FIXTURE_MEMINFO, encoding="utf-8")
    (root / "proc" / "sys" / "kernel").mkdir(parents=True)
    (root / "proc" / "sys" / "kernel" / "osrelease").write_text(FIXTURE_OSRELEASE, encoding="utf-8")


FIXTURE_LSBLK = (
    "NAME       SIZE TYPE ROTA\n"
    "sda  512110190592 disk    1\n"
    "sda1  53687091200 part    1\n"
    "sdb 1000204886016 disk    0\n"
)


def run_probe(args, timeout=60):
    return subprocess.run(
        ["bash", str(PROBE_SH), *args],
        capture_output=True, text=True, timeout=timeout, env=clean_env(),
    )


class TestSyntaxGate(unittest.TestCase):
    """Гейт сборки-подобной проверки: bash -n на probe.sh и forge.sh."""

    def test_bash_n_gate(self):
        for script in (PROBE_SH, FORGE_SH):
            with self.subTest(script=script.name):
                self.assertTrue(script.is_file(), f"нет файла: {script}")
                proc = subprocess.run(
                    ["bash", "-n", str(script)], capture_output=True, text=True, timeout=60
                )
                self.assertEqual(proc.returncode, 0, f"bash -n {script.name}: {proc.stderr}")


class TestProbeFixture(unittest.TestCase):
    """Фикстурный прогон probe: JSON-схема, BIOS-детект, сырой журнал, без записей в фикстуры."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.fix = base / "fix"
        self.out = base / "out"
        self.out.mkdir()
        make_fixtures(self.fix)
        self.fixture_before = {str(p.relative_to(self.fix)) for p in self.fix.rglob("*")}

    def tearDown(self):
        self._tmp.cleanup()

    def test_probe_fixture_run(self):
        proc = run_probe(["--root", str(self.fix), "--out", str(self.out)])
        self.assertEqual(
            proc.returncode, 0,
            f"probe упал:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )

        # ровно два артефакта дня: probe-<дата>.json + probe-<дата>.log
        artifacts = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(len(artifacts), 2, f"ожидались json+log, получено: {artifacts}")
        for name in artifacts:
            self.assertRegex(name, r"^probe-\d{4}-\d{2}-\d{2}\.(json|log)$")

        json_path = next(self.out.glob("probe-*.json"))
        log_path = next(self.out.glob("probe-*.log"))
        data = json.loads(json_path.read_text(encoding="utf-8"))

        # OS — из фикстуры (карта = территория), не CI-машины
        self.assertEqual(data["host"]["os"], "Debian GNU/Linux 12 (bookworm)")
        self.assertEqual(data["host"]["os_id"], "debian")
        self.assertEqual(data["host"]["os_version"], "12")
        # EFI-каталога в фикстуре нет → BIOS, efi=false
        self.assertFalse(data["host"]["efi"])
        self.assertEqual(data["host"]["boot"], "bios")
        # ядро — из фикстуры, не хоста
        self.assertEqual(data["host"]["kernel"], "6.1.0-fixture-amd64")
        self.assertTrue(data["fixture_mode"])

        # CPU/RAM непустые
        self.assertEqual(data["resources"]["cpu_model"], "Fixture CPU Model @ 3.00GHz")
        self.assertEqual(data["resources"]["cpu_cores"], 2)
        self.assertIsNotNone(data["resources"]["cpu_cores_physical"])
        self.assertIsNotNone(data["resources"]["ram_gb"])
        self.assertGreater(data["resources"]["ram_gb"], 0)

        # диски: в фикстуре нет lsblk.txt — домен null («нет данных»), не [] и не ошибка
        self.assertIsNone(data["resources"]["disks"])

        # таблица инструментов — ровно перечень тикета (спека 02, инструменты)
        self.assertEqual(
            sorted(data["tools"]),
            ["curl", "gpg", "oscdimg", "pwsh", "python3", "xorriso"],
        )

        # вердикт-блок существует; forge-win на Linux — pending
        self.assertIn("verdict", data)
        self.assertIn("forge_linux", data["verdict"])
        self.assertIn("forge_win", data["verdict"])
        self.assertIsInstance(data["verdict"]["forge_linux"]["sufficient"], bool)
        self.assertEqual(data["verdict"]["forge_linux"]["required"], ["xorriso", "curl", "python3"])
        self.assertIsNone(data["verdict"]["forge_win"]["sufficient"])
        self.assertEqual(data["verdict"]["forge_win"]["state"], "pending")

        # python3 присутствует всегда (этим же тестом и запускается)
        self.assertTrue(data["tools"]["python3"]["present"])

        # сырой журнал: секции доменов + сырой вывод фикстуры (аксиома 2)
        log = log_path.read_text(encoding="utf-8")
        self.assertIn("os-release", log)
        self.assertIn("PRETTY_NAME", log)
        self.assertIn("Fixture CPU Model @ 3.00GHz", log)
        self.assertIn("ПРОПУЩЕНО", log)          # lsblk/fdisk/df/id пропущены в fixture-режиме
        self.assertIn("fixture-режим", log)

        # probe не написал в фикстуры (картография без вмешательства)
        after = {str(p.relative_to(self.fix)) for p in self.fix.rglob("*")}
        self.assertEqual(after, self.fixture_before, "probe модифицировал фикстуры")

    def test_probe_fixture_disks_from_lsblk_fixture(self):
        """«В fixture-режиме — из фикстуры» (тикет 0002): lsblk.txt = подставной сырой
        вывод lsblk (спека 02: подставные /sys-деревья И выводы команд); парсятся только
        строки type=disk, размер — байты → ГБ, rota — флаг."""
        disks_fix = self.fix.parent / "disks-fix"
        make_fixtures(disks_fix)
        (disks_fix / "lsblk.txt").write_text(FIXTURE_LSBLK, encoding="utf-8")
        out = self.fix.parent / "disks-out"
        out.mkdir()
        proc = run_probe(["--root", str(disks_fix), "--out", str(out)])
        self.assertEqual(
            proc.returncode, 0,
            f"probe упал:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        data = json.loads(next(out.glob("probe-*.json")).read_text(encoding="utf-8"))
        disks = data["resources"]["disks"]
        self.assertEqual([d["name"] for d in disks], ["sda", "sdb"])  # part-строка отфильтрована
        self.assertEqual(disks[0]["type"], "disk")
        self.assertEqual(disks[0]["rota"], True)
        self.assertEqual(disks[1]["rota"], False)
        self.assertAlmostEqual(disks[0]["size_gb"], round(512110190592 / 1024 ** 3, 2))
        self.assertIn("lsblk.txt", data["resources"]["disks_note"])
        # сырой вывод фикстуры зафиксирован в журнале (аксиома 2)
        log = next(out.glob("probe-*.log")).read_text(encoding="utf-8")
        self.assertIn("1000204886016", log)

    def test_probe_fixture_uefi(self):
        """Загрузка в fixture-режиме — по наличию каталога в фикстуре: есть
        sys/firmware/efi → uefi (спека 02: детект BIOS vs UEFI)."""
        uefi_fix = self.fix.parent / "uefi-fix"
        make_fixtures(uefi_fix)
        (uefi_fix / "sys" / "firmware" / "efi").mkdir(parents=True)
        out = self.fix.parent / "uefi-out"
        out.mkdir()
        proc = run_probe(["--root", str(uefi_fix), "--out", str(out)])
        self.assertEqual(
            proc.returncode, 0,
            f"probe упал:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        data = json.loads(next(out.glob("probe-*.json")).read_text(encoding="utf-8"))
        self.assertEqual(data["host"]["boot"], "uefi")
        self.assertTrue(data["host"]["efi"])

    def test_probe_missing_domains_are_unknown(self):
        """Пустая фикстура: отсутствующие домены → unknown, код 0 (спека 02, приёмка п.3)."""
        empty_fix = self.fix.parent / "empty-fix"
        empty_fix.mkdir(parents=True)  # существующий, но пустой каталог-фикстур
        proc = run_probe(["--root", str(empty_fix), "--out", str(self.out)])
        self.assertEqual(
            proc.returncode, 0,
            f"probe упал:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        json_path = next(self.out.glob("probe-*.json"))
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["host"]["os"], "unknown")
        self.assertEqual(data["host"]["boot"], "bios")
        self.assertIsNone(data["resources"]["ram_gb"])

    def test_probe_fixture_via_forge_passthrough(self):
        """forge.sh probe — прозрачный диспетчер: --root/--out доходят до probe.sh."""
        proc = subprocess.run(
            ["bash", str(FORGE_SH), "probe", "--root", str(self.fix), "--out", str(self.out)],
            capture_output=True, text=True, timeout=60, env=clean_env(),
        )
        self.assertEqual(
            proc.returncode, 0,
            f"forge.sh probe упал:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        json_path = next(self.out.glob("probe-*.json"))
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["host"]["os"], "Debian GNU/Linux 12 (bookworm)")


class TestForgeEntry(unittest.TestCase):
    """Точка входа forge.sh: usage в stderr при ошибке вызова, честный отказ win."""

    def test_usage_and_unknown_target(self):
        # без цели и с --help: exit != 0, usage (перечень целей из пинов) в stderr
        for args in ([], ["--help"]):
            with self.subTest(args=args):
                proc = subprocess.run(
                    ["bash", str(FORGE_SH), *args],
                    capture_output=True, text=True, timeout=60, env=clean_env(),
                )
                self.assertNotEqual(proc.returncode, 0, f"ожидался ненулевой код: {args}")
                for fragment in ("probe", "debian12", "ubuntu-2404", "forge.debian-netinst"):
                    self.assertIn(fragment, proc.stderr, f"usage без {fragment}: {args}")

    def test_unknown_target_names_itself(self):
        proc = subprocess.run(
            ["bash", str(FORGE_SH), "sovet-skynet"],
            capture_output=True, text=True, timeout=60, env=clean_env(),
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("незнакомая", proc.stderr)
        self.assertIn("debian12", proc.stderr)  # usage показан вместе с предупреждением

    def test_win_honest_refusal(self):
        proc = subprocess.run(
            ["bash", str(FORGE_SH), "win"],
            capture_output=True, text=True, timeout=60, env=clean_env(),
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("forge.ps1", proc.stderr)
        self.assertIn("Windows-хосте", proc.stderr)

    def test_build_branch_probes_first_and_stops_honestly(self):
        """debian12: forge.sh сам снимает probe-карту дня, печатает вердикт, потом честная
        остановка (гейт инструментов вердикта и/или сборщик R4 ещё не реализован).
        Все записи — только в TemporaryDirectory (NOUS_TARGET_DIR переопределён)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            proc = subprocess.run(
                ["bash", str(FORGE_SH), "debian12"],
                capture_output=True, text=True, timeout=120,
                env=clean_env(NOUS_TARGET_DIR=str(target)),
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            # probe-отчёт дня создан автоматически (ТЗ §2 п.1: карта до вмешательства)
            reports = list(target.glob("probe-*.json"))
            self.assertEqual(
                len(reports), 1,
                f"forge.sh обязан сам запустить probe; в {target}: {[p.name for p in target.iterdir()]}",
            )
            data = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertIn("verdict", data)
            # вердикт-блок напечатан сырыми значениями JSON
            self.assertIn('"forge_linux"', proc.stdout)
            self.assertIn('"forge_win"', proc.stdout)
            # остановка честная: гейт инструментов ИЛИ отсутствующий сборщик фазы R4
            self.assertTrue(
                any(marker in proc.stderr for marker in ("отсутствуют", "не реализован")),
                f"неожиданная ошибка: {proc.stderr}",
            )


class TestProbeInvariants(unittest.TestCase):
    """Текстовые инварианты: probe не содержит деструктив (строки-комментарии исключены)."""

    def test_probe_has_no_destructive_commands(self):
        text = PROBE_SH.read_text(encoding="utf-8")
        # только код: в шапке модуля деструктив задокументирован словесно — комментарии
        # исключаются, чтобы инвариант не ловил собственную декларацию об отсутствии
        code_lines = [
            line for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        code = "\n".join(code_lines)
        forbidden = {
            "rm -rf": r"\brm\s+-rf\b",
            "mkfs": r"\bmkfs",
            "dd": r"\bdd\b",
            "sudo": r"\bsudo\b",
            "apt": r"\bapt(-get)?\b",
        }
        for label, pattern in forbidden.items():
            match = re.search(pattern, code)
            self.assertIsNone(match, f"запрещённое в probe.sh ({label}): {match.group(0) if match else ''}")


if __name__ == "__main__":
    unittest.main()
