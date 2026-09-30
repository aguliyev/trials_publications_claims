from core.models import Intervention, Ner


LABELS = frozenset({"chem", "simple_chemical", "drug", "chemical"})


def save_ner_interventions():
    for ner in Ner.objects.filter(intervention__isnull=True).iterator():
        if not LABELS.intersection(str(label).casefold() for label in (ner.label or [])):
            continue
        name = ner.text.strip()
        if not name:
            continue
        mesh = next((link.get("id") for link in (ner.links or [])
                     if isinstance(link, dict) and isinstance(link.get("id"), str)
                     and link["id"].upper().startswith("MESH:")), "")
        intervention = Intervention.objects.filter(mesh__iexact=mesh).first() if mesh else None
        if intervention is None:
            intervention = Intervention.objects.filter(name__iexact=name).first()
        if intervention is None:
            intervention = Intervention.objects.create(name=name, mesh=mesh)
        elif mesh and not intervention.mesh:
            intervention.mesh = mesh
            intervention.save(update_fields=["mesh", "modified"])
        ner.intervention = intervention
        ner.save(update_fields=["intervention", "modified"])
        owner = ner.publication or ner.trial
        owner.interventions.add(intervention)
