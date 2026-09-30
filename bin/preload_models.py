from gliner import GLiNER
from flair.models import EntityMentionLinker, PrefixedSequenceTagger
import spacy
from flair.data import Sentence
from flair.nn import Classifier
# from huggingface_hub import snapshot_download
from openmed import ModelLoader, OpenMedConfig
from django_app.lib.ner import MODELS


GLiNER.from_pretrained(MODELS["GLiNER"])
PrefixedSequenceTagger.load(MODELS["hunflair/PrefixedSequenceTagger"])
Classifier.load(MODELS["hunflair/Classifier"])
for model in MODELS["hunflair/Linkers"]:
    EntityMentionLinker.load(model)
for model in MODELS["OpenMed"]:
    ModelLoader(OpenMedConfig(cache_dir="/models/openmed")).load_model(model)
# spacy.load("en_ner_bc5cdr_md")
