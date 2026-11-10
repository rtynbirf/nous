#!/usr/bin/env python3
"""НОУС · мембрана выпуска (ADR-0016).

Три команды, одна философия: релиз не «похож на правильный», он СВЕРЕН.

  self-check         — сверка только что собранного набора: точный набор,
                       формат SHA256SUMS, каждый хэш пересчитан, суммы
                       не хэшируют сами себя.
  gate               — сверка с ПОСЛЕДНИМ изданным релизом: ассеты живы,
                       хэши совпадают с изданным SHA256SUMS.txt, SBOM-drift
                       между изданным и свежим SBOM разрешён только при
                       акке в state/sbom-ack.json (ничего не входит в
                       организм молча).
  sbom-diff          — чистый дифф двух CycloneDX-файлов (отчёт).

Только stdlib (урок ADR-0015: инструмент в TCB не тянет зависимости).
Сеть — только api.github.com через GH_TOKEN/GITHUB_TOKEN из окружения;
токен не читается из файлов и не пишется в логи (ADR-0012).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

SUMS_NAME = "SHA256SUMS.txt"
# Единственный источник истины о наборе — инвариант ADR-0015, который
# исполняет tests/test_release_sbom.py. Здесь множество повторено и СВЕРЕНО
# тестом-крестом tests/test_release_membrane.py: расходятся — CI красный.
EXACT_SET = (
    "nous-docs-site.tar.gz",
    "sbom-cyclonedx.json",
    "sbom-spdx.json",
    SUMS_NAME,
)

API_BASE = os.environ.get("GH_API", "https://api.github.com")
REPO = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY") or ""
_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _http(url: str, accept: str = "application/vnd.github+json") -> bytes:
    """GET с токеном из окружения; тело — байты (json или octet-stream)."""
    req = urllib.request.Request(url, headers={"Accept": accept})
    if _TOKEN:
        req.add_header("Authorization", f"Bearer {_TOKEN}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_json(url: str) -> dict | list:
    return json.loads(_http(url).decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    return _http(url, accept="application/octet-stream")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _die(code: int, msg: str) -> None:
    """Единый отказ мембраны: код в SystemExit, причина — в stderr (A2)."""
    print(f"мембрана[{code}]: {msg}", file=sys.stderr)
    raise SystemExit(code)



def parse_sums(text: str) -> dict[str, str]:
    """Парс SHA256SUMS: строки '<64 hex>␠␠<имя>'. Чужой формат = отказ."""
    result: dict[str, str] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            _die(3, f"формат SHA256SUMS сломан (строка {lineno}): {line[:60]!r}")
        digest, name = parts[0].strip(), parts[1].strip()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            _die(3, f"строка {lineno}: не sha256-хэш: {digest!r}")
        if name in result:
            _die(3, f"строка {lineno}: дубль имени {name!r}")
        result[name] = digest
    if not result:
        _die(3, "SHA256SUMS пуст")
    return result


def self_check(workdir: str) -> dict[str, str]:
    """Сверка свежесобранного набора. Возврат — карты имён->хэш."""
    wd = os.path.abspath(workdir)
    missing = [n for n in EXACT_SET if not os.path.isfile(os.path.join(wd, n))]
    extra = [
        f
        for f in os.listdir(wd)
        if os.path.isfile(os.path.join(wd, f))
        and f not in EXACT_SET
        and not f.startswith(".")
        and f not in ("site",)
    ]
    if missing:
        _die(2, f"точный набор нарушен (нет файлов): {missing}")
    if extra:
        print(f"мембрана: рядом лежат внепроцессные файлы (не гейт): {extra}")
    sums_path = os.path.join(wd, SUMS_NAME)
    sums_map = parse_sums(open(sums_path, encoding="utf-8").read())
    if SUMS_NAME in sums_map:
        _die(3, "SHA256SUMS хэширует сам себя — себя нельзя создать до суммы (инвариант ADR-0015)")
    expected = set(EXACT_SET) - {SUMS_NAME}
    if set(sums_map) != expected:
        _die(3, f"суммы покрывают не тот набор: {sorted(sums_map)} != {sorted(expected)}")
    for name, digest in sums_map.items():
        actual = sha256_bytes(open(os.path.join(wd, name), "rb").read())
        if actual != digest:
            _die(3, f"hash_mismatch: {name} — суммы {digest}, диск {actual} (A2: пересобери, не переписывай)")
    return sums_map


def sbom_components(data: dict) -> set[tuple[str, str]]:
    """Компоненты CycloneDX как (name, version). Не знаем схему — не выдумываем:
    берём только то, что реально есть в файле."""
    out: set[tuple[str, str]] = set()
    for comp in data.get("components", []) or []:
        out.add((str(comp.get("name", "")), str(comp.get("version", ""))))
    return out


def diff_components(old: set, new: set) -> dict:
    return {
        "added": sorted(new - old),
        "removed": sorted(old - new),
    }


def load_acks(state_path: str) -> list[dict]:
    if not os.path.isfile(state_path):
        return []
    try:
        data = json.loads(open(state_path, encoding="utf-8").read())
    except json.JSONDecodeError as exc:
        _die(3, f"state/sbom-ack.json битый JSON: {exc}")
    if not isinstance(data, list):
        _die(3, "state/sbom-ack.json обязан быть списком записей")
    for i, entry in enumerate(data):
        for key in ("prev_sums_sha256", "ticket", "reason"):
            if key not in entry:
                _die(3, f"ack[{i}]: нет поля {key} — акка не существует")
    return data


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    print(text)


def cmd_gate(workdir: str, state_path: str, fail_on_change: bool) -> int:
    local_sums = self_check(workdir)
    wd = os.path.abspath(workdir)
    if not REPO:
        _die(2, "gate: GH_REPO/GITHUB_REPOSITORY не задан")
    url = f"{API_BASE}/repos/{REPO}/releases/latest"
    try:
        release = fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            _summary(
                "## Мембрана выпуска\n\nИзданных релизов ещё нет — сверяться "
                "не с чем (first-run). Свежий набор самопроверку прошёл.\n"
            )
            return 0
        raise
    assets = release.get("assets", [])
    names = {a["name"]: a for a in assets}
    missing = [n for n in EXACT_SET if n not in names]
    if missing:
        _die(4, f"у изданного релиза не хватает ассетов: {missing}")

    prev_sums_bytes = fetch_bytes(names[SUMS_NAME]["url"])
    prev_sums_text = prev_sums_bytes.decode("utf-8")
    prev_sums_map = parse_sums(prev_sums_text)
    if SUMS_NAME in prev_sums_map:
        _die(4, "изданный SHA256SUMS хэширует сам себя — это брак")

    report = ["## Мембрана выпуска (ADR-0016)", ""]
    report.append(f"Изданный релиз: `{release.get('tag_name', '?')}`")
    bad = []
    for name, digest in prev_sums_map.items():
        if name not in names:
            bad.append(name)
            continue
        actual = sha256_bytes(fetch_bytes(names[name]["url"]))
        if actual != digest:
            bad.append(f"{name} (издан {digest}, байты {actual})")
    if bad:
        _die(5, f"hash_mismatch у изданного релиза: {bad}")
    report.append("Ассеты изданного релиза: точный набор, все хэши сходятся ✓")

    prev_cdx = json.loads(
        fetch_bytes(names["sbom-cyclonedx.json"]["url"]).decode("utf-8")
    )
    with open(os.path.join(wd, "sbom-cyclonedx.json"), "rb") as fh:
        new_cdx = json.loads(fh.read().decode("utf-8"))
    drift = diff_components(sbom_components(prev_cdx), sbom_components(new_cdx))

    if not (drift["added"] or drift["removed"]):
        report.append("SBOM-drift: нет — состав организма не менялся ✓")
        _summary("\n".join(report) + "\n")
        return 0

    report.append(
        f"SBOM-drift: +{len(drift['added'])} / −{len(drift['removed'])} компонентов"
    )
    for name in drift["added"][:20]:
        report.append(f"- добавлен: `{name}`")
    for name in drift["removed"][:20]:
        report.append(f"- удалён: `{name}`")

    acks = load_acks(state_path)
    prev_sums_sha = sha256_bytes(prev_sums_bytes)
    covered = [a for a in acks if a["prev_sums_sha256"] == prev_sums_sha]
    if covered:
        who = covered[0]
        report.append(
            f"Акк найден: тикет {who['ticket']} — {who['reason']}. "
            "Дрейф узаконен, мембрана пропускает ✓"
        )
        _summary("\n".join(report) + "\n")
        return 0
    if not fail_on_change:
        _summary("\n".join(report) + "\n")
        return 0
    report.append("")
    report.append(
        "Дрейф БЕЗ акка. Добавь в `state/sbom-ack.json` запись:\n"
        f"  prev_sums_sha256: {prev_sums_sha}\n"
        "  ticket: <NNNN>, reason: <почему состав изменился>.\n"
        "Молча состав не меняется (ничего не отменять — и ничего не добавлять)."
    )
    _summary("\n".join(report) + "\n")
    _die(6, "sbom-drift без акка в state/sbom-ack.json")


def cmd_sbom_diff(old_path: str, new_path: str, fail_on_change: bool) -> int:
    old = sbom_components(json.load(open(old_path, encoding="utf-8")))
    new = sbom_components(json.load(open(new_path, encoding="utf-8")))
    drift = diff_components(old, new)
    if not (drift["added"] or drift["removed"]):
        print("SBOM-diff: различий нет")
        return 0
    print(f"added ({len(drift['added'])}):")
    for name in drift["added"]:
        print(f"  + {name}")
    print(f"removed ({len(drift['removed'])}):")
    for name in drift["removed"]:
        print(f"  - {name}")
    return 1 if fail_on_change else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="мембрана выпуска НОУС (ADR-0016)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_self = sub.add_parser("self-check")
    p_self.add_argument("--dir", default=".")

    p_gate = sub.add_parser("gate")
    p_gate.add_argument("--dir", default=".")
    p_gate.add_argument(
        "--state", default=os.path.join("state", "sbom-ack.json")
    )
    p_gate.add_argument("--fail-on-change", action="store_true")

    p_diff = sub.add_parser("sbom-diff")
    p_diff.add_argument("--old", required=True)
    p_diff.add_argument("--new", required=True)
    p_diff.add_argument("--fail-on-change", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "self-check":
        self_check(args.dir)
        print("мембрана: self-check — точный набор, формат и хэши сходятся ✓")
        return 0
    if args.cmd == "gate":
        return cmd_gate(args.dir, args.state, args.fail_on_change)
    return cmd_sbom_diff(args.old, args.new, args.fail_on_change)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — единый формат отказа мембраны
        print(f"мембрана: отказ ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(2)
