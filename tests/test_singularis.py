"""НОУС · иммунитет SINGULARIS: схемы валидны, пакет органов на месте, nav знает контур.

Интеграция прототипа 0.1.0-proto → НОУС 0.5.0 (ADR-0013).
"""
import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
PKG = ROOT / "docs" / "singularis"
SPEC = ROOT / "docs" / "spec" / "singularis"

SCHEMA_FILES = (
    "subject-contract.schema.json",
    "evidence-entry.schema.json",
    "task-ticket.schema.json",
)
PKG_FILES = (
    "index.md", "manifest.md", "vision.md",
    "axioms-v2.md", "architecture.md", "safety-governance.md",
)
SPEC_FILES = (
    "tz-singularis.md", "runtime-spec.md",
    "evidence-protocol.md", "contract-schema.md",
)
TICKETS = (
    "0010-runtime-mvp.md", "0011-evidence-gate.md",
    "0012-status-self-perception.md", "0013-closed-loop-scan.md",
    "0014-contract-schema-ci.md", "0015-provenance-graph.md",
)
TICKET_SECTIONS = ("Роль", "Цель", "Границы", "Критерии приёмки", "ПОЧЕМУ ТОЛЬКО ТАК")


def nav_paths(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from nav_paths(value)
    elif isinstance(node, list):
        for item in node:
            yield from nav_paths(item)


class TestSchemas(unittest.TestCase):
    def test_schemas_valid_draft_2020_12(self):
        for name in SCHEMA_FILES:
            data = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
            self.assertEqual(
                data.get("$schema"), "https://json-schema.org/draft/2020-12/schema",
                f"{name}: схема обязана объявлять draft 2020-12",
            )
            self.assertEqual(data.get("type"), "object", name)
            self.assertTrue(data.get("required"), f"{name}: required пуст")

    def test_subject_contract_required_fields(self):
        data = json.loads((SCHEMAS / "subject-contract.schema.json").read_text(encoding="utf-8"))
        for field in ("id", "version", "role", "scope", "tools", "budget", "report_protocol"):
            self.assertIn(field, data["required"], f"subject-contract: {field} не обязателен")

    def test_evidence_entry_required_fields(self):
        data = json.loads((SCHEMAS / "evidence-entry.schema.json").read_text(encoding="utf-8"))
        for field in ("evidence_id", "run_id", "subject_id", "timestamp", "type", "claim", "hash"):
            self.assertIn(field, data["required"], f"evidence-entry: {field} не обязателен")

    def test_task_ticket_status_enum(self):
        data = json.loads((SCHEMAS / "task-ticket.schema.json").read_text(encoding="utf-8"))
        statuses = set(data["properties"]["status"]["enum"])
        self.assertLessEqual({"open", "in_progress", "done", "failed"}, statuses)


class TestSingularisPackage(unittest.TestCase):
    def test_package_docs_exist(self):
        for name in PKG_FILES:
            self.assertTrue((PKG / name).is_file(), f"нет docs/singularis/{name}")
        for name in SPEC_FILES:
            self.assertTrue((SPEC / name).is_file(), f"нет docs/spec/singularis/{name}")

    def test_axioms_v2_has_a7_a8_as_candidates(self):
        text = (PKG / "axioms-v2.md").read_text(encoding="utf-8")
        self.assertIn("A7", text, "аксиомы 2.0 без A7")
        self.assertIn("A8", text, "аксиомы 2.0 без A8")
        self.assertIn("кандидат", text, "A7/A8 обязаны быть помечены кандидатом до Фазы 1")

    def test_genealogy_recorded(self):
        """Генеалогия прототипа (аксиома 5): ZIP → репо, ADR, тикеты."""
        index = (PKG / "index.md").read_text(encoding="utf-8")
        self.assertIn("nous-singularis-prototype.zip", index, "прототип без генеалогии")
        self.assertTrue(
            (ROOT / "docs" / "decisions" / "0013-singularis-adoption.md").is_file(),
            "нет ADR-0013",
        )

    def test_roadmap_phase0_closed(self):
        text = (ROOT / "docs" / "spec" / "roadmap-singularis.md").read_text(encoding="utf-8")
        phase0 = text.split("### Фаза 1")[0]
        boxes = re.findall(r"^- \[( |x)\]", phase0, re.MULTILINE)
        self.assertTrue(boxes, "Фаза 0 без чек-боксов")
        self.assertEqual(boxes, ["x"] * len(boxes), "Фаза 0 закрыта не полностью")

    def test_tickets_exist_with_sections(self):
        for name in TICKETS:
            text = (ROOT / "tasks" / "open" / name).read_text(encoding="utf-8")
            for section in TICKET_SECTIONS:
                self.assertIn(section, text, f"{name}: нет секции «{section}»")


class TestSingularisInNav(unittest.TestCase):
    def test_nav_covers_singularis(self):
        cfg = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
        nav = set(nav_paths(cfg.get("nav", [])))
        for path in (
            "singularis/index.md", "singularis/axioms-v2.md",
            "spec/singularis/tz-singularis.md", "spec/roadmap-singularis.md",
            "decisions/0013-singularis-adoption.md",
        ):
            self.assertIn(path, nav, f"nav mkdocs не знает SINGULARIS-орган {path}")


if __name__ == "__main__":
    unittest.main()
