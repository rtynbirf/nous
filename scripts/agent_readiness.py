#!/usr/bin/env python3
"""НОУС · self-probe готовности репозитория к AI-агентам.

Тренд 2026 (Larrin Agent Readiness 84 checks, agent-next/agent-ready,
Harness agent-ready repo): «agent-ready» стало измеримой категорией.
НОУС отвечает принципиально иначе: не внешний грейдер, а СВОЯ проба —
каждое требование мировой практики исполнимо здесь и сейчас
(аксиома A10: convincing ≠ verifiable). Карта практик:
  AGENTS.md-стандарт (agents.md, 60k+ репо) · llms.txt · пин actions
  по SHA (GitHub hardening, урок tj-actions/Shai-Hulud) ·
  минимальные permissions · persist-credentials:false ·
  SLSA Build L2 (аттестация за гейтом) · SBOM двух форматов (OpenSSF) ·
  SHA256SUMS последним · pins-freshness (ADR-0010) · dependabot ·
  CODEOWNERS · governance-триада SECURITY/LICENSE/AI_POLICY ·
  исполняемая карта тестов · лёгкое сканирование секретов (не замена
  gitleaks — независимый пояс).

Fail-closed: любая неуспешная проба = ненулевой выход.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_PATTERNS = (
    ("ghp_", re.compile(r"ghp_[0-9A-Za-z]{36}")),
    ("github_pat_", re.compile(r"github_pat_[0-9A-Za-z_]{40,}")),
    ("aws_akia", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack_xox", re.compile(r"xox[baprs]-[0-9A-Za-z-]{20,}")),
)
SKIP_DIRS = {".git", ".verify-site", "site", "__pycache__", ".venv"}


def _load(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def _workflows() -> list[tuple[Path, str, dict]]:
    out = []
    import yaml
    for p in sorted(WF.glob("*.yml")):
        out.append((p, p.read_text(encoding="utf-8"),
                    yaml.safe_load(p.read_text(encoding="utf-8")) or {}))
    return out


def _tracked() -> list[Path]:
    import subprocess
    raw = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True, check=True,
    ).stdout
    return [ROOT / p.decode("utf-8") for p in raw.split(b"\0") if p]


# ------------------------------------------------------------------ probes

def probe_agints_md() -> tuple[bool, str]:
    t = _load(ROOT / "AGENTS.md")
    return len(t) >= 500, f"{len(t)} символов"


def probe_llms_txt() -> tuple[bool, str]:
    t = _load(ROOT / "llms.txt")
    return len(t) >= 200, f"{len(t)} символов"


def probe_actions_pinned() -> tuple[bool, str]:
    bad = []
    for path, _, _ in _workflows():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith("uses:") and "@" in s:
                ref = s.split("uses:", 1)[1].strip().split()[0].split("@", 1)[1]
                if not SHA_RE.match(ref):
                    bad.append(f"{path.name}:{i}")
    return not bad, f"не пиновано: {bad or 'нет'}"


def probe_persist_credentials() -> tuple[bool, str]:
    bad = []
    for path, _, data in _workflows():
        for job in data.get("jobs", {}).values():
            for step in job.get("steps", []):
                if "actions/checkout" in step.get("uses", ""):
                    if step.get("with", {}).get("persist-credentials") is not False:
                        bad.append(path.name)
    return not bad, f"нарушения: {bad or 'нет'}"


def probe_permissions_minimal() -> tuple[bool, str]:
    bad = []
    for path, _, data in _workflows():
        perms = data.get("permissions")
        if not isinstance(perms, dict) or perms.get("contents") != "read":
            bad.append(path.name)
    return not bad, f"не contents:read: {bad or 'нет'}"


def probe_no_dangerous_triggers() -> tuple[bool, str]:
    forbidden = {"pull_request_target", "workflow_run"}
    bad = []
    for path, _, data in _workflows():
        triggers = data.get(True, {}) or data.get("on", {}) or {}
        used = forbidden & set(triggers)
        if used:
            bad.append(f"{path.name}:{sorted(used)}")
    return not bad, f"запрещённые: {bad or 'нет'}"


def probe_attestation_gated() -> tuple[bool, str]:
    blob = _load(WF / "release.yml")
    ok = "ENABLE_ATTESTATION" in blob and "attest-build-provenance" in blob
    return ok, "гейт + attest-build-provenance" if ok else "нет гейта или шага"


def probe_sbom_two_formats() -> tuple[bool, str]:
    gen = (ROOT / "scripts" / "gen_sbom.py").is_file()
    blob = _load(WF / "release.yml")
    ok = gen and "gen_sbom.py gen" in blob and "gen_sbom.py verify" in blob
    return ok, "gen+verify в release" if ok else "SBOM не в релизе"


def probe_sha256sums_last() -> tuple[bool, str]:
    """SHA256SUMS пишется последним из создателей артефактов (до аттестации)."""
    lines = _load(WF / "release.yml").splitlines()
    idx = {
        "gen": next((i for i, l in enumerate(lines) if "gen_sbom.py gen" in l), None),
        "sums": next((i for i, l in enumerate(lines) if "sha256sum " in l and ">" in l), None),
        "attest": next((i for i, l in enumerate(lines)
                        if "attest-build-provenance@" in l), None),
    }
    ok = idx["gen"] is not None and idx["sums"] is not None \
        and idx["attest"] is not None and idx["gen"] < idx["sums"] < idx["attest"]
    return ok, (f"порядок нарушен: {idx}" if not ok else
                f"gen < sha256sum < attest OK")


def probe_pins_fresh() -> tuple[bool, str]:
    import yaml
    pins = yaml.safe_load((ROOT / "manifests" / "pins.yaml")
                          .read_text(encoding="utf-8"))
    stale = []
    for section in ("actions", "tools"):
        for name, pin in (pins.get(section) or {}).items():
            checked = datetime.strptime(str(pin["verified_at"]), "%Y-%m-%d").date()
            if (date.today() - checked).days >= 90:
                stale.append(f"{section}/{name}")
    return not stale, f"устаревшие: {stale or 'нет'}"


def probe_dependabot_codeowners() -> tuple[bool, str]:
    ok = (ROOT / ".github" / "dependabot.yml").is_file() \
        and (ROOT / ".github" / "CODEOWNERS").is_file()
    return ok, "dependabot + CODEOWNERS" if ok else "нет dependabot/CODEOWNERS"


def probe_governance_triad() -> tuple[bool, str]:
    names = ("SECURITY.md", "LICENSE", "AI_POLICY.md")
    missing = [n for n in names if not (ROOT / n).is_file()]
    return not missing, f"нет: {missing or 'ничего'}"


def probe_executable_map() -> tuple[bool, str]:
    tests = sorted((ROOT / "tests").glob("test_*.py"))
    return len(tests) >= 5, f"{len(tests)} тест-модулей"


def probe_secret_scan() -> tuple[bool, str]:
    hits = []
    for p in _tracked():
        if set(p.parts) & SKIP_DIRS or p.suffix == ".lock":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pat in SECRET_PATTERNS:
            if pat.search(text):
                hits.append(f"{p.relative_to(ROOT)}:{label}")
    return not hits, f"попадания: {hits or 'нет'} (лёгкий пояс, не замена gitleaks)"


PROBES = [
    ("R-01", "AGENTS.md — интерфейс к агентам (стандарт agents.md)", probe_agints_md),
    ("R-02", "llms.txt — машиночитаемый срез для retrieval", probe_llms_txt),
    ("R-03", "actions пинованы полным SHA (GitHub hardening)", probe_actions_pinned),
    ("R-04", "checkout persist-credentials:false", probe_persist_credentials),
    ("R-05", "минимальные permissions (contents: read)", probe_permissions_minimal),
    ("R-06", "нет опасных триггеров (pull_request_target/workflow_run)", probe_no_dangerous_triggers),
    ("R-07", "аттестация SLSA L2 за гейтом ENABLE_ATTESTATION", probe_attestation_gated),
    ("R-08", "SBOM двух форматов gen+verify в релизе", probe_sbom_two_formats),
    ("R-09", "SHA256SUMS пишется последним, до аттестации", probe_sha256sums_last),
    ("R-10", "pins.yaml свежий (<90 дней, ADR-0010)", probe_pins_fresh),
    ("R-11", "dependabot.yml + CODEOWNERS", probe_dependabot_codeowners),
    ("R-12", "governance-триада SECURITY/LICENSE/AI_POLICY", probe_governance_triad),
    ("R-13", "исполняемая карта: ≥5 тест-модулей", probe_executable_map),
    ("R-14", "лёгкое сканирование секретов (независимый пояс)", probe_secret_scan),
]


def run() -> dict:
    checks = []
    for pid, title, fn in PROBES:
        try:
            ok, detail = fn()
        except Exception as exc:  # проба сломалась — это честный FAIL
            ok, detail = False, f"ошибка пробы: {exc!r}"
        checks.append({"id": pid, "title": title, "ok": bool(ok), "detail": detail})
    return {
        "schema": 1,
        "score": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "checks": checks,
    }


def render_md(report: dict) -> str:
    lines = [
        "# Self-probe готовности к агентам",
        "",
        f"Счёт: **{report['score']}/{report['total']}** — "
        "каждая строка исполнима (A10: convincing ≠ verifiable).",
        "",
        "| ID | Проба | ✓ | Детали |",
        "|---|---|---|---|",
    ]
    for c in report["checks"]:
        lines.append(
            f"| {c['id']} | {c['title']} | {'✓' if c['ok'] else '✗'} | {c['detail']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="НОУС · self-probe готовности")
    ap.add_argument("--json", action="store_true", help="только JSON")
    ap.add_argument("--write", type=Path, default=None,
                    help="дополнительно записать JSON в файл")
    ns = ap.parse_args(argv)
    report = run()
    if ns.write:
        ns.write.parent.mkdir(parents=True, exist_ok=True)
        ns.write.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
    if ns.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(render_md(report))
    ok = report["score"] == report["total"]
    print(f"[readiness] {report['score']}/{report['total']} — "
          + ("полный счёт" if ok else "ЕСТЬ ПРОВАЛЫ"), file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
