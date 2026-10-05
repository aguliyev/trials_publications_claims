"""Helpers for preserving immutable snapshots of reviewed claims."""

from typing import Any

from rest_framework.exceptions import ValidationError

from .models import Claim, ClaimTrails, sanitize_json_payload


def _concrete_fields(instance: Any) -> dict[str, Any]:
    return {
        field.name: sanitize_json_payload(field.value_from_object(instance))
        for field in instance._meta.concrete_fields
    }


def snapshot_claim(claim: Claim) -> dict[str, Any]:
    ners = list(claim.ners.all().order_by('pk'))
    diseases = list(claim.diseases.all().order_by('pk'))
    interventions = list(claim.interventions.all().order_by('pk'))
    genetics = list(claim.genetics.all().order_by('pk'))
    claim_data = _concrete_fields(claim)
    claim_data.update({
        'ners': [row.pk for row in ners],
        'diseases': [row.pk for row in diseases],
        'interventions': [row.pk for row in interventions],
        'genetics': [row.pk for row in genetics],
    })
    return {
        'claim': claim_data,
        'ners': [_concrete_fields(row) for row in ners],
        'diseases': [_concrete_fields(row) for row in diseases],
        'interventions': [_concrete_fields(row) for row in interventions],
        'genetics': [_concrete_fields(row) for row in genetics],
    }


def create_claim_trail(claim: Claim, status_from: str) -> ClaimTrails:
    if not claim.trial_id and not claim.publication_id:
        raise ValidationError('A reviewed claim must belong to a trial or publication.')
    meta = snapshot_claim(claim)
    return ClaimTrails.objects.create(
        trial_id=claim.trial_id,
        publication_id=claim.publication_id,
        notes=claim.notes,
        status_from=status_from,
        new_status=claim.status,
        diseases=list(meta['claim']['diseases']),
        interventions=list(meta['claim']['interventions']),
        genetics=list(meta['claim']['genetics']),
        meta=meta,
    )
