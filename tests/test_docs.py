"""НОУС · целостность знаний: nav mkdocs соответствует файлам, ссылки живые."""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#\s]+)(?:#[^)]*)?\)")


def nav_paths(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from nav_paths(value)
    elif isinstance(node, list):
        for item in node:
            yield from nav_paths(item)


class TestDocs(unittest.TestCase):
    def setUp(self):
        self.cfg = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))

    def test_nav_targets_exist(self):
        missing = [
            p for p in nav_paths(self.cfg.get("nav", []))
            if not (DOCS / p).is_file()
        ]
        self.assertEqual(missing, [], f"nav mkdocs ссылается на отсутствующее: {missing}")

    def test_docs_files_are_in_nav(self):
        nav = {str(p) for p in nav_paths(self.cfg.get("nav", []))}
        on_disk = {
            str(p.relative_to(DOCS)) for p in DOCS.rglob("*.md")
        }
        stray = on_disk - nav
        self.assertEqual(stray, set(), f"документы вне nav: {sorted(stray)}")

    def test_internal_markdown_links_resolve(self):
        broken = []
        for md in DOCS.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            for target in LINK_RE.findall(text):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                resolved = (md.parent / target).resolve()
                if not resolved.is_file():
                    broken.append(f"{md.relative_to(ROOT)} → {target}")
        self.assertEqual(broken, [], f"разорванные ссылки знаний: {broken}")

    def test_llms_generator_covers_all_doc_sections(self):
        script = (ROOT / "scripts" / "gen_llms.sh").read_text(encoding="utf-8")
        for section in ("getting-started", "guides", "concepts", "decisions",
                        "reference", "implementation"):
            self.assertIn(section, script,
                          f"gen_llms.sh не индексирует раздел {section}")


if __name__ == "__main__":
    unittest.main()
