from django.test import TestCase


class WorkspaceShellTestCase(TestCase):
    def test_workspace_shell(self):
        root = self.client.get('/')
        self.assertEqual(root['Content-Type'], 'application/json')
        page = self.client.get('/app/')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        for label in ['claims', 'diseases', 'interventions', 'trials', 'publications']:
            self.assertIn(label, html.lower())

    def test_workspace_shell_structure(self):
        html = self.client.get('/app/').content.decode()
        lowered = html.lower()
        # Search, filter, table and pane containers.
        self.assertIn('type="search"', lowered)
        self.assertIn('ws-filters', lowered)
        self.assertIn('<table', lowered)
        self.assertIn('<thead', lowered)
        self.assertIn('<tbody', lowered)
        self.assertIn('ws-upper', lowered)
        self.assertIn('ws-lower', lowered)
        self.assertIn('ws-detail', lowered)
        # Modal/dialog container.
        self.assertIn('<dialog', lowered)
        # Static asset references.
        self.assertIn('core/workspace.css', html)
        self.assertIn('core/workspace.js', html)
        # CSRF token for the same-origin PATCH.
        self.assertIn('csrfmiddlewaretoken', lowered)
        # Exactly one local stylesheet, no inline styles.
        self.assertEqual(lowered.count('<link'), 1)
        self.assertIn('rel="stylesheet"', lowered)
        self.assertNotIn('<style', lowered)
        self.assertNotIn('style=', lowered)
        self.assertNotIn('@import', lowered)
