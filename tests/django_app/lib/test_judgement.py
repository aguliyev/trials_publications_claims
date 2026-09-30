from unittest.mock import patch

from django.test import TestCase

from core.models import Claim, Judgement, Publication, Trial
from lib.judgement import save_judgements


class JudgementTestCase(TestCase):
    def test_no_pending_claims_does_not_require_api_key(self):
        with patch('lib.judgement.TypeSafeClient', side_effect=AssertionError('unnecessary client')):
            self.assertEqual(save_judgements(), [])

    def test_scores_claim_against_all_source_fields_once(self):
        trial = Trial.objects.create(
            nct_id="NCT123", title="Trial title", official_title="Official title",
            summary="Positive outcome", detailed_description="Study details",
            eligibility_criteria="Adult participants",
        )
        claim = Claim.objects.create(
            trial=trial, section="summary", claim_type="intervention_worked_for_disease",
            meta={"evidence": "Positive outcome"},
        )
        response = type("Response", (), {
            "model": "jev-latest",
            "answers": {"support": type("Answer", (), {
                "choice": "supports", "probabilities": {"supports": 0.81, "contradicts": 0.12, "unaddressed": 0.07},
            })()},
        })()
        with patch("lib.judgement.TypeSafeClient") as client:
            client.return_value.__enter__.return_value.system_one.return_value = response
            save_judgements()
            save_judgements()
            request = client.return_value.__enter__.return_value.system_one.call_args.kwargs

        self.assertEqual(Judgement.objects.count(), 1)
        judgement = Judgement.objects.get()
        self.assertEqual((judgement.claim, judgement.method, judgement.score), (claim, "system_one", 0.81))
        self.assertEqual(judgement.meta["verdict"], "supports")
        self.assertEqual(request["state"]["claim"]["evidence"], "Positive outcome")
        self.assertEqual(request["state"]["trial"], {
            "title": "Trial title", "official_title": "Official title", "summary": "Positive outcome",
            "detailed_description": "Study details", "eligibility_criteria": "Adult participants",
        })
        self.assertEqual(client.return_value.__enter__.return_value.system_one.call_count, 1)

    def test_publication_claim_uses_publication_fields_and_support_probability(self):
        publication = Publication.objects.create(pmid="123", title="Publication title", abstract="No efficacy result")
        claim = Claim.objects.create(publication=publication, section="abstract", claim_type="intervention_worked_for_disease")
        response = type("Response", (), {
            "model": "jev-latest",
            "answers": {"support": type("Answer", (), {
                "choice": "unaddressed", "probabilities": {"supports": 0.05, "contradicts": 0.1, "unaddressed": 0.85},
            })()},
        })()
        with patch("lib.judgement.TypeSafeClient") as client:
            client.return_value.__enter__.return_value.system_one.return_value = response
            save_judgements()
            state = client.return_value.__enter__.return_value.system_one.call_args.kwargs["state"]

        self.assertEqual(state["publication"], {"title": "Publication title", "abstract": "No efficacy result"})
        self.assertNotIn("trial", state)
        judgement = Judgement.objects.get(claim=claim)
        self.assertEqual(judgement.score, 0.05)
        self.assertEqual(judgement.meta["verdict"], "unaddressed")
