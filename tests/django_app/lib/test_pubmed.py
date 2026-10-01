import datetime
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from core.models import Disease, Intervention, Publication, PublicationTrial, Trial
from lib.pubmed import fetch_and_upsert_publication, search_publications


class PubMedSearchTestCase(SimpleTestCase):
    @patch("lib.pubmed.httpx.get")
    def test_search_publications_returns_identifiers_links_and_titles(self, get):
        get.side_effect = [
            _response({"esearchresult": {"idlist": ["41115454", "39278994"]}}),
            _response({"result": {
                "41115454": {"title": "Colon cancer treatment"},
                "39278994": {"title": "Neoadjuvant therapy"},
            }}),
        ]

        self.assertEqual(search_publications("colorectal cancer"), [
            {"id": "41115454", "link": "https://pubmed.ncbi.nlm.nih.gov/41115454/", "title": "Colon cancer treatment"},
            {"id": "39278994", "link": "https://pubmed.ncbi.nlm.nih.gov/39278994/", "title": "Neoadjuvant therapy"},
        ])
        self.assertEqual(get.call_args_list[0].kwargs["params"], {
            "db": "pubmed", "term": "colorectal cancer", "retmode": "json", "retmax": 100,
        })

    @patch("lib.pubmed.httpx.get")
    def test_search_publications_with_no_matches_skips_summary(self, get):
        get.return_value.json.return_value = {"esearchresult": {"idlist": []}}

        self.assertEqual(search_publications("nonexistent term"), [])
        get.assert_called_once()


class PubMedTestCase(TestCase):
    def test_fetch_enriches_existing_entities_with_mesh(self):
        disease = Disease.objects.create(name="colonic neoplasms")
        intervention = Intervention.objects.create(name="nivolumab")

        pub = fetch_and_upsert_publication({
            "pmid": "123", "title": "Article",
            "mesh": {"D003110": {"descriptor_name": "Colonic Neoplasms"}},
            "chemicals": {"D000077594": {"substance_name": "Nivolumab"}},
        })

        disease.refresh_from_db()
        intervention.refresh_from_db()
        self.assertEqual(disease.mesh, "MESH:D003110")
        self.assertEqual(intervention.mesh, "MESH:D000077594")
        self.assertEqual(list(pub.diseases.all()), [disease])
        self.assertEqual(list(pub.interventions.all()), [intervention])
        self.assertEqual(Disease.objects.count(), 1)
        self.assertEqual(Intervention.objects.count(), 1)

    def test_fetch_accepts_prefixed_mesh_identifiers(self):
        pub = fetch_and_upsert_publication({
            "pmid": "124", "title": "Article",
            "mesh": {"MESH:D003110": {"descriptor_name": "Colonic Neoplasms"}},
            "chemicals": {"MESH:D000077594": {"substance_name": "Nivolumab"}},
        })

        self.assertEqual(pub.diseases.get().mesh, "MESH:D003110")
        self.assertEqual(pub.interventions.get().mesh, "MESH:D000077594")

    def test_fetch_reuses_mesh_for_alias_without_overwriting_existing_mesh(self):
        disease = Disease.objects.create(name="Colonic Neoplasms", mesh="MESH:D003110")
        intervention = Intervention.objects.create(name="Nivolumab", mesh="MESH:D000077594")

        pub = fetch_and_upsert_publication({
            "pmid": "456", "title": "Article",
            "mesh": {"D003110": {"descriptor_name": "Colon Cancer"}},
            "chemicals": {"D000077594": {"substance_name": "Checkpoint Drug"}},
        })

        self.assertEqual(list(pub.diseases.all()), [disease])
        self.assertEqual(list(pub.interventions.all()), [intervention])
        self.assertEqual(Disease.objects.count(), 1)
        self.assertEqual(Intervention.objects.count(), 1)

        fetch_and_upsert_publication({
            "pmid": "457", "title": "Another article",
            "mesh": {"D009999": {"descriptor_name": "Colonic Neoplasms"}},
            "chemicals": {"D009999": {"substance_name": "Nivolumab"}},
        })
        disease.refresh_from_db()
        intervention.refresh_from_db()
        self.assertEqual(disease.mesh, "MESH:D003110")
        self.assertEqual(intervention.mesh, "MESH:D000077594")
        self.assertEqual(Disease.objects.count(), 1)
        self.assertEqual(Intervention.objects.count(), 1)

    def test_fetch_and_upsert_publication(self):
        trial = Trial.objects.create(
            nct_id="NCT03026140",
            title="NICHE trial",
            status="RECRUITING",
        )

        sample_article = {
            "pmid": "41115454",
            "title": "Neoadjuvant immunotherapy in mismatch-repair-proficient colon cancers.",
            "abstract": "Immune checkpoint blockade...",
            "journal": "Nature",
            "year": "2025",
            "pubdate": "2025-12-01",
            "volume": "648",
            "issue": "8094",
            "pages": "726-735",
            "doi": "10.1038/s41586-025-09679-4",
            "pmc": "12711568",
            "author1_last_fm": "Tan PB",
            "authors_str": "Tan PB; Verschoor YL; Chalabi M",
            "citation": "Tan PB, et al. Nature. 2025.",
            "authors": ["Tan PB", "Verschoor YL", "Chalabi M"],
            "chemicals": {
                "D000077594": {"substance_name": "Nivolumab", "registry_number": "31YO63LBSN"},
                "D000074324": {"substance_name": "Ipilimumab", "registry_number": "0"},
            },
            "mesh": {
                "D003110": {
                    "descriptor_name": "Colonic Neoplasms",
                    "descriptor_major_topic": True,
                    "qualifiers": [{"qualifier_name": "therapy"}],
                }
            },
            "databanks": [{"name": "ClinicalTrials.gov", "accessions": ["NCT03026140"]}],
        }

        pub = fetch_and_upsert_publication(sample_article, link_entities=True)
        self.assertEqual(pub.pmid, "41115454")
        self.assertEqual(pub.journal, "Nature")
        self.assertEqual(pub.year, 2025)
        self.assertEqual(pub.pub_date, datetime.date(2025, 12, 1))
        self.assertEqual(pub.first_author, "Tan PB")
        self.assertTrue(pub.interventions.filter(name="Nivolumab").exists())
        self.assertTrue(pub.interventions.filter(name="Ipilimumab").exists())
        self.assertTrue(pub.diseases.filter(name="Colonic Neoplasms").exists())
        self.assertTrue(PublicationTrial.objects.filter(publication=pub, trial=trial).exists())

        sample_article["journal"] = "Nature Medicine"
        updated_pub = fetch_and_upsert_publication(sample_article, link_entities=True)
        self.assertEqual(updated_pub.id, pub.id)
        self.assertEqual(updated_pub.journal, "Nature Medicine")

    def test_fetch_and_upsert_publication_ids(self):
        def article(pmid):
            return {"pmid": pmid, "title": f"Publication {pmid}"}

        with patch("lib.pubmed.PubMedFetcher") as fetcher:
            fetcher.return_value.article_by_pmid.side_effect = article
            publications = fetch_and_upsert_publication(["10000001", "10000002"])

        self.assertEqual([pub.pmid for pub in publications], ["10000001", "10000002"])
        self.assertEqual(Publication.objects.filter(pmid__in=["10000001", "10000002"]).count(), 2)
        self.assertEqual(fetch_and_upsert_publication([]), [])


def _response(data):
    from unittest.mock import Mock

    response = Mock()
    response.json.return_value = data
    return response
