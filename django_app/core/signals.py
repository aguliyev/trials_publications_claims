"""Django signals and automatic linking helpers for Trials and Publications."""

import logging
from typing import List, Set
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import (
    Trial,
    Publication,
    PublicationTrial,
    PublicationTrialRelation,
)

logger = logging.getLogger(__name__)

REFERENCE_TYPE_MAP = {
    "RESULT": PublicationTrialRelation.REPORTS_TRIAL_RESULT,
    "BACKGROUND": PublicationTrialRelation.BACKGROUND_FOR_TRIAL,
    "DERIVED": PublicationTrialRelation.DERIVED_FROM_TRIAL,
}


def update_trial_publication_links(trial: Trial) -> List[PublicationTrial]:
    """
    Update or create links between the given Trial and any Publications in the database.

    Checks:
    1. PMIDs referenced in `trial.references` (and `trial.raw`).
    2. Publications in the database whose `databanks` (or `raw`) reference this `trial.nct_id`.

    Returns the list of created or existing PublicationTrial link instances.
    """
    if not trial or not trial.pk:
        logger.debug("Skipping publication links for unsaved trial")
        return []

    logger.debug("Updating publication links trial_id=%s", trial.pk)

    created_or_found_links: List[PublicationTrial] = []

    # 1. Publications referenced by this trial
    references = trial.references if isinstance(trial.references, list) else []
    if not references and isinstance(trial.raw, dict):
        references = (
            trial.raw.get("protocolSection", {})
            .get("referencesModule", {})
            .get("references", [])
        )

    for ref in references:
        if isinstance(ref, dict):
            ref_pmid = str(ref.get("pmid") or "").strip()
            ref_type = str(ref.get("type") or "").strip().upper()
        elif isinstance(ref, (str, int)):
            ref_pmid = str(ref).strip()
            ref_type = ""
        else:
            continue

        if not ref_pmid:
            continue

        relation = REFERENCE_TYPE_MAP.get(
            ref_type,
            ref_type if ref_type in PublicationTrialRelation.values else PublicationTrialRelation.RELATED,
        )

        matching_pubs = Publication.objects.filter(pmid=ref_pmid)
        for pub in matching_pubs:
            link = PublicationTrial.objects.filter(publication=pub, trial=trial).first()
            if not link:
                link = PublicationTrial.objects.create(
                    publication=pub,
                    trial=trial,
                    relation=relation,
                    meta={"source": "trial_references", "pmid": ref_pmid, "type": ref_type},
                )
            elif link.relation == PublicationTrialRelation.RELATED and relation != PublicationTrialRelation.RELATED:
                link.relation = relation
                link.save(update_fields=["relation", "modified"])
            created_or_found_links.append(link)

    # 2. Existing publications whose databanks reference this trial's NCT ID
    nct_id = (trial.nct_id or "").strip().upper()
    if nct_id:
        databank_pubs = Publication.objects.filter(
            models.Q(databanks__icontains=nct_id) | models.Q(raw__icontains=nct_id)
        ).distinct()

        for pub in databank_pubs:
            # Confirm nct_id matches accessions in databanks or raw
            has_accession = False
            databanks = pub.databanks if isinstance(pub.databanks, list) else []
            if not databanks and isinstance(pub.raw, dict):
                databanks = pub.raw.get("databanks", [])

            for db_entry in databanks:
                if isinstance(db_entry, dict):
                    for acc in db_entry.get("accessions", []):
                        if acc and str(acc).strip().upper() == nct_id:
                            has_accession = True
                            break
                if has_accession:
                    break

            if has_accession:
                link = PublicationTrial.objects.filter(publication=pub, trial=trial).first()
                if not link:
                    link = PublicationTrial.objects.create(
                        publication=pub,
                        trial=trial,
                        relation=PublicationTrialRelation.REPORTS_TRIAL_RESULT,
                        meta={"source": "pubmed_databank", "accession": nct_id},
                    )
                created_or_found_links.append(link)

    logger.debug("Updated publication links trial_id=%s count=%s", trial.pk, len(created_or_found_links))
    return created_or_found_links


