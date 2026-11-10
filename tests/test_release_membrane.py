"""НОУС · мембрана выпуска (ADR-0016): инварианты, которые могут провалиться.

Покрывают: тест-крест с exact-set (ADR-0015), формат SHA256SUMS,
self-check на живом наборе в tmp, дифф SBOM, акк-логику дрейфа и
gate-контур с подменой сети (монкепатч fetch_json/fetch_bytes — сеть
в тесты не ходит).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import release_membrane as rm  # noqa: E402

try:  # тест-крест: один инвариант — один источник (и discover, и пакет)
    from tests import test_release_sbom  # noqa: E402
except ImportError:  # pragma: no cover
    import test_release_sbom  # noqa: E402

TARBALL = "nous-docs-site.tar.gz"
CDX = "sbom-cyclonedx.json"
SPDX = "sbom-spdx.json"
SUMS = "SHA256SUMS.txt"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_set(tmp: Path, tarball: bytes = b"T1", cdx: bytes = b"{\"components\": []}") -> dict[str, bytes]:
    blobs = {TARBALL: tarball, CDX: cdx, SPDX: b"{\"packages\": []}"}
    for name, data in blobs.items():
        (tmp / name).write_bytes(data)
    lines = [f"{_sha(blobs[n])}  {n}" for n in (TARBALL, CDX, SPDX)]
    sums = ("\n".join(lines) + "\n").encode("utf-8")
    (tmp / SUMS).write_bytes(sums)
    blobs[SUMS] = sums
    return blobs


def _rewrite_sums(wd: Path) -> bytes:
    """Пересобрать SHA256SUMS по ТЕКУЩИМ байтам набора (для дрейф-сценариев:
    новый состав сначала честно согласован, мембрану интересует только дрейф)."""
    lines = [
        f"{_sha((wd / n).read_bytes())}  {n}" for n in (TARBALL, CDX, SPDX)
    ]
    sums = ("\n".join(lines) + "\n").encode("utf-8")
    (wd / SUMS).write_bytes(sums)
    return sums


class TestCrossRegistry(unittest.TestCase):
    def test_exact_set_matches_release_sbom_registry(self):
        self.assertEqual(
            set(rm.EXACT_SET), set(test_release_sbom.EXPECTED_ARTIFACTS),
            "два реестра точного набора разошлись — мембрана стеречь не может",
        )


class TestParseSums(unittest.TestCase):
    def test_valid(self):
        m = rm.parse_sums(f"{_sha(b'a')}  a.txt\n{_sha(b'b')}  b.txt\n")
        self.assertEqual(m, {"a.txt": _sha(b"a"), "b.txt": _sha(b"b")})

    def test_bad_format(self):
        with self.assertRaises(SystemExit) as cm:
            rm.parse_sums("это не суммы\n")
        self.assertEqual(cm.exception.code, 3)

    def test_empty(self):
        with self.assertRaises(SystemExit) as cm:
            rm.parse_sums("\n")
        self.assertEqual(cm.exception.code, 3)


class TestSelfCheck(unittest.TestCase):
    def test_green_set_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_set(Path(tmp))
            result = rm.self_check(tmp)
            self.assertEqual(
                set(result), {TARBALL, CDX, SPDX},
                "суммы обязаны покрывать набор без самих себя",
            )

    def test_corrupted_byte_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_set(Path(tmp))
            # тампер ПОСЛЕ сборки: байты расходятся с уже записанными суммами
            (Path(tmp) / TARBALL).write_bytes(b"TAMPERED")
            with self.assertRaises(SystemExit) as cm:
                rm.self_check(tmp)
            self.assertEqual(cm.exception.code, 3)

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_set(Path(tmp))
            os.unlink(Path(tmp) / SPDX)
            with self.assertRaises(SystemExit) as cm:
                rm.self_check(tmp)
            self.assertEqual(cm.exception.code, 2)

    def test_sums_hashing_itself_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            blobs = _build_set(Path(tmp))
            lines = [f"{_sha(blobs[n])}  {n}" for n in (TARBALL, CDX, SPDX)]
            # суммы, включающие сами себя (вырожденный случай)
            all_bytes = dict(blobs)
            all_bytes[SUMS] = ("\n".join(lines) + "\n").encode()
            for name, data in all_bytes.items():
                (Path(tmp) / name).write_bytes(data)
            sums = ("\n".join(lines + [f"{_sha(all_bytes[SUMS])}  {SUMS}"]) + "\n")
            (Path(tmp) / SUMS).write_text(sums, encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                rm.self_check(tmp)
            self.assertEqual(cm.exception.code, 3)


class TestSbomDiff(unittest.TestCase):
    def test_added_removed(self):
        old = {("lib/a", "1"), ("lib/b", "2")}
        new = {("lib/b", "2"), ("lib/c", "3")}
        drift = rm.diff_components(old, new)
        self.assertEqual(drift["added"], [("lib/c", "3")])
        self.assertEqual(drift["removed"], [("lib/a", "1")])

    def test_components_ignore_unknown_shape(self):
        self.assertEqual(rm.sbom_components({"components": None}), set())


class TestAck(unittest.TestCase):
    def test_load_validates_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ack.json"
            path.write_text(json.dumps([{"prev_sums_sha256": "x" * 64}]))
            with self.assertRaises(SystemExit) as cm:
                rm.load_acks(str(path))
            self.assertEqual(cm.exception.code, 3)
            path.write_text(json.dumps([{
                "prev_sums_sha256": "a" * 64,
                "ticket": "0023",
                "reason": "калибровка",
            }]))
            acks = rm.load_acks(str(path))
            self.assertEqual(len(acks), 1)


class _FakeNet:
    """Подмена сети: url → байты; fetch_json → dict."""

    def __init__(self, release: dict, blobs: dict[str, bytes]):
        self.release = release
        self.blobs = blobs
        self.calls: list[str] = []

    def fetch_json(self, url: str):
        self.calls.append(url)
        if url.endswith("/releases/latest"):
            return self.release
        raise AssertionError(f"неожиданный json-запрос {url}")

    def fetch_bytes(self, url: str) -> bytes:
        self.calls.append(url)
        for name, data in self.blobs.items():
            if url.endswith(f"::{name}"):
                return data
        raise AssertionError(f"неожиданный байтовый запрос {url}")


class TestGate(unittest.TestCase):
    def setUp(self):
        self._old = (rm.REPO, rm.fetch_json, rm.fetch_bytes)
        self.tmp = tempfile.TemporaryDirectory()
        wd = Path(self.tmp.name)
        blobs = _build_set(wd)
        prev_blobs = dict(blobs)
        release = {
            "tag_name": "v0.4.0",
            "assets": [
                {"name": n, "url": f"https://example/::{n}"} for n in rm.EXACT_SET
            ],
        }
        self.net = _FakeNet(release, prev_blobs)
        rm.REPO = "rtynbirf/nous"
        rm.fetch_json = self.net.fetch_json
        rm.fetch_bytes = self.net.fetch_bytes

    def tearDown(self):
        rm.REPO, rm.fetch_json, rm.fetch_bytes = self._old
        self.tmp.cleanup()

    def _run(self, fail_on_change: bool, state: Path):
        return rm.cmd_gate(self.tmp.name, str(state), fail_on_change)

    def test_no_drift_green(self):
        self.assertEqual(self._run(True, Path(self.tmp.name) / "ack.json"), 0)

    def test_drift_without_ack_red(self):
        wd = Path(self.tmp.name)
        # свежий SBOM отличается: +один компонент; набор согласован
        (wd / CDX).write_text(json.dumps({
            "components": [{"name": "lib/x", "version": "9"}]
        }), encoding="utf-8")
        _rewrite_sums(wd)
        with self.assertRaises(SystemExit) as cm:
            self._run(True, wd / "ack.json")
        self.assertEqual(cm.exception.code, 6, "дрейф без акка обязан краснить")

    def test_drift_with_ack_green(self):
        wd = Path(self.tmp.name)
        (wd / CDX).write_text(json.dumps({
            "components": [{"name": "lib/x", "version": "9"}]
        }), encoding="utf-8")
        _rewrite_sums(wd)
        prev_sums_sha = _sha(self.net.blobs[SUMS])
        ack = wd / "ack.json"
        ack.write_text(json.dumps([{
            "prev_sums_sha256": prev_sums_sha,
            "ticket": "0023",
            "reason": "осознанная калибровка состава",
        }]), encoding="utf-8")
        self.assertEqual(self._run(True, ack), 0)

    def test_no_releases_first_run_green(self):
        import urllib.error

        def fetch_json_404(url: str):
            if url.endswith("/releases/latest"):
                raise urllib.error.HTTPError(url, 404, "no releases", {}, None)
            raise AssertionError(url)

        rm.fetch_json = fetch_json_404
        self.assertEqual(
            rm.cmd_gate(self.tmp.name, str(Path(self.tmp.name) / "ack.json"), True),
            0,
        )


if __name__ == "__main__":
    unittest.main()
