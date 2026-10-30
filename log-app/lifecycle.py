"""Project lifecycle edits use the same readable files and revision checks as other saves."""
import re
import difflib
from datetime import datetime
STATES=('active','pending','blocked','completed','archived')

def sections(text,name):
    lines=text.splitlines(keepends=True);heads=[];fence=False
    for i,line in enumerate(lines):
        if line.lstrip().startswith(('```','~~~')): fence=not fence
        if not fence and re.match(r'^##\s+',line):heads.append(i)
    return [(i, next((j for j in heads if j>i),len(lines))) for i in heads
            if lines[i].strip().casefold()=='## '+name.casefold()],lines

def state(text):
    spans,lines=sections(text,'Lifecycle')
    if len(spans)!=1:return {'value':None,'reason':'','warning':'Lifecycle is missing or duplicated. Review LOG_STATUS.md.'}
    a,b=spans[0];body=''.join(lines[a+1:b]).strip();first=body.splitlines()[0] if body else ''
    match=re.fullmatch(r'(active|pending|blocked|completed|archived)(?:\.|\s*[—–-]\s*.*)?',first,re.I)
    reason='\n'.join(body.splitlines()[1:]).strip()
    reason=re.sub(r'^Reason:\s*','',reason)
    if match and not reason:
        reason=re.sub(r'^(active|pending|blocked|completed|archived)[.\s—–-]*','',first,flags=re.I)
    return {'value':match.group(1).lower() if match else None,'reason':reason,
            'warning':'' if match else 'Unrecognized lifecycle: '+first+'. Choose a supported status.'}

def replace_section(text,name,body):
    spans,lines=sections(text,name)
    if len(spans)>1:raise ValueError('Multiple '+name+' sections found. Resolve them in the file first.')
    block='## '+name+'\n\n'+body.strip()+'\n\n'
    if not spans:return text.rstrip()+'\n\n'+block
    a,b=spans[0];return ''.join(lines[:a])+block+''.join(lines[b:])

def preview(s,body):
    identity=body.get('project')
    if identity not in {p['id'] for p in s.catalog()['projects']}:raise ValueError('Choose an existing project.')
    value=body.get('status');reason=body.get('reason','')
    if value not in STATES:raise ValueError('Choose Active, Pending, Blocked, Completed or Archived.')
    if not isinstance(reason,str) or len(reason)>2000:raise ValueError('Keep the reason under 2,000 characters.')
    if any(re.match(r'^\s*(?:#|```|~~~)',line) for line in reason.splitlines()):raise ValueError('Use plain text for the status reason, without headings or code fences.')
    path=(s.ROOT/identity/'LOG_STATUS.md').relative_to(s.ROOT).as_posix()
    old=s.file_view(path)
    content=replace_section(old['content'],'Lifecycle',value.capitalize()+'.'+('\n\nReason: '+reason.strip() if reason.strip() else ''))
    content=replace_section(content,'Recently Updated',datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z'))
    return {**old,'content':content,'before':old['content'],
            'diff':''.join(difflib.unified_diff(old['content'].splitlines(True),content.splitlines(True),fromfile='Before',tofile='Proposed'))}
