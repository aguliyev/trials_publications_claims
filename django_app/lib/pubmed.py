"""PubMed database ingestion."""

import os
from typing import Any, Dict
import django
from django.apps import apps
from metapub import PubMedFetcher
import httpx

from lib.logs import get_logger, logged

logger = get_logger(__name__)

if not apps.ready and not apps.loading:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings")
    django.setup()

from core.models import (
    Publication,
    Disease,
    Intervention,
)
from core.signals import update_publication_trial_links
from lib.entities import mesh_from_uid, upsert_entity
from lib.text_tools import save_publication_chunks


@logged
def search_publications(query: str) -> list[dict[str, str]]:
    """Search the first 100 matching PubMed records without saving them."""
    logger.debug("Requesting PubMed search")
    response = httpx.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={
            "db": "pubmed", "term": query, "retmode": "json", "retmax": 100,
            "sort": "relevance",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    logger.debug("PubMed search responded status=%s", response.status_code)
    pmids = response.json()["esearchresult"]["idlist"]
    if not pmids:
        logger.info("PubMed search returned no publications")
        return []

    logger.debug("Requesting PubMed summaries count=%s", len(pmids))
    response = httpx.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
        timeout=30.0,
    )
    response.raise_for_status()
    logger.debug("PubMed summaries responded status=%s", response.status_code)
    summaries = response.json()["result"]
    return [
        {"id": pmid, "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "title": summaries[pmid]["title"]}
        for pmid in pmids
    ]


@logged
def fetch_and_upsert_publication(
    pmid_or_data: str | int | Dict[str, Any] | list[str | int] | Any,
    link_entities: bool = True,
) -> Publication | list[Publication]:
    """
    Fetch and upsert a publication by PMID or payload, or a list of PMIDs.
    Lists return the upserted Publication records in input order.

    Populates all relational columns, JSONB attributes, and stores the complete raw payload
    in `raw` (also accessible via `raw_json`).
    When link_entities=True, also associates or creates related Disease, Intervention, and Trial entities.
    """
    if isinstance(pmid_or_data, list):
        return [fetch_and_upsert_publication(pmid, link_entities=link_entities) for pmid in pmid_or_data]

    if isinstance(pmid_or_data, (str, int)):
        pmid = str(pmid_or_data).strip()
        logger.debug("Fetching PubMed article pmid=%s", pmid)
        article_data = PubMedFetcher().article_by_pmid(pmid)
        logger.debug("Fetched PubMed article pmid=%s", pmid)
    else:
        article_data = pmid_or_data

    parsed_fields = Publication.parse_article_data(article_data)
    lookup_pmid = parsed_fields.pop("pmid", None)
    if not lookup_pmid:
        raise ValueError("Could not determine PMID from provided publication data.")

    logger.debug("Upserting publication pmid=%s", lookup_pmid)
    publication, _ = Publication.objects.update_or_create(
        pmid=lookup_pmid,
        defaults=parsed_fields,
    )
    logger.debug("Upserted publication pmid=%s pk=%s", lookup_pmid, publication.pk)
    save_publication_chunks(publication)

    if link_entities:
        # 1. Link interventions from chemicals / substances
        chemicals = parsed_fields.get("chemicals", {})
        if isinstance(chemicals, dict):
            for uid, chem_info in chemicals.items():
                if isinstance(chem_info, dict):
                    name = chem_info.get("substance_name")
                else:
                    name = str(chem_info)
                if name and str(name).strip():
                    intervention = upsert_entity(Intervention, str(name).strip(), mesh_from_uid(uid))
                    publication.interventions.add(intervention)

        # 2. Link diseases from MeSH terms
        mesh_terms = parsed_fields.get("mesh_terms", {})
        if isinstance(mesh_terms, dict):
            for uid, term_info in mesh_terms.items():
                if isinstance(term_info, dict):
                    desc_name = term_info.get("descriptor_name")
                    qualifiers = term_info.get("qualifiers", [])
                else:
                    desc_name = str(term_info)
                    qualifiers = []

                if not desc_name or not str(desc_name).strip():
                    continue
                desc_name = str(desc_name).strip()

                is_disease_concept = (
                    any(desc_name.lower().endswith(s) for s in ("neoplasm", "neoplasms", "cancer", "carcinoma", "tumors", "disease", "diseases", "syndrome"))
                    or any(isinstance(q, dict) and any(kw in str(q.get("qualifier_name", "")).lower() for kw in ("therapy", "drug", "pathology", "surgery")) for q in qualifiers)
                    or Disease.objects.filter(name__iexact=desc_name).exists()
                )
                if is_disease_concept:
                    disease = upsert_entity(Disease, desc_name, mesh_from_uid(uid))
                    publication.diseases.add(disease)

        # 3. Link trials from DataBank accession numbers and trial references
        update_publication_trial_links(publication)

    return publication
