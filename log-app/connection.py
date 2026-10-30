"""LOG connection: lets any MCP-capable AI assistant work with the projects the user turns on.

The assistant can read and search granted projects and propose changes. It can never write
project files: every proposal waits for the user's approval in the LOG app. Sign-in is OAuth 2.1
(authorization code with PKCE, dynamic client registration), approved with the LOG connection
password plus a one-time code shown in the LOG app. Standard library only; Python 3.9+.
"""
import base64
import difflib
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import tempfile
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode

PROTOCOL_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26')
SCOPE = 'log'
ACCESS_FILE = 'LOG-ACCESS.json'
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 86400
CODE_TTL = 300
SIGNIN_TTL = 600
PASSWORD_MIN = 12
PBKDF2_ROUNDS = 600000
MAX_BODY = 2000000
MAX_CLIENTS = 100
MAX_PENDING = 25          # proposals one assistant may have waiting at once
LOG_LIMIT = 5000000      # activity log size before it is rotated
CODE_GUESSES = 10        # wrong sign-in codes per hour, across all sign-ins, before sign-in locks
REGISTER_LIMIT = 30      # registrations per source address per hour
LOCK_AFTER = 5
LOCK_SECONDS = 900
CALL_LIMIT = 300
CALL_WINDOW = 600
TEXT_FORMATS = ('.md', '.txt', '.csv', '.json')
RULES_FILE = 'LOG-AI-RULES.md'
RULES_HINT = "LOG's rules for AI assistants apply to every project. If you have not read them in this conversation, call get_rules first."
# Redirect addresses are limited to a plain form that Python and browsers read the same way:
# no user name, backslash, spaces, control or non-ASCII characters.
IPV4 = r'(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])(\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])){3}'
REDIRECT_FORM = re.compile(r'(https|http)://([a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?|\[::1\])(?::([0-9]{1,5}))?'
                           r'(/[!$-;=?-\[\]-~]*)?\Z')

def now(): return time.time()
def iso(ts=None): return datetime.fromtimestamp(ts if ts is not None else now(), timezone.utc).isoformat()
def token_hash(value): return hashlib.sha256(value.encode()).hexdigest()
def default_state_path():
    home = Path.home()
    base = home / 'Library' / 'Application Support' / 'LOG' if (home / 'Library').is_dir() else home / '.log-connection'
    return base / 'connection.json'

class AuthError(Exception):
    def __init__(self, error, description, status=400):
        super().__init__(description); self.error = error; self.description = description; self.status = status

class ToolError(Exception):
    """A problem the assistant can fix (reported to it with isError, not as a protocol error)."""


class State:
    """Secrets live outside the LOG folder; tokens and the password are stored only as hashes."""
    def __init__(self, path):
        self.path = Path(path); self.lock = threading.RLock(); self.data = self._load()
    def _load(self):
        if self.path.exists():
            doc = json.loads(self.path.read_text())
            if isinstance(doc, dict) and doc.get('version') == 1: return doc
        return {'version': 1, 'password': None, 'clients': {}, 'grants': {}, 'access': {}, 'refresh': {}, 'usedRefresh': {}}
    def save(self):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix='.connection-', dir=str(self.path.parent))
            try:
                with os.fdopen(fd, 'w') as f: json.dump(self.data, f, indent=1)
                os.chmod(tmp, 0o600); os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
    def prune(self):
        t = now()
        with self.lock:
            for key in ('access', 'refresh'):
                self.data[key] = {h: v for h, v in self.data[key].items() if v['expires'] > t}
            self.data['usedRefresh'] = {h: v for h, v in self.data['usedRefresh'].items() if v['expires'] > t}
            live = {v['grant'] for v in self.data['refresh'].values()} | {v['grant'] for v in self.data['access'].values()}
            self.data['grants'] = {g: v for g, v in self.data['grants'].items() if g in live and not v.get('revoked')}
            used = {v['client'] for v in self.data['grants'].values()}
            self.data['clients'] = {c: v for c, v in self.data['clients'].items() if c in used or v['created'] > t - 86400}


