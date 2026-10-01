"""Re-fetch an existing source and discard its derived analysis."""

from django.db import transaction
from metapub import PubMedFetcher

from core.models import Publication, Trial
from lib.clinical_trials import fetch_and_upsert_trial, fetch_study_v2, fetch_trial_publications
from lib.logs import get_logger, logged
from lib.pubmed import fetch_and_upsert_publication

logger = get_logger(__name__)


@logged
def refetch_source(source: Trial | Publication) -> Trial | Publication:
    """Refresh a saved source; leave disease/intervention rows and existing publications intact."""
    if isinstance(source, Trial):
        data = fetch_study_v2(source.nct_id)
        if Trial.parse_api_study(data)['nct_id'] != source.nct_id:
            raise ValueError('Fetched trial ID does not match the requested record.')
    elif isinstance(source, Publication):
        data = PubMedFetcher().article_by_pmid(source.pmid)
        if Publication.parse_article_data(data)['pmid'] != source.pmid:
            raise ValueError('Fetched publication ID does not match the requested record.')
    else:
        raise TypeError('Expected a saved Trial or Publication.')

    # ponytail: the row lock spans new PubMed fetches; prefetch before locking if throughput matters.
    with transaction.atomic():
        source = type(source).objects.select_for_update().get(pk=source.pk)
        load_publications = False
        if isinstance(source, Trial):
            references = source.references if isinstance(source.references, list) else []
            referenced_pmids = {str(ref.get('pmid') or '').strip() for ref in references if isinstance(ref, dict)} - {''}
            load_publications = source.publications.distinct().count() == len(referenced_pmids)

        logger.info('Clearing derived data for %s id=%s', type(source).__name__, source.pk)
        source.claims.all().delete()
        source.ners.all().delete()
        source.diseases.clear()
        source.interventions.clear()

        if isinstance(source, Trial):
            refreshed = fetch_and_upsert_trial(data)
            if load_publications:
                fetch_trial_publications(refreshed.nct_id, missing_only=True)
        else:
            refreshed = fetch_and_upsert_publication(data)
        return refreshed
