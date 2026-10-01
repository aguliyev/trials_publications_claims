"""Score extracted claims against their original source material."""

import time

from typesafe_sdk import Choice, TypeSafeClient

from core.models import Claim, Judgement
from lib.text_tools import (
    PUBLICATION_FIELDS_NOT_TO_CHUNK, PUBLICATION_FIELDS_TO_CHUNK,
    TRIAL_FIELDS_NOT_TO_CHUNK, TRIAL_FIELDS_TO_CHUNK,
)
from lib.logs import get_logger, logged
from lib.prompts.judgement import SUPPORT_QUESTION

logger = get_logger(__name__)


@logged
def save_judgements():
    """Evaluate claims without judgements using System One."""
    created = []
    started = time.monotonic()
    claims = Claim.objects.filter(judgements__isnull=True).select_related('trial', 'publication').prefetch_related(
        'diseases', 'interventions',
    )
    total = claims.count()
    if not total:
        logger.info("No claims pending judgement")
        return created
    logger.info("Starting judgement evaluation pending=%s", total)
    with TypeSafeClient() as client:
        for index, claim in enumerate(claims, start=1):
            state = {
                'claim': {
                    'claim_type': claim.claim_type, 'section': claim.section,
                    'evidence': claim.evidence,
                    'diseases': [d.name for d in claim.diseases.all()],
                    'interventions': [i.name for i in claim.interventions.all()],
                },
            }
            if claim.trial_id:
                state['trial'] = {field: getattr(claim.trial, field) for field in
                                  (*TRIAL_FIELDS_NOT_TO_CHUNK, *TRIAL_FIELDS_TO_CHUNK)}
            if claim.publication_id:
                state['publication'] = {field: getattr(claim.publication, field) for field in
                                        (*PUBLICATION_FIELDS_NOT_TO_CHUNK, *PUBLICATION_FIELDS_TO_CHUNK)}
            logger.info("Requesting System One judgement claim_id=%s progress=%s/%s", claim.pk, index, total)
            call_started = time.monotonic()
            response = client.system_one(
                state=state,
                questions={'support': Choice(**SUPPORT_QUESTION)},
            )
            logger.info("Received System One judgement claim_id=%s elapsed_s=%.1f", claim.pk, time.monotonic() - call_started)
            answer = response.answers['support']
            created.append(Judgement.objects.create(
                claim=claim, method='system_one', score=answer.probabilities['supports'],
                meta={'verdict': answer.choice, 'model': response.model},
            ))
            logger.debug("Saved judgement claim_id=%s", claim.pk)
    logger.info("Judgement evaluation complete created=%s elapsed_s=%.1f", len(created), time.monotonic() - started)
    return created
