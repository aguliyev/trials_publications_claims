import runpy
import sys
from importlib import import_module
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, call, patch

from django.apps import apps
from django.test import TestCase as DatabaseTestCase

from core.models import Chunk, Ner, Publication, Trial


NER_FILE = Path(__file__).resolve().parents[3] / "django_app" / "lib" / "ner.py"


class NerTestCase(TestCase):
    def setUp(self):
        self.modules = {
            "gliner": SimpleNamespace(GLiNER=Mock()),
            "flair.data": SimpleNamespace(Sentence=Mock()),
            "flair.models": SimpleNamespace(EntityMentionLinker=Mock()),
            "flair.nn": SimpleNamespace(Classifier=Mock()),
            "openmed": SimpleNamespace(analyze_text=Mock()),
        }

    def test_gliner_returns_normalized_entity_dicts(self):
        model = Mock()
        entities = [{"text": "imatinib", "label": "Drug", "start": 0, "end": 8, "score": 0.9}]
        model.predict_entities.return_value = entities
        gliner = SimpleNamespace(GLiNER=SimpleNamespace(from_pretrained=Mock(return_value=model)))

        with patch.dict(sys.modules, self.modules | {"gliner": gliner}):
            ner = runpy.run_path(str(NER_FILE))
            result = ner["gliner_entities"]("imatinib")

        self.assertEqual(result, [{
            "text": "imatinib", "label": ["Drug"], "start": 0, "end": 8, "score": 0.9,
            "method": ["gliner"], "model_name": ["Ihor/gliner-biomed-large-v1.0"],
        }])
        gliner.GLiNER.from_pretrained.assert_called_once_with(ner["MODELS"]["GLiNER"])
        model.predict_entities.assert_called_once_with(
            "imatinib",
            ["Disease", "Drug", "Drug dosage", "Drug frequency", "Lab test", "Lab test value", "Demographic information"],
            threshold=0.5,
        )

    def test_hunflair2_links_entities_before_returning_normalized_dicts(self):
        span = Mock(text="imatinib", start_position=0, end_position=8)
        span.get_label.return_value = SimpleNamespace(value="Chemical", score=0.9)
        span.get_labels.return_value = [SimpleNamespace(value="MESH:D0001", score=12.5)]
        spans = [span]
        sentence = Mock()
        sentence.get_spans.return_value = spans
        tagger = Mock(label_type="ner")
        predictions = []
        tagger.predict.side_effect = lambda tagged: predictions.append("ner")
        linker = Mock()
        linker.load.side_effect = lambda name: SimpleNamespace(predict=lambda tagged: predictions.append(name))
        modules = {
            "flair.data": SimpleNamespace(Sentence=Mock(return_value=sentence)),
            "flair.models": SimpleNamespace(EntityMentionLinker=linker),
            "flair.nn": SimpleNamespace(Classifier=SimpleNamespace(load=Mock(return_value=tagger))),
        }

        with patch.dict(sys.modules, self.modules | modules):
            ner = runpy.run_path(str(NER_FILE))
            result = ner["hunflair2_entities"]("imatinib")

        self.assertEqual(result, [{
            "text": "imatinib", "label": ["Chemical"], "start": 0, "end": 8, "score": 0.9,
            "method": ["hunflair"], "model_name": ["hunflair2"],
            "links": [{"id": "MESH:D0001", "score": 12.5}],
        }])
        modules["flair.data"].Sentence.assert_called_once_with("imatinib")
        modules["flair.nn"].Classifier.load.assert_called_once_with(ner["MODELS"]["hunflair/Classifier"])
        tagger.predict.assert_called_once_with(sentence)
        self.assertEqual(predictions, ["ner", *ner["MODELS"]["hunflair/Linkers"]])
        self.assertEqual(linker.load.call_count, len(ner["MODELS"]["hunflair/Linkers"]))
        sentence.get_spans.assert_called_once_with("ner")
        span.get_label.assert_called_once_with("ner")
        span.get_labels.assert_called_once_with("link")

    def test_openmed_returns_normalized_entities_for_selected_model(self):
        entities = [SimpleNamespace(text="imatinib", label="DRUG", start=0, end=8, confidence=0.9)]
        analyze_text = Mock(return_value=SimpleNamespace(entities=entities))

        with patch.dict(sys.modules, self.modules | {"openmed": SimpleNamespace(analyze_text=analyze_text)}):
            ner = runpy.run_path(str(NER_FILE))
            for model in ner["MODELS"]["OpenMed"]:
                with self.subTest(model=model):
                    result = ner["openmed_entities"]("imatinib", model)
                    self.assertEqual(result, [{
                        "text": "imatinib", "label": ["DRUG"], "start": 0, "end": 8, "score": 0.9,
                        "method": ["openmed"], "model_name": [model],
                    }])
                    analyze_text.assert_called_with("imatinib", model_name=model)

    def test_openmed_all_entities_merges_predictions_by_span_with_max_score(self):
        first = SimpleNamespace(text="imatinib", start=0, end=8, label="DRUG", confidence=0.9)
        duplicate = SimpleNamespace(text="imatinib", start=0, end=8, label="drug", confidence=0.8)
        other_label = SimpleNamespace(text="imatinib", start=0, end=8, label="DISEASE", confidence=0.95)
        other_position = SimpleNamespace(text="imatinib", start=9, end=17, label="DRUG", confidence=0.6)
        analyze_text = Mock(side_effect=[
            SimpleNamespace(entities=[first]),
            SimpleNamespace(entities=[duplicate, other_label]),
            SimpleNamespace(entities=[other_position]),
            SimpleNamespace(entities=[]),
        ])

        with patch.dict(sys.modules, self.modules | {"openmed": SimpleNamespace(analyze_text=analyze_text)}):
            ner = runpy.run_path(str(NER_FILE))
            result = ner["openmed_all_entities"]("imatinib imatinib")

        self.assertEqual(result, [
            {"text": "imatinib", "start": 0, "end": 8, "label": ["DRUG", "drug", "DISEASE"], "score": 0.95,
             "method": ["openmed"], "model_name": [
                 "OpenMed/OpenMed-NER-DiseaseDetect-PubMed-335M",
                 "OpenMed/OpenMed-NER-PharmaDetect-PubMed-335M",
                 "OpenMed/OpenMed-NER-PharmaDetect-PubMed-335M",
             ]},
            {"text": "imatinib", "start": 9, "end": 17, "label": ["DRUG"], "score": 0.6,
             "method": ["openmed"], "model_name": ["OpenMed/OpenMed-NER-PathologyDetect-PubMed-335M"]},
        ])
        self.assertEqual(analyze_text.call_args_list, [
            call("imatinib imatinib", model_name=model) for model in ner["MODELS"]["OpenMed"]
        ])

    def test_ner_entities_merges_all_methods_by_span_and_preserves_links(self):
        openmed = Mock(return_value=[
            {"text": "imatinib", "start": 0, "end": 8, "score": 0.7,
             "method": ["openmed"], "model_name": ["openmed-a", "openmed-b"], "label": ["DRUG", "drug"]},
            {"text": "disease", "start": 10, "end": 17, "score": 0.5,
             "method": ["openmed"], "model_name": ["openmed-c"], "label": ["DISEASE"]},
        ])
        gliner = Mock(return_value=[
            {"text": "imatinib", "start": 0, "end": 8, "score": 0.95,
             "method": ["gliner"], "model_name": ["gliner-model"], "label": ["Drug"]},
            {"text": "other", "start": 19, "end": 24, "score": 0.3,
             "method": ["gliner"], "model_name": ["gliner-model"], "label": ["Other"]},
        ])
        hunflair = Mock(return_value=[
            {"text": "imatinib", "start": 0, "end": 8, "score": 0.8,
             "method": ["hunflair"], "model_name": ["hunflair2"], "label": ["Chemical"],
             "links": [{"id": "MESH:D0001", "score": 12.5}]},
        ])

        with patch.dict(sys.modules, self.modules):
            ner = runpy.run_path(str(NER_FILE))
        with patch.dict(ner["ner_entities"].__globals__, {
            "openmed_all_entities": openmed, "gliner_entities": gliner, "hunflair2_entities": hunflair,
        }):
            result = ner["ner_entities"]("imatinib disease other")

        self.assertEqual(result, [
            {"text": "imatinib", "start": 0, "end": 8, "score": 0.95,
             "method": ["openmed", "gliner", "hunflair"],
             "model_name": ["openmed-a", "openmed-b", "gliner-model", "hunflair2"],
             "label": ["DRUG", "drug", "Drug", "Chemical"],
             "links": [{"id": "MESH:D0001", "score": 12.5}]},
            {"text": "disease", "start": 10, "end": 17, "score": 0.5,
             "method": ["openmed"], "model_name": ["openmed-c"], "label": ["DISEASE"]},
            {"text": "other", "start": 19, "end": 24, "score": 0.3,
             "method": ["gliner"], "model_name": ["gliner-model"], "label": ["Other"]},
        ])
        openmed.assert_called_once_with("imatinib disease other")
        gliner.assert_called_once_with("imatinib disease other")
        hunflair.assert_called_once_with("imatinib disease other")


