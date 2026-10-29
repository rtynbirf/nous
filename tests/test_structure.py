"""НОУС · исполняемая карта: структура репо (тесты следят за телом организма)."""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "README.md", "AGENTS.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md",
    "AI_POLICY.md", "CHANGELOG.md", "Makefile", "mkdocs.yml",
    ".gitignore", ".gitattributes", ".editorconfig", ".mise.toml",
    ".envrc.example", ".pre-commit-config.yaml", "requirements-dev.txt",
    ".devcontainer/devcontainer.json", ".claude/settings.json",
    ".github/CODEOWNERS", ".github/copilot-instructions.md",
    ".github/dependabot.yml", ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/config.yml", ".github/ISSUE_TEMPLATE/task.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/workflows/ci.yml", ".github/workflows/release.yml",
    ".cursor/rules/nous-core.mdc", ".cursor/rules/forge-safety.mdc",
    "docs/index.md",
    "docs/getting-started/01-bootstrap.md",
    "docs/guides/new-subject.md", "docs/guides/execution-branch.md",
    "docs/guides/release.md",
    "docs/concepts/axioms.md", "docs/concepts/map-territory.md",
    "docs/concepts/subjects.md", "docs/concepts/emergence.md",
    "docs/concepts/safe-defaults.md",
    "docs/spec/tz-nous-forge.md", "docs/spec/roadmap.md",
    "docs/spec/implementation/01-sources.md",
    "docs/spec/implementation/02-probe.md",
    "docs/spec/implementation/03-windows-iso.md",
    "docs/spec/implementation/04-linux-iso.md",
    "docs/spec/implementation/05-verify.md",
    "docs/spec/implementation/06-safe-defaults.md",
    "docs/spec/implementation/07-agent-dispatch.md",
    "docs/reference/structure.md", "docs/reference/commands.md",
    "docs/reference/security-baseline.md",
    "scripts/bootstrap.sh", "scripts/verify.sh", "scripts/state.sh",
    "scripts/gen_llms.sh", "scripts/pin_action.sh",
    "manifests/pins.yaml", "manifests/safe-defaults.yaml",
    "state/README.md", "tasks/README.md", "tasks/done/.gitkeep",
    "src/forge/README.md", "templates/README.md",
    # территория форжа (v0.2.0, revision-0 §4)
    "src/lib/common.sh", "src/lib/verify-iso.sh",
    "src/forge/probe/probe.sh", "src/forge/forge.sh", "src/forge/forge.ps1",
    "src/forge/win/build.ps1", "src/forge/win/fetch-fido.ps1",
    "src/forge/win/autounattend.template.xml",
    "src/forge/linux/build.sh",
    "src/forge/linux/templates/debian12.preseed",
    "src/forge/linux/templates/ubuntu-24.04/user-data",
    "src/forge/linux/templates/ubuntu-24.04/meta-data",
    ".github/workflows/forge.yml",
    "tests/test_forge_win.py", "tests/test_forge_linux.py", "tests/test_forge_probe.py",
    "docs/genesis/revision-0.md",
]

REQUIRED_DIRS = [
    ".claude/agents", "docs/decisions", "tests", "tasks/open", "tasks/done",
]

SAFE_DEFAULTS_KEYS = {
    "wipe_disk", "write_to_physical_media", "auto_publish", "repo_visibility",
    "push_force", "destructive_ops", "secrets_in_repo", "actions_pinning",
    "oobe_will_wipe_disk", "partman_confirm_nooverwrite",
}