def update_publication_trial_links(publication: Publication) -> List[PublicationTrial]:
    """
    Update or create links between the given Publication and any Trials in the database.

    Checks:
    1. NCT accession numbers in `publication.databanks` (and `publication.raw`).
    2. Trials in the database whose `references` (or `raw`) reference this `publication.pmid`.

    Returns the list of created or existing PublicationTrial link instances.
    """
    if not publication or not publication.pk:
        logger.debug("Skipping trial links for unsaved publication")
        return []

    logger.debug("Updating trial links publication_id=%s", publication.pk)

    created_or_found_links: List[PublicationTrial] = []

    # 1. Trials referenced via PubMed DataBank accession numbers
    databanks = publication.databanks if isinstance(publication.databanks, list) else []
    if not databanks and isinstance(publication.raw, dict):
        databanks = publication.raw.get("databanks", [])

    linked_nct_ids: Set[str] = set()
    for db_entry in databanks:
        if isinstance(db_entry, dict):
            for acc in db_entry.get("accessions", []):
                acc_str = str(acc).strip().upper()
                if acc_str.startswith("NCT"):
                    linked_nct_ids.add(acc_str)

    for nct_id in linked_nct_ids:
        matching_trials = Trial.objects.filter(nct_id=nct_id)
        for trial in matching_trials:
            link = PublicationTrial.objects.filter(publication=publication, trial=trial).first()
            if not link:
                link = PublicationTrial.objects.create(
                    publication=publication,
                    trial=trial,
                    relation=PublicationTrialRelation.REPORTS_TRIAL_RESULT,
                    meta={"source": "pubmed_databank", "accession": nct_id},
                )
            created_or_found_links.append(link)

    # 2. Existing trials whose references mention this publication's PMID
    pmid = (publication.pmid or "").strip()
    if pmid:
        referencing_trials = Trial.objects.filter(
            models.Q(references__icontains=pmid) | models.Q(raw__icontains=pmid)
        ).distinct()

        for trial in referencing_trials:
            ref_type = ""
            refs = trial.references if isinstance(trial.references, list) else []
            for ref in refs:
                if isinstance(ref, dict) and str(ref.get("pmid", "")).strip() == pmid:
                    ref_type = str(ref.get("type", "")).strip().upper()
                    break

            relation = REFERENCE_TYPE_MAP.get(
                ref_type,
                ref_type if ref_type in PublicationTrialRelation.values else PublicationTrialRelation.RELATED,
            )

            link = PublicationTrial.objects.filter(publication=publication, trial=trial).first()
            if not link:
                link = PublicationTrial.objects.create(
                    publication=publication,
                    trial=trial,
                    relation=relation,
                    meta={"source": "trial_references", "pmid": pmid, "type": ref_type},
                )
            elif link.relation == PublicationTrialRelation.RELATED and relation != PublicationTrialRelation.RELATED:
                link.relation = relation
                link.save(update_fields=["relation", "modified"])
            created_or_found_links.append(link)

    logger.debug("Updated trial links publication_id=%s count=%s", publication.pk, len(created_or_found_links))
    return created_or_found_links


@receiver(post_save, sender=Trial)
def trial_post_save_link_publications(sender, instance: Trial, created: bool, raw: bool = False, **kwargs) -> None:
    """Trigger trial-to-publications link updates on Trial insert or update."""
    if raw:
        return
    try:
        logger.debug("Linking publications after trial save id=%s created=%s", instance.pk, created)
        update_trial_publication_links(instance)
    except Exception as exc:
        logger.error("Error updating publication links for trial id=%s error_type=%s", instance.pk, type(exc).__name__)


@receiver(post_save, sender=Publication)
def publication_post_save_link_trials(sender, instance: Publication, created: bool, raw: bool = False, **kwargs) -> None:
    """Trigger publication-to-trials link updates on Publication insert or update."""
    if raw:
        return
    try:
        logger.debug("Linking trials after publication save id=%s created=%s", instance.pk, created)
        update_publication_trial_links(instance)
    except Exception as exc:
        logger.error("Error updating trial links for publication id=%s error_type=%s", instance.pk, type(exc).__name__)
