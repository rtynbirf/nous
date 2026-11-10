#!/usr/bin/env python3
"""НОУС · SBOM релиза в двух форматах: CycloneDX 1.6 + SPDX 2.3.1.

ADR-0015: релиз несёт SBOM в двух форматах (OpenSSF: SPDX и CycloneDX
взаимодополняемы; CISA 2026 minimum elements: supplier, name, version,
хэши, связи, автор, временная метка — все закрыты).

Диск — истина (карта = территория): инвентаризация берётся из
``git ls-files`` (карта), а байты и хэши — с диска (территория).
Два разных кода отказа, чтобы не врать о причине (аксиома A2):
- missing_on_disk  — файл в индексе, но удалён с диска;
- modified_vs_index — байты на диске не совпадают с индексом
  (сравнение git-blob-sha1, а не mtime).

stdlib-only: никакого внешнего SBOM-инструмента в TCB — формат
минимален, проверяется нашим же ``verify`` (A10: convincing ≠ verifiable).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

TOOL_NAME = "scripts/gen_sbom.py"
TOOL_VERSION = "1.0.0"
REPO_URL = "https://github.com/rtynbirf/nous"
NAMESPACE_UUID = uuid.UUID("d3f1c0a2-6e75-4000-8000-4e6f75730000")


# ---------------------------------------------------------------- inventory


def _git(root: Path, *args: str) -> bytes:
    out = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=True,
    )
    return out.stdout


def _batch_blob_sha1(root: Path, paths: list[str]) -> dict[str, str]:
    """git hash-object --stdin-paths: применяет те же clean-фильтры
    (.gitattributes/eol), что и git при записи в индекс. Сравнение
    «диск vs индекс» обязано идти через него, иначе EOL-нормализация
    даёт ложные срабатывания на каждом файле."""
    if not paths:
        return {}
    stdin = ("\n".join(paths) + "\n").encode("utf-8")
    out = subprocess.run(
        ["git", "-C", str(root), "hash-object", "--stdin-paths"],
        input=stdin, capture_output=True, check=True,
    )
    hashes = out.stdout.decode("ascii").split()
    return dict(zip(paths, hashes))


def inventory(root: Path) -> tuple[list[dict], list[str]]:
    """[(path, size, sha256, sha1)], [ошибки-причины]."""
    tracked = [p.decode("utf-8") for p in _git(root, "ls-files", "-z").split(b"\0") if p]
    index = {}
    for entry in _git(root, "ls-files", "-s", "-z").split(b"\0"):
        if not entry:
            continue
        meta, _, name = entry.partition(b"\t")
        mode, sha, _stage = meta.split()  # <mode> <blob-sha> <stage>
        index[name.decode("utf-8")] = sha.decode("ascii")

    files: list[dict] = []
    errors: list[str] = []
    # missing_on_disk отфильтровываем ДО батч-хэширования: git hash-object
    # падает на всём батче, если хотя бы одного файла нет на диске.
    existing = [p for p in tracked if (root / p).is_file()]
    for path in tracked:
        if path not in set(existing):
            errors.append(f"missing_on_disk: {path} (в индексе, на диске нет)")
    blob_of = _batch_blob_sha1(root, existing)
    for path in sorted(existing):
        data = (root / path).read_bytes()
        if path in index and blob_of.get(path) != index[path]:
            errors.append(f"modified_vs_index: {path} (диск ≠ индекс)")
            continue
        files.append(
            {
                "path": path,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "sha1": hashlib.sha1(data).hexdigest(),
            }
        )
    return files, errors


def _meta(root: Path, version_arg: str | None) -> tuple[str, str, str]:
    """(version, commit, timestamp) — детерминированно от репо."""
    version = version_arg or ""
    if not version:
        env = subprocess.run(
            ["bash", "-c", "printenv NOUS_RELEASE_VERSION"], capture_output=True
        )
        version = env.stdout.decode().strip()
    if not version:
        try:
            version = _git(
                root, "describe", "--tags", "--always", "--dirty"
            ).decode().strip()
        except subprocess.CalledProcessError:
            version = "0+unknown"
    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    ts = (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return version, commit, ts


def _serial(commit: str, version: str) -> str:
    return "urn:uuid:" + str(
        uuid.uuid5(NAMESPACE_UUID, f"{REPO_URL}|{commit}|{version}")
    )


# --------------------------------------------------------------- CycloneDX


def build_cyclonedx(
    files: list[dict], version: str, commit: str, ts: str
) -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": _serial(commit, version),
        "version": 1,
        "metadata": {
            "timestamp": ts,
            "lifecycles": [{"phase": "build"}],
            "tools": {
                "components": [
                    {"type": "application", "name": TOOL_NAME,
                     "version": TOOL_VERSION}
                ]
            },
            "manufacturer": {"name": "rtynbirf"},
            "component": {
                "bom-ref": "root:nous",
                "type": "application",
                "name": "nous",
                "version": version,
                "purl": f"pkg:github/rtynbirf/nous@{version.lstrip('v')}",
                "supplier": {"name": "rtynbirf"},
            },
            "properties": [
                {"name": "nous:commit", "value": commit},
            ],
        },
        "components": [
            {
                "type": "file",
                "bom-ref": f"file:{f['path']}",
                "name": f["path"],
                "size": f["size"],
                "hashes": [{"alg": "SHA-256", "content": f["sha256"]}],
            }
            for f in files
        ],
        "dependencies": [
            {
                "ref": "root:nous",
                "dependsOn": [f"file:{f['path']}" for f in files],
            }
        ],
    }


# ------------------------------------------------------------------- SPDX


def build_spdx(
    files: list[dict], version: str, commit: str, ts: str
) -> dict:
    # packageVerificationCode (SPDX 2.3 §3.9.2): SHA1 от конкатенации
    # отсортированных SHA1-хэшей файлов; алгоритм зафиксирован в ADR-0015
    # и пересчитывается нашим verify (проверяемость не делегируется).
    concat = "".join(sorted(f["sha1"] for f in files))
    verification_code = hashlib.sha1(concat.encode()).hexdigest()

    def sid(i: int) -> str:
        return f"SPDXRef-File-{i:04d}"

    return {
        "spdxVersion": "SPDX-2.3.1",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"nous-release-{version}",
        "documentNamespace": f"{REPO_URL}/sbom/{commit[:12]}/{version}",
        "creationInfo": {
            "created": ts,
            "creators": [
                f"Tool: {TOOL_NAME}-{TOOL_VERSION}",
                "Organization: rtynbirf",
            ],
        },
        "packages": [
            {
                "SPDXID": "SPDXRef-Package-nous",
                "name": "nous",
                "versionInfo": version,
                "supplier": "Organization: rtynbirf",
                "originator": f"Organization: rtynbirf",
                "downloadLocation": f"git+{REPO_URL}.git@{commit}",
                "filesAnalyzed": True,
                "packageVerificationCode": {
                    "packageVerificationCodeValue": verification_code
                },
                "licenseConcluded": "NOASSERTION",
                "licenseInfoFromFiles": ["NOASSERTION"],
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "primaryPackagePurpose": "APPLICATION",
                "comment": (
                    "Инвентаризация = tracked-файлы репо на коммите "
                    f"{commit[:12]}; хэши SHA-256 на диск (диск — истина)."
                ),
            }
        ],
        "files": [
            {
                "SPDXID": sid(i),
                "fileName": f"./{f['path']}",
                "checksums": [
                    {"algorithm": "SHA256", "checksumValue": f["sha256"]},
                    {"algorithm": "SHA1", "checksumValue": f["sha1"]},
                ],
                "licenseConcluded": "NOASSERTION",
                "licenseInfoInFiles": ["NOASSERTION"],
                "copyrightText": "NOASSERTION",
            }
            for i, f in enumerate(files, start=1)
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": "SPDXRef-Package-nous",
            }
        ]
        + [
            {
                "spdxElementId": "SPDXRef-Package-nous",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": sid(i),
            }
            for i in range(1, len(files) + 1)
        ],
    }


# ------------------------------------------------------------------ verify


def _recompute(files: list[dict]) -> dict[str, str]:
    return {f["path"]: f["sha256"] for f in files}


def verify(cdx_path: Path, spdx_path: Path, root: Path) -> list[str]:
    """Сверка SBOM с диском: missing / changed / extra. Пусто = зелёный."""
    problems: list[str] = []
    cdx = json.loads(cdx_path.read_text(encoding="utf-8"))
    spdx = json.loads(spdx_path.read_text(encoding="utf-8"))

    cdx_hashes = {
        c["name"]: next(h["content"] for h in c.get("hashes", [])
                        if h["alg"] == "SHA-256")
        for c in cdx.get("components", []) if c.get("type") == "file"
    }
    spdx_hashes = {
        f["fileName"].removeprefix("./"): next(
            c["checksumValue"] for c in f.get("checksums", [])
            if c["algorithm"] == "SHA256"
        )
        for f in spdx.get("files", [])
    }
    disk = _recompute(inventory(root)[0])

    for name, h in disk.items():
        for label, table in (("cyclonedx", cdx_hashes), ("spdx", spdx_hashes)):
            if name not in table:
                problems.append(f"{label}: missing_in_sbom: {name}")
            elif table[name] != h:
                problems.append(f"{label}: hash_mismatch: {name}")
    for label, table in (("cyclonedx", cdx_hashes), ("spdx", spdx_hashes)):
        for name in table:
            if name not in disk:
                problems.append(f"{label}: stale_entry: {name} (нет на диске)")
    if cdx.get("specVersion") != "1.6" or spdx.get("spdxVersion") != "SPDX-2.3.1":
        problems.append("formats: неожиданные версии спецификаций SBOM")
    return problems


# -------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="НОУС · SBOM релиза")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("gen", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--cyclonedx", required=True, type=Path)
        s.add_argument("--spdx", required=True, type=Path)
        s.add_argument("--root", type=Path, default=None)
        if name == "gen":
            s.add_argument("--version", dest="version", default=None)
            s.add_argument(
                "--allow-dirty", action="store_true",
                help="не падать на modified_vs_index (только разработка;"
                " missing_on_disk фатален всегда)",
            )
    ns = ap.parse_args(argv)
    root = (ns.root or Path(__file__).resolve().parent.parent).resolve()

    files, errors = inventory(root)

    if ns.cmd == "gen":
        dirty = [e for e in errors if e.startswith("missing_on_disk")]
        uncommitted = [e for e in errors if e.startswith("modified_vs_index")]
        if dirty or (uncommitted and not ns.allow_dirty):
            print("FAIL: карта ≠ территория, SBOM не строится:", file=sys.stderr)
            for e in errors:
                print(f"  {e}", file=sys.stderr)
            if uncommitted and not ns.allow_dirty:
                print(
                    "  (подсказка: для локальной разработки есть --allow-dirty;"
                    " релиз обязан идти по чистому чекауту)",
                    file=sys.stderr,
                )
            return 2
        if uncommitted:
            print(
                f"[sbom] ПРЕДУПРЕЖДЕНИЕ: {len(uncommitted)} файлов не совпадают"
                " с индексом — хэшируются байты диска (разработка, не релиз)",
                file=sys.stderr,
            )
        version, commit, ts = _meta(root, ns.version)
        ns.cyclonedx.write_text(
            json.dumps(build_cyclonedx(files, version, commit, ts),
                       indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        ns.spdx.write_text(
            json.dumps(build_spdx(files, version, commit, ts),
                       indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            f"[sbom] {len(files)} файлов → {ns.cyclonedx.name} (CycloneDX 1.6) "
            f"+ {ns.spdx.name} (SPDX 2.3.1); версия {version}, {commit[:12]}"
        )
        return 0

    problems = verify(ns.cyclonedx, ns.spdx, root)
    if problems:
        print("FAIL: SBOM ≠ территория:", file=sys.stderr)
        for p in problems[:40]:
            print(f"  {p}", file=sys.stderr)
        if len(problems) > 40:
            print(f"  … и ещё {len(problems) - 40}", file=sys.stderr)
        return 3
    print(f"[sbom] verify OK: {len(files)} файлов совпадают в обоих форматах")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
