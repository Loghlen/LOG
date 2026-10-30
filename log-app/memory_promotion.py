"""Conservative, two-stage memory promotion. No semantic equivalence guesses."""
from collections import Counter
import copy
import uuid

def content_lines(text):
    # Preserve every nonblank line, including headings and source links.
    return Counter(line.strip() for line in text.splitlines() if line.strip())

def removed(before,after):
    return list((content_lines(before)-content_lines(after)).elements())

def contains(text,lines):
    return not (Counter(lines)-content_lines(text))

def saved_copy(s,path,text):
    value=s.read_bytes(s.ROOT/path)
    if value.decode()!=text:return False
    result=s.git('show','HEAD:'+path,check=False)
    return result.returncode==0 and result.stdout==value

def stage(s,identity,proposals,docs,mode):
    status=(s.ROOT/identity/'LOG_STATUS.md').relative_to(s.ROOT).as_posix()
    durable=(s.ROOT/identity/'LOG_PROJECT.md').relative_to(s.ROOT).as_posix()
    bypath={p['path']:p for p in proposals}
    if mode!='memory' and not (status in bypath and durable in bypath):return proposals,[]
    result=[];notes=[]
    destination=bypath.get(durable)
    if destination and removed(destination['before'],destination['content']):
        notes.append('The durable-memory rewrite was withheld because it removes existing text. Memory review only adds information; use an explicit document edit for intentional replacement.')
        destination=None
    durable_doc=next((d for d in docs if d['path']==durable),None)
    for p in proposals:
        if p['path']==durable:
            if destination:result.append(p)
            continue
        if p['path']!=status or not removed(p['before'],p['content']):
            result.append(p);continue
        lines=removed(p['before'],p['content'])
        if destination and contains(destination['content'],lines):
            destination['promotionCleanup']=copy.deepcopy(p)
            notes.append('Save and verify the durable-memory proposal first. Then use Review status cleanup to prepare a separate approval; current status remains unchanged until then.')
        elif durable_doc and contains(durable_doc['text'],lines) and saved_copy(s,durable,durable_doc['text']):
            p['promotionDestination']={'path':durable,'version':durable_doc['sha256'],'preservedLines':lines}
            result.append(p)
        else:
            notes.append('Status cleanup was withheld: some removed text has no exact, saved copy in durable memory. The original status remains unchanged. Ask to copy the exact text, including its headings and source links, first.')
    return result,notes

def verify_cleanup(s,p):
    dest=p.get('promotionDestination')
    if not dest:raise s.Conflict('This memory cleanup has no verified durable copy. Run a new memory review before removing status information.')
    value=s.read_bytes(s.ROOT/dest['path'])
    if s.digest(value)!=dest['version'] or not contains(value.decode(),removed(p['before'],p['content'])):
        raise s.Conflict('Durable memory changed since cleanup was prepared. Nothing was removed. Prepare a new memory review.')
    if not saved_copy(s,dest['path'],value.decode()):
        raise s.Conflict('The durable copy is not in saved history. Save it before preparing cleanup.')
    return dest['path'],value

def prepare(s,c,parent):
    if parent['status']!='approved':raise s.Conflict('Approve and save the durable-memory copy first.')
    draft=parent.get('promotionCleanup')
    if not draft:raise ValueError('This proposal has no staged status cleanup.')
    existing=next((p for t in c['turns'] for p in t.get('proposals',[]) if p.get('promotionParent')==parent['id']),None)
    if existing:return existing,False
    value=s.read_bytes(s.ROOT/parent['path'])
    if value.decode()!=parent['content'] or not saved_copy(s,parent['path'],parent['content']):
        raise s.Conflict('The durable-memory copy changed or is not saved. Run a new review. Status was not changed.')
    if s.digest(s.read_bytes(s.ROOT/draft['path']))!=draft['version']:
        raise s.Conflict('Current status changed after the proposal. Run a new review; nothing was removed.')
    lines=removed(draft['before'],draft['content'])
    if not contains(value.decode(),lines):raise s.Conflict('The durable copy does not contain all removed text. Nothing was removed.')
    p=copy.deepcopy(draft);p['id']=uuid.uuid4().hex;p['promotionParent']=parent['id']
    p['promotionDestination']={'path':parent['path'],'version':s.digest(value),'preservedLines':lines}
    return p,True
