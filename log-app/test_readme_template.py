"""MVP-03: a new project's LOG_README.md records identity, ownership, scope and access as v0.1 §4 and §7 describe."""
import re
import tempfile
import unittest
from pathlib import Path
import server

SECTIONS = ['Purpose', 'Owner', 'Collaborators', 'Parent Project', 'Child Projects', 'Scope', 'Out of Scope',
            'Permissions', 'Information Sharing', 'Expected Structure', 'Operating Rules', 'Created']


class ReadmeTemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        server.ROOT = Path(self.tmp.name, 'LOG').resolve(); server.ROOT.mkdir()
        server.init_history()

    def root(self):
        (server.ROOT / 'LOG_README.md').write_text('# LOG\n\n## Purpose\n\nRoot.\n\n## Owner\n\nLoghlen Rickard (single user on this Mac).\n')
        (server.ROOT / 'LOG_STATUS.md').write_text('# LOG\n\n## Lifecycle\n\nActive.\n')
        (server.ROOT / 'LOG_PROJECT.md').write_text('# LOG\n')
        (server.ROOT / 'LOG-AI-RULES.md').write_text('# LOG rules for AI assistants\n')

    def readme(self, project):
        return (server.ROOT / project / 'LOG_README.md').read_text()

    def section(self, text, name):
        m = re.search(r'^## ' + re.escape(name) + r'\n\n(.*?)(?=\n## |\Z)', text, re.S | re.M)
        return m.group(1).strip() if m else None

    def test_all_identity_sections_are_recorded(self):
        self.root()
        server.create_project('Taxes 2026', 'File the 2026 tax return.', '')
        text = self.readme('Taxes 2026')
        self.assertTrue(text.startswith('# Taxes 2026\n'))
        self.assertEqual(re.findall(r'^## (.+)$', text, re.M), SECTIONS)
        self.assertEqual(self.section(text, 'Purpose'), 'File the 2026 tax return.')
        self.assertEqual(self.section(text, 'Owner'), 'Loghlen Rickard (single user on this Mac).')  # from the root project
        self.assertEqual(self.section(text, 'Collaborators'), 'None recorded.')
        self.assertEqual(self.section(text, 'Parent Project'), '[LOG](../LOG_README.md) (the root LOG project)')
        self.assertIn('Not yet defined', self.section(text, 'Out of Scope'))
        self.assertIn('no separate access is configured', self.section(text, 'Permissions'))
        self.assertIn('only if this project is turned on under Connected AI', self.section(text, 'Permissions'))
        self.assertIn('[LOG\'s rules for AI assistants](../LOG-AI-RULES.md)', self.section(text, 'Operating Rules'))
        self.assertRegex(self.section(text, 'Created'), r'^\d{4}-\d{2}-\d{2} · Project ID: [0-9a-f]{16}$')
        for link in re.findall(r'\]\(([^)]+)\)', text):  # every link resolves from the project folder
            self.assertTrue((server.ROOT / 'Taxes 2026' / link).resolve().exists(), link)

    def test_child_inherits_owner_and_takes_given_details(self):
        self.root()
        server.create_project('Home', 'Run the household.', '', owner='Alex Example', collaborators='Sam (partner)')
        server.create_project('Garden', 'Plan the garden.', 'Home', scope='Plants and tools', out_of_scope='House repairs')
        text = self.readme('Home/Garden')
        self.assertEqual(self.section(text, 'Owner'), 'Alex Example')  # from its parent
        self.assertEqual(self.section(text, 'Scope'), 'Plants and tools')
        self.assertEqual(self.section(text, 'Out of Scope'), 'House repairs')
        self.assertEqual(self.section(text, 'Parent Project'), '[Home](../LOG_README.md)')
        self.assertIn('(../../LOG-AI-RULES.md)', text)
        self.assertEqual(self.section(self.readme('Home'), 'Collaborators'), 'Sam (partner)')
        for link in re.findall(r'\]\(([^)]+)\)', text):
            self.assertTrue((server.ROOT / 'Home/Garden' / link).resolve().exists(), link)

    def test_without_a_root_project(self):
        server.create_project('Solo', 'Stand alone.', '')
        text = self.readme('Solo')
        self.assertEqual(self.section(text, 'Owner'), 'Not recorded.')
        self.assertIn('None. This is a top-level project', self.section(text, 'Parent Project'))
        self.assertNotIn('LOG-AI-RULES.md', text)

    def test_details_are_checked(self):
        self.root()
        with self.assertRaises(ValueError): server.create_project('A', 'p', '', owner='two\nlines')
        with self.assertRaises(ValueError): server.create_project('B', 'p', '', collaborators='x' * 2001)
        with self.assertRaises(ValueError): server.create_project('C', 'p', '', scope=7)
        self.assertFalse((server.ROOT / 'A').exists())


if __name__ == '__main__': unittest.main()
