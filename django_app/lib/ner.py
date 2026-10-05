from __future__ import annotations

from functools import cache

import time
from collections.abc import Iterable
from typing import Any, Literal, TYPE_CHECKING

from django.db.models import QuerySet

from flair.data import Sentence
from flair.models import EntityMentionLinker
from flair.nn import Classifier
from gliner import GLiNER
from openmed import analyze_text
from lib.text_tools import PUBLICATION_FIELDS_NOT_TO_CHUNK, TRIAL_FIELDS_NOT_TO_CHUNK
from lib.logs import get_logger, logged

if TYPE_CHECKING:
    from core.models import Ner, Publication, Trial

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
def _gliner_model() -> GLiNER:
    logger.info("Loading GLiNER model name=%s", MODELS["GLiNER"])
    started = time.monotonic()
    model = GLiNER.from_pretrained(MODELS["GLiNER"])
    logger.info("Loaded GLiNER model elapsed_s=%.1f", time.monotonic() - started)
    return model


@logged
def gliner_entities(sentence: str) -> list[dict[str, Any]]:
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
def _hunflair2_model() -> Classifier:
    logger.info("Loading HunFlair classifier name=%s", MODELS["hunflair/Classifier"])
    started = time.monotonic()
    model = Classifier.load(MODELS["hunflair/Classifier"])
    logger.info("Loaded HunFlair classifier elapsed_s=%.1f", time.monotonic() - started)
    return model


@cache
@logged
def _hunflair2_linkers() -> list[EntityMentionLinker]:
    logger.info("Loading HunFlair linkers count=%s", len(MODELS["hunflair/Linkers"]))
    started = time.monotonic()
    linkers = [EntityMentionLinker.load(model) for model in MODELS["hunflair/Linkers"]]
    logger.info("Loaded HunFlair linkers elapsed_s=%.1f", time.monotonic() - started)
    return linkers


@logged
def hunflair2_entities(sentence: str) -> list[dict[str, Any]]:
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
def openmed_entities(sentence: str, model: str) -> list[dict[str, Any]]:
    logger.debug("Analyzing OpenMed text model=%s text_length=%s", model, len(sentence))
    result = [
        {"text": entity.text, "label": [entity.label], "start": entity.start,
         "end": entity.end, "score": entity.confidence, "method": ["openmed"], "model_name": [model]}
        for entity in analyze_text(sentence, model_name=model).entities
    ]
    logger.debug("OpenMed analysis complete model=%s entities=%s", model, len(result))
    return result


@logged
def _merge_entities(groups: Iterable[Iterable[dict[str, Any]]]) -> list[dict[str, Any]]:
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
def openmed_all_entities(sentence: str) -> list[dict[str, Any]]:
    return _merge_entities(openmed_entities(sentence, model) for model in MODELS["OpenMed"])


def ner_entities(sentence: str) -> list[dict[str, Any]]:
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
def _save_ner(
    source: Publication | Trial,
    owner: Literal["publication", "trial"],
    title_fields: tuple[str, ...],
) -> list[Ner]:
    from core.models import Ner

    texts = [(chunk.body, chunk, chunk.section) for chunk in source.chunks.all()]
    texts.extend((getattr(source, field), None, field) for field in title_fields)
    records = []
    logger.info("Extracting NER owner=%s id=%s texts=%s", owner, source.pk, len(texts))
    started = time.monotonic()
    for text, chunk, section in texts:
        if not text:
            continue
        for entity in ner_entities(text):
            links = [{**link, "score": float(link["score"])} for link in entity.get("links", [])]
            records.append(Ner(**{**entity, "links": links, "chunk": chunk, "section": section, owner: source}))
    logger.info("NER extraction done owner=%s id=%s entities=%s elapsed_s=%.1f",
                owner, source.pk, len(records), time.monotonic() - started)
    saved = Ner.objects.bulk_create(records)
    logger.info("Saved NER records owner=%s id=%s count=%s", owner, source.pk, len(saved))
    return saved


def _save_ner_sources(
    queryset: QuerySet[Any],
    owner: Literal["publication", "trial"],
    title_fields: tuple[str, ...],
) -> None:
    total = queryset.count()
    logger.info("Starting NER owner=%s pending=%s", owner, total)
    started = time.monotonic()
    saved_total = 0
    for index, source in enumerate(queryset, start=1):
        logger.info("Processing NER owner=%s id=%s progress=%s/%s", owner, source.pk, index, total)
        saved_total += len(_save_ner(source, owner, title_fields) or [])
    logger.info("NER complete owner=%s processed=%s saved=%s elapsed_s=%.1f",
                owner, total, saved_total, time.monotonic() - started)


def save_ner_trials() -> None:
    from core.models import Trial

    logger.debug("save_ner_trials called args=[] kwargs={}")
    try:
        _save_ner_sources(
            Trial.objects.filter(ners__isnull=True).prefetch_related("chunks"), "trial", TRIAL_FIELDS_NOT_TO_CHUNK)
    except Exception as exc:
        logger.error("save_ner_trials failed error_type=%s", type(exc).__name__)
        raise
    logger.debug("save_ner_trials returned NoneType")


def save_ner_publications() -> None:
    from core.models import Publication

    logger.debug("save_ner_publications called args=[] kwargs={}")
    try:
        _save_ner_sources(
            Publication.objects.filter(ners__isnull=True).prefetch_related("chunks"),
            "publication", PUBLICATION_FIELDS_NOT_TO_CHUNK)
    except Exception as exc:
        logger.error("save_ner_publications failed error_type=%s", type(exc).__name__)
        raise
    logger.debug("save_ner_publications returned NoneType")
