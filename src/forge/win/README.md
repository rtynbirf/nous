# src/forge/win — Windows-ветка форжа (реализовано, R3)

Спека: [docs/spec/implementation/03-windows-iso.md](../../../docs/spec/implementation/03-windows-iso.md)
Тикет: 0003 (фаза R3) · Субъект: forge-builder-win
Инварианты: [manifests/safe-defaults.yaml](../../../manifests/safe-defaults.yaml) · Пины: [manifests/pins.yaml](../../../manifests/pins.yaml)

## Состав модуля

```
fetch-fido.ps1             # фаза fetch: пины → релиз Fido (TOFU) → официальная ссылка Microsoft → ISO
build.ps1                  # главный конвейер: fetch → extract → render → inject → build → verify → emit
autounattend.template.xml  # шаблон ответа установки (WillWipeDisk=false, без паролей и учёток)
```

Точка входа верхнего уровня: `src/forge/forge.ps1` (выжимка фактов хоста + диспетчеризация).

## Конвейер (build.ps1)

| Фаза | Что делает | Сырые факты в лог |
|---|---|---|
| fetch | вызов `fetch-fido.ps1`: пин `forge.fido` → релиз (TOFU: `tag`/`sha256` фиксируются при первом прогоне либо сверяются) → Fido `-GetUrl` → официальная ссылка Microsoft → скачивание ISO → SHA256 | stdout fetch-fido, JSON-отчёт |
| extract | `Mount-DiskImage` + `Copy-Item` во временный каталог (в `finally` — `Dismount-DiskImage`); фиксация путей `boot\etfsboot.com` и `efi\microsoft\boot\efisys.bin` | DriveLetter, размеры, счётчики файлов |
| render | подстановка `__LOCALE__ / __UI_LANG__ / __TIMEZONE__ / __KEY_INDEX__` в шаблон (нативный string replace); неизвестный токен = отказ | полный отрендеренный XML |
| inject | `autounattend.xml` в корень дерева образа | размер + SHA256 файла |
| build | `oscdimg -m -o -u2 -udfver102 -bootdata:2#p0,e,b<etfsboot>#pEF,e,b<efisys> <src> <out.iso>` — аргументная строка ПЕЧАТАЕТСЯ в лог до исполнения | вывод oscdimg |
| verify | если найдены bash+xorriso — `src/lib/verify-iso.sh` (El Torito BIOS+UEFI, /autounattend.xml); иначе честное предупреждение и raw-факты (размер, SHA256) | вывод верификатора |
| emit | `NOUS_TARGET_DIR/win/<дата>/<имя>.iso` + `SHA256SUMS` + `build-log.txt` + `fetch-report.json` | список артефактов |

Инвариант `WillWipeDisk=false` проверяется ДВАЖДЫ (после render и перед build) и в
ОБЕИХ формах — элементной `<WillWipeDisk>false</WillWipeDisk>` и строковой
`WillWipeDisk="true"`: «одна защита — не защита» (спека 03).

`-bootdata` передаётся oscdimg ОДНИМ аргументом: pwsh сам закавычивает значение
с пробелами целиком; внутренние кавычки недопустимы — pwsh экранирует их как `\"`,
а oscdimg такой экранированный формат не парсит.

## Как запускать (Windows-хост владельца)

```powershell
# полная сборка (скачает ISO через Fido — официальная ссылка Microsoft)
pwsh -NoProfile -File src/forge/win/build.ps1 -TargetDir D:\out

# то же через точку входа (выжимка systeminfo + диск TargetDir, затем build)
pwsh -NoProfile -File src/forge/forge.ps1 -Target win -TargetDir D:\out

# повтор/тест без скачивания (уже скачанный ISO)
pwsh -NoProfile -File src/forge/win/build.ps1 -TargetDir D:\out -SkipDownload -IsoPath C:\iso\win11.iso

# список релизов/языков Fido (если нужно сменить релиз или язык)
pwsh -NoProfile -File C:\temp\Fido.ps1 -Win 11 -Rel List -Ed Pro -Lang List
```

