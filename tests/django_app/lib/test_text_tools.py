import runpy
from pathlib import Path
from unittest import TestCase


TEXT_TOOLS_FILE = Path(__file__).resolve().parents[3] / "django_app" / "lib" / "text_tools.py"


class TextToolsTestCase(TestCase):
    def test_split_ner_text_respects_size_and_overlaps_at_word_boundaries(self):
        split_ner_text = runpy.run_path(str(TEXT_TOOLS_FILE))["split_ner_text"]

        chunks = split_ner_text("Aspirin treats pain. Aspirin reduces fever.", chunk_size=23, chunk_overlap=8)

        self.assertEqual(chunks, ["Aspirin treats pain.", "pain. Aspirin reduces", "reduces fever."])
        self.assertTrue(all(len(chunk) <= 23 for chunk in chunks))

    def test_split_ner_text_handles_empty_and_short_input(self):
        split_ner_text = runpy.run_path(str(TEXT_TOOLS_FILE))["split_ner_text"]

        self.assertEqual(split_ner_text(""), [])
        self.assertEqual(split_ner_text("Aspirin treats pain."), ["Aspirin treats pain."])
