# Evidence-gate Ф1 · «эффект без evidence невозможен»

Волна ×3 · W3-B · issue 15 (SINGULARIS Ф1). Существующие workflows и возможный
ledger.sh не тронуты — гейт аддитивен и живёт под новым именем
`scripts/evidence_gate.py`.

## Закон

Каждое действие субъекта → JSONL-доказательство в хеш-цепь. Нет записи — нет
эффекта. Verifier читает только артефакты: пересчитывает хеши, ничего не
доверяя памяти процесса. Budget kill-switch — стена, а не настройка: исчерпан
дневной бюджет — append запрещён кодом выхода, а не предупреждением.

## Артефакты

- Леджер: `state/evidence-gate/ledger.jsonl` (append-only, создаётся при
  первом append; (заполняется скриптом при первом прогоне)).
- Политика: `state/evidence-gate/policy.json` —
  `{"scopes": {"<актор>": ["glob", ...]}, "budget_per_day": {"<актор>": N}}`
  (пустая при первом прогоне — заполняется владельцем; актора без записи в
  scopes любой append отвергает: незаявленное не действует).
- Запись леджера:
  `{"seq", "ts", "actor", "action", "scope", "proof_sha256", "prev", "entry_sha256"}`,
  где `entry_sha256 = sha256(canonical-json записи без entry_sha256)`,
  `prev` — entry_sha256 предыдущей записи (цепь), `proof_sha256` — sha256
  файла-доказательства (если передан).

## Коды выхода (стены)

- 0 — запись принята / цепь валидна;
- 3 — SCOPE_VIOLATION (действие вне зон, заявленных для актора);
- 4 — BUDGET_EXCEED (дневной бюджет исчерпан — kill-switch);
- 5 — TAMPERED / CHAIN_BROKEN (хеш не сходится, prev разорван, дыра в seq).

## Команды

    python3 scripts/evidence_gate.py --append --actor bot --action edit \
      --scope "src/pulse.md" --proof path/to/proof.bin
    python3 scripts/evidence_gate.py --verify
    python3 scripts/evidence_gate.py --selftest

`--selftest` детерминированно покрывает: нормальный append, scope violation
(код 3), budget exceed (код 4), валидность цепи, ловлю подделки (код 5) — на
временных файлах, без сети.

## Связь с приёмкой issue 15

- «verifier зелёный» и «тесты scope violation и budget exceed» — покрываются
  selftest'ом уже в коммите;
- «ledger.sh --verify валиден» — реализовано под аддитивным именем
  `evidence_gate.py --verify` (чтобы не столкнуться с возможным существующим
  ledger.sh);
- «end-to-end run реального тикета» — живой прогон: политика и леджер
  наполняются с первого реального действия.
