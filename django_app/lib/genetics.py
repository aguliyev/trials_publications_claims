"""Link gene NERs to Genetic records and backfill existing Claims on demand."""

import time

from core.models import Claim, Genetic, Ner
from lib.entities import upsert_entity
from lib.logs import get_logger, logged

logger = get_logger(__name__)

LABELS = frozenset({'gene_or_gene_product', 'gene'})


@logged
def save_ner_genetic() -> None:
    """Link unprocessed gene mentions to Genetics and their source records."""
    pending = Ner.objects.filter(genetic__isnull=True)
    logger.info('Starting genetic linking pending=%s', pending.count())
    started = time.monotonic()
    linked = 0
    for index, ner in enumerate(pending.iterator(), start=1):
        if index % 1000 == 0:
            logger.info('Linking genetics progress=%s linked=%s elapsed_s=%.1f',
                        index, linked, time.monotonic() - started)
        if not LABELS.intersection(str(label).casefold() for label in (ner.label or [])):
            continue
        name = ner.text.strip()[:255]
        if not name:
            logger.warning('Skipping genetic NER with empty text id=%s', ner.pk)
            continue
        mesh = next((link.get('id') for link in (ner.links or [])
                     if isinstance(link, dict) and isinstance(link.get('id'), str)
                     and link['id'].upper().startswith('MESH:')), '')
        genetic = upsert_entity(Genetic, name, mesh)
        if genetic:
            ner.genetic = genetic
            ner.save(update_fields=['genetic', 'modified'])
            linked += 1
            logger.debug('Linked genetic ner_id=%s genetic_id=%s', ner.pk, genetic.pk)
            owner = ner.publication or ner.trial
            if owner:
                owner.genetics.add(genetic)
    logger.info('Genetic linking complete linked=%s elapsed_s=%.1f',
                linked, time.monotonic() - started)
