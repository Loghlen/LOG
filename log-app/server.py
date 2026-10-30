#!/usr/bin/env python3
"""Local LOG browser and revision-backed Markdown editor."""
import argparse
import sys
import chat_service
import connection
import lifecycle
import decisions
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CONTROL = ('LOG_README.md', 'LOG_STATUS.md', 'LOG_PROJECT.md')
ROOT = Path('/Users/loghlenrickard/Desktop/LOG').resolve()
CONNECTION = None  # project access and sign-in for connected AI assistants (see connection.py)
CONNECTION_LISTENING = False
WEB = Path(__file__).parent / 'index.html'
LOCK = threading.RLock()
MAX_FILE = 1000000
PREVIEW = ('.md','.txt','.csv','.json')
# Documents, images and media that LOG may open in their own apps. Anything else (scripts, apps, installers)
# can only be shown in Finder, so a click in LOG never runs a program.
OPENABLE = {'.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.key','.pages','.numbers','.rtf','.md','.txt','.csv','.json',
            '.png','.jpg','.jpeg','.gif','.heic','.tif','.tiff','.webp','.mp3','.m4a','.wav','.mp4','.mov'}
NATIVE_OPEN = ['/usr/bin/open'] if sys.platform=='darwin' else None
MAX_FOLDER_FILES = 300
class Conflict(Exception): pass
class HistoryError(Exception): pass

def allowed(path):
    path = Path(path)
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT)
        lexical = path.absolute().relative_to(ROOT)
    except ValueError:
        raise ValueError('File is outside the connected LOG folder.')
    if any(part.startswith('.') for part in relative.parts) or any(part.startswith('.') for part in lexical.parts):
        raise ValueError('Hidden files are not available.')
    cursor = ROOT
    for part in lexical.parts:
        cursor = cursor / part
        if cursor.is_symlink(): raise ValueError('Symbolic links are not available for editing or preview.')
    return resolved

def read_bytes(path):
    path = allowed(path)
    if path.suffix.lower() not in ('.md', '.txt', '.csv', '.json'):
        raise ValueError('Only text files can be previewed.')
    if path.stat().st_size > MAX_FILE:
        raise ValueError('This file is larger than the 1 MB preview limit.')
    return path.read_bytes()

def content(path): return read_bytes(path).decode('utf-8')
def digest(value): return hashlib.sha256(value).hexdigest()
def file_view(name):
    value = read_bytes(ROOT / name)
    return {'path':name,'content':value.decode('utf-8'),'version':digest(value),'editable':Path(name).suffix.lower()=='.md'}

