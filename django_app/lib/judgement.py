"""Score extracted claims against their original source material."""

from typesafe_sdk import Choice, TypeSafeClient

from core.models import Claim, Judgement
from lib.text_tools import (
    PUBLICATION_FIELDS_NOT_TO_CHUNK, PUBLICATION_FIELDS_TO_CHUNK,
    TRIAL_FIELDS_NOT_TO_CHUNK, TRIAL_FIELDS_TO_CHUNK,
)
from lib.logs import get_logger, logged

logger = get_logger(__name__)


@logged
def save_judgements():
    """Evaluate claims without judgements using System One."""
    created = []
    claims = Claim.objects.filter(judgements__isnull=True).select_related('trial', 'publication').prefetch_related(
        'diseases', 'interventions',
    )
    if not claims.exists():
        return created
    with TypeSafeClient() as client:
        for claim in claims:
            state = {
                'claim': {
                    'claim_type': claim.claim_type, 'section': claim.section,
                    'evidence': claim.meta.get('evidence', ''),
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
            logger.debug("Requesting System One judgement claim_id=%s", claim.pk)
            response = client.system_one(
                state=state,
                questions={'support': Choice(
                    instructions=(
                        'Does the source support the claim that the named intervention worked for the named disease? '
                        'Evaluate reported outcomes, not study objectives or mere mentions. '
                        'Use unaddressed when there is insufficient evidence in the source.'
                    ),
                    criteria={
                        'supports': 'The source reports a positive outcome supporting the claim.',
                        'contradicts': 'The source reports an outcome contradicting the claim.',
                        'unaddressed': 'The source does not establish whether the claim is true.',
                    },
                )},
            )
            logger.debug("Received System One judgement claim_id=%s", claim.pk)
            answer = response.answers['support']
            created.append(Judgement.objects.create(
                claim=claim, method='system_one', score=answer.probabilities['supports'],
                meta={'verdict': answer.choice, 'model': response.model},
            ))
            logger.debug("Saved judgement claim_id=%s", claim.pk)
    logger.info("Judgement evaluation complete created=%s", len(created))
    return created
