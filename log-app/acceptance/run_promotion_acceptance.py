"""Live exact-copy promotion on a disposable fixture; never real project facts."""
import sys,json,tempfile,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,chat_service as chat
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
server.ROOT=Path(tempfile.mkdtemp(prefix='log-promotion-acceptance-')).resolve();server.init_history();server.create_project('Test','Fictional promotion test','')
status='# Current Status\n\n## Confirmed preference\n- Vegetarian meals. Source: user confirmation in this fictional fixture.\n\n## Next actions\n- Compare trains.\n'
memory='# Durable Memory\n\n- Existing fact: this is a fictional test.\n'
for name,text in [('Test/LOG_STATUS.md',status),('Test/LOG_PROJECT.md',memory)]:server.save(name,text,server.file_view(name)['version'])
chat.restore_connection()
if not chat.KEY:raise SystemExit('No saved API connection.')
r=chat.chat(server,{'project':'Test','mode':'memory','message':'Promote the confirmed preference into durable memory. Copy the entire Confirmed preference section verbatim including its heading and source; retain all existing durable memory. Propose removing only that section from current status after the copy is saved. Preserve Current Status and Next actions.','sources':[],'reviewConversations':[],'requestId':uuid.uuid4().hex})
c=r['conversation'];t=c['turns'][0]
evidence={'fixtureRoot':str(server.ROOT),'model':chat.MODEL,'turn':t,'stages':[]}
assert (server.ROOT/'Test/LOG_STATUS.md').read_text()==status
p=next((p for p in t.get('proposals',[]) if p.get('promotionCleanup')),None)
if p:
 chat.decide_proposal(server,{'project':'Test','conversation':c['id'],'proposal':p['id'],'decision':'approve'})
 assert (server.ROOT/'Test/LOG_STATUS.md').read_text()==status
 evidence['stages'].append('Durable copy saved; status unchanged')
 cleanup=chat.prepare_promotion_cleanup(server,{'project':'Test','conversation':c['id'],'proposal':p['id']})
 evidence['stages'].append('Cleanup prepared; status unchanged')
 chat.decide_proposal(server,{'project':'Test','conversation':c['id'],'proposal':cleanup['proposal'],'decision':'approve'})
 assert 'Vegetarian meals' not in (server.ROOT/'Test/LOG_STATUS.md').read_text()
 assert 'Vegetarian meals' in (server.ROOT/'Test/LOG_PROJECT.md').read_text()
 assert '- Compare trains.' in (server.ROOT/'Test/LOG_STATUS.md').read_text()
 assert 'Existing fact' in (server.ROOT/'Test/LOG_PROJECT.md').read_text()
 evidence['stages'].append('Cleanup approved; unique fact preserved in durable memory and unrelated text retained')
else:evidence['stages'].append('Model did not return an exact-copy staged proposal; no cleanup applied')
(out/'promotion-live.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
print(json.dumps({'status':t['status'],'stagedProposal':bool(p),'stages':evidence['stages']}),flush=True)
