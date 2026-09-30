from functools import cache

from flair.data import Sentence
from flair.models import EntityMentionLinker
from flair.nn import Classifier
from gliner import GLiNER
from openmed import analyze_text
from lib.text_tools import PUBLICATION_FIELDS_NOT_TO_CHUNK, TRIAL_FIELDS_NOT_TO_CHUNK
from lib.logs import get_logger, logged

logger = get_logger(__name__)

MODELS = {
    "GLiNER": "Ihor/gliner-biomed-large-v1.0",
    "hunflair/PrefixedSequenceTagger": "hunflair/hunflair2-ner",
    "hunflair/Classifier": "hunflair2",
    "hunflair/Linkers": [
        "disease-linker",
        # "chemical-linker",
        # "gene-linker",
    ],
    "OpenMed": [
        "OpenMed/OpenMed-NER-DiseaseDetect-PubMed-335M",
        "OpenMed/OpenMed-NER-PharmaDetect-PubMed-335M",
        "OpenMed/OpenMed-NER-PathologyDetect-PubMed-335M",
        "OpenMed/OpenMed-NER-OncologyDetect-PubMed-335M",
    ],
}


@cache
@logged
def _gliner_model():
    logger.debug("Loading GLiNER model")
    return GLiNER.from_pretrained(MODELS["GLiNER"])


@logged
def gliner_entities(sentence: str) -> list:
    labels = ["Disease", "Drug", "Drug dosage", "Drug frequency", "Lab test", "Lab test value", "Demographic information"]
    logger.debug("Predicting GLiNER entities text_length=%s", len(sentence))
    result = [
        {"text": entity["text"], "label": [entity["label"]], "start": entity["start"],
         "end": entity["end"], "score": entity["score"],
         "method": ["gliner"], "model_name": [MODELS["GLiNER"]]}
        for entity in _gliner_model().predict_entities(sentence, labels, threshold=0.5)
    ]
    logger.debug("GLiNER prediction complete entities=%s", len(result))
    return result


@cache
@logged
def _hunflair2_model():
    logger.debug("Loading HunFlair classifier")
    return Classifier.load(MODELS["hunflair/Classifier"])


@cache
@logged
def _hunflair2_linkers():
    logger.debug("Loading HunFlair linkers count=%s", len(MODELS["hunflair/Linkers"]))
    return [EntityMentionLinker.load(model) for model in MODELS["hunflair/Linkers"]]


@logged
def hunflair2_entities(sentence: str) -> list:
    tagged = Sentence(sentence)
    tagger = _hunflair2_model()
    logger.debug("Predicting HunFlair entities text_length=%s", len(sentence))
    tagger.predict(tagged)
    for linker in _hunflair2_linkers():
        linker.predict(tagged)
    logger.debug("HunFlair prediction complete")
    entities = []
    for span in tagged.get_spans(tagger.label_type):
        label = span.get_label(tagger.label_type)
        entities.append({
            "text": span.text,
            "label": [label.value],
            "start": span.start_position,
            "end": span.end_position,
            "score": label.score,
            "method": ["hunflair"],
            "model_name": [MODELS["hunflair/Classifier"]],
            "links": [{"id": link.value, "score": link.score} for link in span.get_labels("link")],
        })
    return entities


@logged
def openmed_entities(sentence: str, model: str) -> list:
    logger.debug("Analyzing OpenMed text model=%s text_length=%s", model, len(sentence))
    result = [
        {"text": entity.text, "label": [entity.label], "start": entity.start,
         "end": entity.end, "score": entity.confidence, "method": ["openmed"], "model_name": [model]}
        for entity in analyze_text(sentence, model_name=model).entities
    ]
    logger.debug("OpenMed analysis complete model=%s entities=%s", model, len(result))
    return result


@logged
def _merge_entities(groups) -> list:
    entities = {}
    for group in groups:
        for entity in group:
            key = (entity["start"], entity["end"])
            if key in entities:
                merged = entities[key]
                for method in entity["method"]:
                    if method not in merged["method"]:
                        merged["method"].append(method)
                merged["model_name"].extend(entity["model_name"])
                merged["label"].extend(entity["label"])
                merged["score"] = max(merged["score"], entity["score"])
                if "links" in entity:
                    merged.setdefault("links", []).extend(entity["links"])
            else:
                entities[key] = entity
    return list(entities.values())


@logged
def openmed_all_entities(sentence: str) -> list:
    return _merge_entities(openmed_entities(sentence, model) for model in MODELS["OpenMed"])


def ner_entities(sentence: str) -> list:
    logger.debug("ner_entities called args=%s kwargs={}", [f"str(len={len(sentence)})"])
    try:
        result = _merge_entities((
            openmed_all_entities(sentence), gliner_entities(sentence), hunflair2_entities(sentence),
        ))
    except Exception as exc:
        logger.error("ner_entities failed error_type=%s", type(exc).__name__)
        raise
    logger.debug("ner_entities returned list(len=%s)", len(result))
    return result


@logged
def _save_ner(source, owner: str, title_fields: tuple[str, ...]):
    from core.models import Ner

    texts = [(chunk.body, chunk, chunk.section) for chunk in source.chunks.all()]
    texts.extend((getattr(source, field), None, field) for field in title_fields)
    records = []
    for text, chunk, section in texts:
        if not text:
            continue
        for entity in ner_entities(text):
            links = [{**link, "score": float(link["score"])} for link in entity.get("links", [])]
            records.append(Ner(**{**entity, "links": links, "chunk": chunk, "section": section, owner: source}))
    logger.debug("Saving NER records owner=%s id=%s count=%s", owner, source.pk, len(records))
    saved = Ner.objects.bulk_create(records)
    logger.debug("Saved NER records owner=%s id=%s count=%s", owner, source.pk, len(saved))
    return saved


def save_ner_trials():
    from core.models import Trial

    logger.debug("save_ner_trials called args=[] kwargs={}")
    try:
        for trial in Trial.objects.filter(ners__isnull=True).prefetch_related("chunks"):
            _save_ner(trial, "trial", TRIAL_FIELDS_NOT_TO_CHUNK)
    except Exception as exc:
        logger.error("save_ner_trials failed error_type=%s", type(exc).__name__)
        raise
    logger.debug("save_ner_trials returned NoneType")


def save_ner_publications():
    from core.models import Publication

    logger.debug("save_ner_publications called args=[] kwargs={}")
    try:
        for publication in Publication.objects.filter(ners__isnull=True).prefetch_related("chunks"):
            _save_ner(publication, "publication", PUBLICATION_FIELDS_NOT_TO_CHUNK)
    except Exception as exc:
        logger.error("save_ner_publications failed error_type=%s", type(exc).__name__)
        raise
    logger.debug("save_ner_publications returned NoneType")
