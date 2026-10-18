import os
import shutil
import tempfile
import unittest

from scripts import embed_covers, embed_lyrics


class LiteralBracketPathTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.album = os.path.join(self.root, "MTV Unplugged [Live]")
        os.mkdir(self.album)
        self.track = os.path.join(self.album, "01 Intro.mp3")
        with open(self.track, "wb"):
            pass

    def test_covers_takes_existing_bracket_folder_literally(self):
        self.assertEqual(list(embed_covers.album_folders([self.album])), [(self.album, [self.track])])

    def test_lyrics_takes_existing_bracket_folder_literally(self):
        self.assertEqual(embed_lyrics.resolve_targets([self.album]), ([self.album], []))

    def test_lyrics_still_expands_wildcards(self):
        self.assertEqual(embed_lyrics.resolve_targets([os.path.join(self.root, "MTV*")]), ([self.album], []))

    def test_lyrics_reports_unmatched_wildcard(self):
        pattern = os.path.join(self.root, "Nope*")
        self.assertEqual(embed_lyrics.resolve_targets([pattern]), ([], [pattern]))


if __name__ == "__main__":
    unittest.main()
