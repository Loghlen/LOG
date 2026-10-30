"""LOG connection tests: a real HTTP listener, real OAuth flow, real Git; disposable folders only."""
import base64
import hashlib
import http.client
import json
import re
import secrets
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
import connection
import chat_service as chat
import server

PASSWORD = 'correct horse battery staple'
REDIRECT = 'https://assistant.example/callback'

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        server.ROOT = Path(self.tmp.name, 'LOG').resolve(); server.ROOT.mkdir()
        server.init_history()
        server.create_project('Family', 'Parent project', '')
        server.create_project('Italy', 'Plan Italy', 'Family')
        server.create_project('Secret', 'Never show me', 'Family')
        self.status = 'Family/Italy/LOG_STATUS.md'
        (server.ROOT / 'Family/Secret/LOG_STATUS.md').write_text('# Status\n\nclassified-phrase\n')
        server.save(self.status, '# Italy — Current Status\n\n## Summary\n\nfour nights in Rome\n\n## Lifecycle\n\nActive.\n\n## Confirmed preference\n- Vegetarian meals. Source: chat.\n\n## Next actions\n- Compare trains.\n',
                    server.file_view(self.status)['version'])
        handler = type('H', (connection.Handler,), {})
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.port = self.httpd.server_port; self.base = 'http://127.0.0.1:%d' % self.port
        self.conn = connection.Connection(server, chat, self.base, Path(self.tmp.name, 'state', 'connection.json'))
        handler.conn = self.conn; server.CONNECTION = self.conn
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close); self.addCleanup(self.httpd.shutdown)
        self.addCleanup(setattr, server, 'CONNECTION', None)

    # ---- HTTP helpers ----
    def request(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse(); data = r.read(); c.close()
        return r.status, dict(r.getheaders()), data
    def post_form(self, path, fields, headers=None):
        return self.request('POST', path, urlencode(fields), dict({'Content-Type': 'application/x-www-form-urlencoded'}, **(headers or {})))
    def post_json(self, path, value, token=None, headers=None):
        h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if token: h['Authorization'] = 'Bearer ' + token
        h.update(headers or {})
        return self.request('POST', path, json.dumps(value), h)

    def register(self, **extra):
        body = dict({'redirect_uris': [REDIRECT], 'client_name': 'Test AI', 'token_endpoint_auth_method': 'none'}, **extra)
        status, _, data = self.post_json('/register', body)
        self.assertEqual(status, 201, data); return json.loads(data)
    def sign_in(self, client_id=None, redirect=REDIRECT, password=PASSWORD):
        if not self.conn.password_set(): self.conn.set_password(PASSWORD)
        client_id = client_id or self.register()['client_id']
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        q = {'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect, 'code_challenge': challenge,
             'code_challenge_method': 'S256', 'state': 'xyz', 'scope': 'log', 'resource': self.base + '/mcp'}
        status, _, page = self.request('GET', '/authorize?' + urlencode(q))
        self.assertEqual(status, 200, page)
        request_id = re.search(r'name="request" value="([^"]+)"', page.decode()).group(1)
        status, _, page = self.post_form('/authorize', {'request': request_id, 'action': 'password', 'password': password})
        self.assertIn(b'6-digit code', page)
        request_id = re.search(r'name="request" value="([^"]+)"', page.decode()).group(1)
        code = self.conn.app_status()['signins'][0]['code']
        status, headers, _ = self.post_form('/authorize', {'request': request_id, 'action': 'code', 'code': code})
        self.assertEqual(status, 302)
        location = urlparse(headers['Location']); params = parse_qs(location.query)
        self.assertEqual(params['state'], ['xyz']); self.assertEqual(params['iss'], [self.base])
        return client_id, verifier, params['code'][0], redirect
    def tokens(self, client_id=None):
        client_id, verifier, code, redirect = self.sign_in(client_id)
        status, _, data = self.post_form('/token', {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect,
                                                     'client_id': client_id, 'code_verifier': verifier, 'resource': self.base + '/mcp'})
        self.assertEqual(status, 200, data); t = json.loads(data); t['client_id'] = client_id; return t
    def rpc(self, token, method, params=None, mid=1):
        status, _, data = self.post_json('/mcp', {'jsonrpc': '2.0', 'id': mid, 'method': method, 'params': params or {}}, token)
        self.assertEqual(status, 200, data); return json.loads(data)
    def tool(self, token, name, **args):
        r = self.rpc(token, 'tools/call', {'name': name, 'arguments': args})['result']
        return r, r['content'][0]['text']
    def grant(self, *projects):
        self.conn.set_grants(list(projects), self.conn.access_doc()[1])

    # ---- discovery and sign-in ----
    def test_unauthenticated_request_points_to_metadata(self):
        status, headers, _ = self.post_json('/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
        self.assertEqual(status, 401)
        self.assertIn('resource_metadata="%s/.well-known/oauth-protected-resource"' % self.base, headers['WWW-Authenticate'])
        self.assertIn('scope="log"', headers['WWW-Authenticate'])
        for path in ('/.well-known/oauth-protected-resource', '/.well-known/oauth-protected-resource/mcp'):
            meta = json.loads(self.request('GET', path)[2])
            self.assertEqual((meta['resource'], meta['authorization_servers']), (self.base + '/mcp', [self.base]))
        meta = json.loads(self.request('GET', '/.well-known/oauth-authorization-server')[2])
        self.assertEqual(meta['code_challenge_methods_supported'], ['S256'])
        self.assertEqual(meta['registration_endpoint'], self.base + '/register')

    def test_full_sign_in_initialize_and_tool_list(self):
        t = self.tokens()
        (server.ROOT / 'LOG-AI-RULES.md').write_text('# LOG rules for AI assistants\n\nRule text.\n')
        r = self.rpc(t['access_token'], 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'x', 'version': '1'}})['result']
        self.assertEqual(r['protocolVersion'], '2025-06-18'); self.assertIn('tools', r['capabilities'])
        self.assertIn('the user approves or rejects in the LOG app', r['instructions'])
        self.assertIn('# LOG rules for AI assistants', r['instructions'])
        status, _, body = self.post_json('/mcp', {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, t['access_token'])
        self.assertEqual((status, body), (202, b''))
        names = [x['name'] for x in self.rpc(t['access_token'], 'tools/list')['result']['tools']]
        self.assertEqual(names, ['get_rules', 'list_projects', 'open_project', 'read_file', 'search', 'list_pending', 'propose_change', 'propose_memory_update', 'propose_project', 'propose_session_record'])
        self.assertEqual(self.rpc(t['access_token'], 'ping')['result'], {})
        r = self.rpc(t['access_token'], 'initialize', {'protocolVersion': '1999-01-01'})['result']
        self.assertEqual(r['protocolVersion'], connection.PROTOCOL_VERSIONS[0])

    def test_password_and_code_are_both_required(self):
        self.conn.set_password(PASSWORD); client = self.register()['client_id']
        q = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43, 'code_challenge_method': 'S256', 'state': 's'}
        page = self.request('GET', '/authorize?' + urlencode(q))[2].decode()
        rid = re.search(r'name="request" value="([^"]+)"', page).group(1)
        self.assertIn('assistant.example', page)
        page = self.post_form('/authorize', {'request': rid, 'action': 'password', 'password': 'wrong password!!'})[2]
        self.assertIn(b'not correct', page); self.assertEqual(self.conn.app_status()['signins'], [])
        status, _, _ = self.post_form('/authorize', {'request': rid, 'action': 'code', 'code': '000000'})
        self.assertEqual(status, 400)
        tampered = rid[:-1] + ('0' if rid[-1] != '0' else '1')
        self.assertIn(b'not valid', self.post_form('/authorize', {'request': tampered, 'action': 'password', 'password': PASSWORD})[2])
        page = self.post_form('/authorize', {'request': rid, 'action': 'password', 'password': PASSWORD})[2].decode()
        step = re.search(r'name="request" value="([^"]+)"', page).group(1)
        self.assertNotEqual(step, rid)
        for _ in range(4): self.assertIn(b'not correct', self.post_form('/authorize', {'request': step, 'action': 'code', 'code': 'xxxxxx'})[2])
        self.assertIn(b'Too many wrong codes', self.post_form('/authorize', {'request': step, 'action': 'code', 'code': 'xxxxxx'})[2])

    def test_wrong_passwords_lock_sign_in(self):
        self.conn.set_password(PASSWORD); client = self.register()['client_id']
        q = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43, 'code_challenge_method': 'S256'}
        for i in range(connection.LOCK_AFTER):
            page = self.request('GET', '/authorize?' + urlencode(q))[2].decode()
            rid = re.search(r'name="request" value="([^"]+)"', page).group(1)
            self.post_form('/authorize', {'request': rid, 'action': 'password', 'password': 'nope nope nope'})
        page = self.request('GET', '/authorize?' + urlencode(q))[2].decode()
        rid = re.search(r'name="request" value="([^"]+)"', page).group(1)
        status, _, body = self.post_form('/authorize', {'request': rid, 'action': 'password', 'password': PASSWORD})
        self.assertEqual(status, 429); self.assertIn(b'Too many wrong passwords', body)

    def test_no_password_set_blocks_sign_in(self):
        client = self.register()['client_id']
        q = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43, 'code_challenge_method': 'S256'}
        status, _, page = self.request('GET', '/authorize?' + urlencode(q))
        self.assertEqual(status, 403); self.assertIn(b'Set a password first', page)
        with self.assertRaises(ValueError): self.conn.set_password('short')

    def test_authorization_request_validation(self):
        self.conn.set_password(PASSWORD); client = self.register()['client_id']
        good = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43, 'code_challenge_method': 'S256'}
        for change in ({'redirect_uri': 'https://evil.example/cb'}, {'code_challenge_method': 'plain'}, {'code_challenge': ''},
                       {'client_id': 'unknown'}, {'response_type': 'token'}, {'resource': 'https://other.example/mcp'}):
            status, _, _ = self.request('GET', '/authorize?' + urlencode(dict(good, **change)))
            self.assertIn(status, (400, 401), change)

    def test_rules_are_readable_whatever_projects_are_on(self):
        token = self.tokens()['access_token']  # no projects turned on
        r, text = self.tool(token, 'get_rules')
        self.assertTrue(r['isError']); self.assertIn('no rules file', text)
        (server.ROOT / 'LOG-AI-RULES.md').write_text('# LOG rules for AI assistants\n\nAnswer from the files.\n')
        r, text = self.tool(token, 'get_rules')
        self.assertFalse(r['isError']); self.assertIn('Answer from the files.', text)
        self.assertEqual(r['structuredContent']['path'], 'LOG-AI-RULES.md')
        self.assertIn('call get_rules first', self.tool(token, 'list_projects')[1])
        self.grant('Family/Italy')
        self.assertIn('call get_rules first', self.tool(token, 'open_project', project='Family/Italy')[1])
        self.assertTrue(self.tool(token, 'read_file', path='LOG-AI-RULES.md')[0]['isError'])  # only through get_rules
        outside = Path(self.tmp.name, 'outside.md'); outside.write_text('secret outside the folder\n')
        (server.ROOT / 'LOG-AI-RULES.md').unlink(); (server.ROOT / 'LOG-AI-RULES.md').symlink_to(outside)
        r, text = self.tool(token, 'get_rules')
        self.assertTrue(r['isError']); self.assertNotIn('secret', text)

    def test_refresh_scope_requests_are_accepted(self):
        meta = json.loads(self.request('GET', '/.well-known/oauth-authorization-server')[2])
        self.assertIn('offline_access', meta['scopes_supported'])
        self.conn.set_password(PASSWORD); client = self.register()['client_id']
        for scope in ('log offline_access', 'offline_access', 'openid log'):
            q = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43,
                 'code_challenge_method': 'S256', 'scope': scope}
            self.assertEqual(self.request('GET', '/authorize?' + urlencode(q))[0], 200, scope)
        t = self.tokens(); self.assertIn('refresh_token', t); self.assertIn('log', t['scope'].split())

    def test_registration_rejects_unsafe_redirects_and_loopback_any_port_works(self):
        for bad in (['http://evil.example/cb'], ['https://x.example/cb#frag'], [], ['javascript:alert(1)']):
            status, _, data = self.post_json('/register', {'redirect_uris': bad})
            self.assertEqual(status, 400, bad); self.assertEqual(json.loads(data)['error'], 'invalid_redirect_uri')
        client = self.register(redirect_uris=['http://127.0.0.1/callback'])['client_id']
        cid, verifier, code, redirect = self.sign_in(client, redirect='http://127.0.0.1:53111/callback')
        self.assertEqual(redirect, 'http://127.0.0.1:53111/callback')

    def test_token_exchange_checks(self):
        client_id, verifier, code, redirect = self.sign_in()
        base = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect, 'client_id': client_id}
        self.assertEqual(json.loads(self.post_form('/token', dict(base, code_verifier='x' * 50))[2])['error'], 'invalid_grant')
        # The code was consumed by the failed attempt: it can never be replayed.
        self.assertEqual(json.loads(self.post_form('/token', dict(base, code_verifier=verifier))[2])['error'], 'invalid_grant')
        client_id, verifier, code, redirect = self.sign_in()
        self.assertEqual(json.loads(self.post_form('/token', {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': 'https://other/cb',
                                                               'client_id': client_id, 'code_verifier': verifier})[2])['error'], 'invalid_grant')
        self.assertEqual(json.loads(self.post_form('/token', {'grant_type': 'password'} | {'client_id': client_id})[2])['error'], 'unsupported_grant_type')

    def test_refresh_rotation_and_reuse_revokes(self):
        t = self.tokens()
        status, _, data = self.post_form('/token', {'grant_type': 'refresh_token', 'refresh_token': t['refresh_token'], 'client_id': t['client_id']})
        new = json.loads(data); self.assertEqual(status, 200); self.assertNotEqual(new['refresh_token'], t['refresh_token'])
        self.rpc(new['access_token'], 'ping')
        status, _, data = self.post_form('/token', {'grant_type': 'refresh_token', 'refresh_token': t['refresh_token'], 'client_id': t['client_id']})
        self.assertEqual(json.loads(data)['error'], 'invalid_grant')
        self.assertEqual(self.post_json('/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, new['access_token'])[0], 401)

    def test_expired_and_disconnected_tokens_are_refused(self):
        t = self.tokens()
        for record in self.conn.state.data['access'].values(): record['expires'] = 0
        status, headers, _ = self.post_json('/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, t['access_token'])
        self.assertEqual(status, 401); self.assertIn('invalid_token', headers['WWW-Authenticate'])
        t = self.tokens()
        self.assertEqual(len(self.conn.app_status()['clients']), 2)
        self.conn.disconnect(t['client_id'])
        self.assertEqual(self.post_json('/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, t['access_token'])[0], 401)

    def test_confidential_client_needs_its_secret(self):
        reg = self.register(token_endpoint_auth_method='client_secret_post')
        client_id, verifier, code, redirect = self.sign_in(reg['client_id'])
        form = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect, 'client_id': client_id, 'code_verifier': verifier}
        status, _, data = self.post_form('/token', dict(form, client_secret='wrong'))
        self.assertEqual(status, 401)
        client_id, verifier, code, redirect = self.sign_in(reg['client_id'])
        basic = base64.b64encode(('%s:%s' % (client_id, reg['client_secret'])).encode()).decode()
        status, _, data = self.post_form('/token', {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect, 'code_verifier': verifier},
                                         {'Authorization': 'Basic ' + basic})
        self.assertEqual(status, 200, data)

    def test_origin_host_version_and_methods(self):
        t = self.tokens()
        msg = {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}
        self.assertEqual(self.post_json('/mcp', msg, t['access_token'], {'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.post_json('/mcp', msg, t['access_token'], {'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.post_json('/mcp', msg, t['access_token'], {'MCP-Protocol-Version': '2000-01-01'})[0], 400)
        self.assertEqual(self.post_json('/mcp', msg, t['access_token'], {'MCP-Protocol-Version': '2025-06-18'})[0], 200)
        self.assertEqual(self.request('GET', '/mcp')[0], 405)
        self.assertEqual(self.request('GET', '/api/projects')[0], 404)
        self.assertEqual(self.rpc(t['access_token'], 'tools/call', {'name': 'delete_everything'})['error']['code'], -32602)
        self.assertEqual(self.rpc(t['access_token'], 'resources/list')['error']['code'], -32601)
        status, _, data = self.request('POST', '/mcp', 'not json', {'Authorization': 'Bearer ' + t['access_token']})
        self.assertEqual((status, json.loads(data)['error']['code']), (400, -32700))

    # ---- access and tools ----
    def test_only_granted_projects_are_visible(self):
        token = self.tokens()['access_token']
        r, text = self.tool(token, 'list_projects'); self.assertIn('No projects are turned on', text)
        self.grant('Family/Italy')
        r, text = self.tool(token, 'list_projects')
        self.assertEqual([p['project'] for p in r['structuredContent']['projects']], ['Family/Italy'])
        self.assertIsNone(r['structuredContent']['projects'][0]['parent'])
        self.assertEqual(r['structuredContent']['projects'][0]['lifecycle'], 'Active.')
        for project in ('Family', 'Family/Secret', '../x', '.'):
            self.assertTrue(self.tool(token, 'open_project', project=project)[0]['isError'], project)
        for path in ('Family/Secret/LOG_STATUS.md', 'Family/LOG_README.md', '../outside.md', '.git/config', 'LOG-ACCESS.json'):
            self.assertTrue(self.tool(token, 'read_file', path=path)[0]['isError'], path)
        r, text = self.tool(token, 'open_project', project='Family/Italy')
        self.assertFalse(r['isError']); self.assertIn('four nights in Rome', text); self.assertIn('Confirmed Decisions', text)
        self.assertNotIn('Never show me', text)
        r, text = self.tool(token, 'read_file', path=self.status)
        self.assertEqual(r['structuredContent']['version'], server.file_view(self.status)['version'])
        self.assertEqual(self.tool(token, 'search', query='classified-phrase')[0]['structuredContent']['files'], [])
        self.assertEqual(self.tool(token, 'search', query='Never show me')[0]['structuredContent']['files'], [])
        hits = self.tool(token, 'search', query='four nights')[0]['structuredContent']['files']
        self.assertEqual([h['path'] for h in hits], [self.status])
        self.assertTrue(self.tool(token, 'search', query='Rome', project='Family/Secret')[0]['isError'])

    def test_propose_change_waits_for_approval_then_applies(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        version = server.file_view(self.status)['version']; before = (server.ROOT / self.status).read_text()
        new = before.replace('Compare trains.', 'Compare trains and buses.')
        r, text = self.tool(token, 'propose_change', project='Family/Italy', path=self.status, content=new, reason='User asked to add buses.', base_version='stale')
        self.assertTrue(r['isError']); self.assertIn('changed since you read it', text)
        r, text = self.tool(token, 'propose_change', project='Family/Italy', path=self.status, content=new, reason='User asked to add buses.', base_version=version)
        self.assertFalse(r['isError'], text); self.assertIn('Nothing has changed yet', text)
        self.assertEqual((server.ROOT / self.status).read_text(), before)
        pending = chat.approvals(server)
        self.assertEqual([(p['source'], p['path'], p['status']) for p in pending], [('Test AI', self.status, 'pending')])
        listed = self.tool(token, 'list_pending')[0]['structuredContent']['pending']
        self.assertEqual(listed[0]['proposal'], pending[0]['proposal'])
        chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': pending[0]['conversation'], 'proposal': pending[0]['proposal'], 'decision': 'approve'})
        self.assertEqual((server.ROOT / self.status).read_text(), new)
        self.assertEqual(chat.approvals(server), [])
        decided = self.tool(token, 'list_pending')[0]['structuredContent']['decided']
        self.assertEqual(decided[0]['status'], 'approved')
        transcript = server.ROOT / 'Family/Italy/conversations' / (pending[0]['conversation'] + '.md')
        self.assertIn('Test AI, through the LOG connection', transcript.read_text())

    def test_proposal_scope_and_rejected_repeats(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy', 'Family/Secret')
        conv = server.ROOT / 'Family/Italy/notes'; conv.mkdir(); (conv / 'n.md').write_text('x\n')
        for path in ('Family/Italy/notes/n.md', 'Family/Secret/LOG_STATUS.md', 'Family/Italy/missing.md'):
            r, text = self.tool(token, 'propose_change', project='Family/Italy', path=path, content='y\n', reason='r', base_version='v')
            self.assertTrue(r['isError'], path)
        version = server.file_view(self.status)['version']; new = (server.ROOT / self.status).read_text() + '\nExtra line.\n'
        self.tool(token, 'propose_change', project='Family/Italy', path=self.status, content=new, reason='Add a line', base_version=version)
        p = chat.approvals(server)[0]
        chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': p['conversation'], 'proposal': p['proposal'], 'decision': 'reject'})
        r, text = self.tool(token, 'propose_change', project='Family/Italy', path=self.status, content=new, reason='Again', base_version=version)
        self.assertTrue(r['isError']); self.assertIn('already rejected', text)

    def test_memory_update_is_staged_and_never_loses_text(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        durable = 'Family/Italy/LOG_PROJECT.md'
        sv = server.file_view(self.status)['version']; dv = server.file_view(durable)['version']
        status_text = (server.ROOT / self.status).read_text(); durable_text = (server.ROOT / durable).read_text()
        cleaned = status_text.replace('## Confirmed preference\n- Vegetarian meals. Source: chat.\n\n', '')
        r, text = self.tool(token, 'propose_memory_update', project='Family/Italy', reason='Promote preference', status_content=cleaned, status_version=sv)
        self.assertTrue(r['isError']); self.assertIn('withheld', text)
        r, text = self.tool(token, 'propose_memory_update', project='Family/Italy', reason='Remove history',
                            project_content='# Durable Memory\n\nOnly this.\n', project_version=dv)
        self.assertTrue(r['isError'])
        promoted = durable_text + '\n## Confirmed preference\n- Vegetarian meals. Source: chat.\n'
        r, text = self.tool(token, 'propose_memory_update', project='Family/Italy', reason='Promote preference',
                            status_content=cleaned, status_version=sv, project_content=promoted, project_version=dv)
        self.assertFalse(r['isError'], text)
        pending = chat.approvals(server)
        self.assertEqual([p['path'] for p in pending], [durable])
        chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': pending[0]['conversation'], 'proposal': pending[0]['proposal'], 'decision': 'approve'})
        self.assertEqual((server.ROOT / self.status).read_text(), status_text)
        cleanup = chat.approvals(server)[0]; self.assertTrue(cleanup['needsCleanup'])
        result = chat.prepare_promotion_cleanup(server, {'project': 'Family/Italy', 'conversation': cleanup['conversation'], 'proposal': cleanup['proposal']})
        chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': cleanup['conversation'], 'proposal': result['proposal'], 'decision': 'approve'})
        self.assertEqual((server.ROOT / self.status).read_text(), cleaned)
        self.assertEqual((server.ROOT / durable).read_text(), promoted)

    def test_session_record_saved_only_on_approval(self):
        for name in server.CONTROL: (server.ROOT / name).write_text('# Root\n\n## Summary\n\nroot\n')
        token = self.tokens()['access_token']; self.grant('Family/Italy', '.')
        args = dict(project='Family/Italy', title='Train route chat', summary='We compared trains.\nRome first.',
                    decisions=['Take the train from Rome to Florence'], open_questions=['Venice or not?'],
                    next_steps=['Check fares'], files_consulted=[self.status])
        r, text = self.tool(token, 'propose_session_record', **args)
        self.assertFalse(r['isError'], text); self.assertIn('Nothing is saved yet', text)
        path = r['structuredContent']['path']
        self.assertRegex(path, r'^Family/Italy/conversations/session-\d{4}-\d{2}-\d{2}-train-route-chat\.md$')
        self.assertFalse((server.ROOT / path).exists())
        pending = chat.approvals(server)
        self.assertEqual([(p['kind'], p['path']) for p in pending], [('session', path)])
        r2, _ = self.tool(token, 'propose_session_record', **args)  # same title the same day gets its own file
        self.assertTrue(r2['structuredContent']['path'].endswith('-train-route-chat-2.md'))
        chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': pending[0]['conversation'], 'proposal': pending[0]['proposal'], 'decision': 'approve'})
        saved = (server.ROOT / path).read_text()
        for expected in ('# Session record: Train route chat', 'Test AI (its own name for itself)', '## Decisions the user confirmed',
                         '- Take the train from Rome to Florence', '- Venice or not?', 'We compared trains.\nRome first.'):
            self.assertIn(expected, saved)
        self.assertNotIn(path, [p['path'] for p in chat.approvals(server)])
        hits = self.tool(token, 'search', query='Take the train from Rome')[0]['structuredContent']['files']
        self.assertIn(path, [h['path'] for h in hits])
        self.assertIn(path, self.tool(token, 'open_project', project='Family/Italy')[1])
        other = [p for p in chat.approvals(server) if p['kind'] == 'session'][0]
        chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': other['conversation'], 'proposal': other['proposal'], 'decision': 'reject'})
        self.assertFalse((server.ROOT / other['path']).exists())
        r, text = self.tool(token, 'propose_session_record', project='.', title='Root work', summary='Root summary')
        self.assertTrue(r['structuredContent']['path'].startswith('conversations/session-'), text)

    def test_session_record_checks(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        self.assertTrue(self.tool(token, 'propose_session_record', project='Family/Secret', title='t', summary='s')[0]['isError'])
        self.assertTrue(self.tool(token, 'propose_session_record', project='Family/Italy', title='', summary='s')[0]['isError'])
        self.assertTrue(self.tool(token, 'propose_session_record', project='Family/Italy', title='t', summary='x' * 8001)[0]['isError'])
        self.assertTrue(self.tool(token, 'propose_session_record', project='Family/Italy', title='t', summary='s', next_steps=['a'] * 31)[0]['isError'])
        r, _ = self.tool(token, 'propose_session_record', project='Family/Italy', title='Ti\u202etle', summary='s\u200b', decisions=['line one\nline two'])
        p = chat.approvals(server)[0]
        conv = chat.read_conversation(server, 'Family/Italy', p['conversation'])
        content = conv['turns'][-1]['proposals'][0]['content']
        self.assertIn('# Session record: Title', content); self.assertIn('- line one line two', content); self.assertNotIn('\u200b', content)
        # A record whose stored location was changed after it was proposed is refused.
        raw = chat.conversation_path(server, 'Family/Italy', p['conversation'])
        doc = json.loads(raw.read_text()); doc['turns'][-1]['proposals'][0]['path'] = 'Family/Italy/LOG_STATUS.md'
        raw.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': p['conversation'], 'proposal': p['proposal'], 'decision': 'approve'})

    def test_new_project_created_only_on_approval(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        self.assertTrue(self.tool(token, 'propose_project', parent='Family', title='X', purpose='p', reason='r')[0]['isError'])
        self.assertTrue(self.tool(token, 'propose_project', parent='Family/Italy', title='../Bad', purpose='p', reason='r')[0]['isError'])
        r, text = self.tool(token, 'propose_project', parent='Family/Italy', title='Rome Hotels', purpose='Compare hotels in Rome', reason='Separate workstream')
        self.assertFalse(r['isError'], text)
        self.assertFalse((server.ROOT / 'Family/Italy/Rome Hotels').exists())
        p = chat.approvals(server)[0]; self.assertEqual(p['kind'], 'project')
        result = chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': p['conversation'], 'proposal': p['proposal'], 'decision': 'approve'})
        self.assertEqual(result['createdProject'], 'Family/Italy/Rome Hotels')
        self.assertTrue((server.ROOT / 'Family/Italy/Rome Hotels/LOG_README.md').exists())
        self.assertNotIn('Family/Italy/Rome Hotels', self.conn.grants())
        self.conn.add_grant(result['createdProject'])
        self.assertIn('Family/Italy/Rome Hotels', self.conn.grants())
        records = (server.ROOT / 'Family/Italy/reviews/LOG_REVIEWS.md').read_text()
        self.assertIn('Approved: Family/Italy/Rome Hotels', records)

    def test_access_file_is_versioned_and_conflict_checked(self):
        self.grant('Family/Italy')
        doc = json.loads((server.ROOT / connection.ACCESS_FILE).read_text())
        self.assertEqual(doc['connectedAI']['projects'], ['Family/Italy'])
        self.assertIn(connection.ACCESS_FILE, server.git('log', '--name-only', '-1').stdout.decode())
        with self.assertRaises(server.Conflict): self.conn.set_grants(['Family'], 'stale-version')
        with self.assertRaises(ValueError): self.conn.set_grants(['Nope'], self.conn.access_doc()[1])
        status = server.connection_status()
        self.assertEqual(status['grants'], ['Family/Italy']); self.assertEqual(len(status['projects']), 3)

    def test_secrets_never_stored_in_plain_text(self):
        t = self.tokens()
        state = self.conn.state.path.read_text()
        for secret in (t['access_token'], t['refresh_token'], PASSWORD): self.assertNotIn(secret, state)
        self.assertEqual(self.conn.state.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(str(self.conn.state.path).startswith(str(server.ROOT)))

    def test_built_in_chat_cannot_continue_a_connection_conversation(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        version = server.file_view(self.status)['version']
        self.tool(token, 'propose_change', project='Family/Italy', path=self.status, content='# New\n', reason='r', base_version=version)
        cid = chat.approvals(server)[0]['conversation']
        chat.KEY = 'sk-test-only-not-a-real-key'; self.addCleanup(setattr, chat, 'KEY', '')
        with self.assertRaises(ValueError):
            chat.chat(server, {'project': 'Family/Italy', 'message': 'hi', 'conversation': cid, 'sources': [], 'requestId': 'c' * 32})


    # ---- regressions from the security review, 2026-10-19 ----
    def test_redirect_addresses_must_read_the_same_in_every_browser(self):
        for bad in ('https://evil.example\\@claude.ai/api/mcp/auth_callback', 'https://user@claude.ai/cb', 'https://evil.example/cb\r\nSet-Cookie: x=1',
                    'https://evil.example/c b', 'https://claude.ai:99999/cb', 'https://éxample.com/cb', 'http://evil.example/cb',
                    'https://claude.ai/cb#frag', 'javascript:alert(1)', 'https:///cb', 'https://localhost.\t/cb', 'https://intranet/cb'):
            status, _, data = self.post_json('/register', {'redirect_uris': [bad]})
            self.assertEqual(status, 400, bad); self.assertIn(b'invalid_redirect_uri', data)
        for good in ('https://claude.ai/api/mcp/auth_callback', 'https://chatgpt.com/connector_platform_oauth_redirect',
                     'http://127.0.0.1/callback', 'http://localhost:33418/cb?x=1', 'http://[::1]:5000/cb'):
            status, _, data = self.post_json('/register', {'redirect_uris': [good]})
            self.assertEqual(status, 201, good)
        self.assertEqual(connection.redirect_host('http://localhost:33418/cb'), 'localhost:33418')
        self.assertFalse(connection.redirect_allowed('http://evil.example\\@127.0.0.1:9/cb', ['http://127.0.0.1/cb']))

    def test_letter_case_and_accent_variants_cannot_reach_other_projects(self):
        server.create_project('Café', 'Accent', 'Family')
        (server.ROOT / 'Family/Café/LOG_STATUS.md').write_text('# Status\n\naccent-phrase\n')
        token = self.tokens()['access_token']; self.grant('Family')
        import unicodedata
        for path in ('Family/Secret/LOG_STATUS.md', 'Family/secret/LOG_STATUS.md', 'Family/SECRET/LOG_STATUS.md',
                     unicodedata.normalize('NFD', 'Family/Café/LOG_STATUS.md'), 'Family/café/LOG_STATUS.md'):
            r, text = self.tool(token, 'read_file', path=path)
            self.assertTrue(r['isError'], path); self.assertNotIn('classified-phrase', text); self.assertNotIn('accent-phrase', text)
        r, text = self.tool(token, 'propose_change', project='Family', path='Family/secret/LOG_STATUS.md', content='x\n', reason='r', base_version='v')
        self.assertTrue(r['isError'])
        r, text = self.tool(token, 'read_file', path='family/log_readme.md')  # a variant of a granted file opens under its stored name
        self.assertFalse(r['isError'], text); self.assertEqual(r['structuredContent']['path'], 'Family/LOG_README.md')
        for title in ('secret', 'SECRET', unicodedata.normalize('NFD', 'café')):
            r, text = self.tool(token, 'propose_project', parent='Family', title=title, purpose='p', reason='r')
            self.assertTrue(r['isError'], title); self.assertIn('already exists', text)

    def test_search_leaves_out_archived_projects_unless_asked(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        text = (server.ROOT / self.status).read_text().replace('## Lifecycle\n\nActive.', '## Lifecycle\n\nArchived.')
        server.save(self.status, text, server.file_view(self.status)['version'])
        self.assertEqual(self.tool(token, 'search', query='four nights')[0]['structuredContent']['files'], [])
        hits = self.tool(token, 'search', query='four nights', include_archived=True)[0]['structuredContent']['files']
        self.assertEqual([h['path'] for h in hits], [self.status])
        self.assertIn('Archived', self.tool(token, 'list_projects')[1])

    def test_one_letter_project_is_not_part_of_the_root(self):
        for name in server.CONTROL: (server.ROOT / name).write_text('# Root\n\n## Summary\n\nroot\n')
        server.create_project('X', 'One letter', '')
        (server.ROOT / 'X/LOG_STATUS.md').write_text('# X\n\nx-only-phrase\n')
        self.assertEqual(server.project_of('X/LOG_STATUS.md', ['.', 'X']), 'X')
        self.assertEqual(server.project_of('notes.md', ['.', 'X']), '.')
        self.assertEqual(server.search('x-only-phrase')['files'][0]['project'], 'X')
        token = self.tokens()['access_token']; self.grant('.')
        self.assertTrue(self.tool(token, 'read_file', path='X/LOG_STATUS.md')[0]['isError'])
        self.assertEqual(self.tool(token, 'search', query='x-only-phrase')[0]['structuredContent']['files'], [])
        self.assertFalse(self.tool(token, 'read_file', path='LOG_STATUS.md')[0]['isError'])

    def test_parallel_wrong_passwords_cannot_get_past_the_lockout(self):
        self.conn.set_password(PASSWORD); client = self.register()['client_id']
        q = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43, 'code_challenge_method': 'S256'}
        rid = re.search(r'name="request" value="([^"]+)"', self.request('GET', '/authorize?' + urlencode(q))[2].decode()).group(1)
        results = []
        def guess(i):
            c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=120)
            c.request('POST', '/authorize', urlencode({'request': rid, 'action': 'password', 'password': 'wrong guess %03d!!' % i}),
                      {'Content-Type': 'application/x-www-form-urlencoded'})
            r = c.getresponse(); results.append((r.status, r.read())); c.close()
        threads = [threading.Thread(target=guess, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()
        checked = sum(1 for _, body in results if b'That password is not correct' in body)
        self.assertEqual(checked, connection.LOCK_AFTER)
        self.assertEqual(sum(1 for status, _ in results if status == 429), 20 - connection.LOCK_AFTER)

    def test_strangers_cannot_fill_up_sign_in_or_registration(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        client = self.register()['client_id']
        q = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43, 'code_challenge_method': 'S256'}
        for _ in range(60): self.assertEqual(self.request('GET', '/authorize?' + urlencode(q))[0], 200)
        self.assertEqual(self.conn.signins, {})
        for i in range(connection.MAX_CLIENTS + 20):  # from many addresses, as through the tunnel
            self.assertEqual(self.post_json('/register', {'redirect_uris': [REDIRECT]}, headers={'CF-Connecting-IP': '203.0.113.%d' % (i % 250)})[0], 201)
        self.assertLessEqual(len(self.conn.state.data['clients']), connection.MAX_CLIENTS)
        self.assertIn(client, self.conn.state.data['clients'])  # its sign-in page was open, so it was kept
        self.assertEqual(self.rpc(token, 'ping')['result'], {})  # the connected assistant is kept
        self.sign_in(client)  # and the assistant mid sign-in can finish

    def test_registrations_are_limited_per_address(self):
        original = connection.REGISTER_LIMIT; connection.REGISTER_LIMIT = 3
        self.addCleanup(setattr, connection, 'REGISTER_LIMIT', original)
        one = {'CF-Connecting-IP': '198.51.100.7'}
        for _ in range(3): self.assertEqual(self.post_json('/register', {'redirect_uris': [REDIRECT]}, headers=one)[0], 201)
        self.assertEqual(self.post_json('/register', {'redirect_uris': [REDIRECT]}, headers=one)[0], 429)
        self.assertEqual(self.post_json('/register', {'redirect_uris': [REDIRECT]}, headers={'CF-Connecting-IP': '198.51.100.8'})[0], 201)
        status, _, _ = self.post_json('/register', {'redirect_uris': ['https://assistant.example/' + 'x' * 600]})
        self.assertEqual(status, 400)
        self.assertEqual(self.post_json('/register', {'redirect_uris': [REDIRECT] * 6})[0], 400)

    def test_activity_log_stays_small(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        log = self.conn.state.path.parent / 'connection-activity.log'
        self.tool(token, 'read_file', path='a' * 1900000)
        self.assertLess(len(log.read_text().splitlines()[-1]), 1000)
        original = connection.LOG_LIMIT; connection.LOG_LIMIT = 10
        self.addCleanup(setattr, connection, 'LOG_LIMIT', original)
        self.tool(token, 'read_file', path=self.status)
        self.assertTrue(log.with_suffix('.log.1').exists()); self.assertEqual(len(log.read_text().splitlines()), 1)

    def test_one_assistant_cannot_pile_up_proposals(self):
        original = connection.MAX_PENDING; connection.MAX_PENDING = 2
        self.addCleanup(setattr, connection, 'MAX_PENDING', original)
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        for i in range(2):
            r, text = self.tool(token, 'propose_project', parent='Family/Italy', title='Idea %d' % i, purpose='p', reason='r')
            self.assertFalse(r['isError'], text)
        r, text = self.tool(token, 'propose_project', parent='Family/Italy', title='Idea 3', purpose='p', reason='r')
        self.assertTrue(r['isError']); self.assertIn('waiting for the user', text)

    # ---- regressions from the second security review, 2026-10-19 ----
    def test_batches_are_refused_and_every_request_counts(self):
        token = self.tokens()['access_token']
        status, _, data = self.post_json('/mcp', [{'jsonrpc': '2.0', 'id': i, 'method': 'tools/list'} for i in range(50)], token)
        self.assertEqual(status, 400); self.assertIn(b'one JSON-RPC message', data)
        original = connection.CALL_LIMIT; connection.CALL_LIMIT = 3
        self.addCleanup(setattr, connection, 'CALL_LIMIT', original)
        for _ in range(3): self.assertIn('result', self.rpc(token, 'ping'))
        self.assertIn('Too many requests', self.rpc(token, 'tools/list')['error']['message'])

    def test_parallel_proposals_respect_the_waiting_limit(self):
        original = connection.MAX_PENDING; connection.MAX_PENDING = 3
        self.addCleanup(setattr, connection, 'MAX_PENDING', original)
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        results = []
        def propose(i):
            c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=60)
            body = json.dumps({'jsonrpc': '2.0', 'id': i, 'method': 'tools/call', 'params': {'name': 'propose_project', 'arguments':
                               {'parent': 'Family/Italy', 'title': 'Idea %d' % i, 'purpose': 'p', 'reason': 'r'}}})
            c.request('POST', '/mcp', body, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
            results.append(json.loads(c.getresponse().read())); c.close()
        threads = [threading.Thread(target=propose, args=(i,)) for i in range(12)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sum(1 for r in results if not r['result']['isError']), 3)
        self.assertEqual(len(chat.approvals(server)), 3)

    def test_wrong_codes_across_sign_ins_lock_sign_in(self):
        original = connection.CODE_GUESSES; connection.CODE_GUESSES = 4
        self.addCleanup(setattr, connection, 'CODE_GUESSES', original)
        self.conn.set_password(PASSWORD); client = self.register()['client_id']
        q = {'response_type': 'code', 'client_id': client, 'redirect_uri': REDIRECT, 'code_challenge': 'a' * 43, 'code_challenge_method': 'S256'}
        def code_step():
            rid = re.search(r'name="request" value="([^"]+)"', self.request('GET', '/authorize?' + urlencode(q))[2].decode()).group(1)
            page = self.post_form('/authorize', {'request': rid, 'action': 'password', 'password': PASSWORD})[2].decode()
            return re.search(r'name="request" value="([^"]+)"', page).group(1)
        for _ in range(2):
            step = code_step()
            for _ in range(2): self.post_form('/authorize', {'request': step, 'action': 'code', 'code': '000000' if self.conn.signins[step]['code'] != '000000' else '111111'})
        self.assertGreater(self.conn.locked_until, connection.now())
        self.assertEqual(self.conn.signins, {})
        status, _, page = self.post_form('/authorize', {'request': re.search(r'name="request" value="([^"]+)"', self.request('GET', '/authorize?' + urlencode(q))[2].decode()).group(1), 'action': 'password', 'password': PASSWORD})
        self.assertEqual(status, 429)

    def test_missing_and_hidden_files_look_the_same(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        hidden = self.tool(token, 'read_file', path='Family/Secret/LOG_STATUS.md')[1]
        missing = self.tool(token, 'read_file', path='Family/Nothing/LOG_STATUS.md')[1]
        self.assertEqual(hidden, missing)
        for i in range(30): (server.ROOT / 'Family/Secret' / ('n%02d.md' % i)).write_text('needle\n' * 10)
        (server.ROOT / 'Family/Italy/note.md').write_text('needle here\n')
        original = server.MAX_RESULTS; server.MAX_RESULTS = 20
        self.addCleanup(setattr, server, 'MAX_RESULTS', original)
        r = self.tool(token, 'search', query='needle')[0]['structuredContent']
        self.assertEqual([f['path'] for f in r['files']], ['Family/Italy/note.md']); self.assertFalse(r['truncated'])

    def test_changing_the_password_signs_everyone_out(self):
        t = self.tokens()
        self.assertEqual(self.rpc(t['access_token'], 'ping')['result'], {})
        self.conn.set_password('a brand new password 42')
        self.assertEqual(self.post_json('/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, t['access_token'])[0], 401)
        status, _, _ = self.post_form('/token', {'grant_type': 'refresh_token', 'refresh_token': t['refresh_token'], 'client_id': t['client_id']})
        self.assertEqual(status, 400)

    def test_malformed_requests_get_an_answer(self):
        token = self.tokens()['access_token']
        reply = self.rpc(token, 'tools/call', {'name': 'read_file', 'arguments': ['not', 'an', 'object']})
        self.assertEqual(reply['error']['code'], -32602)
        status, _, data = self.request('POST', '/register', '[' * 100000, {'Content-Type': 'application/json'})
        self.assertEqual(status, 400)

    def test_assistant_names_lose_invisible_characters(self):
        cid = self.register(client_name='Cla\u200bude\u202e moc.liame')['client_id']
        self.assertEqual(self.conn.state.data['clients'][cid]['name'], 'Claude moc.liame')

    def test_invisible_characters_do_not_bypass_a_rejection(self):
        token = self.tokens()['access_token']; self.grant('Family/Italy')
        version = server.file_view(self.status)['version']; before = (server.ROOT / self.status).read_text()
        new = before + '\nBook the night train.\n'
        self.tool(token, 'propose_change', project='Family/Italy', path=self.status, content=new, reason='Add', base_version=version)
        p = chat.approvals(server)[0]
        chat.decide_proposal(server, {'project': 'Family/Italy', 'conversation': p['conversation'], 'proposal': p['proposal'], 'decision': 'reject'})
        r, text = self.tool(token, 'propose_change', project='Family/Italy', path=self.status, content=new.replace('night', 'ni\u200bght'), reason='Again', base_version=version)
        self.assertTrue(r['isError']); self.assertIn('already rejected', text)


if __name__ == '__main__': unittest.main()
