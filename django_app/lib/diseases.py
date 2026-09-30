from django.db import IntegrityError
from core.models import Disease, Ner
from lib.logs import get_logger, logged

logger = get_logger(__name__)


LABELS = frozenset({"disease", "cancer"})


@logged
def save_ner_diseases():
    linked = 0
    for ner in Ner.objects.filter(disease__isnull=True).iterator():
        if not LABELS.intersection(str(label).casefold() for label in (ner.label or [])):
            continue
        name = ner.text.strip()[:255]
        if not name:
            logger.warning("Skipping disease NER with empty text id=%s", ner.pk)
            continue
        mesh = next((link.get("id") for link in (ner.links or [])
                     if isinstance(link, dict) and isinstance(link.get("id"), str)
                     and link["id"].upper().startswith("MESH:")), "")
        disease = Disease.objects.filter(mesh__iexact=mesh).first() if mesh else None
        if disease is None:
            disease = Disease.objects.filter(name__iexact=name).first()
        if disease is None:
            try:
                logger.debug("Creating disease for ner_id=%s", ner.pk)
                disease = Disease.objects.create(name=name, mesh=mesh)
            except IntegrityError:
                logger.warning("Disease creation raced ner_id=%s; looking up existing record", ner.pk)
                disease = Disease.objects.filter(name__iexact=name).first()
        elif mesh and not disease.mesh:
            disease.mesh = mesh
            disease.save(update_fields=["mesh", "modified"])
        if disease:
            ner.disease = disease
            ner.save(update_fields=["disease", "modified"])
            linked += 1
            logger.debug("Linked disease ner_id=%s disease_id=%s", ner.pk, disease.pk)
            owner = ner.publication or ner.trial
            if owner:
                owner.diseases.add(disease)
    logger.info("Disease linking complete linked=%s", linked)
