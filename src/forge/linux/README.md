# src/forge/linux — Linux-ветка форжа (равноправная)

Спека: [04-linux-iso.md](../../../docs/spec/implementation/04-linux-iso.md)
Тикет: 0004 (фаза R4) · Субъект: forge-builder-linux
Статус: код готов (R4), реальная сборка — первый прогон (TOFU-фиксация пинов)

## Запуск

```bash
# 1. Обследование хоста (только чтение; вердикт «достаточен?»)
bash src/forge/probe/probe.sh

# 2. Сборка (одна команда; фазы: fetch → extract → render → inject → build → verify)
NOUS_PW_HASH="$(openssl passwd -6)" bash src/forge/forge.sh debian12
NOUS_PW_HASH="$(openssl passwd -6)" bash src/forge/forge.sh ubuntu-2404

# 3. Прямой вызов без probe-гейта (не рекомендуется)
bash src/forge/linux/build.sh debian12
```

`NOUS_PW_HASH` — криптохеш (`openssl passwd -6`) из окружения владельца.
Пароли в репо запрещены (`safe-defaults.yaml: secrets_in_repo=forbidden`);
в отрендеренный лог содержимое ответа не печатается (маскирование).

## Структура

| Путь | Орган |
|---|---|
| `build.sh` | конвейер: fetch → extract → render → inject → build → verify |
| `templates/debian12.preseed` | ответ установки Debian 12 (`__PW_HASH__`) |
| `templates/ubuntu-24.04/{user-data,meta-data}` | autoinstall nocloud (`__PW_HASH__/__USER__/__HOSTNAME__`) |

## Инварианты (тест-гейт `tests/test_forge_linux.py`)

- `partman/confirm_nooverwrite=true`, guided LVM: стирание чужих носителей
  отсутствует (`safe-defaults.yaml: wipe_disk=false`);
- URL каналов — только из `manifests/pins.yaml` (хардкод доменов запрещён);
- xorriso-гибрид BIOS+UEFI по спеке 04 (`-isohybrid-mbr` + `-isohybrid-gpt-basdat`);
- SHA256 против официального `SHA256SUMS` канала; TOFU-принуждение пина;
- артефакт всегда с SHA256SUMS + логом сырых команд (аксиома 2).

## CI

Ночной и ручной прогон — `.github/workflows/forge.yml` (ADR-0009):
одноразовый раннер, пароль рождается и умирает в раннере, артефакты —
только в артефакты прогона (`auto_publish=false`).