def git(*args, check=True):
    env = dict(os.environ)
    for key in list(env):
        if key.startswith('GIT_'): env.pop(key)
    env['GIT_TERMINAL_PROMPT']='0'
    result=subprocess.run(['git','-C',str(ROOT),'-c','user.name=LOG Local', '-c','user.email=log@localhost','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',*args],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    if check and result.returncode:
        raise HistoryError('Git could not finish the checkpoint. Your previous revisions are retained. '+result.stderr.decode('utf-8',errors='replace')[:300])
    return result

def history_ready():
    return (ROOT/'.git').is_dir() and git('config','--local','--get','log.managed',check=False).stdout.strip()==b'true'

def require_history():
    if not history_ready(): raise HistoryError('Local history is not initialized. Start with --init-history before editing.')
    if git('diff','--cached','--name-only').stdout.strip():
        raise Conflict('Git has staged changes from another operation. Resolve those changes before saving in LOG.')
    for marker in ('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply'):
        if (ROOT/'.git'/marker).exists(): raise Conflict('A Git operation is in progress. Complete it before saving in LOG.')

def markdown_files():
    result=[]
    for base,dirs,names in os.walk(ROOT,followlinks=False):
        dirs[:]=[d for d in dirs if not d.startswith('.') and not (Path(base)/d).is_symlink()]
        for name in names:
            path=Path(base)/name
            if name.lower().endswith('.md') and not name.startswith('.') and not path.is_symlink():
                allowed(path)
                result.append(path.relative_to(ROOT).as_posix())
    return sorted(result)

def init_history():
    if (ROOT/'.git').exists():
        if history_ready(): return
        raise HistoryError('This folder already has a Git repository not managed by LOG. It has been left unchanged.')
    git('init')
    # Only explicitly selected Markdown files are tracked, never credentials or arbitrary binaries.
    names=markdown_files()
    for name in names: git('--literal-pathspecs','add','--',name)
    git('commit','--allow-empty','-m','Initial LOG checkpoint')
    git('config','--local','log.managed','true')

def checkpoint(names,message):
    for name in names: git('--literal-pathspecs','add','--',name)
    staged = set(git('diff','--cached','--name-only','-z').stdout.decode().strip('\0').split('\0')) - {''}
    if not staged.issubset(set(names)):
        raise Conflict('Unexpected staged files were detected. No commit was made; inspect Git before continuing.')
    if git('diff','--cached','--quiet',check=False).returncode:
        git('commit','-m',message)
    return git('rev-parse','HEAD').stdout.decode().strip()

def history(name):
    path=allowed(ROOT/name)
    if path.suffix.lower()!='.md': raise ValueError('History is available for Markdown files.')
    if not history_ready(): return []
    log=git('--literal-pathspecs','log','--format=%H%x09%aI%x09%s','--',path.relative_to(ROOT).as_posix()).stdout.decode()
    return [{'id':parts[0],'date':parts[1],'message':parts[2]} for row in log.splitlines() if len(parts:=row.split('\t',2))==3]

def revision_bytes(name,rev):
    if not isinstance(rev,str) or not re.fullmatch('[0-9a-f]{40}',rev): raise ValueError('Choose a valid saved revision.')
    if rev not in {r['id'] for r in history(name)}: raise ValueError('That revision is not in this file’s history.')
    result=git('show',f'{rev}:{allowed(ROOT/name).relative_to(ROOT).as_posix()}')
    if len(result.stdout)>MAX_FILE: raise ValueError('This revision exceeds the preview limit.')
    result.stdout.decode('utf-8')
    return result.stdout

def compare(name,old,new):
    a=revision_bytes(name,old)
    b=read_bytes(ROOT/name) if new=='working' else revision_bytes(name,new)
    diff=''.join(difflib.unified_diff(a.decode().splitlines(keepends=True),b.decode().splitlines(keepends=True),fromfile='Saved '+old[:8],tofile='Current file' if new=='working' else 'Saved '+new[:8]))
    return {'diff':diff,'identical':a==b,'old':a.decode(),'new':b.decode()}

def atomic_write(path,value):
    mode=path.stat().st_mode & 0o777
    fd,tmp=tempfile.mkstemp(prefix='.log-save-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(value); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp,mode)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def save(name,text,expected,restore=None):
    with LOCK:
        require_history()
        path=allowed(ROOT/name)
        if path.suffix.lower()!='.md': raise ValueError('Editing is available for Markdown files only.')
        current=read_bytes(path)
        if not isinstance(expected,str) or digest(current)!=expected:
            raise Conflict('This file changed since you opened it. Your draft is still here. Reload the latest file before applying changes.')
        if restore:
            value=revision_bytes(name,restore)
        else:
            if not isinstance(text,str): raise ValueError('Document content must be text.')
            value=text.encode('utf-8')
        if len(value)>MAX_FILE: raise ValueError('The document exceeds the 1 MB size limit.')
        if value==current: return {**file_view(name),'unchanged':True}
        # Capture changes made outside the app before replacing them.
        checkpoint([name],f'Checkpoint before editing {path.name}')
        if read_bytes(path)!=current: raise Conflict('The file changed while a checkpoint was being made. Reload before saving.')
        atomic_write(path,value)
        try:
            # Do not report a save as complete if another process changed it during persistence.
            if read_bytes(path)!=value: raise Conflict('Another application changed the file during saving. Refresh to inspect it; the previous revision is preserved.')
            commit=checkpoint([name],f'Restore {path.name} from {restore[:8]}' if restore else f'Update {path.name}')
        except HistoryError:
            if read_bytes(path)==value: atomic_write(path,current)
            git('--literal-pathspecs','reset','HEAD','--',name,check=False)
            raise
        if read_bytes(path)!=value:
            raise Conflict('The file changed after saving. The saved revision is preserved; reload to inspect the latest contents.')
        return {**file_view(name),'commit':commit}

def write_transaction(changes, expected, message):
    """Commit the approved document and review record together; roll back on failure."""
    with LOCK:
        require_history()
        paths={name:allowed(ROOT/name) for name in changes}
        before={name:path.read_bytes() if path.exists() else None for name,path in paths.items()}
        for name,version in expected.items():
            if before.get(name) is None or digest(before[name])!=version:
                raise Conflict('This file changed after the proposal was prepared. Nothing was approved. Ask for a fresh proposal using the latest files.')
        existing=[name for name,value in before.items() if value is not None]
        if existing: checkpoint(existing,'Checkpoint before '+message.lower())
        def current(name):
            path=allowed(paths[name])
            return path.read_bytes() if path.exists() else None
        if any(current(name)!=value for name,value in before.items()):
            raise Conflict('A file changed during review. Refresh before trying again.')
        written=[]
        try:
            for name,value in changes.items():
                path=allowed(paths[name])
                if before[name] is None:
                    with path.open('xb') as f: f.write(value)
                else: atomic_write(path,value)
                written.append(name)
            if any(current(name)!=value for name,value in changes.items()):
                raise Conflict('Another application changed a file during saving. Inspect the files before continuing.')
            commit=checkpoint(list(changes),message)
        except Exception:
            for name in written:
                if current(name)==changes[name]:
                    if before[name] is None: paths[name].unlink()
                    else: atomic_write(paths[name],before[name])
            for name in written: git('--literal-pathspecs','reset','HEAD','--',name,check=False)
            raise
        return commit

def readme_title(folder):
    try: first=content(folder/'LOG_README.md').split('\n',1)[0]
    except (OSError,ValueError,UnicodeError): return ''
    return first[2:].strip() if first.startswith('# ') else ''

def readme_section(folder,name):
    """The first paragraph of a section in a project's LOG_README.md, or ''."""
    try: text=content(folder/'LOG_README.md')
    except (OSError,ValueError,UnicodeError): return ''
    spans,lines=lifecycle.sections(text,name)
    if not spans: return ''
    body=''.join(lines[spans[0][0]+1:spans[0][1]]).strip()
    return body.split('\n\n')[0].strip()

def default_owner(parent):
    """A new project's owner defaults to its parent's, then the root project's."""
    for folder in ([ROOT/parent] if parent and parent!='.' else [])+[ROOT]:
        owner=readme_section(folder,'Owner')
        if owner: return owner
    return ''

def create_project(title,purpose,parent,owner=None,collaborators='',scope='',out_of_scope=''):
    with LOCK:
        require_history()
        if not isinstance(title,str) or not title.strip() or len(title)>80 or any(c in title for c in '/\\\n\r\t') or title.strip().startswith('.') or title.strip() in ('.','..'):
            raise ValueError('Use a project title of 1–80 characters without slashes or line breaks.')
        if not isinstance(purpose,str) or not purpose.strip() or len(purpose)>4000: raise ValueError('Add a purpose of up to 4,000 characters.')
        owner=(owner if isinstance(owner,str) and owner.strip() else default_owner(parent)).strip()
        if len(owner)>200 or '\n' in owner: raise ValueError('Give the owner on one line, up to 200 characters.')
        extras={}
        for key,value in (('collaborators',collaborators),('scope',scope),('out of scope',out_of_scope)):
            if value is None: value=''
            if not isinstance(value,str) or len(value)>2000: raise ValueError('Keep %s under 2,000 characters.'%key)
            extras[key]=value.strip()
        base=ROOT
        if parent:
            if parent not in {p['id'] for p in catalog()['projects']}: raise ValueError('Choose an existing parent project.')
            base=allowed(ROOT/parent)
        folder=allowed(base/title.strip())
        if folder.exists(): raise Conflict('A folder with this name already exists. Choose another title.')
        day=datetime.now(timezone.utc).date().isoformat()
        identity=os.urandom(8).hex()
        effective=parent if parent and parent!='.' else ('.' if (ROOT/'LOG_README.md').exists() else '')
        parent_name=(Path(parent).name if effective and effective!='.' else readme_title(ROOT) or 'LOG')
        parent_text=f'[{parent_name}](../LOG_README.md)'+(' (the root LOG project)' if effective=='.' else '') if effective else 'None. This is a top-level project and there is no root LOG project.'
        depth=len(folder.relative_to(ROOT).parts)
        rules=f' AI assistants follow [LOG\'s rules for AI assistants]({"../"*depth}LOG-AI-RULES.md).' if (ROOT/'LOG-AI-RULES.md').is_file() else ''
        docs={
            'LOG_README.md':(f'# {title.strip()}\n\n## Purpose\n\n{purpose.strip()}\n\n'
                             f'## Owner\n\n{owner or "Not recorded."}\n\n'
                             f'## Collaborators\n\n{extras["collaborators"] or "None recorded."}\n\n'
                             f'## Parent Project\n\n{parent_text}\n\n'
                             f'## Child Projects\n\nNone yet. Child projects appear as nested folders and in the LOG sidebar.\n\n'
                             f'## Scope\n\n{extras["scope"] or "Work that supports the purpose above. Not yet defined in more detail."}\n\n'
                             f'## Out of Scope\n\n{extras["out of scope"] or "Not yet defined."}\n\n'
                             f'## Permissions\n\n- View and edit: the owner, through the LOG app and this Mac\'s file permissions.\n'
                             f'- Collaborators: no separate access is configured.\n'
                             f'- Connected AI assistants: only if this project is turned on under Connected AI in the LOG app. Turning on a parent project does not include this one.\n\n'
                             f'## Information Sharing\n\nNo cross-project AI access is configured. Local filesystem permissions apply.\n\n'
                             f'## Expected Structure\n\n- LOG_README.md, LOG_STATUS.md and LOG_PROJECT.md\n- Other documents and folders as the work needs them\n- conversations/: saved chats and session records\n\n'
                             f'## Operating Rules\n\nKeep proposals separate from confirmed decisions. Use LOG’s save function to preserve history.{rules}\n\n'
                             f'## Created\n\n{day} · Project ID: {identity}\n'),
            'LOG_STATUS.md':f'# {title.strip()} — Current Status\n\n## Summary\n\nProject created. Planning has not started yet.\n\n## Lifecycle\n\nActive.\n\n## Pending Decisions\n\n- Define the first deliverable.\n\n## Next Actions\n\n1. Review the project purpose.\n2. Record the first tasks and decisions.\n\n## Recently Updated\n\n{day}\n',
            'LOG_PROJECT.md':f'# {title.strip()} — Durable Memory\n\n## Overview\n\n{purpose.strip()}\n\n## Confirmed Decisions\n\n### {day}: Project created\n\nCreated through the LOG app. No other decisions have been recorded.\n\n## Important References\n\n- [Project rules](LOG_README.md)\n- [Current status](LOG_STATUS.md)\n'}
        folder.mkdir()
        names=[]
        try:
            for name,text in docs.items():
                (folder/name).write_text(text,encoding='utf-8'); names.append((folder/name).relative_to(ROOT).as_posix())
            commit=checkpoint(names,f'Create project: {title.strip()}')
        except Exception:
            for name in names: git('--literal-pathspecs','reset','HEAD','--',name,check=False)
            for name,text in docs.items():
                p=folder/name
                if p.exists() and p.read_text()==text: p.unlink()
            if not list(folder.iterdir()): folder.rmdir()
            raise
        return {'id':folder.relative_to(ROOT).as_posix(),'commit':commit}

def file_entry(f):
    return {'name':f.name,'path':f.relative_to(ROOT).as_posix(),'previewable':f.suffix.lower() in PREVIEW,'openable':f.suffix.lower() in OPENABLE}

def folder_tree(folder,depth=0):
    """Subfolders of a project that are not projects themselves (MVP-07), with their files."""
    out=[]
    if depth>=6: return out
    try: entries=sorted(folder.iterdir(),key=lambda e:e.name.casefold())
    except OSError: return out
    for d in entries:
        if d.name.startswith('.') or d.is_symlink() or not d.is_dir(): continue
        if any((d/n).exists() for n in CONTROL): continue  # a child project, shown as a project
        try: children=sorted(d.iterdir(),key=lambda e:e.name.casefold())
        except OSError: continue
        files=[file_entry(f) for f in children if f.is_file() and not f.is_symlink() and not f.name.startswith('.')]
        out.append({'name':d.name,'path':d.relative_to(ROOT).as_posix(),'files':files[:MAX_FOLDER_FILES],
                    'more':max(0,len(files)-MAX_FOLDER_FILES),'folders':folder_tree(d,depth+1)})
    return out

def open_native(name,reveal=False):
    """Open a project file in its own app, or show it in Finder. Only from the LOG app on this Mac."""
    if not isinstance(name,str) or not name: raise ValueError('Choose a file.')
    path=allowed(ROOT/name)
    if not path.is_file(): raise ValueError('File not found. Refresh the project list.')
    if not reveal and path.suffix.lower() not in OPENABLE:
        raise ValueError('LOG opens documents, images and media only. Use Show in Finder for this file.')
    if not NATIVE_OPEN: raise ValueError('Opening files in their own apps works on a Mac.')
    result=subprocess.run(NATIVE_OPEN+(['-R'] if reveal else [])+[str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    if result.returncode: raise ValueError('macOS could not open this file.')
    return {'opened':path.relative_to(ROOT).as_posix(),'revealed':bool(reveal)}

def catalog():
    projects=[]
    for base,dirs,names in os.walk(ROOT,followlinks=False):
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not (Path(base)/d).is_symlink())
        if not any(n in names for n in CONTROL): continue
        folder=Path(base); files=[]
        for f in sorted(folder.iterdir()):
            if f.is_file() and not f.is_symlink() and not f.name.startswith('.'):
                files.append(file_entry(f))
        docs,errors={},[]
        for name in CONTROL:
            try: docs[name]=content(folder/name)
            except (OSError,ValueError,UnicodeError) as e: errors.append(f'{name}: {"Missing file" if not (folder/name).exists() else str(e)}')
        projects.append({'id':folder.relative_to(ROOT).as_posix(),'name':folder.name,'files':files,'folders':folder_tree(folder),'docs':docs,'errors':errors,'lifecycle':lifecycle.state(docs.get('LOG_STATUS.md',''))})
    for p in projects:
        ancestors=[q for q in projects if q!=p and (p['id'].startswith(q['id']+'/') or q['id']=='.')]
        p['parent']=max(ancestors,key=lambda q:len(q['id']))['id'] if ancestors else None
    library=[{'name':p.name,'path':p.name} for p in sorted(ROOT.glob('*.md')) if p.name not in CONTROL and not p.is_symlink()]
    return {'root':str(ROOT),'projects':projects,'library':library,'historyReady':history_ready()}

def project_of(rel,ids):
    """The project that owns a path: the deepest project folder containing it, else the root project."""
    deeper=sorted((pid for pid in ids if pid!='.'),key=len,reverse=True)
    return next((pid for pid in deeper if rel.startswith(pid+'/')),'.' if '.' in ids else None)

SEARCH_FORMATS=('.md','.txt','.csv','.json')
MAX_RESULTS=200
MAX_LINES_PER_FILE=5
SNIPPET=240

def _fold(text): return ' '.join(text.split()).casefold()

def _snippet(line,needle):
    clean=' '.join(line.split())
    if len(clean)<=SNIPPET: return clean
    folded=clean.casefold()
    folded_at=folded.find(needle)
    at=0;match_end=0;offset=0
    # Case folding can expand characters (ß -> ss); map back to original positions.
    for i,char in enumerate(clean):
        next_offset=offset+len(char.casefold())
        if offset<=folded_at<next_offset: at=i
        if offset<folded_at+len(needle)<=next_offset:
            match_end=i+1;break
        offset=next_offset
    start=max(0,at-(SNIPPET-(match_end-at))//2)
    end=min(len(clean),start+SNIPPET);start=max(0,end-SNIPPET)
    return ('…' if start else '')+clean[start:end]+('…' if end<len(clean) else '')

def search(query,show_archived=False,only=None):
    """Plain-text search of project names and text files, read fresh from disk on every request.
    only: a set of project ids to search (for connected AIs); other projects are skipped before results are counted."""
    if not isinstance(query,str): raise ValueError('Enter something to search for.')
    text_query=' '.join(query.split())
    if not 2<=len(text_query)<=200: raise ValueError('Search for 2–200 characters.')
    needle=text_query.casefold()
    projects=catalog()['projects']
    archived={p['id'] for p in projects if p['lifecycle']['value']=='archived'}
    names={p['id']:p['name'] for p in projects}
    def owner(rel): return project_of(rel,names)
    project_hits=[{'id':p['id'],'name':p['name']} for p in projects if needle in _fold(p['name']) and (show_archived or p['id'] not in archived) and (only is None or p['id'] in only)]
    found,skipped=[],[];searched=0
    for base,dirs,fnames in os.walk(ROOT,followlinks=False):
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not (Path(base)/d).is_symlink())
        present=set(fnames)
        for name in sorted(fnames,key=lambda n:(n not in CONTROL,n.casefold())):
            path=Path(base)/name
            if name.startswith('.') or path.is_symlink(): continue
            rel=path.relative_to(ROOT).as_posix()
            if not show_archived and owner(rel) in archived: continue
            if only is not None and owner(rel) not in only: continue
            suffix=path.suffix.lower()
            if suffix not in SEARCH_FORMATS:
                skipped.append({'path':rel,'reason':'Not a searchable text format'});continue
            # Saved conversations and review records also have a readable .md copy; search that once.
            generated=(path.parent.name=='conversations' and len(path.stem)==32
                       and all(c in '0123456789abcdef' for c in path.stem)) or (
                       path.parent.name=='reviews' and path.name=='LOG_REVIEWS.json')
            if suffix=='.json' and generated and path.with_suffix('.md').name in present:
                try:
                    read_bytes(path.with_suffix('.md')).decode('utf-8')
                except (OSError,UnicodeError,ValueError): pass
                else: continue
            try:
                allowed(path)
                if path.stat().st_size>MAX_FILE:
                    skipped.append({'path':rel,'reason':'Larger than the 1 MB limit'});continue
                text=path.read_bytes().decode('utf-8')
            except (OSError,UnicodeError,ValueError):
                skipped.append({'path':rel,'reason':'Could not be read as UTF-8 text'});continue
            searched+=1
            hits=[(n,line) for n,line in enumerate(text.splitlines(),1) if needle in _fold(line)]
            name_hit=needle in _fold(name)
            if hits or name_hit: found.append((rel,name,name_hit,hits))
    # Control files first, then other documents, then raw history and data (conversations, review records, JSON).
    def rank(item):
        rel=item[0];parts=rel.split('/')
        if item[1] in CONTROL: return 0
        return 2 if {'conversations','reviews'} & set(parts[:-1]) or rel.lower().endswith('.json') else 1
    files=[];returned=0;truncated=False
    for rel,name,name_hit,hits in sorted(found,key=rank):
        if returned>=MAX_RESULTS:
            truncated=True;break
        shown=hits[:min(MAX_LINES_PER_FILE,MAX_RESULTS-returned)]
        returned+=max(1,len(shown))
        pid=owner(rel)
        files.append({'path':rel,'name':name,'project':pid,'projectName':names.get(pid),'nameMatch':name_hit,
                      'matchCount':len(hits),'matches':[{'line':n,'text':_snippet(line,needle)} for n,line in shown]})
    return {'query':text_query,'projects':project_hits,'files':files,'searchedFiles':searched,
            'formats':list(SEARCH_FORMATS),'skipped':skipped,'truncated':truncated,
            'searchedAt':datetime.now(timezone.utc).isoformat()}

def connection_required():
    if CONNECTION is None: raise ValueError('The LOG connection is not available in this session.')
    return CONNECTION

def connection_status():
    if CONNECTION is None: return {'available':False}
    status=CONNECTION.app_status(CONNECTION_LISTENING)
    status['available']=True
    status['projects']=[{'id':p['id'],'name':p['name'],'parent':p['parent']} for p in catalog()['projects']]
    return status

class Handler(BaseHTTPRequestHandler):
    def reply(self,status,data,mime='application/json; charset=utf-8'):
        payload=data if isinstance(data,bytes) else json.dumps(data).encode()
        self.send_response(status)
        for k,v in {'Content-Type':mime,'Content-Length':str(len(payload)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'none'; connect-src 'self'; frame-ancestors 'none'"}.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(payload)
    def access(self,write=False):
        origins=(f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        if self.headers.get('Host') not in tuple(x[7:] for x in origins): raise PermissionError('Unrecognized host.')
        if self.headers.get('Origin') and self.headers['Origin'] not in origins: raise PermissionError('Cross-origin access is not allowed.')
        if self.headers.get('Sec-Fetch-Site')=='cross-site': raise PermissionError('Cross-site access is not allowed.')
        if write and (self.headers.get('X-LOG-Request')!='1' or self.headers.get_content_type()!='application/json'):
            raise PermissionError('Writes require a same-origin LOG app request.')
    def do_GET(self): self.route(False)
    def do_POST(self): self.route(True)
    def route(self,write):
        try:
            self.access(write)
            url=urlparse(self.path); q=parse_qs(url.query)
            if write:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<7000000: raise ValueError('Invalid request size.')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict): raise ValueError('Invalid request body.')
                if url.path=='/api/openai/connect': result=chat_service.connect(body)
                elif url.path=='/api/openai/disconnect': result=chat_service.disconnect()
                elif url.path=='/api/promotion/cleanup': result=chat_service.prepare_promotion_cleanup(sys.modules[__name__],body)
                elif url.path=='/api/proposal/decision':
                    result=chat_service.decide_proposal(sys.modules[__name__],body)
                    if body.get('grant') is True and result.get('createdProject') and CONNECTION: CONNECTION.add_grant(result['createdProject'])
                elif url.path=='/api/connection/password': result=connection_required().set_password(body.get('password')) or connection_status()
                elif url.path=='/api/connection/access': connection_required().set_grants(body.get('projects'),body.get('version'));result=connection_status()
                elif url.path=='/api/connection/disconnect': connection_required().disconnect(body.get('client'));result=connection_status()
                elif url.path=='/api/connection/deny': connection_required().deny(body.get('request'));result=connection_status()
                elif url.path=='/api/chat': result=chat_service.chat(sys.modules[__name__],body)
                elif url.path=='/api/lifecycle/preview':
                    with LOCK: result=lifecycle.preview(sys.modules[__name__],body)
                elif url.path=='/api/save': result=save(body.get('path',''),body.get('content'),body.get('version'))
                elif url.path=='/api/restore': result=save(body.get('path',''),None,body.get('version'),restore=body.get('revision')) if body.get('revision') else (_ for _ in ()).throw(ValueError('Choose a saved revision.'))
                elif url.path=='/api/open': result=open_native(body.get('path'),body.get('reveal') is True)
                elif url.path=='/api/create-project': result=create_project(body.get('title'),body.get('purpose'),body.get('parent'),body.get('owner'),body.get('collaborators'),body.get('scope'),body.get('outOfScope'))
                else: return self.reply(404,{'error':'Not found.'})
                return self.reply(200,result)
            if url.path=='/': return self.reply(200,WEB.read_bytes(),'text/html; charset=utf-8')
            with LOCK:
                if url.path=='/api/openai/status': return self.reply(200,chat_service.status())
                if url.path=='/api/connection': return self.reply(200,connection_status())
                if url.path=='/api/approvals': return self.reply(200,{'approvals':chat_service.approvals(sys.modules[__name__])})
                if url.path=='/api/chat/scope': return self.reply(200,chat_service.scope(sys.modules[__name__],q.get('project',[''])[0]))
                if url.path=='/api/conversations': return self.reply(200,{'conversations':chat_service.list_conversations(sys.modules[__name__],q.get('project',[''])[0])})
                if url.path=='/api/conversation': return self.reply(200,chat_service.read_conversation(sys.modules[__name__],q.get('project',[''])[0],q.get('id',[''])[0]))
                if url.path=='/api/projects': return self.reply(200,catalog())
                if url.path=='/api/decisions': return self.reply(200,decisions.overview(sys.modules[__name__],q.get('showArchived',['false'])[0]=='true'))
                if url.path=='/api/search': return self.reply(200,search(q.get('q',[''])[0],q.get('showArchived',['false'])[0]=='true'))
                name=q.get('path',[''])[0]
                if url.path=='/api/file': return self.reply(200,file_view(name))
                if url.path=='/api/history': return self.reply(200,{'revisions':history(name)})
                if url.path=='/api/compare': return self.reply(200,compare(name,q.get('old',[''])[0],q.get('new',['working'])[0]))
            self.reply(404,{'error':'Not found.'})
        except chat_service.ChatError as e: self.reply(503,{'error':str(e)})
        except Conflict as e: self.reply(409,{'error':str(e)})
        except PermissionError as e: self.reply(403,{'error':str(e)})
        except FileNotFoundError: self.reply(404,{'error':'File not found. Refresh the project list.'})
        except (ValueError,UnicodeError,TypeError) as e: self.reply(400,{'error':str(e)})
        except (HistoryError,subprocess.TimeoutExpired) as e: self.reply(503,{'error':str(e)})
        except OSError: self.reply(500,{'error':'The operation could not finish. Check file access and available disk space.'})

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default=str(ROOT));parser.add_argument('--port',type=int,default=8765);parser.add_argument('--init-history',action='store_true')
    parser.add_argument('--connection',action='store_true',help='Accept connected AI assistants on the connection port (sign-in required).')
    parser.add_argument('--connection-port',type=int,default=8766);parser.add_argument('--public-url',default='')
    parser.add_argument('--connection-state',default=str(connection.default_state_path()))
    args=parser.parse_args();ROOT=Path(args.root).expanduser().resolve()
    if not ROOT.is_dir(): raise SystemExit('The LOG folder does not exist.')
    if args.init_history: init_history()
    chat_service.restore_connection()
    public=args.public_url or 'http://127.0.0.1:%d'%args.connection_port
    if args.connection:
        CONNECTION,_=connection.start(sys.modules[__name__],chat_service,args.connection_port,public,args.connection_state);CONNECTION_LISTENING=True
        print(f'LOG connection: {public}/mcp (listening on 127.0.0.1:{args.connection_port})',flush=True)
    else: CONNECTION=connection.Connection(sys.modules[__name__],chat_service,public,args.connection_state)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'LOG app: http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
