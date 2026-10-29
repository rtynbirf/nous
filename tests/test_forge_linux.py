"""НОУС · Linux-ветка форжа: инварианты спеки 04 и safe-defaults (тест-гейты).

Гейты: (1) синтаксис bash; (2) каркас и верификатор подключены; (3) только
официальные каналы (https, без посторонних URL); (4) xorriso-флаги гибрида;
(5) preseed: confirm_nooverwrite=true, отсутствие плейнтекст-пароля, реестр
токенов; (6) user-data: autoinstall, lvm, токены реестра; (7) meta-data.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINUX = ROOT / "src" / "forge" / "linux"
BUILD = LINUX / "build.sh"
PRESEED = LINUX / "templates" / "debian12.preseed"
USER_DATA = LINUX / "templates" / "ubuntu-24.04" / "user-data"
META_DATA = LINUX / "templates" / "ubuntu-24.04" / "meta-data"

# Реестр токенов рендера (build.sh фаза RENDER; всё прочее — невалидный токен)
ALLOWED_TOKENS = {"PW_HASH", "USER", "HOSTNAME"}

XORRISO_FLAGS = [
    "-isohybrid-mbr", "-isohybrid-gpt-basdat", "-eltorito-alt-boot",
    "-as", "mkisofs", "-boot-info-table",
]


def tokens_of(text: str) -> set:
    return set(re.findall(r"__([A-Z0-9_]+)__", text))


class TestBuildScript(unittest.TestCase):
    def setUp(self):
        self.assertTrue(BUILD.is_file(), "build.sh отсутствует")
        self.text = BUILD.read_text(encoding="utf-8")

    def test_bash_syntax(self):
        proc = subprocess.run(
            ["bash", "-n", str(BUILD)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, f"bash -n: {proc.stderr}")

    def test_common_skeleton_and_verifier_connected(self):
        self.assertIn("src/lib/common.sh", self.text, "каркас common.sh не подключён")
        self.assertIn("verify-iso.sh", self.text, "верификатор артефакта не вызван")

    def test_only_official_channels_https(self):
        # Идеал: каналы берутся ТОЛЬКО из пинов (URL в коде может не быть вовсе).
        urls = re.findall(r"https?://[^\s\"')]+", self.text)
        for url in urls:
            self.assertTrue(url.startswith("https://"), f"не-https URL: {url}")
        # Хардкод доменов каналов запрещён: источник — только manifests/pins.yaml
        for domain in ("cdimage.debian.org", "releases.ubuntu.com", "deb.debian.org"):
            self.assertNotIn(domain, self.text,
                             f"домен {domain} вшит в код — должен браться из пинов")

    def test_xorriso_hybrid_flags_of_spec(self):
        for flag in XORRISO_FLAGS:
            self.assertIn(flag, self.text, f"нет флага гибрида спеки 04: {flag}")

    def test_sha256sums_gate_present(self):
        self.assertIn("SHA256SUMS", self.text, "гейт контрольных сумм канала отсутствует")
        self.assertIn("iso_sha256", self.text, "TOFU-принуждение пина отсутствует")


class TestPreseed(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PRESEED.is_file(), "debian12.preseed отсутствует")
        self.text = PRESEED.read_text(encoding="utf-8")

    def test_confirm_nooverwrite_true(self):
        self.assertRegex(
            self.text,
            r"partman/confirm_nooverwrite\s+boolean\s+true",
            "инвариант спеки 06: partman/confirm_nooverwrite=true",
        )

    def test_no_plaintext_password(self):
        self.assertNotRegex(
            self.text,
            r"root-password\b(?!-crypted)|password-plain",
            "плейнтекст-пароль запрещён: только root-password-crypted",
        )

    def test_tokens_within_registry(self):
        extra = tokens_of(self.text) - ALLOWED_TOKENS
        self.assertEqual(extra, set(), f"токены вне реестра: {extra}")
        self.assertIn("__PW_HASH__", self.text, "криптохеш обязан быть токеном")


class TestAutoinstall(unittest.TestCase):
    def setUp(self):
        self.assertTrue(USER_DATA.is_file(), "user-data отсутствует")
        self.assertTrue(META_DATA.is_file(), "meta-data отсутствует")
        self.meta = META_DATA.read_text(encoding="utf-8")

    def test_user_data_structure(self):
        import yaml  # pyyaml входит в requirements-dev и CI
        text = USER_DATA.read_text(encoding="utf-8")
        extra = tokens_of(text) - ALLOWED_TOKENS
        self.assertEqual(extra, set(), f"токены вне реестра: {extra}")
        rendered = re.sub(r"__([A-Z0-9_]+)__", "fixture", text)
        data = yaml.safe_load(rendered)
        self.assertEqual(data.get("version"), 1, "autoinstall: version: 1 обязателен")
        self.assertIn("storage", data, "autoinstall: storage обязателен")
        layout = data.get("storage", {}).get("layout", {}).get("name")
        self.assertEqual(layout, "lvm", "инвариант спеки 06: guided LVM")
        ident = data.get("identity", {})
        self.assertTrue(ident.get("crypted-password"), "криптохеш обязателен")
        self.assertNotRegex(
            USER_DATA.read_text(encoding="utf-8"),
            r"plain-?text|passwd: ['\"]\$?[a-z]",
            "плейнтекст-пароль запрещён",
        )

    def test_meta_data_nonempty(self):
        self.assertGreater(len(self.meta.strip()), 10, "meta-data подозрительно пуст")


if __name__ == "__main__":
    unittest.main()