class NerPersistenceTestCase(DatabaseTestCase):
    def setUp(self):
        modules = {
            "gliner": SimpleNamespace(GLiNER=Mock()),
            "flair.data": SimpleNamespace(Sentence=Mock()),
            "flair.models": SimpleNamespace(EntityMentionLinker=Mock()),
            "flair.nn": SimpleNamespace(Classifier=Mock()),
            "openmed": SimpleNamespace(analyze_text=Mock()),
        }
        with patch.dict(sys.modules, modules):
            self.ner = runpy.run_path(str(NER_FILE))

    def test_trial_saves_chunk_and_both_titles_and_skips_existing_ner(self):
        trial = Trial.objects.create(nct_id="NCT00000001", title="Brief cancer", official_title="Official cancer")
        chunk = Chunk.objects.create(trial=trial, section="summary", sequ=0, body="Chunk cancer")
        other_chunk = Chunk.objects.create(trial=trial, section="detailed_description", sequ=0, body="More cancer")
        skipped = Trial.objects.create(nct_id="NCT00000002", title="Already processed")
        Ner.objects.create(trial=skipped, text="processed", label=["Disease"], start=8, end=17,
                           score=0.9, method=["gliner"], model_name=["model"])

        def extract(text):
            return [{"text": text, "label": ["Disease"], "start": 0, "end": len(text), "score": 0.9,
                     "method": ["gliner"], "model_name": ["model"]}]

        with patch.dict(self.ner["save_ner_trials"].__globals__, {"ner_entities": extract}):
            self.ner["save_ner_trials"]()
            self.ner["save_ner_trials"]()

        self.assertEqual(list(trial.ners.order_by("id").values_list("text", "chunk_id", "section", "meta")), [
            ("Chunk cancer", chunk.pk, "summary", {}),
            ("More cancer", other_chunk.pk, "detailed_description", {}),
            ("Brief cancer", None, "title", {}),
            ("Official cancer", None, "official_title", {}),
        ])
        self.assertEqual(skipped.ners.count(), 1)

    def test_publication_saves_title_and_chunks_with_json_safe_links(self):
        pub = Publication.objects.create(pmid="1", title="Cancer title")
        chunk = Chunk.objects.create(publication=pub, section="abstract", sequ=0, body="Cancer abstract")

        def extract(text):
            return [{"text": "Cancer", "label": ["DISEASE", "Disease"], "start": 0, "end": 6,
                     "score": 0.95, "method": ["openmed", "hunflair"],
                     "model_name": ["openmed-model", "hunflair2"],
                     "links": [{"id": "MESH:D015464", "score": Decimal("203.84323")}]}]

        with patch.dict(self.ner["save_ner_publications"].__globals__, {"ner_entities": extract}):
            self.ner["save_ner_publications"]()
            self.ner["save_ner_publications"]()

        self.assertEqual(list(pub.ners.order_by("id").values_list("chunk_id", "section", "meta")), [
            (chunk.pk, "abstract", {}), (None, "title", {}),
        ])
        entity = pub.ners.get(chunk=chunk)
        self.assertEqual(entity.label, ["DISEASE", "Disease"])
        self.assertEqual(entity.links, [{"id": "MESH:D015464", "score": 203.84323}])
        self.assertEqual(entity.method, ["openmed", "hunflair"])
        self.assertEqual(entity.model_name, ["openmed-model", "hunflair2"])
        self.assertIsNotNone(entity.created)
        self.assertIsNotNone(entity.modified)

    def test_section_migration_moves_existing_sections_out_of_meta(self):
        pub = Publication.objects.create(pmid="migration", title="Title")
        chunk = Chunk.objects.create(publication=pub, section="abstract", sequ=0, body="Abstract")
        title_ner = Ner.objects.create(publication=pub, meta={"section": "title", "source": "existing"},
                                       text="Title", label=["Disease"], start=0, end=5, score=0.9)
        chunk_ner = Ner.objects.create(publication=pub, chunk=chunk, text="Abstract", label=["Disease"],
                                       start=0, end=8, score=0.9)

        import_module("core.migrations.0011_ner_section").move_ner_sections(apps, None)

        title_ner.refresh_from_db()
        chunk_ner.refresh_from_db()
        self.assertEqual((title_ner.section, title_ner.meta), ("title", {"source": "existing"}))
        self.assertEqual((chunk_ner.section, chunk_ner.meta), ("abstract", {}))
