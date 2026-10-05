import datetime
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from core.models import Disease, Intervention, Publication, PublicationTrial, PublicationTrialRelation, Trial
from lib.clinical_trials import fetch_and_upsert_trial, fetch_trial_publications, iter_trial_search_ids, search_trials


class ClinicalTrialsSearchTestCase(SimpleTestCase):
    @patch("lib.clinical_trials.httpx.get")
    def test_search_trials_returns_identifiers_links_and_titles(self, get):
        get.return_value.json.return_value = {
            "studies": [
                 {"protocolSection": {"identificationModule": {
                     "nctId": "NCT03026140", "briefTitle": "Colon cancer trial"
                }, "referencesModule": {"references": [
                    {"pmid": "41115454"}, {"pmid": "39278994"}, {"citation": "No PMID"},
                ]}}},
                {"protocolSection": {"identificationModule": {
                    "nctId": "NCT00000001", "briefTitle": "No references"
                }}},
            ]
        }

        self.assertEqual(search_trials("colorectal cancer"), [
            {"id": "NCT03026140", "link": "https://clinicaltrials.gov/study/NCT03026140", "title": "Colon cancer trial", "publication_count": 2},
            {"id": "NCT00000001", "link": "https://clinicaltrials.gov/study/NCT00000001", "title": "No references", "publication_count": 0},
        ])
        get.assert_called_once_with(
            "https://clinicaltrials.gov/api/v2/studies",
            params={"query.term": "colorectal cancer", "pageSize": 100, "sort": "@relevance"},
            timeout=30.0,
        )


def _response(data):
    from unittest.mock import Mock
    response = Mock()
    response.json.return_value = data
    return response


class ClinicalTrialsIterTestCase(SimpleTestCase):
    @patch('lib.clinical_trials.httpx.get')
    def test_iter_trial_search_ids_follows_next_page_tokens(self, get):
        get.side_effect = [
            _response({
                'studies': [
                    {'protocolSection': {'identificationModule': {'nctId': 'NCT00000001'}}},
                    {'protocolSection': {'identificationModule': {'nctId': 'NCT00000002'}}},
                ],
                'nextPageToken': 'token-2',
            }),
            _response({
                'studies': [
                    {'protocolSection': {'identificationModule': {'nctId': 'NCT00000003'}}},
                ],
            }),
        ]

        self.assertEqual(
            list(iter_trial_search_ids('colon cancer', page_size=2)),
            ['NCT00000001', 'NCT00000002', 'NCT00000003'],
        )
        self.assertNotIn('pageToken', get.call_args_list[0].kwargs['params'])
        self.assertEqual(get.call_args_list[1].kwargs['params']['pageToken'], 'token-2')

    @patch('lib.clinical_trials.httpx.get')
    def test_iter_trial_search_ids_stops_on_final_empty_page(self, get):
        get.return_value = _response({'studies': []})

        self.assertEqual(list(iter_trial_search_ids('no matches')), [])
        get.assert_called_once()

    @patch('lib.clinical_trials.httpx.get')
    def test_iter_trial_search_ids_follows_token_after_empty_page(self, get):
        get.side_effect = [
            _response({'studies': [], 'nextPageToken': 'token-2'}),
            _response({
                'studies': [
                    {'protocolSection': {'identificationModule': {'nctId': 'NCT00000009'}}},
                ],
            }),
        ]

        self.assertEqual(
            list(iter_trial_search_ids('sparse results')),
            ['NCT00000009'],
        )
        self.assertEqual(get.call_args_list[1].kwargs['params']['pageToken'], 'token-2')


