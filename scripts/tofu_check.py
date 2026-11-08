#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 14 — TOFU-гейт: сверка сборок с first_burn-пломбой.

Читает блок `first_burn:` из manifests/pins.yaml (минимальный чтатель плоского
YAML: пары `key: value` и список `- name: ...`). Пока блок пуст — код 0 с
пометкой «ждёт первого огня». После пломбы: sha256 каждого проверяемого файла
сверяется с запечатанным; расхождение = код 1 (красный до ADR).
Только stdlib, Python 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path


def parse_first_burn(text: str) -> dict:
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.rstrip() == "first_burn:":
            start = i + 1
            break
    if start is None:
        return {}
    out: dict = {"artifacts": []}
    cur: dict | None = None
    for ln in lines[start:]:
        if ln.strip() and not ln.startswith((" ", "\t")):
            break  # следующий блок верхнего уровня
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s == "artifacts: []":
            out["artifacts"] = []
            cur = None
            continue
        if s.startswith("- "):
            cur = {}
            out["artifacts"].append(cur)
            s = s[2:].strip()
            if not s:
                continue
        key, _, val = s.partition(":")
        key = key.strip()
        val = val.strip()
        if cur is None and key == "artifacts" and val in ("", "[]", "null", "~"):
            out["artifacts"] = []
            continue
        target = cur if cur is not None else out
        target[key] = None if val in ("", "null", "~") else val
    return out


def is_sealed(fb: dict) -> bool:
    arts = fb.get("artifacts") or []
    return bool(arts) and all(a.get("sha256") for a in arts)


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_check(pins: Path, pairs: list[str]) -> int:
    fb = parse_first_burn(pins.read_text(encoding="utf-8")) if pins.exists() else {}
    if not fb:
        print(f"{pins}: блока first_burn нет — гейт молчит (норма до решения о пломбе)")
        return 0
    if not is_sealed(fb):
        print("TOFU не запечатан: first_burn пуст — ждёт первого огня форжа "
              "(норма до первого реального прогона)")
        return 0
    by_name = {a.get("name"): a for a in fb["artifacts"]}
    rc = 0
    for pair in pairs:
        name, _, path = pair.partition("=")
        art = by_name.get(name)
        if art is None:
            print(f"🔴 {name}: имени нет в first_burn — сверка невозможна")
            rc = 2
            continue
        p = Path(path)
        if not p.exists():
            print(f"🔴 {name}: файл не найден: {path}")
            rc = 2
            continue
        digest = sha_file(p)
        if digest != art["sha256"]:
            print(f"🔴 {name}: расхождение с first_burn — красный до ADR (issue 14)")
            rc = 1
        else:
            print(f"🟢 {name}: sha256 совпадает с first_burn")
    if rc == 0:
        print("TOFU-гейт зелёный")
    return rc


def cmd_list(pins: Path) -> int:
    fb = parse_first_burn(pins.read_text(encoding="utf-8")) if pins.exists() else {}
    if not fb:
        print(f"{pins}: блока first_burn нет")
        return 0
    print(f"sealed_at: {fb.get('sealed_at')}, run_id: {fb.get('run_id')}")
    for a in fb.get("artifacts", []):
        print(f"- {a.get('name')}: {a.get('sha256')}")
    return 0


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        art = root / "artifact.bin"
        art.write_bytes(b"first-burn-payload")
        good = hashlib.sha256(art.read_bytes()).hexdigest()
        pins = root / "pins.yaml"
        pins.write_text(
            "other_block:\n  a: 1\nfirst_burn:\n  sealed_at: 2026-11-09T00:00:00Z\n"
            "  run_id: run-test\n  artifacts:\n    - name: artifact\n"
            f"      path: artifact.bin\n      sha256: {good}\n",
            encoding="utf-8")
        fb = parse_first_burn(pins.read_text(encoding="utf-8"))
        assert is_sealed(fb) and fb["artifacts"][0]["sha256"] == good
        assert cmd_check(pins, [f"artifact={art}"]) == 0
        art.write_bytes(b"tampered-payload")
        assert cmd_check(pins, [f"artifact={art}"]) == 1
        pins.write_text("first_burn:\n  sealed_at: null\n  run_id: null\n  artifacts: []\n",
                        encoding="utf-8")
        assert cmd_check(pins, []) == 0  # не запечатан — ждёт первого огня
    print("selftest: OK (пустая пломба → 0, совпадение → 0, расхождение → 1)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="TOFU-гейт first_burn (issue 14)")
    ap.add_argument("--pins", default="manifests/pins.yaml")
    ap.add_argument("--check", action="append", default=[],
                    help="сверка в виде имя=путь (можно несколько раз)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.list:
        return cmd_list(Path(args.pins))
    return cmd_check(Path(args.pins), args.check)


if __name__ == "__main__":
    raise SystemExit(main())
