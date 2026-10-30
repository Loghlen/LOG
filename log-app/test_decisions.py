"""MVP-10: pending decisions are identified from the files: unanswered choices only, never suggestions or settled decisions."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import decisions
import server

STATUS = """# Trip — Current Status

## Summary

Planning.

## Lifecycle

Active.

## Suggestions

- Maybe add a day in Naples.

## Pending Decisions

1. Fly early or take the noon train
   from London to Paris?
2. Take the train to Florence after Rome?

## Next Actions

1. Compare fares.
"""
PROJECT = """# Trip — Durable Memory

## Confirmed Decisions

### 2026-10-20: Take the train to Florence

Decision: Travel from Rome to Florence by train.

Source: chat, 2026-10-20.

## Lessons Learned

- Book early.
"""


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        server.ROOT = Path(self.tmp.name, 'LOG').resolve(); server.ROOT.mkdir()
        server.init_history()
        server.create_project('Trip', 'Plan a trip', '')
        (server.ROOT / 'Trip/LOG_STATUS.md').write_text(STATUS)
        (server.ROOT / 'Trip/LOG_PROJECT.md').write_text(PROJECT)

    def trip(self, **kw):
        return next(p for p in decisions.overview(server, **kw)['projects'] if p['id'] == 'Trip')

    def test_only_unanswered_choices_are_pending(self):
        t = self.trip()
        self.assertEqual([i['text'] for i in t['pending']],
                         ['Fly early or take the noon train from London to Paris?', 'Take the train to Florence after Rome?'])
        self.assertEqual(t['pending'][0]['line'], 17)
        self.assertNotIn('Naples', json.dumps(t))  # a suggestion is neither pending nor decided
        self.assertEqual([(d['date'], d['title'], d['decision']) for d in t['confirmed']],
                         [('2026-10-20', 'Take the train to Florence', 'Travel from Rome to Florence by train.')])

    def test_a_pending_item_that_looks_decided_is_flagged(self):
        t = self.trip()
        self.assertIsNone(t['pending'][0]['possiblyDecided'])
        self.assertEqual(t['pending'][1]['possiblyDecided'], {'date': '2026-10-20', 'title': 'Take the train to Florence'})

    def test_related_but_different_questions_are_not_flagged(self):
        status = '## Pending Decisions\n\n- Should the built-in OpenAI chat stay as LOG\'s main AI interface now that the LOG connection lets any assistant that supports MCP work with LOG?\n'
        durable = '## Decisions\n\n### 2026-10-19: Let any AI assistant work with LOG through a connection\n\nDecision: Build a connection that any AI assistant supporting MCP can use.\n'
        p = decisions.project({'id': '.', 'name': 'LOG', 'docs': {'LOG_STATUS.md': status, 'LOG_PROJECT.md': durable}})
        self.assertIsNone(p['pending'][0]['possiblyDecided'])

    def test_prose_and_empty_sections(self):
        p = decisions.project({'id': 'x', 'name': 'X', 'docs': {'LOG_STATUS.md': '## Pending Decisions\n\nNone at the moment.\n', 'LOG_PROJECT.md': ''}})
        self.assertEqual((p['pending'], p['note'], p['confirmed']), ([], 'None at the moment.', []))
        p = decisions.project({'id': 'y', 'name': 'Y', 'docs': {'LOG_STATUS.md': '```\n## Pending Decisions\n- fenced\n```\n', 'LOG_PROJECT.md': ''}})
        self.assertEqual(p['pending'], [])

    def test_archived_projects_follow_show_archived(self):
        server.create_project('Old', 'Finished work', '')
        server.create_project('Still going', 'Active child', 'Old')
        (server.ROOT / 'Old/LOG_STATUS.md').write_text('## Lifecycle\n\nArchived.\n\n## Pending Decisions\n\n- Anything left?\n')
        ids = [p['id'] for p in decisions.overview(server)['projects']]
        self.assertNotIn('Old', ids); self.assertIn('Old/Still going', ids)
        self.assertIn('Old', [p['id'] for p in decisions.overview(server, show_archived=True)['projects']])
        self.assertEqual(decisions.overview(server)['pendingCount'], 2 + 1)  # Trip's two and the active child's default one

    def test_http_route(self):
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close); self.addCleanup(httpd.shutdown)
        c = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
        c.request('GET', '/api/decisions', headers={'Host': '127.0.0.1:%d' % httpd.server_port})
        r = c.getresponse(); body = json.loads(r.read()); c.close()
        self.assertEqual(r.status, 200); self.assertEqual(body['pendingCount'], 2)


if __name__ == '__main__': unittest.main()
