"""File-backed review decisions and deterministic repeated-edit checks."""
import difflib
import json
import re
import unicodedata

MAX_RECORD=8000000

def edit_parts(before,after):
    # Ignore formatting and source-link labels when recognizing the same edit.
    def normal(line):
        # Invisible characters and look-alike forms must not make a rejected edit look new.
        line=''.join(c for c in unicodedata.normalize('NFKC',line) if unicodedata.category(c)!='Cf')
        line=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',line)
        return ' '.join(re.sub(r'[*_`#]','',line).casefold().split()).strip('- ')
    a=before.splitlines();b=after.splitlines();removed=[];added=[]
    for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if tag!='equal':
            removed.extend(filter(None,(normal(x) for x in a[i:j])))
            added.extend(filter(None,(normal(x) for x in b[k:l])))
    return {'removed':sorted(set(removed)),'added':sorted(set(added))}

def from_conversation(c):
    result=[]
    for t in c['turns']:
        for p in t.get('proposals',[]):
            if p.get('status') not in ('approved','rejected'):continue
            result.append({'id':p['id'],'project':c['project'],'conversation':c['id'],
                'path':p['path'],'decision':p['status'],'reviewed':p.get('reviewed',t.get('created','')),
                'reason':p['reason'],'beforeHash':p['version'],
                'edit':edit_parts(p['before'],p['content']),
                'diff':p['diff'],'sources':t.get('sources',[]),
                'reversal':p.get('reversal'),
                'reconsidered':bool(t.get('reconsiderRejected',False))})
    return result

def load(s,chat,identity):
    folder=s.allowed(s.ROOT/identity/'reviews')
    path=s.allowed(folder/'LOG_REVIEWS.json')
    records={}
    if path.exists():
        if path.stat().st_size>MAX_RECORD:raise ValueError('The review record exceeds the local size limit.')
        doc=json.loads(path.read_text())
        if doc.get('project')!=identity or not isinstance(doc.get('reviews'),list):raise ValueError('Invalid project review record.')
        for r in doc['reviews']:records[r['id']]=r
    # Backfill all existing review decisions, including those made before this feature.
    convfolder=s.allowed(s.ROOT/identity/'conversations')
    if convfolder.exists():
        for path in sorted(convfolder.glob('*.json')):
            if not re.fullmatch('[a-f0-9]{32}',path.stem):continue
            c=chat.read_conversation(s,identity,path.stem)
            for r in from_conversation(c):records[r['id']]=r
    return sorted(records.values(),key=lambda r:(r['reviewed'],r['id']))

def writes(s,identity,records):
    folder=s.allowed(s.ROOT/identity/'reviews');folder.mkdir(exist_ok=True)
    jsonpath=s.allowed(folder/'LOG_REVIEWS.json');mdpath=s.allowed(folder/'LOG_REVIEWS.md')
    raw=json.dumps({'project':identity,'reviews':records},ensure_ascii=False,indent=2).encode()
    if len(raw)>MAX_RECORD:raise ValueError('The review record exceeds the local size limit.')
    lines=['# Project review record','','Project: '+identity,'',
           'Supporting history, not project facts. Rejection means do not apply this edit; it does not mean the underlying fact is false.',
           'Generated from saved proposal decisions. Each decision and its source evidence remain in the linked conversation.','']
    for r in records:
        lines += ['## '+r['decision'].capitalize()+(' (later reversed)' if r.get('reversal') else '')+': '+r['path'],'',
                  'Reviewed: '+r['reviewed'],'',*(['Later reversal: '+json.dumps(r['reversal'],ensure_ascii=False),''] if r.get('reversal') else []),r['reason'],'',
                  '[Conversation](../conversations/'+r['conversation']+'.md)',
                  '','Explicit reconsideration: '+str(r['reconsidered']),'',
                  'Sources: '+', '.join(d['path']+' (SHA-256 '+d['sha256']+')' for d in r['sources']),'',
                  '```diff',r['diff'],'```','']
    return {jsonpath.relative_to(s.ROOT).as_posix():raw,mdpath.relative_to(s.ROOT).as_posix():'\n'.join(lines).encode()}

def context(records,docs):
    permitted={d['path'] for d in docs}
    eligible=[{'path':r['path'],'decision':r['decision'],'reason':r['reason'],'edit':r['edit'],'reviewed':r['reviewed'],'reversal':r.get('reversal')}
              for r in records if r['path'] in permitted and all(d['path'] in permitted for d in r['sources'])]
    text=json.dumps(eligible,ensure_ascii=False)
    if len(text)>24000:raise ValueError('Relevant review history is too large for this request. No decisions were silently omitted.')
    return text

def repeated(proposal,records):
    edit=edit_parts(proposal['before'],proposal['content'])
    for r in reversed(records):
        if r['decision']!='rejected' or r['path']!=proposal['path']:continue
        prior=r['edit']
        if (prior['added'] or prior['removed']) and all(set(prior[k]).issubset(edit[k]) for k in ('added','removed')):
            return True
    return False