class ClinicalTrialsTestCase(TestCase):
    def test_fetch_reuses_entities_by_case_insensitive_name(self):
        disease = Disease.objects.create(name="colon carcinoma", mesh="MESH:D003110")
        intervention = Intervention.objects.create(name="nivolumab", mesh="MESH:D000077594")
        study = {"protocolSection": {
            "identificationModule": {"nctId": "NCT03026140", "briefTitle": "Trial"},
            "conditionsModule": {"conditions": ["Colon Carcinoma"]},
            "armsInterventionsModule": {"interventions": [{"name": "Nivolumab"}]},
        }}

        trial = fetch_and_upsert_trial(study)
        self.assertEqual(list(trial.diseases.all()), [disease])
        self.assertEqual(list(trial.interventions.all()), [intervention])
        self.assertEqual(Disease.objects.count(), 1)
        self.assertEqual(Intervention.objects.count(), 1)

    @patch("lib.clinical_trials.fetch_and_upsert_publication")
    def test_fetch_trial_publications_accepts_nct_id_list(self, fetch_publication):
        publications = {
            pmid: Publication.objects.create(pmid=pmid, title="Article")
            for pmid in ("41115454", "39278994")
        }
        fetch_publication.side_effect = publications.get
        first = Trial.objects.create(
            nct_id="NCT00000001", title="First", references=[{"pmid": "41115454", "type": "DERIVED"}],
        )
        second = Trial.objects.create(
            nct_id="NCT00000002", title="Second", references=[{"pmid": "39278994", "type": "RESULT"}],
        )

        links = fetch_trial_publications([second.nct_id, first.nct_id])

        self.assertEqual(
            [(link.trial.nct_id, link.publication.pmid) for link in links],
            [("NCT00000002", "39278994"), ("NCT00000001", "41115454")],
        )
        self.assertEqual(PublicationTrial.objects.filter(trial__in=[first, second]).count(), 2)
        self.assertEqual(fetch_trial_publications([]), [])

    @patch("lib.clinical_trials.fetch_and_upsert_publication")
    def test_fetch_trial_publications_uses_reference_types(self, fetch_publication):
        publications = {
            pmid: Publication.objects.create(pmid=pmid, title="Article")
            for pmid in ("41115454", "39278994", "99110001")
        }
        trial = Trial.objects.create(
            nct_id="NCT00000001", title="Study",
            references=[
                {"pmid": "41115454", "type": "DERIVED"},
                {"pmid": "39278994", "type": "UNKNOWN"},
                {"pmid": "99110001", "type": "primary"},
                {"type": "RESULT"},
            ],
        )
        fetch_publication.side_effect = publications.get
        PublicationTrial.objects.filter(trial=trial, publication=publications["41115454"]).delete()
        PublicationTrial.objects.create(
            trial=trial, publication=publications["41115454"],
            relation=PublicationTrialRelation.DERIVED_FROM_TRIAL,
        )

        fetch_trial_publications(trial.nct_id)
        fetch_trial_publications(trial.nct_id)

        self.assertEqual(
            set(PublicationTrial.objects.filter(trial=trial).values_list("publication__pmid", "relation")),
            {("41115454", "DERIVED"), ("39278994", "RELATED"), ("99110001", "PRIMARY")},
        )
        self.assertEqual(fetch_publication.call_count, 6)

    def test_fetch_and_upsert_trial(self):
        sample_study = {
            "hasResults": False,
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT03026140",
                    "briefTitle": "Neoadjuvant Immune Checkpoint Inhibition in Colon Cancer",
                    "officialTitle": "Official Title of NICHE",
                    "acronym": "NICHE",
                    "orgStudyIdInfo": {"id": "N16NCI"},
                    "organization": {"fullName": "The Netherlands Cancer Institute"},
                },
                "statusModule": {
                    "overallStatus": "RECRUITING",
                    "startDateStruct": {"date": "2017-03-29", "type": "ACTUAL"},
                    "completionDateStruct": {"date": "2032-03-01", "type": "ESTIMATED"},
                },
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "The Netherlands Cancer Institute"},
                    "collaborators": [{"name": "Bristol-Myers Squibb", "class": "INDUSTRY"}],
                },
                "designModule": {
                    "studyType": "INTERVENTIONAL",
                    "phases": ["PHASE2"],
                    "designInfo": {"allocation": "RANDOMIZED"},
                    "enrollmentInfo": {"count": 353, "type": "ESTIMATED"},
                },
                "descriptionModule": {
                    "briefSummary": "Exploratory study in colon cancer.",
                    "detailedDescription": "Multi-center exploratory study.",
                },
                "conditionsModule": {
                    "conditions": ["Colon Carcinoma"],
                    "keywords": ["immunotherapy", "nivolumab"],
                },
                "armsInterventionsModule": {
                    "armGroups": [{"label": "group 1", "type": "EXPERIMENTAL"}],
                    "interventions": [{"name": "Nivolumab", "type": "DRUG", "description": "IV infusion"}],
                },
                "eligibilityModule": {
                    "sex": "ALL",
                    "minimumAge": "18 Years",
                    "healthyVolunteers": False,
                    "eligibilityCriteria": "Age >= 18",
                },
                "referencesModule": {
                    "references": [{"pmid": "41115454", "type": "DERIVED"}],
                },
            },
        }

        trial = fetch_and_upsert_trial(sample_study, link_entities=True)
        self.assertEqual(trial.nct_id, "NCT03026140")
        self.assertEqual(trial.acronym, "NICHE")
        self.assertEqual(trial.phase, "PHASE2")
        self.assertEqual(trial.lead_sponsor, "The Netherlands Cancer Institute")
        self.assertEqual(trial.enrollment, 353)
        self.assertEqual(trial.start_date, datetime.date(2017, 3, 29))
        self.assertEqual(trial.completion_date, datetime.date(2032, 3, 1))
        self.assertTrue(trial.diseases.filter(name="Colon Carcinoma").exists())
        self.assertTrue(trial.interventions.filter(name="Nivolumab").exists())
        self.assertEqual(trial.raw, sample_study)

        trial.claims_generated = True
        trial.save(update_fields=["claims_generated"])
        sample_study["protocolSection"]["statusModule"]["overallStatus"] = "ACTIVE_NOT_RECRUITING"
        updated_trial = fetch_and_upsert_trial(sample_study, link_entities=True)
        self.assertEqual(updated_trial.id, trial.id)
        self.assertEqual(updated_trial.status, "ACTIVE_NOT_RECRUITING")
        self.assertTrue(updated_trial.claims_generated)

    def test_fetch_and_upsert_trial_ids(self):
        def study(nct_id):
            return {"protocolSection": {"identificationModule": {"nctId": nct_id, "briefTitle": nct_id}}}

        with patch("lib.clinical_trials.fetch_study_v2", side_effect=study):
            trials = fetch_and_upsert_trial(["NCT00000001", "NCT00000002"])

        self.assertEqual([trial.nct_id for trial in trials], ["NCT00000001", "NCT00000002"])
        self.assertEqual(Trial.objects.filter(nct_id__in=["NCT00000001", "NCT00000002"]).count(), 2)
        self.assertEqual(fetch_and_upsert_trial([]), [])
