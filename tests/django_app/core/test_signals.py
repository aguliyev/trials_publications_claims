from django.test import TestCase

from core.models import Publication, PublicationTrial, PublicationTrialRelation, Trial
from core.signals import update_publication_trial_links, update_trial_publication_links


class PublicationTrialSignalsTestCase(TestCase):
    def test_trial_post_save_signal_links_existing_publication(self):
        pub = Publication.objects.create(
            pmid="77770001",
            title="Pre-existing publication in DB",
        )

        trial = Trial.objects.create(
            nct_id="NCT07770001",
            title="Trial referencing publication",
            references=[{"pmid": "77770001", "type": "RESULT"}],
        )

        link = PublicationTrial.objects.filter(publication=pub, trial=trial).first()
        self.assertIsNotNone(link)
        self.assertEqual(link.relation, PublicationTrialRelation.REPORTS_TRIAL_RESULT)
        self.assertEqual(link.meta.get("source"), "trial_references")

        pub_databank = Publication.objects.create(
            pmid="77770002",
            title="Publication with databank accession",
            databanks=[{"name": "ClinicalTrials.gov", "accessions": ["NCT07770001"]}],
        )

        trial.status = "COMPLETED"
        trial.save()

        link2 = PublicationTrial.objects.filter(publication=pub_databank, trial=trial).first()
        self.assertIsNotNone(link2)
        self.assertEqual(link2.meta.get("source"), "pubmed_databank")

    def test_publication_post_save_signal_links_existing_trial(self):
        trial = Trial.objects.create(
            nct_id="NCT08880001",
            title="Pre-existing trial in DB",
        )

        pub = Publication.objects.create(
            pmid="88880001",
            title="Publication referencing trial via databanks",
            databanks=[{"name": "ClinicalTrials.gov", "accessions": ["NCT08880001"]}],
        )

        link = PublicationTrial.objects.filter(publication=pub, trial=trial).first()
        self.assertIsNotNone(link)
        self.assertEqual(link.relation, PublicationTrialRelation.REPORTS_TRIAL_RESULT)
        self.assertEqual(link.meta.get("source"), "pubmed_databank")

        trial_with_ref = Trial.objects.create(
            nct_id="NCT08880002",
            title="Trial with reference",
            references=[{"pmid": "88880001", "type": "BACKGROUND"}],
        )

        pub.journal = "Updated Journal"
        pub.save()

        link2 = PublicationTrial.objects.filter(publication=pub, trial=trial_with_ref).first()
        self.assertIsNotNone(link2)
        self.assertEqual(link2.relation, PublicationTrialRelation.BACKGROUND_FOR_TRIAL)
        self.assertEqual(link2.meta.get("source"), "trial_references")

    def test_bidirectional_arrival_order_linking(self):
        trial_a = Trial.objects.create(
            nct_id="NCT09990001",
            title="Trial created first",
            references=[{"pmid": "99990001", "type": "RESULT"}],
        )
        self.assertEqual(PublicationTrial.objects.filter(trial=trial_a).count(), 0)

        pub_a = Publication.objects.create(
            pmid="99990001",
            title="Publication arriving later",
        )
        self.assertEqual(PublicationTrial.objects.filter(trial=trial_a, publication=pub_a).count(), 1)

        pub_b = Publication.objects.create(
            pmid="99990002",
            title="Publication created first",
            databanks=[{"name": "ClinicalTrials.gov", "accessions": ["NCT09990002"]}],
        )
        self.assertEqual(PublicationTrial.objects.filter(publication=pub_b).count(), 0)

        trial_b = Trial.objects.create(
            nct_id="NCT09990002",
            title="Trial arriving later",
        )
        self.assertEqual(PublicationTrial.objects.filter(trial=trial_b, publication=pub_b).count(), 1)

        res_trial = update_trial_publication_links(trial_b)
        self.assertGreaterEqual(len(res_trial), 1)
        res_pub = update_publication_trial_links(pub_b)
        self.assertGreaterEqual(len(res_pub), 1)
        self.assertEqual(PublicationTrial.objects.filter(trial=trial_b, publication=pub_b).count(), 1)
