"""Import new records requested by saved Focus rows."""

import os
from dataclasses import dataclass
from typing import Callable, Iterable

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_app.settings')

import django

django.setup()

from django.db import transaction
from django.db.models import F, Q

from core.models import Focus, Publication, Trial
from lib.clinical_trials import fetch_and_upsert_trial, iter_trial_search_ids
from lib.logs import get_logger
from lib.pubmed import fetch_and_upsert_publication, iter_publication_search_ids

logger = get_logger('lib.jobs.ingest_focus')


@dataclass(frozen=True)
class IngestSpec:
    label: str
    count_field: str
    model: type
    identifier_field: str
    search: Callable[[str], Iterable[str]]
    fetch: Callable[[str], object]


def _decrement(focus: Focus, field: str) -> None:
    updated = Focus.objects.filter(pk=focus.pk, **{f'{field}__gt': 0}).update(
        **{field: F(field) - 1},
    )
    if updated != 1:
        raise RuntimeError(f'Could not decrement {field} for Focus {focus.pk}.')


def _import_one(focus: Focus, spec: IngestSpec, identifier: str) -> bool:
    lookup = {spec.identifier_field: identifier}
    with transaction.atomic():
        # Repeat the existence check in the transaction. This also handles a
        # duplicate identifier yielded twice by a source iterator.
        if spec.model.objects.filter(**lookup).exists():
            return False
        spec.fetch(identifier)
        if not spec.model.objects.filter(**lookup).exists():
            raise RuntimeError(
                f'Importer returned without saving {spec.label} {identifier}.'
            )
        _decrement(focus, spec.count_field)

    # Update the in-memory snapshot only after the transaction committed.
    setattr(focus, spec.count_field, getattr(focus, spec.count_field) - 1)
    return True


def ingest_kind(focus: Focus, spec: IngestSpec) -> int:
    pending = getattr(focus, spec.count_field)
    if pending <= 0:
        return 0
    completed = 0
    search_ended = 'quota reached'
    try:
        identifiers = iter(spec.search(focus.query))
    except Exception:
        logger.error(
            'Search failed focus_id=%s kind=%s query=%r',
            focus.pk, spec.label, focus.query, exc_info=True,
        )
        return 0
    while completed < pending:
        try:
            identifier = next(identifiers)
        except StopIteration:
            search_ended = 'exhausted'
            break
        except Exception:
            search_ended = 'failed'
            logger.error(
                'Search failed focus_id=%s kind=%s query=%r',
                focus.pk, spec.label, focus.query, exc_info=True,
            )
            break
        lookup = {spec.identifier_field: identifier}
        if spec.model.objects.filter(**lookup).exists():
            logger.info(
                'Skipping existing %s focus_id=%s identifier=%s',
                spec.label, focus.pk, identifier,
            )
            continue
        try:
            imported = _import_one(focus, spec, identifier)
        except Exception:
            logger.error(
                'Failed %s focus_id=%s identifier=%s',
                spec.label, focus.pk, identifier, exc_info=True,
            )
            continue
        if not imported:
            logger.info(
                'Skipping existing %s focus_id=%s identifier=%s',
                spec.label, focus.pk, identifier,
            )
            continue
        completed += 1
        logger.info(
            'Imported %s focus_id=%s identifier=%s remaining=%s',
            spec.label, focus.pk, identifier, getattr(focus, spec.count_field),
        )
    if completed < pending and search_ended != 'failed':
        logger.warning(
            'Search ended focus_id=%s kind=%s reason=%s imported=%s pending=%s',
            focus.pk, spec.label, search_ended, completed,
            getattr(focus, spec.count_field),
        )
    return completed


def ingest_focus(focus: Focus) -> dict[str, int]:
    trials = IngestSpec(
        label='trials', count_field='ingest_trials_count', model=Trial,
        identifier_field='nct_id', search=iter_trial_search_ids,
        fetch=fetch_and_upsert_trial,
    )
    publications = IngestSpec(
        label='publications', count_field='ingest_publications_count', model=Publication,
        identifier_field='pmid', search=iter_publication_search_ids,
        fetch=fetch_and_upsert_publication,
    )
    return {
        'trials': ingest_kind(focus, trials),
        'publications': ingest_kind(focus, publications),
    }


def run() -> None:
    focuses = Focus.objects.filter(
        Q(ingest_trials_count__gt=0) | Q(ingest_publications_count__gt=0),
    ).order_by('id')
    for focus in focuses.iterator():
        logger.info(
            'Starting Focus focus_id=%s trials=%s publications=%s query=%r',
            focus.pk, focus.ingest_trials_count, focus.ingest_publications_count, focus.query,
        )
        result = ingest_focus(focus)
        logger.info(
            'Completed Focus focus_id=%s imported_trials=%s imported_publications=%s',
            focus.pk, result['trials'], result['publications'],
        )


if __name__ == '__main__':
    run()