class Connection:
    def __init__(self, s, chat, public_url, state_path):
        self.s = s; self.chat = chat
        self.public = public_url.rstrip('/')
        self.resource = self.public + '/mcp'
        self.state = State(state_path)
        self.lock = threading.RLock()
        self.signins = {}; self.codes = {}; self.failures = []; self.locked_until = 0
        self.password_lock = threading.Lock(); self.seal_key = secrets.token_bytes(32)
        self.propose_lock = threading.Lock(); self.code_failures = []; self.registrations = {}; self.authorizing = {}
        self.calls = {}; self.last_saved_use = 0

    # ---------- password ----------
    def password_set(self): return bool(self.state.data.get('password'))
    def set_password(self, password):
        if not isinstance(password, str) or len(password) < PASSWORD_MIN or len(password) > 200:
            raise ValueError('Use a connection password of at least %d characters.' % PASSWORD_MIN)
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ROUNDS)
        with self.state.lock:
            changed = bool(self.state.data.get('password'))
            self.state.data['password'] = {'salt': salt.hex(), 'rounds': PBKDF2_ROUNDS, 'hash': digest.hex(), 'set': iso()}
            if changed:  # A new password usually means the old one may be known: every assistant signs in again.
                for grant in list(self.state.data['grants']): self._revoke_grant(grant)
                self.state.prune()
            self.state.save()
        with self.lock:
            if changed: self.signins = {}; self.codes = {}
    def check_password(self, password):
        record = self.state.data.get('password')
        if not record or not isinstance(password, str): return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(record['salt']), record['rounds'])
        return hmac.compare_digest(digest.hex(), record['hash'])

    # ---------- project access ----------
    def projects(self): return {p['id']: p for p in self.s.catalog()['projects']}
    def access_doc(self):
        path = self.s.ROOT / ACCESS_FILE
        if not path.exists(): return None, None
        raw = path.read_bytes()
        doc = json.loads(raw.decode('utf-8'))
        if not isinstance(doc, dict): raise ValueError('LOG-ACCESS.json is not valid.')
        return doc, self.s.digest(raw)
    def grants(self):
        try: doc, _ = self.access_doc()
        except (ValueError, OSError): return set()
        if not doc: return set()
        listed = doc.get('connectedAI', {}).get('projects', []) if isinstance(doc.get('connectedAI'), dict) else []
        if not isinstance(listed, list): return set()
        known = set(self.projects())
        return {p for p in listed if isinstance(p, str) and p in known}
    def set_grants(self, projects, version):
        known = set(self.projects())
        if not isinstance(projects, list) or any(not isinstance(p, str) or p not in known for p in projects):
            raise ValueError('Choose existing projects only.')
        doc, current = self.access_doc()
        if version != current:
            raise self.s.Conflict('Project access changed since this page loaded. Reload before saving.')
        payload = {'version': 1,
                   'about': 'Projects that AI assistants connected through the LOG connection may see. Change this in the LOG app.',
                   'connectedAI': {'projects': sorted(set(projects))}}
        raw = (json.dumps(payload, indent=2, ensure_ascii=False) + '\n').encode()
        expected = {ACCESS_FILE: current} if current else {}
        self.s.write_transaction({ACCESS_FILE: raw}, expected, 'Update connected-AI project access')
        return sorted(set(projects))
    def add_grant(self, project):
        doc, current = self.access_doc()
        listed = list(self.grants()) + [project]
        return self.set_grants(listed, current)
    def owner(self, rel): return self.s.project_of(rel, self.projects())
    def canonical(self, rel):
        """Map a path to the names stored on disk. Folders on a Mac ignore letter case and accent forms, so
        'family/secret' would open 'Family/Secret'; access is checked on the stored names only."""
        current = self.s.ROOT; parts = []
        for part in rel.split('/'):
            try: names = os.listdir(current)
            except OSError: raise ToolError('File not found.')
            if part not in names:
                folded = fold_name(part)
                matches = [n for n in names if fold_name(n) == folded]
                if len(matches) != 1: raise ToolError('File not found.')
                part = matches[0]
            parts.append(part); current = current / part
        return '/'.join(parts)
    def require_project(self, project):
        if not isinstance(project, str) or project not in self.grants():
            raise ToolError('That project is not available. Use list_projects to see the projects you can open.')
        return self.projects()[project]

    # ---------- OAuth: clients ----------
    def register(self, body, source='local'):
        if not isinstance(body, dict): raise AuthError('invalid_client_metadata', 'Send client metadata as a JSON object.')
        uris = body.get('redirect_uris')
        if not isinstance(uris, list) or not 1 <= len(uris) <= 5 or any(not valid_redirect(u) or len(u) > 512 for u in uris):
            raise AuthError('invalid_redirect_uri', 'Redirect addresses must be plain https addresses, or http on localhost or 127.0.0.1, without user names, spaces, fragments or unusual characters.')
        method = body.get('token_endpoint_auth_method') or 'none'
        if method not in ('none', 'client_secret_post', 'client_secret_basic'):
            raise AuthError('invalid_client_metadata', 'Unsupported token endpoint authentication method.')
        name = body.get('client_name') if isinstance(body.get('client_name'), str) else ''
        name = ''.join(c for c in name[:500] if unicodedata.category(c)[0] != 'C')  # no invisible or direction-changing characters
        name = re.sub(r'\s+', ' ', name).strip()[:80] or 'AI assistant'
        with self.lock:
            t = now()
            self.registrations = {k: [x for x in v if x > t - 3600] for k, v in self.registrations.items() if any(x > t - 3600 for x in v)}
            if len(self.registrations.get(source, [])) >= REGISTER_LIMIT:
                raise AuthError('temporarily_unavailable', 'Too many new connections from this address. Try again later.', 429)
            self.registrations.setdefault(source, []).append(t)
        with self.state.lock:
            self.state.prune()
            clients = self.state.data['clients']
            if len(clients) >= MAX_CLIENTS:  # Make room by forgetting the oldest assistants that never finished signing in.
                with self.lock:
                    busy = {v['client'] for v in self.state.data['grants'].values()}
                    busy |= {v['client'] for v in self.signins.values()} | {v['client'] for v in self.codes.values()}
                    busy |= {c for c, t in self.authorizing.items() if t > now() - SIGNIN_TTL}
                for old in sorted((c for c in clients if c not in busy), key=lambda c: clients[c]['created']):
                    if len(clients) < MAX_CLIENTS: break
                    del clients[old]
                if len(clients) >= MAX_CLIENTS:
                    raise AuthError('temporarily_unavailable', 'Too many connected assistants. Disconnect one in the LOG app.', 503)
            client_id = 'log-' + secrets.token_urlsafe(18)
            record = {'name': name, 'redirect_uris': uris, 'method': method, 'created': now()}
            reply = {'client_id': client_id, 'client_id_issued_at': int(now()), 'client_name': name, 'redirect_uris': uris,
                     'grant_types': ['authorization_code', 'refresh_token'], 'response_types': ['code'],
                     'token_endpoint_auth_method': method, 'scope': SCOPE + ' offline_access'}
            if method != 'none':
                secret = secrets.token_urlsafe(32)
                record['secret_hash'] = token_hash(secret)
                reply.update(client_secret=secret, client_secret_expires_at=0)
            self.state.data['clients'][client_id] = record
            self.state.save()
        return reply
    def client(self, client_id):
        record = self.state.data['clients'].get(client_id) if isinstance(client_id, str) else None
        if not record: raise AuthError('invalid_client', 'Unknown client. Connect again from your AI assistant.', 401)
        return record

    # ---------- OAuth: sign-in ----------
    def start_signin(self, q):
        """Check a sign-in request and return it sealed. Nothing is stored until the password is correct,
        so strangers cannot fill up LOG with sign-ins."""
        client_id = q.get('client_id', ''); redirect = q.get('redirect_uri', '')
        client = self.client(client_id)
        if not valid_redirect(redirect) or not redirect_allowed(redirect, client['redirect_uris']):
            raise AuthError('invalid_request', 'This redirect address is not registered for the assistant.')
        if q.get('response_type') != 'code': raise AuthError('unsupported_response_type', 'Only the authorization code flow is supported.')
        challenge = q.get('code_challenge', '')
        if q.get('code_challenge_method') != 'S256' or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}', challenge):
            raise AuthError('invalid_request', 'A PKCE S256 code challenge is required.')
        resource = q.get('resource')
        if resource and not same_resource(resource, self.resource):
            raise AuthError('invalid_target', 'This sign-in is for a different server.')
        # There is one kind of access ("log"). Other requested scopes, such as offline_access, which ChatGPT asks
        # for to get refresh tokens, are accepted and ignored: refresh tokens are always issued.
        scope = q.get('scope') or SCOPE
        if not isinstance(scope, str) or len(scope) > 500: raise AuthError('invalid_scope', 'Request the "log" scope.')
        state = q.get('state', '')
        if len(state) > 500: raise AuthError('invalid_request', 'The state value is too long.')
        with self.lock:  # Keep this assistant while its sign-in page is open, even if strangers register many others.
            self.authorizing = {c: t for c, t in self.authorizing.items() if t > now() - SIGNIN_TTL}
            if len(self.authorizing) < 200 or client_id in self.authorizing: self.authorizing[client_id] = now()
        return self.seal({'client': client_id, 'redirect': redirect, 'challenge': challenge, 'state': state,
                          'expires': now() + SIGNIN_TTL})
    def seal(self, record):
        body = base64.urlsafe_b64encode(json.dumps(record, separators=(',', ':')).encode()).decode().rstrip('=')
        return 's1.' + body + '.' + hmac.new(self.seal_key, body.encode(), hashlib.sha256).hexdigest()
    def unseal(self, sealed):
        """A sign-in that has not passed the password step yet."""
        try:
            prefix, body, mac = sealed.split('.')
            if prefix != 's1' or not hmac.compare_digest(mac, hmac.new(self.seal_key, body.encode(), hashlib.sha256).hexdigest()): raise ValueError
            record = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        except (ValueError, AttributeError, TypeError):
            raise AuthError('invalid_request', 'This sign-in is not valid. Start again from your AI assistant.')
        if record['expires'] <= now(): raise AuthError('invalid_request', 'This sign-in has expired. Start again from your AI assistant.')
        self.client(record['client'])
        return record
    def signin(self, request_id):
        with self.lock:
            record = self.signins.get(request_id) if isinstance(request_id, str) else None
            if not record or record['expires'] <= now():
                raise AuthError('invalid_request', 'This sign-in has expired. Start again from your AI assistant.')
            return record
    def password_step(self, sealed, password):
        """Return the id of the code step if the password is right, otherwise None."""
        record = self.unseal(sealed)
        with self.password_lock:  # One check at a time, so parallel guesses cannot get past the lockout.
            t = now()
            if self.locked_until > t:
                raise AuthError('temporarily_unavailable', 'Too many wrong passwords. Try again in %d minutes.' % ((self.locked_until - t) // 60 + 1), 429)
            if not self.check_password(password):
                self.failures = [f for f in self.failures if f > now() - LOCK_SECONDS] + [now()]
                if len(self.failures) >= LOCK_AFTER: self.locked_until = now() + LOCK_SECONDS; self.failures = []
                return None
        with self.lock:
            self.signins = {k: v for k, v in self.signins.items() if v['expires'] > now()}
            if len(self.signins) >= 20: raise AuthError('temporarily_unavailable', 'Too many sign-ins in progress. Deny the ones you do not recognise in the LOG app.', 503)
            request_id = secrets.token_urlsafe(24)
            self.signins[request_id] = dict(record, stage='code', code='%06d' % secrets.randbelow(1000000), attempts=0,
                                            expires=now() + SIGNIN_TTL, created=now())
        return request_id
    def code_step(self, request_id, code):
        with self.lock:
            record = self.signins.get(request_id) if isinstance(request_id, str) else None
            if not record or record['expires'] <= now():
                raise AuthError('invalid_request', 'This sign-in has expired. Start again from your AI assistant.')
            t = now()
            if self.locked_until > t:
                raise AuthError('temporarily_unavailable', 'Sign-in is locked after too many wrong codes or passwords. Try again in %d minutes.' % ((self.locked_until - t) // 60 + 1), 429)
            record['attempts'] += 1
            if not isinstance(code, str) or not hmac.compare_digest(code.strip(), record['code']):
                if record['attempts'] >= 5: self.signins.pop(request_id, None)
                self.code_failures = [f for f in self.code_failures if f > t - 3600] + [t]
                if len(self.code_failures) >= CODE_GUESSES:  # Someone may know the password: stop all sign-ins for a while.
                    self.locked_until = t + LOCK_SECONDS; self.code_failures = []; self.signins = {}
                return None
            self.signins.pop(request_id, None)
            auth_code = secrets.token_urlsafe(32)
            self.codes[token_hash(auth_code)] = {'client': record['client'], 'redirect': record['redirect'],
                                                 'challenge': record['challenge'], 'expires': now() + CODE_TTL}
        return redirect_with(record['redirect'], {'code': auth_code, 'state': record['state'], 'iss': self.public})
    def deny(self, request_id):
        if isinstance(request_id, str) and request_id.startswith('s1.'):
            try: record = self.unseal(request_id)
            except AuthError: record = None
        else:
            with self.lock: record = self.signins.pop(request_id, None)
        if record: return redirect_with(record['redirect'], {'error': 'access_denied', 'state': record['state'], 'iss': self.public})
        return None

    # ---------- OAuth: tokens ----------
    def authenticate_client(self, form, header):
        client_id = form.get('client_id')
        secret = form.get('client_secret')
        if header and header.lower().startswith('basic '):
            try:
                pair = base64.b64decode(header[6:]).decode()
                client_id, secret = [unquote_basic(x) for x in pair.split(':', 1)]
            except (ValueError, UnicodeError): raise AuthError('invalid_client', 'Bad client credentials.', 401)
        client = self.client(client_id)
        if client['method'] != 'none':
            if not secret or not hmac.compare_digest(token_hash(secret), client['secret_hash']):
                raise AuthError('invalid_client', 'Bad client credentials.', 401)
        return client_id, client
    def token(self, form, header):
        client_id, client = self.authenticate_client(form, header)
        resource = form.get('resource')
        if resource and not same_resource(resource, self.resource):
            raise AuthError('invalid_target', 'Tokens are only issued for this LOG connection.')
        grant_type = form.get('grant_type')
        if grant_type == 'authorization_code':
            with self.lock: record = self.codes.pop(token_hash(form.get('code') or ''), None)
            if not record or record['expires'] <= now() or record['client'] != client_id:
                raise AuthError('invalid_grant', 'The authorization code is invalid or expired.')
            if form.get('redirect_uri') != record['redirect']:
                raise AuthError('invalid_grant', 'The redirect address does not match.')
            verifier = form.get('code_verifier') or ''
            if not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier) or not hmac.compare_digest(pkce(verifier), record['challenge']):
                raise AuthError('invalid_grant', 'PKCE verification failed.')
            with self.state.lock:
                grant = 'g-' + secrets.token_urlsafe(12)
                self.state.data['grants'][grant] = {'client': client_id, 'created': now(), 'lastUsed': now()}
                reply = self._issue(grant)
            return reply
        if grant_type == 'refresh_token':
            presented = token_hash(form.get('refresh_token') or '')
            with self.state.lock:
                record = self.state.data['refresh'].pop(presented, None)
                if not record:
                    reused = self.state.data['usedRefresh'].get(presented)
                    if reused:  # A rotated token came back: assume theft and end the whole connection.
                        self._revoke_grant(reused['grant'])
                    self.state.save()
                    raise AuthError('invalid_grant', 'The refresh token is invalid or expired.')
                grant = self.state.data['grants'].get(record['grant'])
                if record['expires'] <= now() or not grant or grant.get('revoked') or grant['client'] != client_id:
                    self.state.save()
                    raise AuthError('invalid_grant', 'The refresh token is invalid or expired.')
                self.state.data['usedRefresh'][presented] = {'grant': record['grant'], 'expires': record['expires']}
                return self._issue(record['grant'])
        raise AuthError('unsupported_grant_type', 'Use authorization_code or refresh_token.')
    def _issue(self, grant):
        access = secrets.token_urlsafe(32); refresh = secrets.token_urlsafe(40)
        self.state.data['access'][token_hash(access)] = {'grant': grant, 'expires': now() + ACCESS_TTL, 'resource': self.resource}
        self.state.data['refresh'][token_hash(refresh)] = {'grant': grant, 'expires': now() + REFRESH_TTL}
        self.state.prune(); self.state.save()
        return {'access_token': access, 'token_type': 'Bearer', 'expires_in': ACCESS_TTL, 'refresh_token': refresh, 'scope': SCOPE + ' offline_access'}
    def _revoke_grant(self, grant):
        with self.state.lock:
            if grant in self.state.data['grants']: self.state.data['grants'][grant]['revoked'] = True
            for key in ('access', 'refresh'):
                self.state.data[key] = {h: v for h, v in self.state.data[key].items() if v['grant'] != grant}
    def revoke(self, form, header):
        client_id, _ = self.authenticate_client(form, header)
        presented = token_hash(form.get('token') or '')
        with self.state.lock:
            record = self.state.data['access'].get(presented) or self.state.data['refresh'].get(presented)
            if record and self.state.data['grants'].get(record['grant'], {}).get('client') == client_id:
                self._revoke_grant(record['grant']); self.state.save()
    def check_access(self, header):
        if not header or not header.startswith('Bearer '): return None
        record = self.state.data['access'].get(token_hash(header[7:].strip()))
        if not record or record['expires'] <= now() or record.get('resource') != self.resource: return None
        grant = self.state.data['grants'].get(record['grant'])
        if not grant or grant.get('revoked'): return None
        client = self.state.data['clients'].get(grant['client'])
        if not client: return None
        if now() - grant.get('lastUsed', 0) > 60:
            with self.state.lock: grant['lastUsed'] = now(); self.state.save()
        return {'grant': record['grant'], 'client': grant['client'], 'name': client['name']}
    def disconnect(self, client_id):
        with self.state.lock:
            for grant, record in list(self.state.data['grants'].items()):
                if record['client'] == client_id: self._revoke_grant(grant)
            self.state.data['clients'].pop(client_id, None)
            self.state.prune(); self.state.save()

    # ---------- information for the LOG app ----------
    def app_status(self, enabled=True):
        with self.lock:
            signins = [{'id': k, 'client': self.state.data['clients'].get(v['client'], {}).get('name', 'AI assistant'),
                        'redirectHost': redirect_host(v['redirect']), 'code': v['code'], 'expires': iso(v['expires'])}
                       for k, v in self.signins.items() if v['stage'] == 'code' and v['expires'] > now()]
        with self.state.lock:
            self.state.prune()
            connected = {}
            for grant in self.state.data['grants'].values():
                client = self.state.data['clients'].get(grant['client'])
                if not client: continue
                item = connected.setdefault(grant['client'], {'id': grant['client'], 'name': client['name'],
                                                             'redirectHost': redirect_host(client['redirect_uris'][0]),
                                                             'connected': iso(grant['created']), 'lastUsed': iso(grant['lastUsed'])})
                item['lastUsed'] = max(item['lastUsed'], iso(grant['lastUsed']))
        try: doc, version = self.access_doc()
        except (ValueError, OSError): doc, version = None, 'invalid'
        return {'enabled': enabled, 'publicUrl': self.public, 'endpoint': self.resource, 'passwordSet': self.password_set(),
                'signins': signins, 'clients': sorted(connected.values(), key=lambda c: c['connected']),
                'grants': sorted(self.grants()), 'accessVersion': version, 'lockedUntil': iso(self.locked_until) if self.locked_until > now() else None}

    # ---------- MCP tools ----------
    def rules(self):
        """LOG-AI-RULES.md at the top of the LOG folder, or None. It is for every assistant, whatever projects are on."""
        try:
            data = self.s.read_bytes(self.s.allowed(self.s.ROOT / RULES_FILE))
            return data.decode('utf-8')[:20000], self.s.digest(data)
        except (OSError, ValueError, UnicodeError):
            return None

    def instructions(self):
        found = self.rules()
        return ('You are connected to LOG, a file-based project memory system. You can only see projects the user has '
                'turned on. You cannot change files directly: propose_change, propose_memory_update and propose_project '
                'create proposals that the user approves or rejects in the LOG app. Start with get_rules, then '
                'list_projects and open_project. Pass the version you read as base_version when proposing a change. '
                'Never describe a proposal as saved or approved.\n\n' + (found[0] if found else ''))

    def tools(self):
        ro = {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}
        propose = {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': False, 'openWorldHint': False}
        def obj(props, required): return {'type': 'object', 'properties': props, 'required': required, 'additionalProperties': False}
        text = {'type': 'string'}
        return [
            {'name': 'get_rules', 'title': 'Read the LOG rules', 'annotations': ro,
             'description': "Read LOG's rules for AI assistants: how to open a project, answer from its files and propose changes. Call this once at the start of a conversation, before anything else. The rules apply to every project.",
             'inputSchema': {'type': 'object', 'additionalProperties': False}},
            {'name': 'list_projects', 'title': 'List LOG projects', 'annotations': ro,
             'description': 'List the LOG projects you may open, with their lifecycle and a one-line summary. ' + RULES_HINT,
             'inputSchema': {'type': 'object', 'additionalProperties': False}},
            {'name': 'open_project', 'title': 'Open a project', 'annotations': ro,
             'description': "Open a project: returns LOG_README.md and LOG_STATUS.md in full, the section headings of LOG_PROJECT.md, and the project's other files. Read more with read_file.",
             'inputSchema': obj({'project': dict(text, description='Project id from list_projects')}, ['project'])},
            {'name': 'read_file', 'title': 'Read a file', 'annotations': ro,
             'description': 'Read a text file (.md, .txt, .csv, .json) in a project you may open. Returns its contents and version.',
             'inputSchema': obj({'path': dict(text, description='Path relative to the LOG folder, e.g. "Family Holidays/LOG_PROJECT.md"')}, ['path'])},
            {'name': 'search', 'title': 'Search projects', 'annotations': ro,
             'description': 'Plain-text search of project names and text files in the projects you may open. Archived projects are left out unless include_archived is true, as in the LOG app.',
             'inputSchema': obj({'query': dict(text, description='2 to 200 characters; case and extra spaces are ignored'),
                                 'project': dict(text, description='Optional: limit to one project id'),
                                 'include_archived': {'type': 'boolean', 'description': 'Also search archived projects (default false)'}}, ['query'])},
            {'name': 'list_pending', 'title': 'List proposals', 'annotations': ro,
             'description': 'List proposals waiting for approval, and recent decisions, in the projects you may open.',
             'inputSchema': obj({'project': dict(text, description='Optional project id')}, [])},
            {'name': 'propose_change', 'title': 'Propose a file change', 'annotations': propose,
             'description': 'Propose new full contents for an existing Markdown file directly in a project. Nothing changes until the user approves it in the LOG app.',
             'inputSchema': obj({'project': text, 'path': dict(text, description='Path relative to the LOG folder'),
                                 'content': dict(text, description='The complete new file contents'),
                                 'reason': dict(text, description='Why this change is needed, citing sources'),
                                 'base_version': dict(text, description='The version returned when you read the file')},
                                ['project', 'path', 'content', 'reason', 'base_version'])},
            {'name': 'propose_memory_update', 'title': 'Propose a memory update', 'annotations': propose,
             'description': ('Propose updates to LOG_STATUS.md and/or LOG_PROJECT.md after reviewing a project. LOG_PROJECT.md may only gain text. '
                             'To move text from status to durable memory, copy it exactly into LOG_PROJECT.md; LOG offers removal from status separately after the copy is saved.'),
             'inputSchema': obj({'project': text, 'reason': text,
                                 'status_content': dict(text, description='Full new LOG_STATUS.md, or omit'),
                                 'status_version': dict(text, description='Version of LOG_STATUS.md you read'),
                                 'project_content': dict(text, description='Full new LOG_PROJECT.md, or omit'),
                                 'project_version': dict(text, description='Version of LOG_PROJECT.md you read')},
                                ['project', 'reason'])},
            {'name': 'propose_project', 'title': 'Propose a new project', 'annotations': propose,
             'description': 'Propose a new child project (with its three LOG files) under a project you may open. Created only if the user approves.',
             'inputSchema': obj({'parent': dict(text, description='Parent project id ("." for the root)'), 'title': text,
                                 'purpose': text, 'reason': text}, ['parent', 'title', 'purpose', 'reason'])},
            {'name': 'propose_session_record', 'title': 'Propose a session record', 'annotations': propose,
             'description': ("At the end of meaningful work on a project, send a short record of this conversation so it is not lost when the chat ends: "
                             "what was discussed, decisions the user confirmed, open questions and next steps. The user approves it in the LOG app; "
                             "it is then saved as a file in the project's conversations folder. Record only what was actually said. "
                             "Put a decision under decisions only if the user confirmed it; suggestions belong in the summary or open questions. "
                             "To change the project's status or memory files, also use propose_memory_update or propose_change."),
             'inputSchema': obj({'project': text, 'title': dict(text, description='A few words, up to 120 characters'),
                                 'summary': dict(text, description='What happened in this conversation, up to 8,000 characters'),
                                 'decisions': {'type': 'array', 'items': text, 'description': 'Decisions the user confirmed in this conversation'},
                                 'open_questions': {'type': 'array', 'items': text},
                                 'next_steps': {'type': 'array', 'items': text},
                                 'files_consulted': {'type': 'array', 'items': text, 'description': 'LOG files you read, as paths'}},
                                ['project', 'title', 'summary'])}
        ]

    def call(self, name, args, who):
        if not isinstance(args, dict): raise ToolError('Arguments must be an object.')
        handler = {'get_rules': self.t_get_rules, 'list_projects': self.t_list_projects, 'open_project': self.t_open_project, 'read_file': self.t_read_file,
                   'search': self.t_search, 'list_pending': self.t_list_pending, 'propose_change': self.t_propose_change,
                   'propose_memory_update': self.t_propose_memory, 'propose_project': self.t_propose_project,
                   'propose_session_record': self.t_propose_session}[name]
        return handler(args, who)

    def _status_bits(self, p):
        status = p['docs'].get('LOG_STATUS.md', '')
        def section(name):
            m = re.search(r'^## ' + re.escape(name) + r'\s*\n(.*?)(?=^## |\Z)', status, re.M | re.S | re.I)
            return ' '.join(m.group(1).split()) if m else ''
        return section('Lifecycle')[:80], section('Summary')[:300]

    def t_get_rules(self, args, who):
        found = self.rules()
        if not found: raise ToolError('This LOG folder has no rules file. Follow the instructions you were given when you connected.')
        text, version = found
        return {'path': RULES_FILE, 'version': version, 'text': text}, text

    def t_list_projects(self, args, who):
        grants = self.grants(); projects = self.projects(); items = []
        for pid in sorted(grants):
            p = projects[pid]; lifecycle, summary = self._status_bits(p)
            items.append({'project': pid, 'name': p['name'], 'parent': p['parent'] if p['parent'] in grants else None,
                          'children': sorted(q for q in grants if projects[q]['parent'] == pid),
                          'lifecycle': lifecycle, 'summary': summary})
        text = '\n'.join('- %s (%s)%s: %s' % (i['name'], i['project'], ' [' + i['lifecycle'] + ']' if i['lifecycle'] else '', i['summary'] or 'No summary recorded.') for i in items)
        return {'projects': items}, (text or 'No projects are turned on for connected AIs. Ask the user to allow a project in the LOG app.') + '\n\n' + RULES_HINT

    def _readable(self, rel):
        if not isinstance(rel, str) or not rel or len(rel) > 1000: raise ToolError('Give a file path relative to the LOG folder.')
        # The same answer whether a file is missing or outside your projects, so names elsewhere stay private.
        unavailable = ToolError('That file does not exist in a project you may open. Use open_project to see the files you can read.')
        try:
            path = self.s.allowed(self.s.ROOT / rel)
            rel = self.canonical(path.relative_to(self.s.ROOT).as_posix())
            path = self.s.allowed(self.s.ROOT / rel)
        except (ValueError, ToolError, OSError): raise unavailable
        owner = self.owner(rel)
        if owner is None or owner not in self.grants(): raise unavailable
        if path.suffix.lower() not in TEXT_FORMATS: raise ToolError('Only .md, .txt, .csv and .json files can be read.')
        if not path.is_file(): raise ToolError('File not found.')
        try: data = self.s.read_bytes(path); text = data.decode('utf-8')
        except (ValueError, UnicodeError, OSError) as e: raise ToolError('The file could not be read as UTF-8 text: %s' % e)
        return rel, owner, text, self.s.digest(data)

    def t_open_project(self, args, who):
        p = self.require_project(args.get('project'))
        pid = p['id']; base = '' if pid == '.' else pid + '/'
        parts = {}; out = ['# %s (%s)' % (p['name'], pid), '', RULES_HINT]
        for name in ('LOG_README.md', 'LOG_STATUS.md'):
            try:
                rel, _, text, version = self._readable(base + name)
                parts[name] = {'path': rel, 'version': version, 'text': text}
                out += ['', '## %s (version %s)' % (rel, version), '', text]
            except ToolError as e: out += ['', '## %s: %s' % (name, e)]
        try:
            rel, _, text, version = self._readable(base + 'LOG_PROJECT.md')
            headings = [line.strip() for line in text.splitlines() if re.match(r'#{2,3} ', line)]
            parts['LOG_PROJECT.md'] = {'path': rel, 'version': version, 'headings': headings}
            out += ['', '## %s (version %s): sections' % (rel, version), ''] + ['- ' + h for h in headings] + ['', 'Read the full file with read_file.']
        except ToolError as e: out += ['', '## LOG_PROJECT.md: %s' % e]
        grants = self.grants(); projects = self.projects(); files = []
        folder = self.s.ROOT if pid == '.' else self.s.ROOT / pid
        for dirpath, dirs, names in os.walk(folder, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(dirpath) / d).is_symlink())
            for name in sorted(names):
                path = Path(dirpath) / name; rel = path.relative_to(self.s.ROOT).as_posix()
                if name.startswith('.') or path.is_symlink() or self.owner(rel) != pid or name in ('LOG_README.md', 'LOG_STATUS.md', 'LOG_PROJECT.md') and path.parent == folder: continue
                files.append({'path': rel, 'bytes': path.stat().st_size, 'readable': path.suffix.lower() in TEXT_FORMATS})
        children = sorted(q for q in grants if projects[q]['parent'] == pid)
        out += ['', '## Other files', ''] + ['- %s (%d bytes)%s' % (f['path'], f['bytes'], '' if f['readable'] else ', not readable as text') for f in files[:200]]
        if children: out += ['', '## Child projects you may open', ''] + ['- ' + c for c in children]
        return {'project': pid, 'name': p['name'], 'files': parts, 'otherFiles': files[:200], 'children': children}, '\n'.join(out)

    def t_read_file(self, args, who):
        rel, owner, text, version = self._readable(args.get('path'))
        return {'path': rel, 'project': owner, 'version': version, 'text': text}, 'File %s (version %s)\n\n%s' % (rel, version, text)

    def t_search(self, args, who):
        grants = self.grants(); only = args.get('project')
        if only is not None: self.require_project(only); grants = {only}
        try: r = self.s.search(args.get('query'), args.get('include_archived') is True, grants)
        except ValueError as e: raise ToolError(str(e))
        files = [f for f in r['files'] if f['project'] in grants]
        projects = [p for p in r['projects'] if p['id'] in grants]
        result = {'query': r['query'], 'projects': projects, 'files': files, 'truncated': r['truncated'],
                  'searchedAt': r['searchedAt']}
        lines = ['Search for "%s": %d project(s), %d file(s).' % (r['query'], len(projects), len(files))]
        lines += ['Project: %s (%s)' % (p['name'], p['id']) for p in projects]
        for f in files:
            lines.append('%s (%d matching line%s)' % (f['path'], f['matchCount'], '' if f['matchCount'] == 1 else 's'))
            lines += ['  line %d: %s' % (m['line'], m['text']) for m in f['matches']]
        return result, '\n'.join(lines)

    def _conversations(self, project):
        folder = self.s.ROOT / ('' if project == '.' else project) / 'conversations'
        if not folder.is_dir(): return []
        out = []
        for f in sorted(folder.glob('*.json')):
            if not re.fullmatch('[a-f0-9]{32}', f.stem): continue
            try: out.append(self.chat.read_conversation(self.s, project, f.stem))
            except (ValueError, OSError): continue
        return out

    def t_list_pending(self, args, who):
        targets = sorted(self.grants())
        if args.get('project') is not None: self.require_project(args['project']); targets = [args['project']]
        pending, decided = [], []
        for pid in targets:
            for c in self._conversations(pid):
                for t in c['turns']:
                    for p in t.get('proposals', []):
                        item = {'project': pid, 'proposal': p['id'], 'path': p['path'], 'kind': p.get('kind', 'file'),
                                'reason': p['reason'], 'status': p['status'], 'reviewed': p.get('reviewed'),
                                'fromYou': c.get('source', {}).get('clientId') == who['client']}
                        (pending if p['status'] == 'pending' else decided).append(item)
        decided = sorted([d for d in decided if d['fromYou']], key=lambda d: d['reviewed'] or '', reverse=True)[:20]
        text = ['Waiting for approval: %d' % len(pending)] + ['- [%s] %s: %s' % (p['project'], p['path'], p['reason']) for p in pending]
        text += ['', 'Your recent proposals that were decided:'] + ['- %s %s: %s' % (d['status'], d['path'], d['reason']) for d in decided]
        return {'pending': pending, 'decided': decided}, '\n'.join(text)

    def _record(self, project, who, reason, proposals, mode, sources, answer):
        """Store proposals in a project conversation so the LOG app's review flow can approve them."""
        with self.propose_lock:
            return self._record_locked(project, who, reason, proposals, mode, sources, answer)
    def _record_locked(self, project, who, reason, proposals, mode, sources, answer):
        waiting = sum(1 for a in self.chat.approvals(self.s) if a.get('clientId') == who['client'] and a['status'] == 'pending')
        if waiting + len(proposals) > MAX_PENDING:
            raise ToolError('You have %d proposals waiting for the user. Wait until they review them in the LOG app before proposing more.' % waiting)
        with self.s.LOCK:
            day = datetime.now(timezone.utc).date().isoformat()
            for n in range(1000):
                cid = hashlib.sha256(('%s|%s|%s|%d' % (who['client'], project, day, n)).encode()).hexdigest()[:32]
                path = self.chat.conversation_path(self.s, project, cid)
                if not path.exists():
                    c = {'id': cid, 'project': project, 'title': 'Connected AI: %s, %s' % (who['name'], day)[:80], 'scope': [],
                         'source': {'type': 'connection', 'client': who['name'], 'clientId': who['client']}, 'turns': []}
                    break
                c = self.chat.read_conversation(self.s, project, cid)
                if len(c['turns']) < 40: break
            c['turns'].append({'requestId': str(uuid.uuid4()), 'question': '[%s, through the LOG connection] %s' % (who['name'], reason),
                               'mode': mode, 'reconsiderRejected': False, 'status': 'complete', 'sources': sources,
                               'model': who['name'], 'created': iso(), 'answer': answer, 'proposals': proposals})
            self.chat.persist(self.s, c, message='Record proposal from connected AI (%s)' % who['name'])
            return c

    def _file_proposal(self, project, rel, content, reason, base_version, allow_names=None):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000: raise ToolError('Give a reason of up to 4,000 characters.')
        if not isinstance(content, str) or not content.strip(): raise ToolError('The proposed file is empty.')
        if len(content.encode()) > self.s.MAX_FILE: raise ToolError('The proposed file is larger than 1 MB.')
        rel, owner, before, version = self._readable(rel)
        folder = '' if project == '.' else project
        if owner != project or Path(rel).parent.as_posix() != (folder or '.') or not rel.lower().endswith('.md'):
            raise ToolError('Only existing Markdown files directly in the project folder can be changed.')
        if allow_names and Path(rel).name not in allow_names: raise ToolError('This tool only changes %s.' % ' and '.join(allow_names))
        if base_version != version:
            raise ToolError('%s changed since you read it (current version %s). Read it again and redo your change.' % (rel, version))
        if content == before: raise ToolError('The proposed contents are identical to the current file.')
        diff = ''.join(difflib.unified_diff(before.splitlines(True), content.splitlines(True), fromfile='Before', tofile='Proposed'))
        return {'id': uuid.uuid4().hex, 'path': rel, 'reason': reason.strip(), 'before': before, 'content': content,
                'version': version, 'diff': diff, 'status': 'pending'}

    def _not_rejected(self, project, proposals):
        records = self.chat.review_records.load(self.s, self.chat, project)
        for p in proposals:
            if self.chat.review_records.repeated(p, records):
                raise ToolError('This repeats a change the user already rejected for %s. Do not propose it again unless the user asks you to reconsider; they can reopen it in the LOG app.' % p['path'])

    def t_propose_change(self, args, who):
        project = self.require_project(args.get('project'))['id']
        p = self._file_proposal(project, args.get('path'), args.get('content'), args.get('reason'), args.get('base_version'))
        self._not_rejected(project, [p])
        sources = [{'id': 'S1', 'path': p['path'], 'sha256': p['version'], 'parent': False}]
        self._record(project, who, p['reason'], [p], 'connection', sources,
                     'Proposed change submitted through the LOG connection. It waits for approval in the LOG app.')
        return ({'proposal': p['id'], 'status': 'pending', 'path': p['path']},
                'Proposal %s submitted for %s. Nothing has changed yet: the user approves or rejects it in the LOG app.' % (p['id'], p['path']))

    def t_propose_memory(self, args, who):
        project = self.require_project(args.get('project'))['id']
        base = '' if project == '.' else project + '/'
        proposals, docs = [], []
        for key, name in (('status', 'LOG_STATUS.md'), ('project', 'LOG_PROJECT.md')):
            rel, _, text, version = self._readable(base + name)
            docs.append({'id': 'S%d' % (len(docs) + 1), 'path': rel, 'sha256': version, 'text': text, 'parent': False})
            if args.get(key + '_content') is not None:
                proposals.append(self._file_proposal(project, rel, args.get(key + '_content'), args.get('reason'), args.get(key + '_version'), [name]))
        if not proposals: raise ToolError('Give status_content, project_content or both.')
        staged, notes = self.chat.memory_promotion.stage(self.s, project, proposals, docs, 'memory')
        if not staged: raise ToolError(' '.join(notes) or 'No approvable changes remain.')
        self._not_rejected(project, staged)
        sources = [{k: v for k, v in d.items() if k != 'text'} for d in docs]
        self._record(project, who, args.get('reason').strip(), staged, 'memory', sources,
                     'Memory update submitted through the LOG connection. ' + ' '.join(notes))
        text = 'Submitted %d proposal(s) for approval in the LOG app: %s.' % (len(staged), ', '.join(p['path'] for p in staged))
        if notes: text += ' ' + ' '.join(notes)
        return {'proposals': [p['id'] for p in staged], 'notes': notes}, text

    def t_propose_project(self, args, who):
        parent = self.require_project(args.get('parent'))['id']
        title = args.get('title'); purpose = args.get('purpose'); reason = args.get('reason')
        if not isinstance(title, str) or not title.strip() or len(title) > 80 or any(c in title for c in '/\\\n\r\t') or title.strip().startswith('.'):
            raise ToolError('Use a project title of 1 to 80 characters without slashes or line breaks.')
        if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 4000: raise ToolError('Give a purpose of up to 4,000 characters.')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000: raise ToolError('Give a reason of up to 4,000 characters.')
        title = title.strip(); base = self.s.ROOT / ('' if parent == '.' else parent)
        if any(fold_name(n) == fold_name(title) for n in os.listdir(base)):
            raise ToolError('A folder with that name already exists in the parent project.')
        rel = (title if parent == '.' else parent + '/' + title)
        preview = '# %s\n\n## Purpose\n\n%s\n\n## Parent Project\n\n%s\n' % (title, purpose.strip(), 'Root' if parent == '.' else parent)
        p = {'id': uuid.uuid4().hex, 'kind': 'project', 'path': rel, 'parent': parent, 'title': title, 'purpose': purpose.strip(),
             'reason': reason.strip(), 'before': '', 'content': preview, 'version': '',
             'diff': ''.join('+' + line for line in preview.splitlines(True)), 'status': 'pending'}
        self._not_rejected(parent, [p])
        self._record(parent, who, p['reason'], [p], 'connection', [],
                     'New project proposed through the LOG connection. It is created only if the user approves.')
        return {'proposal': p['id'], 'status': 'pending', 'project': rel}, 'Proposed new project "%s". It is created only if the user approves it in the LOG app.' % rel

    def t_propose_session(self, args, who):
        project = self.require_project(args.get('project'))['id']
        def clean(value, limit, keep_lines=False):
            if not isinstance(value, str): raise ToolError('Text fields must be text.')
            value = value.replace('\r\n', '\n').replace('\t', ' ')
            if not keep_lines: value = value.replace('\n', ' ').replace('\r', ' ')
            value = ''.join(c for c in value if (keep_lines and c == '\n') or unicodedata.category(c)[0] != 'C')
            return value.strip()[:limit] if keep_lines else ' '.join(value.split())[:limit]
        title = clean(args.get('title'), 120); summary = clean(args.get('summary'), 8000, keep_lines=True)
        if not title or not summary: raise ToolError('Give a title and a summary.')
        if len(args.get('summary')) > 8000: raise ToolError('Keep the summary under 8,000 characters.')
        lists = {}
        for key in ('decisions', 'open_questions', 'next_steps', 'files_consulted'):
            items = args.get(key) or []
            if not isinstance(items, list) or len(items) > 30: raise ToolError('%s must be a list of up to 30 items.' % key)
            lists[key] = [x for x in (clean(i, 600) for i in items) if x]
        day = datetime.now().astimezone().date().isoformat()
        slug = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()).strip('-')[:50] or 'session'
        folder = 'conversations' if project == '.' else project + '/conversations'
        waiting = {a['path'] for a in self.chat.approvals(self.s)}
        for n in range(1, 100):
            rel = '%s/session-%s-%s%s.md' % (folder, day, slug, '' if n == 1 else '-%d' % n)
            if rel not in waiting and not (self.s.ROOT / rel).exists(): break
        else: raise ToolError('Too many session records with this title today. Use a different title.')
        def section(heading, items):
            return ['', '## ' + heading, ''] + (['- ' + i for i in items] if items else ['None recorded.'])
        lines = ['# Session record: ' + title, '',
                 '- Date: ' + day,
                 '- Assistant: ' + who['name'] + ' (its own name for itself), through the LOG connection',
                 '- Project: ' + project,
                 "- This is the assistant's summary of a conversation, approved by the user before saving. It is not a word-for-word transcript, and it does not change the project's status or memory files.",
                 '', '## Summary', '', summary]
        lines += section('Decisions the user confirmed', lists['decisions']) + section('Open questions', lists['open_questions'])
        lines += section('Next steps', lists['next_steps']) + section('Files consulted', lists['files_consulted'])
        content = '\n'.join(lines) + '\n'
        p = {'id': uuid.uuid4().hex, 'kind': 'session', 'path': rel, 'title': title,
             'reason': 'Session record from %s: %s' % (who['name'], title), 'before': '', 'content': content, 'version': '',
             'diff': ''.join('+' + line for line in content.splitlines(True)), 'status': 'pending'}
        self._not_rejected(project, [p])
        self._record(project, who, p['reason'], [p], 'connection', [],
                     'Session record submitted through the LOG connection. It is saved only if the user approves it in the LOG app.')
        return ({'proposal': p['id'], 'status': 'pending', 'path': rel},
                'Session record %s submitted for %s. Nothing is saved yet: the user approves or rejects it in the LOG app.' % (p['id'], rel))

    # ---------- JSON-RPC ----------
    def rpc(self, message, who):
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            return {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid request'}}
        if 'method' not in message: return None  # a response from the client: nothing to do
        mid = message.get('id'); method = message['method']; params = message.get('params') or {}
        if mid is None: return None  # notification
        def ok(result): return {'jsonrpc': '2.0', 'id': mid, 'result': result}
        def err(code, text): return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': code, 'message': text}}
        key = who['grant']; t = now()
        with self.lock:  # Every request counts toward the limit, not only tool calls.
            recent = [c for c in self.calls.get(key, []) if c > t - CALL_WINDOW]
            if len(recent) >= CALL_LIMIT: return err(-32000, 'Too many requests. Wait a few minutes and try again.')
            self.calls[key] = recent + [t]
        if method == 'initialize':
            wanted = params.get('protocolVersion') if isinstance(params, dict) else None
            version = wanted if wanted in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return ok({'protocolVersion': version, 'capabilities': {'tools': {'listChanged': False}},
                       'serverInfo': {'name': 'log', 'title': 'LOG', 'version': '0.1.0'}, 'instructions': self.instructions()})
        if method == 'ping': return ok({})
        if method == 'tools/list': return ok({'tools': self.tools()})
        if method == 'tools/call':
            name = params.get('name') if isinstance(params, dict) else None
            if name not in {t['name'] for t in self.tools()}: return err(-32602, 'Unknown tool: %s' % str(name)[:80])
            args = params.get('arguments')
            if args is None: args = {}
            if not isinstance(args, dict): return err(-32602, 'Tool arguments must be an object.')
            try:
                structured, text = self.call(name, args, who)
                self.log(who, name, args, 'ok')
                return ok({'content': [{'type': 'text', 'text': text}], 'structuredContent': structured, 'isError': False})
            except ToolError as e:
                self.log(who, name, args, 'refused')
                return ok(tool_error(str(e)))
            except (self.s.Conflict, ValueError) as e:
                self.log(who, name, args, 'refused')
                return ok(tool_error(str(e)))
            except Exception as e:  # Report without exposing internals; the activity log keeps the type.
                self.log(who, name, args, 'failed: ' + type(e).__name__)
                return ok(tool_error('LOG could not complete this request. Nothing was changed. Try again, or ask the user to check the LOG app.'))
        return err(-32601, 'Method not found: %s' % str(method)[:80])

    def log(self, who, tool, args, outcome):
        def short(v): return v[:200] if isinstance(v, str) else None
        entry = {'time': iso(), 'client': who['name'], 'tool': tool, 'outcome': outcome,
                 'project': short(args.get('project') or args.get('parent')), 'path': short(args.get('path'))}
        try:
            path = self.state.path.parent / 'connection-activity.log'
            if path.exists() and path.stat().st_size > LOG_LIMIT: os.replace(path, path.with_suffix('.log.1'))
            with open(path, 'a') as f: f.write(json.dumps(entry) + '\n')
            os.chmod(path, 0o600)
        except OSError: pass

    # ---------- metadata ----------
    def resource_metadata(self):
        return {'resource': self.resource, 'authorization_servers': [self.public], 'scopes_supported': [SCOPE],
                'bearer_methods_supported': ['header'], 'resource_name': 'LOG'}
    def server_metadata(self):
        return {'issuer': self.public, 'authorization_endpoint': self.public + '/authorize', 'token_endpoint': self.public + '/token',
                'registration_endpoint': self.public + '/register', 'revocation_endpoint': self.public + '/revoke',
                'response_types_supported': ['code'], 'grant_types_supported': ['authorization_code', 'refresh_token'],
                'code_challenge_methods_supported': ['S256'], 'scopes_supported': [SCOPE, 'offline_access'],
                'token_endpoint_auth_methods_supported': ['none', 'client_secret_post', 'client_secret_basic'],
                'revocation_endpoint_auth_methods_supported': ['none', 'client_secret_post', 'client_secret_basic'],
                'authorization_response_iss_parameter_supported': True}


def tool_error(text): return {'content': [{'type': 'text', 'text': text}], 'isError': True}
def pkce(verifier): return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
def unquote_basic(value):
    from urllib.parse import unquote_plus
    return unquote_plus(value)
def fold_name(name): return unicodedata.normalize('NFC', name).casefold()
def valid_redirect(uri):
    if not isinstance(uri, str) or len(uri) > 2000: return False
    m = REDIRECT_FORM.match(uri)
    if not m or (m.group(3) and not 0 < int(m.group(3)) < 65536): return False
    host = m.group(2)
    if re.fullmatch(r'0x[0-9a-f]*|[0-9]+', host.rsplit('.', 1)[-1]) and not re.fullmatch(IPV4, host):
        return False  # browsers read hosts like 0x7f.1 as an IP address
    if m.group(1) == 'https': return '.' in host or host == 'localhost'
    return m.group(2) in ('localhost', '127.0.0.1', '[::1]')
def redirect_host(uri):
    m = REDIRECT_FORM.match(uri or '')
    return (m.group(2) + (':' + m.group(3) if m.group(3) else '')) if m else ''
def redirect_allowed(uri, registered):
    if not valid_redirect(uri): return False
    if uri in registered: return True
    u = urlparse(uri)
    if u.scheme != 'http' or u.hostname not in ('localhost', '127.0.0.1', '::1'): return False
    for r in registered:  # loopback redirects may use any port (RFC 8252)
        v = urlparse(r)
        if v.scheme == 'http' and v.hostname == u.hostname and v.path == u.path and v.query == u.query: return True
    return False
def same_resource(given, ours):
    def norm(x):
        u = urlparse(x.strip())
        return (u.scheme.lower(), (u.netloc or '').lower(), u.path.rstrip('/'))
    return norm(given) == norm(ours)
def redirect_with(uri, params):
    sep = '&' if urlparse(uri).query else '?'
    return uri + sep + urlencode({k: v for k, v in params.items() if v != ''})


PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connect to LOG</title><style>
body{margin:0;background:#f7f7f2;color:#263b32;font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
main{max-width:460px;margin:8vh auto;padding:32px;background:#fff;border:1px solid #e1e5dc;border-radius:14px}
h1{font:30px Georgia,serif;margin:0 0 12px}.host{font:600 14px ui-monospace,monospace;background:#eef1e8;padding:2px 6px;border-radius:5px}
label{display:block;margin:18px 0 6px;font-size:13px}input{width:100%%;box-sizing:border-box;font:inherit;padding:10px;border:1px solid #cdd7c3;border-radius:8px}
.code{letter-spacing:6px;font:24px ui-monospace,monospace;text-align:center}.row{display:flex;gap:10px;margin-top:20px}
button{font:inherit;padding:9px 16px;border-radius:8px;border:1px solid #d3dccb;background:#fff;cursor:pointer}.primary{background:#244c3b;color:#fff;border-color:#244c3b}
.note{font-size:13px;color:#68746b}.warn{background:#fff3db;border:1px solid #e6ce9f;padding:10px 12px;border-radius:8px;font-size:13px}.error{color:#9c402d}
</style></head><body><main>%s</main></body></html>'''


class Handler(BaseHTTPRequestHandler):
    conn = None
    server_version = 'LOG-connection'
    sys_version = ''
    timeout = 30  # slow or stalled connections are closed instead of holding a thread
    def log_message(self, *args): pass
    def send(self, status, body=b'', ctype='application/json', headers=None):
        if isinstance(body, (dict, list)): body = json.dumps(body).encode()
        elif isinstance(body, str): body = body.encode()
        self.send_response(status)
        base = {'Content-Type': ctype, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                'Referrer-Policy': 'same-origin'}
        if ctype.startswith('text/html'):
            base['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
            base['X-Frame-Options'] = 'DENY'
        base.update(headers or {})
        if any(ch in str(v) for v in base.values() for ch in '\r\n'):
            return self.send(500, {'error': 'server_error'})
        for k, v in base.items(): self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(body)
    def origin_ok(self):
        c = self.conn
        public = urlparse(c.public)
        hosts = {public.netloc.lower(), '127.0.0.1:%d' % self.server.server_port, 'localhost:%d' % self.server.server_port}
        if (self.headers.get('Host') or '').lower() not in hosts: return False
        origin = self.headers.get('Origin')
        return not origin or origin.rstrip('/').lower() == (public.scheme + '://' + public.netloc).lower()
    def body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if not 0 <= length <= MAX_BODY: raise AuthError('invalid_request', 'Request too large.', 413)
        return self.rfile.read(length)
    def form(self):
        q = parse_qs(self.body().decode('utf-8', 'replace'), keep_blank_values=True)
        return {k: v[0] for k, v in q.items()}
    def challenge(self, error=None):
        value = 'Bearer resource_metadata="%s/.well-known/oauth-protected-resource", scope="%s"' % (self.conn.public, SCOPE)
        if error: value += ', error="%s"' % error
        return {'WWW-Authenticate': value}

    def do_GET(self):
        c = self.conn; path = urlparse(self.path).path
        if not self.origin_ok(): return self.send(403, {'error': 'forbidden'})
        if path in ('/.well-known/oauth-protected-resource', '/.well-known/oauth-protected-resource/mcp'):
            return self.send(200, c.resource_metadata())
        if path in ('/.well-known/oauth-authorization-server', '/.well-known/openid-configuration'):
            return self.send(200, c.server_metadata())
        if path == '/authorize': return self.authorize_page()
        if path == '/mcp': return self.send(405, {'error': 'Use POST for MCP messages.'}, headers={'Allow': 'POST'})
        if path == '/': return self.send(200, 'LOG connection. Add %s to your AI assistant as an MCP server.\n' % c.resource, 'text/plain; charset=utf-8')
        return self.send(404, {'error': 'not_found'})
    def do_DELETE(self):
        if urlparse(self.path).path == '/mcp': return self.send(405, b'', headers={'Allow': 'POST'})
        return self.send(404, {'error': 'not_found'})
    def do_POST(self):
        c = self.conn; path = urlparse(self.path).path
        if not self.origin_ok(): return self.send(403, {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32000, 'message': 'Forbidden origin or host'}})
        try:
            if path == '/mcp': return self.mcp()
            if path == '/register':
                try: data = json.loads(self.body() or b'null')
                except (ValueError, RecursionError): raise AuthError('invalid_client_metadata', 'Send JSON.')
                return self.send(201, c.register(data, self.source()))
            if path == '/token': return self.send(200, c.token(self.form(), self.headers.get('Authorization')), headers={'Pragma': 'no-cache'})
            if path == '/revoke':
                c.revoke(self.form(), self.headers.get('Authorization')); return self.send(200, {})
            if path == '/authorize': return self.authorize_post()
            return self.send(404, {'error': 'not_found'})
        except AuthError as e:
            headers = {'WWW-Authenticate': 'Basic realm="LOG"'} if e.status == 401 else None
            return self.send(e.status, {'error': e.error, 'error_description': e.description}, headers=headers)
        except Exception:  # Never drop the connection without an answer.
            return self.send(500, {'error': 'server_error', 'error_description': 'LOG could not handle this request.'})
    def source(self):
        """Where a request came from. Behind the Cloudflare Tunnel every request arrives from this Mac, and
        Cloudflare passes the visitor's address in CF-Connecting-IP (visitors cannot set it themselves)."""
        return (self.headers.get('CF-Connecting-IP') or 'local').strip()[:64]

    def mcp(self):
        c = self.conn
        who = c.check_access(self.headers.get('Authorization'))
        if not who:
            return self.send(401, {'error': 'invalid_token', 'error_description': 'Sign in to LOG.'},
                             headers=self.challenge('invalid_token' if self.headers.get('Authorization') else None))
        version = self.headers.get('MCP-Protocol-Version')
        if version and version not in PROTOCOL_VERSIONS:
            return self.send(400, {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Unsupported MCP protocol version'}})
        try: message = json.loads(self.body().decode('utf-8'))
        except (ValueError, UnicodeError, RecursionError):
            return self.send(400, {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}})
        if isinstance(message, list):  # Batches were removed from MCP in 2025-06-18; refusing them caps the work per request.
            return self.send(400, {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Send one JSON-RPC message per request.'}})
        reply = c.rpc(message, who)
        return self.send(202) if reply is None else self.send(200, reply)

    def page(self, inner, status=200): return self.send(status, PAGE % inner, 'text/html; charset=utf-8')
    def authorize_page(self):
        c = self.conn
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        try: sealed = c.start_signin(q)
        except AuthError as e: return self.page('<h1>Can\'t connect</h1><p class="error">%s</p>' % html.escape(e.description), 400)
        return self.password_form(sealed, c.unseal(sealed))
    def describe(self, record):
        c = self.conn; client = c.client(record['client'])
        host = redirect_host(record['redirect'])
        loop = host.split(':')[0] in ('localhost', '127.0.0.1', '[::1]')
        return ('<h1>Connect to LOG</h1><p>An assistant calling itself <strong>%s</strong> wants to connect. It will return to <span class="host">%s</span>.</p>'
                '<p class="note">It will be able to read and search the projects you have turned on in LOG and propose changes. Nothing changes until you approve it in the LOG app.</p>%s'
                % (html.escape(client['name']), html.escape(host),
                   '<p class="warn">This address is on your own computer. Continue only if you just started this connection from an app on this Mac.</p>' if loop else ''))
    def password_form(self, sealed, record, error=''):
        c = self.conn
        if not c.password_set():
            return self.page('<h1>Set a password first</h1><p>Open the LOG app on your Mac, choose <strong>Connected AI</strong>, and set a connection password. Then start again from your AI assistant.</p>', 403)
        return self.page(self.describe(record) + ('<p class="error">%s</p>' % html.escape(error) if error else '') +
                         '<form method="post" action="/authorize"><input type="hidden" name="request" value="%s">'
                         '<label for="pw">LOG connection password</label><input id="pw" name="password" type="password" autocomplete="current-password" required autofocus>'
                         '<div class="row"><button class="primary" name="action" value="password">Continue</button><button name="action" value="deny" formnovalidate>Cancel</button></div></form>'
                         % html.escape(sealed))
    def code_form(self, request_id, error=''):
        return self.page(self.describe(self.conn.signin(request_id)) + ('<p class="error">%s</p>' % html.escape(error) if error else '') +
                         '<form method="post" action="/authorize"><input type="hidden" name="request" value="%s">'
                         '<label for="code">Enter the 6-digit code shown in the LOG app on your Mac (Connected AI)</label>'
                         '<input id="code" class="code" name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required autofocus>'
                         '<div class="row"><button class="primary" name="action" value="code">Approve</button><button name="action" value="deny" formnovalidate>Cancel</button></div></form>'
                         % html.escape(request_id))
    def authorize_post(self):
        c = self.conn; f = self.form(); request_id = f.get('request', '')
        try:
            if f.get('action') == 'deny':
                target = c.deny(request_id)
                return self.send(302, b'', headers={'Location': target}) if target else self.page('<h1>Cancelled</h1>')
            if f.get('action') == 'password':
                record = c.unseal(request_id)
                step = c.password_step(request_id, f.get('password', ''))
                if step: return self.code_form(step)
                return self.password_form(request_id, record, 'That password is not correct.')
            if f.get('action') == 'code':
                c.signin(request_id)
                target = c.code_step(request_id, f.get('code', ''))
                if target: return self.send(302, b'', headers={'Location': target})
                if request_id not in c.signins: return self.page('<h1>Sign-in stopped</h1><p class="error">Too many wrong codes. Start again from your AI assistant.</p>', 400)
                return self.code_form(request_id, 'That code is not correct.')
            return self.page('<h1>Something went wrong</h1>', 400)
        except AuthError as e:
            return self.page('<h1>Can\'t connect</h1><p class="error">%s</p>' % html.escape(e.description), e.status)


def start(s, chat, port, public_url, state_path):
    conn = Connection(s, chat, public_url, state_path)
    handler = type('LOGConnectionHandler', (Handler,), {'conn': conn})
    httpd = ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True, name='log-connection').start()
    return conn, httpd
