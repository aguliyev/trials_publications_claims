from django.test import TestCase

from core.models import Claim, Genetic, Publication, PublicationTrial, Trial
from lib.claim_groups import add_claim_to_existing_or_new_claim_group
from core.signals import update_publication_trial_links, update_trial_publication_links


class PublicationTrialSignalsTestCase(TestCase):
    def test_genetic_changes_do_not_regroup_claims_or_populate_group_genetics(self):
        first = Claim.objects.create(section='title', claim_type='genetic')
        second = Claim.objects.create(section='abstract', claim_type='genetic')
        first_group = add_claim_to_existing_or_new_claim_group(first)
        second.refresh_from_db()
        self.assertEqual(first_group.pk, second.claim_group_id)
        genetic = Genetic.objects.create(name='KRAS')

        first.genetics.add(genetic)
        first.refresh_from_db()
        second.refresh_from_db()
        first_group.refresh_from_db()

        self.assertEqual(first.claim_group_id, first_group.pk)
        self.assertEqual(second.claim_group_id, first_group.pk)
        self.assertEqual(first_group.genetics.count(), 0)

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
        self.assertEqual(link.relation, 'RESULT')
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
        self.assertEqual(link.relation, 'RESULT')
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
        self.assertEqual(link2.relation, 'BACKGROUND')
        self.assertEqual(link2.meta.get("source"), "trial_references")

    def test_all_reference_types_link_regardless_of_arrival_order(self):
        for index, relation in enumerate((
            'RESULT', 'BACKGROUND', 'PRIMARY', 'SECONDARY', 'CONCLUSION', 'SUPPORTING', 'DERIVED',
        ), start=1):
            with self.subTest(relation=relation):
                first_pmid = f'7000{index:04d}'
                publication = Publication.objects.create(pmid=first_pmid, title='First arrival')
                trial = Trial.objects.create(nct_id=f'NCT7000{index:04d}', title='Second arrival',
                                             references=[{'pmid': first_pmid, 'type': relation}])
                link = PublicationTrial.objects.get(publication=publication, trial=trial)
                self.assertEqual(link.relation, relation)
                link.full_clean()

                second_pmid = f'8000{index:04d}'
                trial = Trial.objects.create(nct_id=f'NCT8000{index:04d}', title='First arrival',
                                             references=[{'pmid': second_pmid, 'type': relation}])
                publication = Publication.objects.create(pmid=second_pmid, title='Second arrival')
                link = PublicationTrial.objects.get(publication=publication, trial=trial)
                self.assertEqual(link.relation, relation)
                link.full_clean()

        publication = Publication.objects.create(pmid='90000001', title='Unknown type')
        trial = Trial.objects.create(nct_id='NCT90000001', title='Unknown type',
                                     references=[{'pmid': publication.pmid, 'type': 'UNKNOWN'}])
        self.assertEqual(PublicationTrial.objects.get(publication=publication, trial=trial).relation, 'RELATED')

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
