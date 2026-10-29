"""НОУС · исполняемая карта: Windows-ветка форжа (спека 03, тикет 0003).

Запуск: python3 -m unittest tests.test_forge_win -v
Среда: python3 + stdlib (спека: CI-среда без Windows-хоста гоняет только статику).
Parse-проверка .ps1 выполняется только при наличии pwsh в PATH, иначе честно
пропускается (Windows-ветка исполняется на Windows-хосте владельца, ТЗ §3).

Гейты теста:
  (a) autounattend.template.xml парсится xml.etree.ElementTree;
  (b) инварианты: нет wipe-инверсии (обе формы), нет парольных хешей,
      нет __TOKEN__ вне реестра {__LOCALE__, __UI_LANG__, __TIMEZONE__, __KEY_INDEX__};
  (c) build.ps1 / fetch-fido.ps1 / forge.ps1 содержат обязательные маркеры
      реальных команд (oscdimg, -bootdata, Mount-DiskImage, строгий режим);
  (d) при наличии pwsh — синтаксическая проверка обоих .ps1 нативным парсером.
"""
import re
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIN = ROOT / "src" / "forge" / "win"
TEMPLATE = WIN / "autounattend.template.xml"
BUILD_PS1 = WIN / "build.ps1"
FETCH_PS1 = WIN / "fetch-fido.ps1"
FORGE_PS1 = ROOT / "src" / "forge" / "forge.ps1"
README_WIN = WIN / "README.md"
PINS = ROOT / "manifests" / "pins.yaml"

# Реестр известных токенов рендера (спека 03): любое другое __...__ — отказ.
KNOWN_TOKENS = {"__LOCALE__", "__UI_LANG__", "__TIMEZONE__", "__KEY_INDEX__"}

# Паттерны парольных хешей: SHA-crypt ($1$/$5$/$6$/yescrypt $y$) и NTLM (32 hex).
HASH_PATTERNS = [r"\$[156y]\$", r"\b[a-fA-F0-9]{32}\b"]

