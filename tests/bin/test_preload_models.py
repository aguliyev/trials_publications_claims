import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, call, patch


class PreloadModelsTestCase(TestCase):
    def test_preloads_biomedical_models(self):
        gliner = Mock()
        flair = Mock()
        linker = Mock()
        classifier = Mock()
        spacy = Mock()
        openmed_config = Mock()
        model_loader = Mock()
        snapshot_download = Mock()
        modules = {
            "gliner": SimpleNamespace(GLiNER=gliner),
            "flair.models": SimpleNamespace(PrefixedSequenceTagger=flair, EntityMentionLinker=linker),
            "flair.data": SimpleNamespace(Sentence=Mock()),
            "flair.nn": SimpleNamespace(Classifier=classifier),
            "spacy": spacy,
            "openmed": SimpleNamespace(OpenMedConfig=openmed_config, ModelLoader=model_loader, analyze_text=Mock()),
            "huggingface_hub": SimpleNamespace(snapshot_download=snapshot_download),
        }
        script = Path(__file__).resolve().parents[2] / "bin" / "preload_models.py"

        with patch.dict(sys.modules, modules) as patched_modules:
            models = runpy.run_path(str(Path(__file__).resolve().parents[2] / "django_app" / "lib" / "ner.py"))["MODELS"]
            patched_modules["django_app.lib.ner"] = SimpleNamespace(MODELS=models)
            runpy.run_path(str(script), run_name="__main__")

        gliner.from_pretrained.assert_called_once_with(models["GLiNER"])
        flair.load.assert_called_once_with(models["hunflair/PrefixedSequenceTagger"])
        classifier.load.assert_called_once_with(models["hunflair/Classifier"])
        self.assertEqual(linker.load.call_args_list, [call(model) for model in models["hunflair/Linkers"]])
        self.assertEqual(openmed_config.call_args_list, [call(cache_dir="/models/openmed")] * len(models["OpenMed"]))
        self.assertEqual(model_loader.call_args_list, [call(openmed_config.return_value)] * len(models["OpenMed"]))
        self.assertEqual(model_loader.return_value.load_model.call_args_list, [call(model) for model in models["OpenMed"]])
        # spacy.load.assert_called_once_with("en_ner_bc5cdr_md")