class TestStructure(unittest.TestCase):
    def test_required_files_exist(self):
        missing = [p for p in REQUIRED_FILES if not (ROOT / p).is_file()]
        self.assertEqual(missing, [], f"карта потеряла органы: {missing}")

    def test_required_dirs_exist(self):
        missing = [d for d in REQUIRED_DIRS if not (ROOT / d).is_dir()]
        self.assertEqual(missing, [], f"нет каталогов: {missing}")

    def test_constitution_nonempty(self):
        for name in ("README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertGreater(len(text), 500, f"{name} подозрительно пуст")

    def test_task_numbering_continuous(self):
        # Очередь поглощается: done ∪ open обязаны быть непрерывны 1..N
        # (тикет уезжает в done/, номер продолжает работать в генеалогии).
        def nums_of(d):
            return sorted(
                int(m.group(1))
                for p in (ROOT / "tasks" / d).glob("*.md")
                if (m := re.match(r"(\d{4})", p.name))
            )
        nums = sorted(nums_of("open") + nums_of("done"))
        self.assertGreaterEqual(len(nums), 5)
        self.assertEqual(nums, list(range(1, len(nums) + 1)),
                         "нумерация тикетов (done+open) разорвана")
        open_nums = nums_of("open")
        self.assertGreaterEqual(len(open_nums), 3,
                                "в очереди воли должно оставаться ≥3 открытых тикета")

    def test_pins_not_stale(self):
        from datetime import date, datetime
        pins = yaml.safe_load((ROOT / "manifests" / "pins.yaml").read_text(encoding="utf-8"))
        today = date.today()
        sections = [pins["actions"], pins["tools"]]
        for section in sections:
            for name, pin in section.items():
                checked = datetime.strptime(str(pin["verified_at"]), "%Y-%m-%d").date()
                age_days = (today - checked).days
                self.assertLess(age_days, 90,
                                f"{name}: пин устарел ({age_days} дн.) — нужна калибровка")

    def test_adr_numbering_continuous(self):
        adr_dir = ROOT / "docs" / "decisions"
        nums = sorted(
            int(m.group(1))
            for p in adr_dir.glob("*.md")
            if (m := re.match(r"(\d{4})", p.name))
        )
        self.assertGreaterEqual(len(nums), 8, "ADR должно быть минимум 8")
        self.assertEqual(nums, list(range(1, len(nums) + 1)),
                         "нумерация ADR разорвана (MADR-инвариант)")

    def test_agent_contracts_have_frontmatter(self):
        agents = sorted((ROOT / ".claude" / "agents").glob("*.md"))
        self.assertGreaterEqual(len(agents), 5, "минимум 5 субъектов")
        for p in agents:
            text = p.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---"), f"{p.name}: нет фронтматтера")
            for key in ("name:", "description:", "tools:"):
                self.assertIn(key, text.split("---")[1], f"{p.name}: нет {key}")
            for section in ("Граница", "Протокол отчёта"):
                self.assertIn(section, text, f"{p.name}: нет секции «{section}»")

    def test_open_tasks_have_required_sections(self):
        tickets = sorted((ROOT / "tasks" / "open").glob("*.md"))
        self.assertGreaterEqual(len(tickets), 5, "минимум 5 тикетов (R1–R5)")
        for p in tickets:
            text = p.read_text(encoding="utf-8")
            for section in ("Роль", "Цель", "Границы", "Критерии приёмки",
                            "ПОЧЕМУ ТОЛЬКО ТАК"):
                self.assertIn(section, text, f"{p.name}: нет секции «{section}»")

    def test_manifests_parse_and_keys(self):
        pins = yaml.safe_load((ROOT / "manifests" / "pins.yaml").read_text(encoding="utf-8"))
        for section in ("meta", "actions", "tools"):
            self.assertIn(section, pins, f"pins.yaml: нет секции {section}")
        for name, pin in pins["actions"].items():
            sha = pin.get("sha", "")
            self.assertRegex(sha, r"^[0-9a-f]{40}$", f"{name}: sha не 40-символьный")
            self.assertTrue(pin.get("verified_at"), f"{name}: нет verified_at")

        defaults = yaml.safe_load(
            (ROOT / "manifests" / "safe-defaults.yaml").read_text(encoding="utf-8")
        )
        missing = SAFE_DEFAULTS_KEYS - set(defaults)
        self.assertEqual(missing, set(), f"safe-defaults.yaml: потеряны ключи {missing}")
        self.assertIs(defaults["wipe_disk"], False, "wipe_disk обязан быть false")
        self.assertIs(defaults["oobe_will_wipe_disk"], False,
                      "WillWipeDisk в autounattend обязан быть false")
        self.assertEqual(defaults["secrets_in_repo"], "forbidden")


if __name__ == "__main__":
    unittest.main()
