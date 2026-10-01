from core.models import Intervention, Ner
from lib.entities import upsert_entity
from lib.logs import get_logger, logged
import time

logger = get_logger(__name__)


LABELS = frozenset({"chem", "simple_chemical", "drug", "chemical"})


@logged
def save_ner_interventions():
    pending = Ner.objects.filter(intervention__isnull=True)
    logger.info("Starting intervention linking pending=%s", pending.count())
    started = time.monotonic()
    linked = 0
    for index, ner in enumerate(pending.iterator(), start=1):
        if index % 1000 == 0:
            logger.info("Linking interventions progress=%s linked=%s elapsed_s=%.1f", index, linked, time.monotonic() - started)
        if not LABELS.intersection(str(label).casefold() for label in (ner.label or [])):
            continue
        name = ner.text.strip()[:255]
        if not name:
            logger.warning("Skipping intervention NER with empty text id=%s", ner.pk)
            continue
        mesh = next((link.get("id") for link in (ner.links or [])
                     if isinstance(link, dict) and isinstance(link.get("id"), str)
                     and link["id"].upper().startswith("MESH:")), "")
        intervention = upsert_entity(Intervention, name, mesh)
        if intervention:
            ner.intervention = intervention
            ner.save(update_fields=["intervention", "modified"])
            linked += 1
            logger.debug("Linked intervention ner_id=%s intervention_id=%s", ner.pk, intervention.pk)
            owner = ner.publication or ner.trial
            if owner:
                owner.interventions.add(intervention)
    logger.info("Intervention linking complete linked=%s elapsed_s=%.1f", linked, time.monotonic() - started)
