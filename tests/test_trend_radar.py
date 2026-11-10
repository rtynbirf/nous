"""НОУС · тренд-радар (ADR-0017): чистые решения и честный отказ источников.

Сеть в тесты не ходит: fetch подменяется, atom-фид — строковый фикс.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import trend_radar as tr  # noqa: E402

ATOM_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>changelog</title>
  <entry><title>Alert one</title><updated>2026-11-09T10:00:00Z</updated></entry>
  <entry><title>Alert two</title><updated>2026-11-08T10:00:00Z</updated></entry>
  <entry><title>Alert three</title><updated>2026-11-07T10:00:00Z</updated></entry>
  <entry><title>Alert four</title><updated>2026-11-06T10:00:00Z</updated></entry>
  <entry><title>Alert five</title><updated>2026-11-05T10:00:00Z</updated></entry>
  <entry><title>Alert six — за срезом</title><updated>2026-11-04T10:00:00Z</updated></entry>
</feed>
"""


class TestFingerprint(unittest.TestCase):
    def test_order_stable(self):
        a = {"x": 1, "y": {"b": 2, "a": 3}}
        b = {"y": {"a": 3, "b": 2}, "x": 1}
        self.assertEqual(tr.fingerprint(a), tr.fingerprint(b))

    def test_change_detected(self):
        self.assertNotEqual(tr.fingerprint({"a": 1}), tr.fingerprint({"a": 2}))


class TestCompare(unittest.TestCase):
    FACTS = {
        "slsa": {"tag": "v1.2"},
        "scorecard": {"tag": "v5.1.0"},
    }

    def test_first_run(self):
        out = tr.compare(None, self.FACTS)
        self.assertEqual(out["mode"], "first-run")

    def test_stable(self):
        prev = {"facts": self.FACTS}
        out = tr.compare(prev, dict(self.FACTS))
        self.assertEqual(out["mode"], "stable")
        self.assertEqual(out["signals"], [])

    def test_moved(self):
        prev = {"facts": {"slsa": {"tag": "v1.1"}, "scorecard": {"tag": "v5.1.0"}}}
        out = tr.compare(prev, dict(self.FACTS))
        self.assertEqual(out["mode"], "moved")
        self.assertEqual(len(out["signals"]), 1)
        self.assertEqual(out["signals"][0]["id"], "slsa")


class _FakeHttp:
    def __init__(self):
        self.json = {}

    def __call__(self, url: str, accept: str = "application/vnd.github+json") -> bytes:
        if url.endswith("changelog/atom/"):
            return ATOM_FIXTURE.encode("utf-8")
        for key, data in self.json.items():
            if key in url:
                return json.dumps(data).encode("utf-8")
        raise AssertionError(f"неожиданный запрос: {url}")


class TestFetchFact(unittest.TestCase):
    def test_gh_release(self):
        fake = _FakeHttp()
        fake.json["repos/ossf/scorecard/releases/latest"] = {
            "tag_name": "v5.1.0", "published_at": "2026-11-01T00:00:00Z",
        }
        saved = tr._http
        tr._http = fake
        try:
            fact = tr.fetch_fact(
                {"id": "scorecard", "kind": "gh_release", "repo": "ossf/scorecard"}
            )
        finally:
            tr._http = saved
        self.assertEqual(fact["tag"], "v5.1.0")

    def test_atom_takes_n_items(self):
        saved = tr._http
        tr._http = _FakeHttp()
        try:
            fact = tr.fetch_fact({"id": "gh-changelog", "kind": "atom",
                                  "url": "https://github.blog/changelog/atom/", "n": 5})
        finally:
            tr._http = saved
        self.assertEqual(len(fact["items"]), 5)
        self.assertEqual(fact["items"][0]["title"], "Alert one")

    def test_unknown_kind_fails_loud(self):
        with self.assertRaises(ValueError):
            tr.fetch_fact({"id": "x", "kind": "rss", "url": "http://x"})


class TestIssueDedupe(unittest.TestCase):
    def test_pull_request_skipped(self):
        saved = (tr._http, tr.REPO)
        fake = _FakeHttp()

        class _Resp:
            @staticmethod
            def read_items():
                return [
                    {"number": 1, "pull_request": {"url": "x"}},
                    {"number": 2},
                ]

        fake.json["repos/rtynbirf/nous/issues"] = _Resp.read_items()
        tr._http = fake
        tr.REPO = "rtynbirf/nous"
        try:
            found = tr.issue_find_open()
        finally:
            tr._http, tr.REPO = saved
        self.assertEqual(found["number"], 2)


class TestRenderReport(unittest.TestCase):
    def test_contains_facts_and_mode(self):
        facts = {"slsa": {"tag": "v1.2", "published_at": "2026-11-01"},
                 "gh-changelog": {"items": [{"title": "A", "updated": "u"}]}}
        known = {"mode": "moved", "signals": [{"id": "slsa", "old": {"tag": "v1.1"}, "new": facts["slsa"]}], "facts": facts}
        md = tr.render_report(known, "state/trend-radar.json")
        self.assertIn("ТРЕНД-РАДАР", md)
        self.assertIn("v1.2", md)
        self.assertIn("Сдвиги", md)

    def test_main_writes_state_on_moved_and_keeps_on_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "radar.json"
            facts1 = {"a": {"tag": "v1"}}
            facts2 = {"a": {"tag": "v2"}}
            saved = (tr._http, tr.SOURCES)
            fake = _FakeHttp()
            fake.json["x"] = {}
            tr.SOURCES = [{"id": "a", "kind": "gh_release", "repo": "a/a"}]

            class _Seq:
                def __init__(self):
                    self.payloads = [json.dumps({"tag_name": "v1", "published_at": None}),
                                     json.dumps({"tag_name": "v2", "published_at": None})]

                def __call__(self, url, accept="application/vnd.github+json"):
                    return self.payloads.pop(0).encode()

            tr._http = _Seq()
            try:
                self.assertEqual(tr.main(["--state", str(state)]), 0)
                first = json.loads(state.read_text())
                self.assertEqual(first["facts"], {"a": {"tag": "v1", "published_at": None}})
                self.assertEqual(tr.main(["--state", str(state)]), 0)
                second = json.loads(state.read_text())
                self.assertEqual(second["facts"]["a"]["tag"], "v2")
            finally:
                tr._http, tr.SOURCES = saved
            del facts1, facts2


if __name__ == "__main__":
    unittest.main()
