import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import Chunk, Publication, Trial


TEXT_TOOLS_FILE = Path(__file__).resolve().parents[3] / "django_app" / "lib" / "text_tools.py"


class ChunkTestCase(TestCase):
    def setUp(self):
        tools = runpy.run_path(str(TEXT_TOOLS_FILE))
        self.save_publication_chunks = tools["save_publication_chunks"]
        self.save_trial_chunks = tools["save_trial_chunks"]

    def _load_upserts(self):
        lib = ModuleType("lib")
        lib.__path__ = [str(TEXT_TOOLS_FILE.parent)]
        with patch.dict(sys.modules, {
            "lib": lib,
            "metapub": SimpleNamespace(PubMedFetcher=Mock()),
            "httpx": SimpleNamespace(get=Mock()),
        }):
            publication = runpy.run_path(str(TEXT_TOOLS_FILE.parent / "pubmed.py"))["fetch_and_upsert_publication"]
            trial = runpy.run_path(str(TEXT_TOOLS_FILE.parent / "clinical_trials.py"))["fetch_and_upsert_trial"]
        return publication, trial

    def test_chunk_has_exactly_one_owner(self):
        pub = Publication.objects.create(pmid="1", title="Article")
        trial = Trial.objects.create(nct_id="NCT00000001", title="Study")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Chunk.objects.create(body="orphan", section="abstract", sequ=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Chunk.objects.create(body="ambiguous", section="abstract", sequ=0, publication=pub, trial=trial)

    def test_publication_chunks_replace_old_abstract_after_update(self):
        pub = Publication.objects.create(pmid="1", title="Article", abstract="Aspirin treats pain. Aspirin reduces fever.")
        other = Publication.objects.create(pmid="2", title="Other")
        Chunk.objects.create(publication=other, section="abstract", sequ=0, body="Keep")

        self.save_publication_chunks(pub, chunk_size=23, chunk_overlap=8)
        self.assertEqual(list(pub.chunks.values_list("section", "sequ", "body").order_by("sequ")), [
            ("abstract", 0, "Aspirin treats pain."),
            ("abstract", 1, "pain. Aspirin reduces"),
            ("abstract", 2, "reduces fever."),
        ])
        self.assertIsNotNone(pub.chunks.first().created)
        self.assertEqual(pub.chunks.first().meta, {})

        pub.abstract = "New abstract"
        pub.save()
        self.save_publication_chunks(pub)
        self.assertEqual(list(pub.chunks.values_list("section", "sequ", "body")), [
            ("abstract", 0, "New abstract"),
        ])
        self.assertEqual(other.chunks.get().body, "Keep")

        pub.abstract = ""
        pub.save()
        self.save_publication_chunks(pub)
        self.assertFalse(pub.chunks.exists())

    def test_trial_chunks_cover_each_section_and_clear_removed_fields(self):
        trial = Trial.objects.create(
            nct_id="NCT00000001", title="Study", summary="Summary",
            detailed_description="Detailed text", eligibility_criteria="Eligible adults",
        )
        self.save_trial_chunks(trial)
        self.assertEqual(set(trial.chunks.values_list("section", "sequ", "body")), {
            ("summary", 0, "Summary"),
            ("detailed_description", 0, "Detailed text"),
            ("eligibility_criteria", 0, "Eligible adults"),
        })

        trial.summary = ""
        trial.detailed_description = "Updated"
        trial.save()
        self.save_trial_chunks(trial)
        self.assertEqual(set(trial.chunks.values_list("section", "sequ", "body")), {
            ("detailed_description", 0, "Updated"),
            ("eligibility_criteria", 0, "Eligible adults"),
        })

    def test_publication_upsert_replaces_chunks_when_abstract_changes_or_disappears(self):
        upsert_publication, _ = self._load_upserts()
        article = {"pmid": "1", "title": "Article", "abstract": "Original abstract"}

        pub = upsert_publication(article, link_entities=False)
        old_chunk = pub.chunks.get()
        self.assertEqual((old_chunk.section, old_chunk.sequ, old_chunk.body), ("abstract", 0, "Original abstract"))

        article["abstract"] = "Updated abstract"
        upsert_publication(article, link_entities=False)
        self.assertEqual(list(pub.chunks.values_list("section", "sequ", "body")), [
            ("abstract", 0, "Updated abstract"),
        ])
        self.assertFalse(pub.chunks.filter(pk=old_chunk.pk).exists())

        article["abstract"] = ""
        upsert_publication(article, link_entities=False)
        self.assertFalse(pub.chunks.exists())

    def test_trial_upsert_replaces_chunks_for_all_sections(self):
        _, upsert_trial = self._load_upserts()
        study = {"protocolSection": {
            "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Study"},
            "descriptionModule": {"briefSummary": "Summary", "detailedDescription": "Details"},
            "eligibilityModule": {"eligibilityCriteria": "Eligible adults"},
        }}

        trial = upsert_trial(study, link_entities=False)
        self.assertEqual(set(trial.chunks.values_list("section", "sequ", "body")), {
            ("summary", 0, "Summary"),
            ("detailed_description", 0, "Details"),
            ("eligibility_criteria", 0, "Eligible adults"),
        })

        study["protocolSection"]["descriptionModule"] = {"briefSummary": "Revised"}
        upsert_trial(study, link_entities=False)
        self.assertEqual(set(trial.chunks.values_list("section", "sequ", "body")), {
            ("summary", 0, "Revised"),
            ("eligibility_criteria", 0, "Eligible adults"),
        })
