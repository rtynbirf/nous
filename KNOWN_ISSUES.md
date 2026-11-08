# KNOWN ISSUES · nous

## Волна ×5 · 2026-11-09

| Воркфлоу | Run id (sha) | Диагноз | Статус после патча |
|---|---|---|---|
| ci (verify: tests) | 42514456648 (46c05f0, PR, 19:19) | test_pins_yaml_is_single_lockfile: guardian-tripwire.yml uses actions/github-script@f28e40c… расходился с manifests/pins.yaml (3a2844b7… — старая запись) | 🟢 выправлено до мержа PR: pins.yaml = f28e40c7f34bde8b3046d885e986cb6290c5673b (v7.1.0, verified_at 2026-11-08); ci push 42515272804 🟢 (19:29, 865268a), 42516622285 🟢 (19:45), диспатч ×5 42527786735 🟢 (152b8e4) |
| ПУЛЬС v2 (self-audit.yml) | 42516341871 (865268a, 19:42) | git push «could not read Username»: persist-credentials: false без явной токен-подстановки | 🟢 ×4 (токен-подстановка x-access-token:GITHUB_TOKEN, комментарий в yml со ссылкой на живой лог); 42516634449 🟢 (19:45, 5924eca), 42516656040 🟢 (19:45, 152b8e4 = сам пульс-коммит), диспатч ×5 42527788744 🟢 |

### Квирки

- YAML-канон этого репо: `on:` парсится как True (YAML 1.1) — в тестах обращение по d[True].
- mkdocs-диатаксис собирается строго (job docs) — «Диатаксис собирается строго» зелёный во всех последних прогонах.
- security-job сканирует секреты и воркфлоу — не вносить токены в файлы, только через env.
