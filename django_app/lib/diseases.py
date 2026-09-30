from django.db import IntegrityError
from core.models import Disease, Ner


LABELS = frozenset({"disease", "cancer"})


def save_ner_diseases():
    for ner in Ner.objects.filter(disease__isnull=True).iterator():
        if not LABELS.intersection(str(label).casefold() for label in (ner.label or [])):
            continue
        name = ner.text.strip()[:255]
        if not name:
            continue
        mesh = next((link.get("id") for link in (ner.links or [])
                     if isinstance(link, dict) and isinstance(link.get("id"), str)
                     and link["id"].upper().startswith("MESH:")), "")
        disease = Disease.objects.filter(mesh__iexact=mesh).first() if mesh else None
        if disease is None:
            disease = Disease.objects.filter(name__iexact=name).first()
        if disease is None:
            try:
                disease = Disease.objects.create(name=name, mesh=mesh)
            except IntegrityError:
                disease = Disease.objects.filter(name__iexact=name).first()
        elif mesh and not disease.mesh:
            disease.mesh = mesh
            disease.save(update_fields=["mesh", "modified"])
        if disease:
            ner.disease = disease
            ner.save(update_fields=["disease", "modified"])
            owner = ner.publication or ner.trial
            if owner:
                owner.diseases.add(disease)