# Запрещённые элементы/атрибуты: пароли и учётные записи не генерируются
# (спека 06: UserAccounts не создаются без параметров; ТЗ §7: серого нет).
FORBIDDEN_XML = ("<Password", "<PlainText", "<LocalAccounts", "<UserAccounts",
                 "<AdministratorPassword", "AutoLogon")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestTemplate(unittest.TestCase):
    """autounattend.template.xml: корректный XML и инварианты safe-defaults."""

    def setUp(self):
        self.text = read(TEMPLATE)

    def test_parses_as_xml(self):
        root = ET.fromstring(self.text)
        self.assertTrue(root.tag.endswith("unattend"), f"корень не unattend: {root.tag}")
        passes = {el.get("pass") for el in list(root) if el.tag.endswith("settings")}
        self.assertLessEqual({"windowsPE", "specialize", "oobeSystem"}, passes,
                             "не все требуемые проходы присутствуют")

    def test_willwipe_disk_false_explicit(self):
        # Элементная форма — реальная схема unattend: <WillWipeDisk>false</WillWipeDisk>
        self.assertRegex(self.text, r"<WillWipeDisk>\s*false\s*</WillWipeDisk>",
                         "нет ЯВНОГО <WillWipeDisk>false</WillWipeDisk> (спека 06)")
        root = ET.fromstring(self.text)
        wipes = [el.text for el in root.iter() if el.tag.endswith("WillWipeDisk")]
        self.assertTrue(wipes, "элемент WillWipeDisk отсутствует в XML-структуре")
        for w in wipes:
            self.assertEqual(w, "false", f"WillWipeDisk={w} — нарушение oobe_will_wipe_disk")
        # Обе формы инверсии запрещены: элементная и атрибутоподобная строка
        # (на случай копипасты из примеров или сбоя рендера).
        self.assertNotRegex(self.text, r"<WillWipeDisk>\s*true\s*</WillWipeDisk>",
                            "инверсия дефолта wipe в шаблоне запрещена (элемент)")
        self.assertNotIn('WillWipeDisk="true"', self.text,
                         "инверсия дефолта wipe в шаблоне запрещена (строка)")

    def test_disk_config_writes_no_partitions(self):
        root = ET.fromstring(self.text)
        # Разметку не создаём и не форматируем: только существующий раздел
        self.assertIsNone(root.find(".//CreatePartitions"),
                          "CreatePartitions в шаблоне недопустим — деструктив по умолчанию")
        install_to = [el.text for el in root.iter() if el.tag.endswith("InstallToAvailablePartition")]
        self.assertEqual(install_to, ["true"],
                         "установка обязана идти в существующий подходящий раздел")

    def test_image_install_pins_edition(self):
        ns = "{urn:schemas-microsoft-com:unattend}"
        root = ET.fromstring(self.text)
        meta = [el for el in root.iter() if el.tag == f"{ns}MetaData"]
        pairs = {el.findtext(f"{ns}Key"): (el.findtext(f"{ns}Value") or "") for el in meta}
        self.assertEqual(pairs.get("/IMAGE/INDEX"), "__KEY_INDEX__",
                         "редакция не зафиксирована индексом __KEY_INDEX__")
        self.assertEqual(pairs.get("/IMAGE/NAME"), "Windows 11 Pro",
                         "редакция не зафиксирована именем (Windows 11 Pro)")

    def test_no_passwords_or_accounts(self):
        for bad in FORBIDDEN_XML:
            self.assertNotIn(bad, self.text, f"шаблон содержит {bad} — пароли/учётки запрещены")

    def test_no_password_hash_like_substrings(self):
        for pattern in HASH_PATTERNS:
            found = re.findall(pattern, self.text)
            self.assertEqual(found, [], f"подозрение на парольный хеш ({pattern}): {found}")

    def test_product_key_not_embedded(self):
        # Скобим ТОЛЬКО ProductKey/Key: у MetaData тоже есть Key (/IMAGE/...) —
        # это координаты образа, а не серийник.
        ns = "{urn:schemas-microsoft-com:unattend}"
        root = ET.fromstring(self.text)
        blocks = [el for el in root.iter() if el.tag == f"{ns}ProductKey"]
        self.assertTrue(blocks, "нет блока ProductKey — лицензирование должно быть помечено как зона владельца")
        for pk in blocks:
            key = pk.findtext(f"{ns}Key")
            self.assertEqual((key or "").strip(), "", "серийный номер вшивать запрещено (ТЗ §7)")
        self.assertIn("лицензиров", self.text, "нет комментария о лицензировании владельцем")

    def test_tokens_within_known_registry(self):
        found = set(re.findall(r"__([A-Z0-9_]+)__", self.text))
        unknown = {"__" + t + "__" for t in found} - KNOWN_TOKENS
        self.assertEqual(unknown, set(), f"неизвестные токены шаблона: {sorted(unknown)}")
        missing = KNOWN_TOKENS - {"__" + t + "__" for t in found}
        self.assertEqual(missing, set(), f"реестр токенов не использован: {sorted(missing)}")


class TestPins(unittest.TestCase):
    """Канонический источник версий/URL — manifests/pins.yaml (ADR-0006).
    Проверка stdlib-регэкспами: тест обязан идти на чистом python3 без зависимостей."""

    def setUp(self):
        self.text = read(PINS)

    def test_forge_section_present(self):
        self.assertRegex(self.text, r"(?m)^  fido:\s*$", "pins.yaml: нет секции forge.fido")
        self.assertRegex(self.text, r"(?m)^  windows-image:\s*$",
                         "pins.yaml: нет секции forge.windows-image")

    def test_fido_repo_pinned(self):
        self.assertRegex(self.text, r'repo:\s*"pbatard/Fido"',
                         "репозиторий Fido должен быть пиннут в pins.yaml")

    def test_tofu_mode_declared(self):
        # sha256/tag null → первый прогон фиксирует значения (TOFU), код обязан
        # печатать «TOFU-фиксация» (см. TestScriptMarkers).
        self.assertRegex(self.text, r"sha256:\s*null", "пин forge.fido.sha256 должен быть null до первого прогона")
        self.assertRegex(self.text, r"iso_sha256:\s*null", "пин forge.windows-image.iso_sha256 должен быть null до первого прогона")
        self.assertGreaterEqual(self.text.count("pending-first-run"), 2,
                                "fido и windows-image обязаны быть в статусе pending-first-run")


