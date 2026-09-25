"""Tests for the FR/EN string table.

A key that doesn't exist fails silently: Jinja renders it as an empty string
and the page's JS hands `undefined` to a DOM property, which surfaces as the
literal "undefined". Parity and references are asserted here instead.
"""

import re
import unittest
from pathlib import Path

from i18n import DEFAULT_LANG, SUPPORTED, TRANSLATIONS

ROOT = Path(__file__).resolve().parent.parent


def referenced_keys():
    """Keys the page asks for, as {key: the file that first asks for it}.

    Only static `I18N.key` / `t.key` access is seen, which is what lets the
    unused-key check below be exhaustive.
    """
    sources = [(path, r"\bI18N\.(\w+)") for path in sorted((ROOT / "static").glob("*.js"))]
    sources += [(path, r"\bt\.(\w+)") for path in sorted((ROOT / "templates").glob("*.html"))]
    found = {}
    for path, pattern in sources:
        for key in re.findall(pattern, path.read_text(encoding="utf-8")):
            found.setdefault(key, path.name)
    return found


class LanguageTableTest(unittest.TestCase):
    def test_every_supported_language_has_a_table(self):
        self.assertEqual(sorted(TRANSLATIONS), sorted(SUPPORTED))
        self.assertIn(DEFAULT_LANG, SUPPORTED)

    def test_the_languages_share_the_same_keys(self):
        reference = sorted(TRANSLATIONS[DEFAULT_LANG])
        for lang in SUPPORTED:
            with self.subTest(lang=lang):
                self.assertEqual(sorted(TRANSLATIONS[lang]), reference)

    def test_no_string_is_left_empty(self):
        for lang, strings in TRANSLATIONS.items():
            blank = sorted(key for key, value in strings.items() if not value.strip())
            self.assertEqual(blank, [], f"empty {lang} string(s)")


class ReferencedKeysTest(unittest.TestCase):
    def test_every_key_the_page_reads_is_translated(self):
        for lang, strings in TRANSLATIONS.items():
            missing = {key: where for key, where in referenced_keys().items() if key not in strings}
            with self.subTest(lang=lang):
                self.assertEqual(missing, {}, f"untranslated in {lang}")

    def test_no_key_goes_unread(self):
        unused = sorted(set(TRANSLATIONS[DEFAULT_LANG]) - set(referenced_keys()))
        self.assertEqual(unused, [], "translated but never displayed")


if __name__ == "__main__":
    unittest.main()
