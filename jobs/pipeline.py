"""Run the existing enrichment pipeline in the Django container."""

import os
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings")

import django

django.setup()

from lib.claims import save_claims
from lib.claim_groups import (merge_duplicate_claim_groups, process_claims_to_claim_groups,
                              process_unsynced_claim_groups)
from lib.diseases import save_ner_diseases
from lib.interventions import save_ner_interventions
from lib.judgement import save_judgements
from lib.logs import get_logger
from lib.ner import save_ner_publications, save_ner_trials


if __name__ == "__main__":
    logger = get_logger("lib.jobs.pipeline")
    for stage in (save_ner_trials, save_ner_publications, save_ner_interventions,
                   save_ner_diseases, save_claims, process_claims_to_claim_groups,
                   merge_duplicate_claim_groups, process_unsynced_claim_groups, save_judgements):
        logger.info("Starting %s", stage.__name__)
        started = time.monotonic()
        try:
            stage()
        except Exception as exc:
            logger.error("Failed %s elapsed_s=%.1f error_type=%s", stage.__name__,
                         time.monotonic() - started, type(exc).__name__, exc_info=True)
            raise
        logger.info("Completed %s elapsed_s=%.1f", stage.__name__, time.monotonic() - started)
