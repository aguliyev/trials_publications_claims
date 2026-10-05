"""Shared matching for diseases and interventions from source records and NER."""

from django.db import models

def upsert_entity(model: type[models.Model], name: str, mesh: str = "") -> models.Model | None:
    entity = model.objects.filter(mesh__iexact=mesh).first() if mesh else None
    if entity is None:
        entity = model.objects.filter(name__iexact=name).first()
    if entity is None:
        entity, _ = model.objects.get_or_create(name=name, defaults={"mesh": mesh})
    elif mesh and not entity.mesh:
        entity.mesh = mesh
        entity.save(update_fields=["mesh", "modified"])
    return entity


def mesh_from_uid(uid: object) -> str:
    uid = str(uid).strip().upper().removeprefix("MESH:")
    return f"MESH:{uid}" if uid[:1] in ("C", "D") and uid[1:].isdigit() else ""
