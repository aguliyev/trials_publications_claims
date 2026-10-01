from core.models import Disease, Ner
from lib.entities import upsert_entity
from lib.logs import get_logger, logged
import time

logger = get_logger(__name__)


LABELS = frozenset({"disease", "cancer"})


@logged
def save_ner_diseases():
    pending = Ner.objects.filter(disease__isnull=True)
    logger.info("Starting disease linking pending=%s", pending.count())
    started = time.monotonic()
    linked = 0
    for index, ner in enumerate(pending.iterator(), start=1):
        if index % 1000 == 0:
            logger.info("Linking diseases progress=%s linked=%s elapsed_s=%.1f", index, linked, time.monotonic() - started)
        if not LABELS.intersection(str(label).casefold() for label in (ner.label or [])):
            continue
        name = ner.text.strip()[:255]
        if not name:
            logger.warning("Skipping disease NER with empty text id=%s", ner.pk)
            continue
        mesh = next((link.get("id") for link in (ner.links or [])
                     if isinstance(link, dict) and isinstance(link.get("id"), str)
                     and link["id"].upper().startswith("MESH:")), "")
        disease = upsert_entity(Disease, name, mesh)
        if disease:
            ner.disease = disease
            ner.save(update_fields=["disease", "modified"])
            linked += 1
            logger.debug("Linked disease ner_id=%s disease_id=%s", ner.pk, disease.pk)
            owner = ner.publication or ner.trial
            if owner:
                owner.diseases.add(disease)
    logger.info("Disease linking complete linked=%s elapsed_s=%.1f", linked, time.monotonic() - started)
