"""Disposable local fixture for the workspace browser check.

Run only against a throwaway local database; never invoke from production startup::

    ./bin/manage shell -c 'from tests.browser.seed import seed; seed()'
"""

from core.models import (
    Chunk,
    Claim,
    Disease,
    Intervention,
    Judgement,
    Ner,
    Publication,
    Trial,
)

TOTAL_CLAIMS = 26


def seed():
    trial, _ = Trial.objects.get_or_create(
        nct_id='NCT09990001',
        defaults={'title': 'UI-SMOKE lung trial', 'status': 'Recruiting', 'phase': 'Phase 2'},
    )
    publication, _ = Publication.objects.get_or_create(
        pmid='UI-SMOKE-9001',
        defaults={'title': 'UI-SMOKE paper', 'journal': 'UI-SMOKE Journal', 'year': 2025},
    )
    trial.publication_trials.get_or_create(
        publication=publication, relation='RELATED',
        defaults={},
    )
    disease, _ = Disease.objects.get_or_create(name='UI-SMOKE Disease')
    intervention, _ = Intervention.objects.get_or_create(name='UI-SMOKE Intervention')
    chunk, _ = Chunk.objects.get_or_create(
        trial=trial, section='summary', sequ=0,
        defaults={'body': 'UI-SMOKE chunk body text.'},
    )
    chunk_claim, _ = Claim.objects.get_or_create(
        section='summary', claim_type='ui_smoke_chunk', trial=trial, chunk=chunk,
        defaults={'evidence': 'UI-SMOKE chunk evidence', 'status': 'pending'},
    )
    chunk_claim.diseases.add(disease)
    chunk_claim.interventions.add(intervention)
    if not chunk_claim.judgements.exists():
        Judgement.objects.create(
            claim=chunk_claim, method='ui-smoke', score=0.9, meta={'verdict': 'supports'})
    if not chunk_claim.ners.exists():
        ner, _ = Ner.objects.get_or_create(
            trial=trial, section='summary', text='UI-SMOKE entity',
            defaults={
                'label': ['DISEASE'], 'start': 0, 'end': 16, 'score': 0.9,
                'method': ['ui-smoke'], 'model_name': ['ui-smoke'],
                'links': [], 'disease': disease, 'intervention': intervention,
            },
        )
        chunk_claim.ners.add(ner)
    title_claim, _ = Claim.objects.get_or_create(
        section='title', claim_type='ui_smoke_title', trial=trial,
        defaults={'evidence': 'UI-SMOKE title evidence', 'status': 'pending'},
    )
    existing = Claim.objects.filter(claim_type__startswith='ui_smoke').count()
    for index in range(existing, TOTAL_CLAIMS):
        Claim.objects.get_or_create(
            section='abstract', claim_type='ui_smoke_bulk', trial=trial,
            evidence=f'UI-SMOKE bulk evidence {index:03d}',
            defaults={'status': 'pending'},
        )
    # Bulk rows predate the abstract-section disambiguation; keep them there
    # so the title-claim search below matches exactly one record.
    Claim.objects.filter(claim_type='ui_smoke_bulk').exclude(section='abstract').update(
        section='abstract')
    return {
        'trial': trial.pk,
        'publication': publication.pk,
        'chunk_claim': chunk_claim.pk,
        'title_claim': title_claim.pk,
        'claims': Claim.objects.filter(claim_type__startswith='ui_smoke').count(),
    }
