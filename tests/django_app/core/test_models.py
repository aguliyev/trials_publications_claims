import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import (
    Trial,
    Publication,
    PublicationTrial,
    PublicationTrialRelation,
    Disease,
    Intervention,
    Biomarker,
    Observation,
    Claim,
    Chunk,
    ClaimStatus,
    ClaimTrails,
    Focus,
)


class ModelSanityTestCase(TestCase):
    def test_focus_defaults_and_audit_fields(self):
        focus = Focus.objects.create(query='Colon cancer Nivolumab')

        self.assertEqual(focus.ingest_trials_count, 0)
        self.assertEqual(focus.ingest_publications_count, 0)
        self.assertEqual(focus.notes, '')
        self.assertEqual(focus.meta, {})
        self.assertIsNotNone(focus.created)
        self.assertIsNotNone(focus.modified)
        self.assertEqual(str(focus), 'Colon cancer Nivolumab')

    def test_focus_counts_must_be_non_negative(self):
        focus = Focus(
            query='Colon cancer',
            ingest_trials_count=-1,
            ingest_publications_count=-2,
        )

        with self.assertRaises(ValidationError):
            focus.full_clean()

    def test_focus_query_is_unique(self):
        Focus.objects.create(query='Colon cancer')
        duplicate = Focus(query='Colon cancer')

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_claim_trails_fields_and_source_relations(self):
        trial = Trial.objects.create(nct_id='NCT08880001', title='Audit trial')
        publication = Publication.objects.create(pmid='8880001', title='Audit publication')
        trial_trail = ClaimTrails.objects.create(
            trial=trial, status_from=ClaimStatus.PENDING,
            new_status=ClaimStatus.APPROVED, meta={'claim': {'id': 17}},
        )
        publication_trail = ClaimTrails.objects.create(
            publication=publication, notes='Rejected after review',
            status_from=ClaimStatus.PENDING, new_status=ClaimStatus.REJECTED,
        )
        self.assertEqual(trial_trail.notes, '')
        self.assertEqual(trial.claim_trails.get(), trial_trail)
        self.assertEqual(publication.claim_trails.get(), publication_trail)
        self.assertIsNotNone(trial_trail.created)
        self.assertEqual(trial_trail.meta, {'claim': {'id': 17}})
        trial_trail.new_status = 'unknown'
        with self.assertRaises(ValidationError):
            trial_trail.full_clean()
        trail_id = trial_trail.pk
        trial.delete()
        self.assertFalse(ClaimTrails.objects.filter(pk=trail_id).exists())

    def test_model_creation_and_metadata(self):
        disease = Disease.objects.create(
            name="Metastatic Colorectal Cancer",
            mesh="MESH:D015179",
            meta={"source": "test"}
        )
        self.assertIsNotNone(disease.id)
        self.assertIsNotNone(disease.created)
        self.assertIsNotNone(disease.modified)
        self.assertEqual(disease.mesh, "MESH:D015179")

        biomarker = Biomarker.objects.create(
            name="KRAS G12C",
            gene="KRAS",
            meta={"exon": 2}
        )

        trial = Trial.objects.create(
            nct_id="NCT09999999",
            title="Colorectal Cancer Clinical Trial",
            phase="Phase 1/2",
            status="Recruiting",
            meta={"target_enrollment": 150}
        )
        trial.diseases.add(disease)
        trial.biomarkers.add(biomarker)

        pub = Publication.objects.create(
            pmid="99999999",
            title="Trial Results and Clinical Utility",
            journal="Clinical Trials Journal",
            meta={"peer_reviewed": True}
        )

        link = PublicationTrial.objects.create(
            publication=pub,
            trial=trial,
            relation=PublicationTrialRelation.REPORTS_TRIAL_RESULT,
            meta={"confidence": 0.98}
        )
        self.assertEqual(link.relation, PublicationTrialRelation.REPORTS_TRIAL_RESULT)
        self.assertEqual(link.meta["confidence"], 0.98)
        self.assertIsNotNone(link.created)

        obs = Observation.objects.create(
            observation_type="SafetyFinding",
            summary="Tolerability profile consistent with expectations.",
            trial=trial,
            publication=pub,
            meta={"grade_3_adverse_events": 0.05}
        )

        self.assertEqual(obs.meta["grade_3_adverse_events"], 0.05)
        self.assertEqual(trial.diseases.count(), 1)
        self.assertEqual(pub.trials.count(), 1)

        claim = Claim.objects.create(
            section="title",
            claim_type="intervention_worked_for_disease",
            trial=trial,
            evidence="Treated successfully."
        )
        claim.diseases.add(disease)
        self.assertEqual(list(claim.diseases.all()), [disease])
        self.assertEqual(claim.section, "title")
        self.assertEqual(claim.evidence, "Treated successfully.")
        self.assertIsNotNone(claim.created)
        self.assertIsNotNone(claim.modified)

    def test_claim_can_link_to_disease_without_source(self):
        disease = Disease.objects.create(name="Leukemia")
        claim = Claim.objects.create(section="title", claim_type="intervention_worked_for_disease")
        claim.diseases.add(disease)
        self.assertEqual(list(claim.diseases.all()), [disease])

    def test_claim_notes_default_and_edit(self):
        claim = Claim.objects.create(section='title', claim_type='review')
        self.assertEqual(claim.notes, '')
        claim.notes = 'Reviewed source text.'
        claim.save(update_fields=['notes'])
        self.assertEqual(Claim.objects.get(pk=claim.pk).notes, 'Reviewed source text.')

    def test_claim_status_accepts_only_review_choices(self):
        claim = Claim(section="title", claim_type="intervention_worked_for_disease")
        for status in ("pending", "approved", "rejected"):
            claim.status = status
            claim.full_clean()
        claim.status = "unknown"
        with self.assertRaises(ValidationError):
            claim.full_clean()

    def test_trial_relational_and_jsonb_fields(self):
        trial = Trial.objects.create(
            nct_id="NCT01234567",
            title="Brief Title Example",
            official_title="Full Official Protocol Title Example",
            acronym="NICHE-EX",
            org_study_id="NCI-001",
            organization="Netherlands Cancer Institute",
            phase="Phase 2",
            status="RECRUITING",
            study_type="INTERVENTIONAL",
            lead_sponsor="Netherlands Cancer Institute",
            collaborators=[{"name": "BMS", "class": "INDUSTRY"}],
            summary="Brief summary text",
            detailed_description="Detailed description text",
            start_date=datetime.date(2017, 3, 29),
            start_date_type="ACTUAL",
            completion_date=datetime.date(2032, 3, 1),
            completion_date_type="ESTIMATED",
            enrollment=353,
            enrollment_type="ESTIMATED",
            sex="ALL",
            minimum_age="18 Years",
            healthy_volunteers=False,
            eligibility_criteria="Inclusion criteria: Age >= 18",
            has_results=False,
            conditions=["Colon Carcinoma"],
            keywords=["MSI tumors", "immunotherapy"],
            design_info={"allocation": "RANDOMIZED", "interventionModel": "PARALLEL"},
            arms=[{"label": "Arm A", "type": "EXPERIMENTAL"}],
            interventions_list=[{"name": "Nivolumab", "type": "DRUG"}],
            outcomes={"primaryOutcomes": [{"measure": "DFS"}]},
            locations=[{"facility": "Site 1", "city": "Amsterdam"}],
            contacts={"centralContacts": [{"name": "Contact 1"}]},
            references=[{"pmid": "41115454", "type": "DERIVED"}],
            raw={"protocolSection": {"identificationModule": {"nctId": "NCT01234567"}}},
        )
        self.assertEqual(trial.nct_id, "NCT01234567")
        self.assertEqual(trial.acronym, "NICHE-EX")
        self.assertEqual(trial.enrollment, 353)
        self.assertEqual(trial.start_date, datetime.date(2017, 3, 29))
        self.assertEqual(trial.conditions, ["Colon Carcinoma"])
        self.assertEqual(trial.arms[0]["label"], "Arm A")
        self.assertEqual(trial.raw["protocolSection"]["identificationModule"]["nctId"], "NCT01234567")
        self.assertEqual(trial.raw_json, trial.raw)

        trial.raw_json = {"updated": True}
        self.assertEqual(trial.raw, {"updated": True})

    def test_publication_relational_and_jsonb_fields(self):
        pub = Publication.objects.create(
            pmid="41115454",
            title="Neoadjuvant immunotherapy in mismatch-repair-proficient colon cancers.",
            abstract="Abstract text here...",
            journal="Nature",
            publication_date="2025",
            pub_date=datetime.date(2025, 12, 1),
            year=2025,
            volume="648",
            issue="8094",
            pages="726-735",
            doi="10.1038/s41586-025-09679-4",
            pmc="12711568",
            first_author="Tan PB",
            authors_str="Tan PB; Verschoor YL; Chalabi M",
            citation="Tan PB, et al. Nature. 2025.",
            pubmed_type="article",
            url="https://pubmed.ncbi.nlm.nih.gov/41115454/",
            authors=["Tan PB", "Verschoor YL", "Chalabi M"],
            mesh_terms={"D003110": {"descriptor_name": "Colonic Neoplasms"}},
            chemicals={"D000077594": {"substance_name": "Nivolumab"}},
            publication_types={"D016428": "Journal Article"},
            keywords=["colon cancer", "immunotherapy"],
            databanks=[{"name": "ClinicalTrials.gov", "accessions": ["NCT03026140"]}],
            grants=[],
            history={"received": "2025-01-23"},
            raw={"pmid": "41115454", "title": "Neoadjuvant immunotherapy"},
        )
        self.assertEqual(pub.pmid, "41115454")
        self.assertEqual(pub.journal, "Nature")
        self.assertEqual(pub.year, 2025)
        self.assertEqual(pub.pub_date, datetime.date(2025, 12, 1))
        self.assertEqual(pub.first_author, "Tan PB")
        self.assertEqual(pub.doi, "10.1038/s41586-025-09679-4")
        self.assertEqual(pub.pmc, "12711568")
        self.assertEqual(len(pub.authors), 3)
        self.assertEqual(pub.raw["pmid"], "41115454")
        self.assertEqual(pub.raw_json, pub.raw)

        pub.raw_json = {"updated": True}
        self.assertEqual(pub.raw, {"updated": True})
