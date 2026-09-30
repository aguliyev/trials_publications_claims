from django.db import IntegrityError
from core.models import Intervention, Ner
from lib.logs import get_logger, logged

logger = get_logger(__name__)


LABELS = frozenset({"chem", "simple_chemical", "drug", "chemical"})


@logged
def save_ner_interventions():
    linked = 0
    for ner in Ner.objects.filter(intervention__isnull=True).iterator():
        if not LABELS.intersection(str(label).casefold() for label in (ner.label or [])):
            continue
        name = ner.text.strip()[:255]
        if not name:
            logger.warning("Skipping intervention NER with empty text id=%s", ner.pk)
            continue
        mesh = next((link.get("id") for link in (ner.links or [])
                     if isinstance(link, dict) and isinstance(link.get("id"), str)
                     and link["id"].upper().startswith("MESH:")), "")
        intervention = Intervention.objects.filter(mesh__iexact=mesh).first() if mesh else None
        if intervention is None:
            intervention = Intervention.objects.filter(name__iexact=name).first()
        if intervention is None:
            try:
                logger.debug("Creating intervention for ner_id=%s", ner.pk)
                intervention = Intervention.objects.create(name=name, mesh=mesh)
            except IntegrityError:
                logger.warning("Intervention creation raced ner_id=%s; looking up existing record", ner.pk)
                intervention = Intervention.objects.filter(name__iexact=name).first()
        elif mesh and not intervention.mesh:
            intervention.mesh = mesh
            intervention.save(update_fields=["mesh", "modified"])
        if intervention:
            ner.intervention = intervention
            ner.save(update_fields=["intervention", "modified"])
            linked += 1
            logger.debug("Linked intervention ner_id=%s intervention_id=%s", ner.pk, intervention.pk)
            owner = ner.publication or ner.trial
            if owner:
                owner.interventions.add(intervention)
    logger.info("Intervention linking complete linked=%s", linked)
