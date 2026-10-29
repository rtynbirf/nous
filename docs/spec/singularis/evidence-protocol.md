# Протокол доказательств (эволюция ADR-0011)

## Принцип

**Evidence-before-effect.**
Любой side-effect (write, commit, PR, image build, public action) возможен только после того, как соответствующая evidence entry стала durable (append-only log + hash).

## Формат записи (минимальный)

```json
{
  "evidence_id": "ev_20261029_a1b2c3",
  "run_id": "run_7f3e",
  "subject_id": "forge-linux",
  "timestamp": "2026-10-29T14:22:01Z",
  "type": "proposal",
  "claim": "Добавлен preseed для debian12 с TOFU pin",
  "actions": [
    {"op": "write", "path": "src/forge/linux/templates/debian12.preseed", "hash": "sha256:..."}
  ],
  "supporting": [
    {"kind": "file", "path": "manifests/pins.yaml", "hash": "..."},
    {"kind": "test", "name": "test_forge_structure", "result": "passed"}
  ],
  "prev_hash": "sha256:...",
  "hash": "sha256:..."
}
```

Схема: `schemas/evidence-entry.schema.json` (обязательные поля: evidence_id, run_id,
subject_id, timestamp, type, claim, hash).

## Требования

- Append-only (или hash-chained)
- Каждая final proposal должна иметь хотя бы один supporting артефакт
- Verifier decision тоже пишется как evidence
- Replay: по evidence можно восстановить, что именно было предложено и почему принято/отклонено

## Интеграция с НОУС

База уже стоит: `src/lib/ledger.sh` (ADR-0011) реализует append-only журнал с цепочкой
хешей (append/verify/weakest), журнал пишется в каждый прогон scan и forge. Журналы
`evidence.jsonl` скана и форжа становятся частными случаями этого протокола: runtime
дописывает run-записи (run_id, subject_id, verifier decision) в тот же журнал или в
выделенный `state/evidence/runs/`, не ломая существующих потребителей.