Параметры `build.ps1`: `-TargetDir` (по умолчанию `$env:NOUS_TARGET_DIR`, иначе `<репо>\dist`),
`-Locale ru-RU`, `-UiLanguage ru-RU`, `-TimeZone "Russian Standard Time"`, `-KeyIndex 6`
(индекс редакции Pro в install.wim — сверьте: `DISM /Get-WimInfo /WimFile:<диск>\sources\install.wim`),
`-SkipDownload`, `-IsoPath`, `-OscdimgPath`, `-FidoRelease Latest`.
`-Locale`/`-UiLanguage` определяют и язык образа у Fido (см. ниже).

## Языки Fido

Fido матчится по `$language.Name -match $Lang` — по **имени языка из официального
списка Microsoft** (проверено по исходнику Fido, 2026-10-29); коды вида `ru-ru`
именем не являются и списком не находятся. Поэтому `fetch-fido.ps1` нормализует
локаль в официальное имя: дефолт ветки — `ru-RU → Russian`. Иные значения уходят
в Fido как есть: при неверном имени Fido честно падает с подсказкой
`Fido.ps1 -Lang List` — тихой подмены языка нет.

## Зависимости

- **pwsh 7** (PowerShell 7.x) — весь код ветки.
- **oscdimg** из Windows ADK (функция «Deployment Tools») — пин-метод в
  `manifests/pins.yaml → forge.windows-image.method`: «oscdimg — ADK на хосте владельца».
  Стандартный путь поиска: `<ProgramFiles(x86)>\Windows Kits\10\Assessment and Deployment
  Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe`; иначе `-OscdimgPath`.
- **Fido** — только из пина `forge.fido` (репозиторий и тег берутся из пина; SHA256 —
  протокол TOFU: первый прогон печатает «TOFU-фиксация: …» и фиксирует значения,
  калибровка вносит их в `manifests/pins.yaml`, дальше — принудительная сверка).
  Нюанс релизов Fido (проверено по релизам, 2026-10-29): ассет — только
  `Fido.ps1.lzma`, поэтому скрипт берётся из исходников того же тега
  (raw.githubusercontent.com) — и его SHA256 пинуется.
- **xorriso + bash** (опционально, напр. из Git for Windows) — только для фазы verify.

## Границы (что НЕ делаем сознательно)

- Активация, серийные номера, «гречка» обхода лицензирования — нет (ТЗ §7): ProductKey
  в шаблоне пуст, лицензирование — решение владельца.
- Учётные записи и пароли не создаются и не вшиваются: OOBE ведёт пользователь (спека 06);
  обходы экрана учётной записи Microsoft сознательно не включены.
- `WillWipeDisk` всегда `false`; diskpart/format/dd — никогда; запись на физические
  USB/CD — никогда (safe-defaults). Запись кода — только temp и `NOUS_TARGET_DIR`.
- Публикация артефактов вовне — никогда (`auto_publish: false`).

## Статус проверки (честно)

- CI-песочница (Linux): статические тесты `tests/test_forge_win.py` — XML/инварианты/
  маркеры — прогоняются; parse-проверка `.ps1` через `Parser::ParseFile` выполняется
  только при наличии pwsh в PATH, иначе честный skipTest.
- Реальный прогон конвейера (Fido → ISO → oscdimg → verify) НЕ выполнялся: у сборщика
  нет Windows-хоста. Fido в commandline-режиме на не-Windows платформах отказывается
  работать (проверено по исходнику: `exit 403` при winver ≤ 6.1, by design),
  а oscdimg — часть Windows ADK. Первый прогон на хосте владельца = TOFU-фиксация
  пинов (`forge.fido.tag/sha256`, `forge.windows-image.iso_sha256`) с внесением
  в `manifests/pins.yaml` тикетом калибровки (спека 01).
- Отчёт владельца — сырыми выводами, с SHA256 и версией пинов (спека 03).
