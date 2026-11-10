"""НОУС · релизный гейт SBOM: точный набор, порядок сборки, оба формата.

ADR-0015. Инвариант «точный набор» (exact-set):
  множество загружаемого в артефакт релиза
  == множество аттестуемого (subject каждого attest-шага)
  == {docs-тарболл, sbom-cyclonedx, sbom-spdx, SHA256SUMS}
а SHA256SUMS хэширует все артефакты, КРОМЕ себя самого, и пишется
последним из создателей (генерация SBOM → sha256sum → attest).

Урок (журнал НОУС): детектор порядка не должен ловить сам себя —
порядок ищется по шагам-СОЗДАТЕЛЯМ (команда ``sha256sum … >`` и
``uses: attest-build-provenance``), а не по последнему вхождению имени.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / ".github" / "workflows" / "release.yml"

TARBALL = "nous-docs-site.tar.gz"
CDX = "sbom-cyclonedx.json"
SPDX = "sbom-spdx.json"
SUMS = "SHA256SUMS.txt"
EXPECTED_ARTIFACTS = {TARBALL, CDX, SPDX, SUMS}
EXPECTED_HASHED = {TARBALL, CDX, SPDX}


def _release_yaml() -> dict:
    return yaml.safe_load(RELEASE.read_text(encoding="utf-8"))


def _release_text() -> str:
    return RELEASE.read_text(encoding="utf-8")


def _job_steps() -> list[dict]:
    data = _release_yaml()
    job = data["jobs"]["publish-docs"]
    return job["steps"]


def _uploaded_paths() -> set[str]:
    for step in _job_steps():
        with_ = step.get("with", {})
        if "upload-artifact" in str(step.get("uses", "")):
            paths = with_.get("path") or []
            if isinstance(paths, str):
                paths = paths.splitlines()
            return {p.strip() for p in paths if p.strip()}
    return set()


def _attested_names() -> set[str]:
    names = set()
    for step in _job_steps():
        if "attest-build-provenance" in str(step.get("uses", "")):
            names.add(step.get("with", {}).get("subject_name", ""))
    names.discard("")
    return names


def _hashed_names() -> set[str]:
    m = re.search(
        r"sha256sum\s+([^\n>]+)\s*>\s*" + re.escape(SUMS),
        _release_text(),
    )
    if not m:
        return set()
    return {p.strip() for p in m.group(1).split() if p.strip()}


class TestReleaseExactSet(unittest.TestCase):
    def test_uploaded_set_is_exact(self):
        self.assertEqual(_uploaded_paths(), EXPECTED_ARTIFACTS,
                         "релиз обязан нести точный набор из 4 артефактов")

    def test_attested_set_equals_uploaded(self):
        self.assertEqual(_attested_names(), EXPECTED_ARTIFACTS,
                         "аттестуются ровно те же 4 артефакта (SLSA L2, "
                         "fail-closed: шаг без гейта — тест красный)")

    def test_attestation_steps_are_gated(self):
        blob = _release_text()
        self.assertEqual(blob.count("attest-build-provenance@"), 4,
                         "4 attest-шага: тарболл, оба SBOM, SHA256SUMS")
        self.assertIn("vars.ENABLE_ATTESTATION == '1'", blob,
                      "каждый attest-шаг за гейтом переменной репо")

    def test_hashed_set_covers_all_but_sums_itself(self):
        self.assertEqual(_hashed_names(), EXPECTED_HASHED,
                         "SHA256SUMS хэширует все артефакты, кроме самого "
                         "себя (себя хэшировать нельзя — он создаётся "
                         "последним)")

    def test_build_order_sbom_then_sums_then_attest(self):
        steps = _job_steps()
        idx_gen = next(i for i, s in enumerate(steps)
                       if "gen_sbom.py gen" in str(s.get("run", "")))
        idx_sums = next(i for i, s in enumerate(steps)
                        if re.search(r"sha256sum\s+", str(s.get("run", ""))))
        idx_attest = next(i for i, s in enumerate(steps)
                          if "attest-build-provenance" in str(s.get("uses", "")))
        self.assertLess(idx_gen, idx_sums,
                        "SBOM строится до SHA256SUMS — иначе суммы не "
                        "покрывают SBOM")
        self.assertLess(idx_sums, idx_attest,
                        "аттестация после SHA256SUMS — манифест сумм "
                        "тоже аттестуется")

    def test_verify_step_is_fail_closed(self):
        steps = _job_steps()
        runs = [str(s.get("run", "")) for s in steps]
        self.assertTrue(any("gen_sbom.py verify" in r for r in runs),
                        "релиз сам сверяет SBOM с территорией перед выкладкой")


class TestGenSbomRoundtrip(unittest.TestCase):
    """gen → verify на живом репо: карта и территория совпадают."""

    def test_gen_and_verify_green(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cdx = Path(tmp) / CDX
            spdx = Path(tmp) / SPDX
            gen = subprocess.run(
                ["python3", str(ROOT / "scripts" / "gen_sbom.py"),
                 "gen", "--allow-dirty",
                 "--cyclonedx", str(cdx), "--spdx", str(spdx)],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(gen.returncode, 0, gen.stderr)
            ver = subprocess.run(
                ["python3", str(ROOT / "scripts" / "gen_sbom.py"),
                 "verify", "--cyclonedx", str(cdx), "--spdx", str(spdx)],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(ver.returncode, 0, ver.stderr)

    def test_two_formats_present_and_hashed(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cdx = Path(tmp) / CDX
            spdx = Path(tmp) / SPDX
            subprocess.run(
                ["python3", str(ROOT / "scripts" / "gen_sbom.py"),
                 "gen", "--allow-dirty",
                 "--cyclonedx", str(cdx), "--spdx", str(spdx)],
                check=True, capture_output=True, cwd=ROOT,
            )
            import json
            cdx_data = json.loads(cdx.read_text(encoding="utf-8"))
            spdx_data = json.loads(spdx.read_text(encoding="utf-8"))
            self.assertEqual(cdx_data["bomFormat"], "CycloneDX")
            self.assertEqual(cdx_data["specVersion"], "1.6")
            self.assertTrue(cdx_data["serialNumber"].startswith("urn:uuid:"))
            self.assertGreater(
                sum(1 for c in cdx_data["components"] if c["type"] == "file"), 50,
                "инвентаризация обязана покрывать тело репо")
            self.assertEqual(spdx_data["spdxVersion"], "SPDX-2.3.1")
            self.assertTrue(spdx_data["packages"][0]["filesAnalyzed"])
            self.assertRegex(spdx_data["packages"][0]
                             ["packageVerificationCode"]
                             ["packageVerificationCodeValue"], r"^[0-9a-f]{40}$")
            self.assertEqual(len(spdx_data["files"]),
                             len(cdx_data["components"]),
                             "оба формата описывают один и тот же набор файлов")

    def test_detects_missing_on_disk_vs_modified(self):
        """A2: два разных кода отказа — не врать о причине."""
        import subprocess
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "mini"
            repo.mkdir()
            def git(*a, **kw):
                return subprocess.run(["git", "-C", str(repo), *a],
                                      capture_output=True, text=True, **kw)
            git("init", "-q", check=True)
            git("config", "user.email", "t@t", check=True)
            git("config", "user.name", "t", check=True)
            (repo / "a.txt").write_text("alpha\n")
            (repo / "b.txt").write_text("beta\n")
            git("add", ".", check=True)
            git("commit", "-qm", "init", check=True)

            def run_gen():
                return subprocess.run(
                    ["python3", "-c",
                     "import sys; sys.path.insert(0, str(__import__('pathlib')"
                     ".Path(r'" + str(ROOT) + "') / 'scripts')); "
                     "import gen_sbom; "
                     "raise SystemExit(gen_sbom.main(["
                     "'gen','--cyclonedx','out.cdx.json','--spdx',"
                     "'out.spdx.json','--root',r'" + str(repo) + "'"
                     "]))"],
                    capture_output=True, text=True, cwd=repo,
                )

            # 1) удалён с диска, остался в индексе
            (repo / "b.txt").unlink()
            r = run_gen()
            self.assertEqual(r.returncode, 2)
            self.assertIn("missing_on_disk: b.txt", r.stderr)
            self.assertNotIn("modified_vs_index: b.txt", r.stderr)
            # 2) байты разошлись с индексом
            (repo / "b.txt").write_text("BETA\n")
            r = run_gen()
            self.assertEqual(r.returncode, 2)
            self.assertIn("modified_vs_index: b.txt", r.stderr)
            self.assertNotIn("missing_on_disk: b.txt", r.stderr)
            del shutil


if __name__ == "__main__":
    unittest.main()
