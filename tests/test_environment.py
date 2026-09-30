"""Verification test script for 1fl environment and Django ORM integration."""

import os
import sys


def test_imports():
    print("Testing core dependency imports...")
    import django
    import psycopg
    import psycopg2
    import asyncpg
    print(f"  [OK] Django {django.__version__}, psycopg {psycopg.__version__}, psycopg2 {psycopg2.__version__}, asyncpg {asyncpg.__version__}")

    import Bio
    import metapub
    print(f"  [OK] BioPython {Bio.__version__}, metapub {metapub.__version__}")

    import pydantic
    import instructor
    import openai
    print(f"  [OK] pydantic {pydantic.__version__}, instructor {instructor.__version__}, openai {openai.__version__}")


def test_shared_lib_and_secrets():
    print("\nTesting shared library imports and secrets handling...")
    import instructor
    # Test import from django_app.lib
    from django_app.lib import db, pubmed, clinical_trials, llm
    print("  [OK] Successfully imported submodules via 'from django_app.lib import ...'")

    # Test direct import from lib
    import lib
    from lib import db as direct_db, pubmed as direct_pubmed, llm as direct_llm
    print("  [OK] Successfully imported submodules via 'from lib import ...'")

    # Test LLM helper client configuration
    client = llm.get_instructor_client()
    assert client is not None
    assert client.mode == instructor.Mode.MD_JSON
    assert llm.get_default_model() == os.environ.get("LLM_MODEL")
    assert llm.get_llm_api_key() == (os.environ.get("LLM_API_KEY") or "dummy_key")
    print(f"  [OK] Instructor client initialized successfully (URI: {llm.get_llm_uri() or 'default-openai'}, Mode: {client.mode.name}, Model: {llm.get_default_model()})")


def test_django_orm_models():
    print("\nTesting Django ORM setup and model operations...")
    import django
    from django.apps import apps
    if not apps.ready:
        django.setup()

    # Import models both from django_app.models and core.models
    from django_app.models import (
        Trial,
        Publication,
        PublicationTrial,
        PublicationTrialRelation,
        Disease,
        Intervention,
        Biomarker,
        Observation,
        Claim,
    )
    from core.models import Disease as CoreDisease
    assert Disease is CoreDisease
    print("  [OK] Models imported cleanly from django_app.models and core.models")

    # Verify db connection
    from lib.db import check_db_connection, get_db_version
    if not check_db_connection():
        print("  [WARN] Database connection not available; skipping live ORM persistence test.")
        return

    print(f"  [OK] Connected to PostgreSQL: {get_db_version().split(',')[0]}")

    # Test model creation and JSONB metadata handling
    test_disease, _ = Disease.objects.get_or_create(
        name="Non-Small Cell Lung Cancer",
        defaults={
            "mesh": "MESH:D002289",
            "meta": {"icd10": "C34.9", "source": "test_verification"}
        }
    )
    assert test_disease.created is not None
    assert test_disease.modified is not None
    assert test_disease.meta.get("source") == "test_verification"

    test_biomarker, _ = Biomarker.objects.get_or_create(
        name="EGFR L858R",
        defaults={
            "gene": "EGFR",
            "biomarker_type": "Somatic Mutation",
            "meta": {"exon": 21, "significance": "Sensitizing"}
        }
    )

    test_intervention, _ = Intervention.objects.get_or_create(
        name="Osimertinib",
        defaults={
            "meta": {"drug_class": "EGFR TKI 3rd gen"}
        }
    )

    test_trial, _ = Trial.objects.get_or_create(
        nct_id="NCT00000001",
        defaults={
            "title": "Verification Study for Targeted Therapy in NSCLC",
            "phase": "Phase 3",
            "status": "Active",
            "summary": "Automated verification study.",
            "meta": {"sponsor": "1FL Workspace", "test_flag": True}
        }
    )
    test_trial.diseases.add(test_disease)
    test_trial.interventions.add(test_intervention)
    test_trial.biomarkers.add(test_biomarker)

    test_pub, _ = Publication.objects.get_or_create(
        pmid="12345678",
        defaults={
            "title": "Verification Publication on Osimertinib in NSCLC",
            "journal": "Journal of Oncology Testing",
            "publication_date": "2026",
            "abstract": "Abstract for verification test run.",
            "meta": {"citations": 42}
        }
    )
    test_pub.diseases.add(test_disease)

    # Link publication and trial with explicit relation through join table
    link, _ = PublicationTrial.objects.get_or_create(
        publication=test_pub,
        trial=test_trial,
        defaults={
            "relation": PublicationTrialRelation.REPORTS_TRIAL_RESULT,
            "meta": {"verified_by": "test_suite"}
        }
    )
    assert link.relation == PublicationTrialRelation.REPORTS_TRIAL_RESULT
    assert link.created is not None
    assert link.meta.get("verified_by") == "test_suite"

    test_obs = Observation.objects.create(
        observation_type="EfficacyFinding",
        summary="Progression-free survival significantly improved.",
        trial=test_trial,
        publication=test_pub,
        biomarker=test_biomarker,
        disease=test_disease,
        meta={"p_value": 0.001, "hazard_ratio": 0.46}
    )

    assert test_obs.id is not None
    assert test_obs.created is not None
    assert test_obs.modified is not None
    assert test_obs.meta["hazard_ratio"] == 0.46

    # Test scientific claim creation
    test_claim = Claim.objects.create(
        section="summary",
        claim_type="intervention_worked_for_disease",
        trial=test_trial,
        meta={"evidence": "Improved survival."},
    )
    test_claim.diseases.add(test_disease)
    test_claim.interventions.add(test_intervention)
    assert test_claim.section == "summary"
    assert test_claim.created is not None
    assert test_claim.modified is not None
    assert test_claim.meta["evidence"] == "Improved survival."

    print("  [OK] Successfully created and queried Trial, Publication, PublicationTrial, Disease, Intervention, Biomarker, Observation, and Claim models with JSONB meta")


if __name__ == "__main__":
    test_imports()
    test_shared_lib_and_secrets()
    test_django_orm_models()
    print("\nAll environment & Django ORM integration checks succeeded!")
