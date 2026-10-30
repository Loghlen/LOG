"""MVP-07: folders inside a project that are not projects can be browsed, previewed or opened in their own apps."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
import server


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        server.ROOT = Path(self.tmp.name, 'LOG').resolve(); server.ROOT.mkdir()
        server.init_history()
        server.create_project('Trip', 'Plan a trip', '')
        server.create_project('Child', 'A child project', 'Trip')
        base = server.ROOT / 'Trip'
        (base / 'documents').mkdir(); (base / 'documents' / 'notes.md').write_text('# Notes\n\nPacking list.\n')
        (base / 'documents' / 'booking.pdf').write_bytes(b'%PDF-1.4 test')
        (base / 'documents' / 'run.command').write_text('#!/bin/sh\necho hi\n')
        (base / 'research' / '2026').mkdir(parents=True); (base / 'research' / '2026' / 'fares.csv').write_text('route,price\nRome,100\n')
        (base / 'research' / 'empty').mkdir()
        (base / '.hidden').mkdir(); (base / '.hidden' / 'secret.md').write_text('no\n')
        (base / 'linked').symlink_to(base / 'documents')

    def trip(self):
        return next(p for p in server.catalog()['projects'] if p['id'] == 'Trip')

    def test_non_project_folders_are_listed_with_their_files(self):
        folders = self.trip()['folders']
        self.assertEqual([f['name'] for f in folders], ['documents', 'research'])  # not the child project, hidden or linked folders
        docs = folders[0]
        self.assertEqual([f['name'] for f in docs['files']], ['booking.pdf', 'notes.md', 'run.command'])
        by_name = {f['name']: f for f in docs['files']}
        self.assertTrue(by_name['notes.md']['previewable']); self.assertFalse(by_name['booking.pdf']['previewable'])
        self.assertTrue(by_name['booking.pdf']['openable']); self.assertFalse(by_name['run.command']['openable'])
        research = folders[1]
        self.assertEqual([f['name'] for f in research['folders']], ['2026', 'empty'])
        self.assertEqual(research['folders'][0]['files'][0]['path'], 'Trip/research/2026/fares.csv')
        child = next(p for p in server.catalog()['projects'] if p['id'] == 'Trip/Child')
        self.assertEqual(child['folders'], [])

    def test_nested_text_files_preview(self):
        self.assertIn('Packing list.', server.file_view('Trip/documents/notes.md')['content'])
        self.assertIn('Rome,100', server.file_view('Trip/research/2026/fares.csv')['content'])

    def test_open_and_show_in_finder(self):
        calls = []
        def fake_run(args, **kw):
            calls.append(args); return mock.Mock(returncode=0)
        with mock.patch.object(server, 'NATIVE_OPEN', ['/usr/bin/open']), mock.patch.object(server.subprocess, 'run', side_effect=fake_run):
            server.open_native('Trip/documents/booking.pdf')
            server.open_native('Trip/documents/run.command', reveal=True)
            with self.assertRaises(ValueError): server.open_native('Trip/documents/run.command')  # never run a script
            for bad in ('Trip/.hidden/secret.md', 'Trip/linked/notes.md', '../outside.pdf', 'Trip/documents', 'Trip/missing.pdf', ''):
                with self.assertRaises((ValueError, FileNotFoundError)): server.open_native(bad)
        self.assertEqual(calls, [['/usr/bin/open', str(server.ROOT / 'Trip/documents/booking.pdf')],
                                 ['/usr/bin/open', '-R', str(server.ROOT / 'Trip/documents/run.command')]])
        with mock.patch.object(server, 'NATIVE_OPEN', None):
            with self.assertRaisesRegex(ValueError, 'works on a Mac'): server.open_native('Trip/documents/booking.pdf')

    def test_open_needs_a_same_origin_app_request(self):
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close); self.addCleanup(httpd.shutdown)
        def post(headers):
            c = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
            c.request('POST', '/api/open', json.dumps({'path': 'Trip/documents/booking.pdf'}), headers)
            r = c.getresponse(); r.read(); c.close(); return r.status
        host = '127.0.0.1:%d' % httpd.server_port
        self.assertEqual(post({'Host': host, 'Content-Type': 'application/json'}), 403)
        self.assertEqual(post({'Host': host, 'Content-Type': 'application/json', 'X-LOG-Request': '1', 'Origin': 'https://evil.example'}), 403)
        with mock.patch.object(server, 'NATIVE_OPEN', None):
            self.assertEqual(post({'Host': host, 'Content-Type': 'application/json', 'X-LOG-Request': '1'}), 400)


if __name__ == '__main__': unittest.main()
