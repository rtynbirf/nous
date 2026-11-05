# Каталог инструментов НОУСа — сингулярные узлы (2026-10-29)

Отличие от каталога коллег (2444 позиции-лексикон, разбор —
`../genesis/sintez-public-repo-synthesis.md`): здесь только инструменты, которые
НОУС **реально использует**, каждый с ролью, статусом и методом верификации.
Capability-модель ESUT (C1–C8) принята как карта ролей, не как слепой список.
Статус по лестнице ADR-0011: CONFIRMED — живой прогон в этом репо; PARTIAL —
упоминание/наводка (с методом); UNKNOWN — заявка без прогона.

## Роли → возможности (ESUT-маппинг)

| Роль НОУСа | ESUT-capabilities | Зачем организму |
|---|---|---|
| Каркас (`src/lib`) | PERCEIVE, TRANSFORM | лог, пины, рендер шаблонов, журнал |
| Форж Linux/Win | TRANSFORM, EXECUTE | сборка ISO-носителей (миссия) |
| Верификатор | OBSERVE, SECURE | гейты факта: El Torito, размер, SHA |
| Сенсор (`src/scan`) | PERCEIVE, SEARCH | калибровка деталей, проверка существования |
| Конституция (CI) | SECURE, ORCHESTRATE | пины, права, гейты, журнал |

## Каталог

| Инструмент | Роль | Capability | Статус | Метод верификации |
|---|---|---|---|---|
| bash | каркас, все скрипты | EXECUTE | CONFIRMED | все прогоны CI 0.2.0–0.3.0 |
| git | источник, журнал-якорь | CREATE | CONFIRMED | клоны/пуши каждого прогона |
| python3 | pins, journal-каноника | TRANSFORM | CONFIRMED | nous::pin, ledger::append в CI |
| xorriso | сборка ISO, верификация El Torito | TRANSFORM | CONFIRMED | прогоны 40868854559 (BIOS+UEFI) |
| oscdimg | Windows-ISO двойной загрузки | TRANSFORM | UNKNOWN | только в среде Windows; нет прогона CI |
| gnupg | TOFU-сверка подписей дистрибутивов | SECURE | CONFIRMED | debian-12.15.0: ключ+SHA сверены |
| openssl | ephemeral NOUS_PW_HASH | SECURE | CONFIRMED | forge.yml, passwd -6 в прогоне |
| mktemp/coreutils | sandbox-гигиена, tmp-каталоги | EXECUTE | CONFIRMED | scan::clone_one, forge build.sh |
| sha256sum | пины, TOFU, верификатор | SECURE | CONFIRMED | pins.yaml lockfile-тест |
| curl | сверка пинов, доктрина B-класса | PERCEIVE | CONFIRMED | находка ключа: живая страница YT |
| yq/pyyaml | lockfile pins.yaml | TRANSFORM | CONFIRMED | test_pins_yaml_is_single_lockfile |
| zizmor | аудит workflows (SAST для Actions) | SECURE | CONFIRMED | чисто в 0.2.0–0.3.0 |
| gitleaks | сканер секретов (сенсор) | SECURE | UNKNOWN | не в контуре; secret-scanning GitHub покрывает публичные |
| trufflehog | сканер секретов с валидацией | SECURE | UNKNOWN | не применяется осознанно: валидация чужих ключей против доктрины ADR-0012 (класс C — не тестировать) |
| syft/grype | SBOM + уязвимости артефактов | SECURE | UNKNOWN | план v0.4 (тикеты 0007/R6) |
| cosign | подпись релизов/журнала | SECURE | UNKNOWN | отложено ADR-0011 |
| shellcheck | SAST для bash-каркаса | SECURE | PARTIAL | локальные прогоны сессии, не в CI-гейтах |
| mkdocs-material | витрина знаний | CREATE | CONFIRMED | сборка доков в CI |
| gh CLI | ревизия настроек репо | ORCHESTRATE | CONFIRMED | audit-2026-10-29 (15 репо API-обходом) |
| qemu | bootsnap-проверка ISO | OBSERVE | UNKNOWN | план тикета 0005 |
| xorriso-report | карта El Torito-структуры | OBSERVE | CONFIRMED | `<iso>.eltorito-report.txt` в прогонах |

## Правила каталога

1. Запись без метода верификации = UNKNOWN — это честный дефолт, не позор (ворота
   коллег: CLAIM→METHOD→RAW→LOG→REPEAT; у нас то же + git-якорь).
2. trufflehog осознанно не применяется к чужим ключам: его «валидация» ключей = акт
   использования чужого секрета, запрещённый доктриной ADR-0012 (класс C). Прибор
   есть, поведение ограничено доктриной.
3. Инструмент добавляется в каталог только с указанием роли НОУСа — «полезный вообще»
   живёт в каталоге коллег, не здесь (граница субъекта, аксиома 5).