class TestScriptMarkers(unittest.TestCase):
    """Обязательные маркеры конвейера: сборка = реальные команды, не псевдокод."""

    def setUp(self):
        self.build = read(BUILD_PS1)
        self.fetch = read(FETCH_PS1)

    def test_strict_mode_everywhere(self):
        for name, text in (("build.ps1", self.build), ("fetch-fido.ps1", self.fetch),
                           ("forge.ps1", read(FORGE_PS1))):
            self.assertRegex(text, r"\$ErrorActionPreference\s*=\s*'Stop'",
                             f"{name}: нет строгого режима $ErrorActionPreference='Stop'")

    def test_build_oscdimg_double_boot(self):
        for marker in ("oscdimg", "-m", "-o", "-u2", "-udfver102", "-bootdata"):
            self.assertIn(marker, self.build, f"build.ps1: нет маркера {marker}")
        # двойная загрузочная запись BIOS+UEFI: генерируемая строка обязана
        # совпадать с эталоном спеки 03 (сверка генератора аргументов)
        self.assertRegex(self.build, r'2#p0,e,b\$etfsboot#pEF,e,b\$efisys',
                         "-bootdata не совпадает с эталоном спеки 03")
        self.assertIn("Mount-DiskImage", self.build, "extract обязан использовать Mount-DiskImage")
        self.assertIn("Dismount-DiskImage", self.build, "образ обязан отмонтироваться (finally)")

    def test_rendered_autounattend_invariant(self):
        """Тест-гейт спеки 03: рендер шаблона с дефолтными параметрами →
        структурная валидация и инвариант wipe=false в ОТРЕНДЕРЕННОМ XML."""
        text = read(TEMPLATE)
        defaults = {"__LOCALE__": "ru-RU", "__UI_LANG__": "ru-RU",
                    "__TIMEZONE__": "Russian Standard Time", "__KEY_INDEX__": "6"}
        rendered = text
        for token, value in defaults.items():
            rendered = rendered.replace(token, value)  # та же семантика, что в build.ps1
        leftover = re.findall(r"__[A-Z0-9_]+__", rendered)
        self.assertEqual(leftover, [], f"после рендера остались токены: {leftover}")
        root = ET.fromstring(rendered)
        wipes = [el.text for el in root.iter() if el.tag.endswith("WillWipeDisk")]
        self.assertEqual(wipes, ["false"], f"отрендеренный XML: wipe={wipes}")
        for bad in FORBIDDEN_XML:
            self.assertNotIn(bad, rendered, f"рендер внёс {bad}")

    def test_build_command_printed_before_run(self):
        self.assertIn("КОМАНДА", self.build,
                      "аргументная строка oscdimg обязана печататься до исполнения (карта=территория)")

    def test_build_double_wipe_gate(self):
        # Гейт-функция ловит ОБЕ формы wipe-инверсии и вызывается дважды.
        self.assertIn('WillWipeDisk\\s*=\\s*"true"', self.build,
                      "build.ps1: нет проверки запрета WillWipeDisk=true (строковая форма)")
        self.assertIn("<WillWipeDisk>\\s*true\\s*</WillWipeDisk>", self.build,
                      "build.ps1: нет проверки запрета wipe-инверсии (элементная форма)")
        self.assertGreaterEqual(self.build.count("Assert-AutounattendInvariant "), 3,
                                "гейт инварианта должен объявляться и вызываться дважды (render и build)")

    def test_build_contract(self):
        self.assertIn("autounattend.template.xml", self.build, "build.ps1 не ссылается на шаблон")
        self.assertIn("fetch-fido.ps1", self.build, "build.ps1 не вызывает фазу fetch")
        self.assertIn("SHA256SUMS", self.build, "build.ps1 не пишет SHA256SUMS")
        self.assertIn("build-log.txt", self.build, "build.ps1 не пишет лог сырых команд")
        self.assertNotIn("Invoke-WebRequest", self.build,
                         "build.ps1 не должен ничего скачивать — загрузка только в fetch-fido.ps1")

    def test_fetch_pin_driven_no_hardcode(self):
        self.assertIn("pins.yaml", self.fetch, "fetch-fido.ps1 не читает пины")
        self.assertIn("TOFU-фиксация", self.fetch, "нет TOFU-протокола для sha256=null")
        self.assertIn("Get-FileHash", self.fetch, "нет подсчёта SHA256")
        self.assertIn("Invoke-WebRequest", self.fetch, "нет скачивания скрипта/ISO")
        # Хардкод источника запрещён: репозиторий Fido — только из пинов;
        # URL Microsoft в коде не появляется вообще (только через Fido).
        self.assertNotIn("pbatard", self.fetch, "репозиторий Fido захардкожен — берётся из pins.yaml")
        self.assertNotIn("microsoft.com", self.fetch,
                         "прямой URL Microsoft в коде запрещён — ссылка только через Fido")
        # Формат JSON-отчёта (спека 03): поля отчёта присутствуют.
        for field in ("source_url", "iso_path", "sha256", "fido_tag", "fido_sha256", "tofu_fixed"):
            self.assertIn(field, self.fetch, f"в JSON-отчёте нет поля {field}")

    def test_fetch_normalizes_locale_to_fido_language_name(self):
        # Fido матчится по ИМЕНИ языка ($language.Name -match $Lang, исходник Fido),
        # поэтому локаль ru-RU обязана нормализоваться в 'Russian' внутри fetch-fido.
        self.assertIn("ru-ru' = 'Russian'", self.fetch,
                      "нет нормализации локали ru-RU → Russian (имя из официального списка)")
        self.assertIn("$fidoLang", self.fetch, "нормализованное имя не используется в вызове Fido")

    def test_build_passes_locale_to_fetch(self):
        self.assertIn("'-Language', $UiLanguage", self.build,
                      "build.ps1 не передаёт локаль в fetch-fido.ps1")

    def test_dispatcher_contract(self):
        forge = read(FORGE_PS1)
        self.assertIn("build.ps1", forge, "forge.ps1 не диспетчеризует build.ps1")
        self.assertIn("systeminfo", forge, "forge.ps1 не печатает выжимку systeminfo")
        self.assertIn("probe.sh", forge, "forge.ps1 не упоминает probe-подсказку")
        self.assertIn("PROCESSOR_ARCHITECTURE", forge, "forge.ps1 не печатает архитектуру хоста")

    def test_readme_documents_pipeline(self):
        readme = read(README_WIN)
        for marker in ("oscdimg", "pwsh", "ADK", "WillWipeDisk", "fetch", "SHA256SUMS"):
            self.assertIn(marker, readme, f"README.md ветки win: нет {marker}")


