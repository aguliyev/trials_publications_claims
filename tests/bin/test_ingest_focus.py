from unittest.mock import patch

from django.test import TestCase

from core.models import Focus, Publication, Trial
from jobs.ingest_focus import ingest_focus, run


class FocusIngestionJobTestCase(TestCase):
    @patch('jobs.ingest_focus.iter_trial_search_ids')
    @patch('jobs.ingest_focus.fetch_and_upsert_trial')
    def test_trials_skip_existing_and_decrement_only_successful_new_rows(
            self, fetch_trial, trial_ids):
        Trial.objects.create(nct_id='NCT00000001', title='Existing')
        focus = Focus.objects.create(query='colon cancer', ingest_trials_count=2)
        trial_ids.return_value = iter([
            'NCT00000001', 'NCT00000002', 'NCT00000003', 'NCT00000004',
        ])

        def save_trial(nct_id):
            if nct_id == 'NCT00000002':
                raise RuntimeError('temporary failure')
            return Trial.objects.create(nct_id=nct_id, title=nct_id)

        fetch_trial.side_effect = save_trial

        result = ingest_focus(focus)

        focus.refresh_from_db()
        trial_ids.assert_called_once_with('colon cancer')
        self.assertEqual(result['trials'], 2)
        self.assertEqual(focus.ingest_trials_count, 0)
        self.assertEqual(
            list(Trial.objects.order_by('nct_id').values_list('nct_id', flat=True)),
            ['NCT00000001', 'NCT00000003', 'NCT00000004'],
        )
        self.assertEqual(
            [call.args[0] for call in fetch_trial.call_args_list],
            ['NCT00000002', 'NCT00000003', 'NCT00000004'],
        )

    @patch('jobs.ingest_focus.iter_publication_search_ids')
    @patch('jobs.ingest_focus.fetch_and_upsert_publication')
    def test_publication_exhaustion_leaves_remainder_pending(self, fetch_publication, publication_ids):
        focus = Focus.objects.create(query='colon cancer', ingest_publications_count=3)
        publication_ids.return_value = iter(['100', '101'])
        fetch_publication.side_effect = lambda pmid: Publication.objects.create(pmid=pmid, title=pmid)

        result = ingest_focus(focus)

        focus.refresh_from_db()
        publication_ids.assert_called_once_with('colon cancer')
        self.assertEqual(result['publications'], 2)
        self.assertEqual(focus.ingest_publications_count, 1)

    @patch('jobs.ingest_focus.ingest_focus')
    def test_run_processes_only_focuses_with_pending_counts(self, process):
        inactive = Focus.objects.create(query='inactive')
        trial_focus = Focus.objects.create(query='trials', ingest_trials_count=1)
        publication_focus = Focus.objects.create(query='publications', ingest_publications_count=1)

        run()

        self.assertEqual(
            {call.args[0].pk for call in process.call_args_list},
            {trial_focus.pk, publication_focus.pk},
        )
        self.assertNotIn(inactive.pk, {call.args[0].pk for call in process.call_args_list})

    @patch('jobs.ingest_focus.iter_trial_search_ids')
    @patch('jobs.ingest_focus.fetch_and_upsert_trial')
    @patch('jobs.ingest_focus._decrement', side_effect=RuntimeError('interrupted'))
    def test_import_rolls_back_when_pending_decrement_fails(
            self, decrement, fetch_trial, trial_ids):
        focus = Focus.objects.create(query='rollback', ingest_trials_count=1)
        trial_ids.return_value = iter(['NCT00000999'])
        fetch_trial.side_effect = lambda nct_id: Trial.objects.create(
            nct_id=nct_id, title='Must roll back',
        )

        result = ingest_focus(focus)

        focus.refresh_from_db()
        self.assertEqual(result['trials'], 0)
        self.assertEqual(focus.ingest_trials_count, 1)
        self.assertFalse(Trial.objects.filter(nct_id='NCT00000999').exists())

    @patch('jobs.ingest_focus.iter_trial_search_ids')
    @patch('jobs.ingest_focus.fetch_and_upsert_trial')
    def test_duplicate_search_identifier_decrements_only_once(self, fetch_trial, trial_ids):
        focus = Focus.objects.create(query='duplicates', ingest_trials_count=2)
        trial_ids.return_value = iter(['NCT00000010', 'NCT00000010'])
        fetch_trial.side_effect = lambda nct_id: Trial.objects.create(nct_id=nct_id, title=nct_id)

        result = ingest_focus(focus)

        focus.refresh_from_db()
        self.assertEqual(result['trials'], 1)
        self.assertEqual(focus.ingest_trials_count, 1)
        fetch_trial.assert_called_once_with('NCT00000010')

    @patch('jobs.ingest_focus.iter_publication_search_ids')
    @patch('jobs.ingest_focus.fetch_and_upsert_publication')
    def test_importer_returning_without_row_does_not_decrement(
            self, fetch_publication, publication_ids):
        focus = Focus.objects.create(query='missing save', ingest_publications_count=1)
        publication_ids.return_value = iter(['900'])
        fetch_publication.return_value = None

        result = ingest_focus(focus)

        focus.refresh_from_db()
        self.assertEqual(result['publications'], 0)
        self.assertEqual(focus.ingest_publications_count, 1)
        self.assertFalse(Publication.objects.filter(pmid='900').exists())

    @patch('jobs.ingest_focus.fetch_and_upsert_publication')
    @patch('jobs.ingest_focus.iter_publication_search_ids')
    @patch('jobs.ingest_focus.iter_trial_search_ids', side_effect=RuntimeError('search unavailable'))
    def test_trial_search_failure_leaves_count_and_still_processes_publications(
            self, trial_ids, publication_ids, fetch_publication):
        focus = Focus.objects.create(
            query='independent sources',
            ingest_trials_count=1,
            ingest_publications_count=1,
        )
        publication_ids.return_value = iter(['901'])
        fetch_publication.side_effect = lambda pmid: Publication.objects.create(
            pmid=pmid, title=pmid,
        )

        result = ingest_focus(focus)

        focus.refresh_from_db()
        self.assertEqual(result, {'trials': 0, 'publications': 1})
        self.assertEqual(focus.ingest_trials_count, 1)
        self.assertEqual(focus.ingest_publications_count, 0)

    def test_job_does_not_expose_related_publication_fetcher(self):
        import jobs.ingest_focus as job_module

        self.assertFalse(hasattr(job_module, 'fetch_trial_publications'))
