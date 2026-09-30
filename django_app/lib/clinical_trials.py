"""ClinicalTrials.gov database ingestion."""

import os
from typing import Any, Dict
import django
from django.apps import apps
import httpx

from lib.logs import get_logger, logged

logger = get_logger(__name__)

if not apps.ready and not apps.loading:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings")
    django.setup()

from core.models import (
    Trial,
    Disease,
    Intervention,
    PublicationTrial,
    PublicationTrialRelation,
)
from core.signals import update_trial_publication_links
from lib.pubmed import fetch_and_upsert_publication
from lib.text_tools import save_trial_chunks

CTGOV_V2_URL = "https://clinicaltrials.gov/api/v2/studies"


@logged
def search_trials(query: str) -> list[dict[str, str]]:
    """Search the first 20 matching studies without saving them."""
    logger.debug("Requesting ClinicalTrials.gov studies")
    response = httpx.get(CTGOV_V2_URL, params={"query.term": query, "pageSize": 20}, timeout=30.0)
    response.raise_for_status()
    logger.debug("ClinicalTrials.gov studies responded status=%s", response.status_code)
    results = []
    for study in response.json()["studies"]:
        identification = study["protocolSection"]["identificationModule"]
        nct_id = identification["nctId"]
        results.append({
            "id": nct_id,
            "link": f"https://clinicaltrials.gov/study/{nct_id}",
            "title": identification["briefTitle"],
        })
    return results


@logged
def fetch_study_v2(nct_id: str) -> Dict[str, Any]:
    """
    Fetch a single study by NCT ID from ClinicalTrials.gov API v2 via httpx.
    """
    logger.debug("Requesting ClinicalTrials.gov study nct_id=%s", nct_id)
    response = httpx.get(f"{CTGOV_V2_URL}/{nct_id}", timeout=30.0)
    response.raise_for_status()
    logger.debug("ClinicalTrials.gov study responded nct_id=%s status=%s", nct_id, response.status_code)
    return response.json()


@logged
def fetch_trial_publications(nct_id: str | list[str]) -> list[PublicationTrial]:
    """Link publications for saved trials; lists return links in input order."""
    # TODO: fetch_trial_publications() can be long-running (one PubMed fetch per
    # reference). The web UI calls it synchronously, so the browser may time out
    # while the server is still working; a timeout response must not be treated
    # as proof the server finished. Revisit with background execution/progress.
    if isinstance(nct_id, list):
        return [link for trial_id in nct_id for link in fetch_trial_publications(trial_id)]

    trial = Trial.objects.get(nct_id=nct_id)
    links = []
    for reference in trial.references if isinstance(trial.references, list) else []:
        if not isinstance(reference, dict):
            continue
        pmid = str(reference.get("pmid") or "").strip()
        if not pmid:
            logger.warning("Skipping reference without PMID for trial %s", nct_id)
            continue

        logger.debug("Fetching referenced publication pmid=%s for trial %s", pmid, nct_id)
        publication = fetch_and_upsert_publication(pmid)
        logger.debug("Fetched referenced publication pmid=%s for trial %s", pmid, nct_id)
        relation = reference.get("type")
        if relation not in PublicationTrialRelation.values:
            relation = PublicationTrial._meta.get_field("relation").get_default()

        link = PublicationTrial.objects.filter(trial=trial, publication=publication, relation=relation).first()
        if link is None:
            link = PublicationTrial.objects.filter(trial=trial, publication=publication).first()
            if link is None:
                link = PublicationTrial.objects.create(trial=trial, publication=publication, relation=relation)
            else:
                link.relation = relation
                link.save(update_fields=["relation", "modified"])
        links.append(link)
    return links


@logged
def fetch_and_upsert_trial(
    nct_id_or_data: str | Dict[str, Any] | list[str],
    link_entities: bool = True,
) -> Trial | list[Trial]:
    """
    Fetch and upsert one study by NCT ID or payload, or a list of NCT IDs.
    Lists return the upserted Trial records in input order.

    Populates all relational columns, JSONB attributes, and stores the complete raw payload
    in `raw` (also accessible via `raw_json`).
    When link_entities=True, also associates or creates related Disease and Intervention entities.
    """
    if isinstance(nct_id_or_data, list):
        return [fetch_and_upsert_trial(nct_id, link_entities=link_entities) for nct_id in nct_id_or_data]

    if isinstance(nct_id_or_data, dict):
        study_data = nct_id_or_data
        nct_id = (
            study_data.get("protocolSection", {})
            .get("identificationModule", {})
            .get("nctId")
        )
        if not nct_id:
            raise ValueError("Study data dictionary missing protocolSection.identificationModule.nctId")
    elif isinstance(nct_id_or_data, str):
        nct_id = nct_id_or_data.strip().upper()
        study_data = fetch_study_v2(nct_id)
    else:
        raise TypeError(f"Expected NCT ID string, dict, or list, got {type(nct_id_or_data).__name__}")

    parsed_fields = Trial.parse_api_study(study_data)
    lookup_nct_id = parsed_fields.pop("nct_id", nct_id)

    logger.debug("Upserting trial nct_id=%s", lookup_nct_id)
    trial, _ = Trial.objects.update_or_create(
        nct_id=lookup_nct_id,
        defaults=parsed_fields,
    )
    logger.debug("Upserted trial nct_id=%s pk=%s", lookup_nct_id, trial.pk)
    save_trial_chunks(trial)

    if link_entities:
        # Link diseases from conditions
        conditions = parsed_fields.get("conditions", [])
        for cond_name in conditions:
            if cond_name and str(cond_name).strip():
                disease, _ = Disease.objects.get_or_create(name=str(cond_name).strip())
                trial.diseases.add(disease)

        # Link interventions from interventions_list
        interventions_list = parsed_fields.get("interventions_list", [])
        for item in interventions_list:
            int_name = item.get("name") if isinstance(item, dict) else str(item)
            if int_name and str(int_name).strip():
                intervention, _ = Intervention.objects.get_or_create(name=str(int_name).strip())
                trial.interventions.add(intervention)

        # Link publications from references and existing database publications
        update_trial_publication_links(trial)

    return trial