@unittest.skipUnless(shutil.which("pwsh"),
                     "pwsh не найден в PATH — parse-проверка .ps1 пропущена "
                     "(на Windows-хосте или после установки PowerShell 7 прогон полный)")
class TestPwshParse(unittest.TestCase):
    """Синтаксическая проверка .ps1 нативным парсером PowerShell (при наличии pwsh)."""

    def parse(self, ps_file: Path):
        ps_path = str(ps_file).replace("'", "''")
        command = (
            "$errs = $null; $toks = $null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{ps_path}', "
            "[ref]$toks, [ref]$errs) | Out-Null; "
            "if ($errs -and $errs.Count -gt 0) { "
            "$errs | ForEach-Object { Write-Output ('{0}:{1}: {2}' -f "
            "$_.Extent.StartLineNumber, $_.Extent.StartColumnNumber, $_.Message) }; exit 1 } "
            "else { Write-Output 'PARSE_OK'; exit 0 }"
        )
        return subprocess.run(
            [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=180,
        )

    def assert_parses(self, ps_file: Path):
        with self.subTest(script=str(ps_file.relative_to(ROOT))):
            proc = self.parse(ps_file)
            self.assertEqual(
                proc.returncode, 0,
                f"{ps_file.name}: ошибки синтаксиса PowerShell:\n{proc.stdout}\n{proc.stderr}",
            )
            self.assertIn("PARSE_OK", proc.stdout)

    def test_build_ps1_parses(self):
        self.assert_parses(BUILD_PS1)

    def test_fetch_fido_ps1_parses(self):
        self.assert_parses(FETCH_PS1)

    def test_forge_ps1_parses(self):
        self.assert_parses(FORGE_PS1)


if __name__ == "__main__":
    unittest.main()
