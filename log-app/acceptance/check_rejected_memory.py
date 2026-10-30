import sys,json,uuid
from pathlib import Path
sys.path.insert(0,str(Path('log-app').resolve()))
import server,chat_service as chat
out=Path(sys.argv[1] if len(sys.argv)>1 else 'log-app/acceptance/memory-2026-10-19');evidence=json.loads((out/'results.json').read_text())
server.ROOT=Path(evidence['fixtureRoot']);chat.restore_connection()
identity='Test Trip';cid=uuid.uuid4().hex
c={'id':cid,'project':identity,'title':'New preference for rejection persistence test','scope':[],'turns':[{'requestId':uuid.uuid4().hex,'question':'I prefer aisle seats. Please remember this for the trip.','answer':'Aisle seats are your stated preference; not saved yet.','created':'2026-10-19','status':'complete','mode':'auto','model':'fixture','sources':[]}]}
with server.LOCK:chat.persist(server,c)
for label in ('before_rejection','after_rejection'):
 r=chat.chat(server,{'project':identity,'message':'Review project memory and propose supported updates.','mode':'memory','sources':[],'reviewConversations':[cid],'requestId':uuid.uuid4().hex})
 t=r['conversation']['turns'][0]
 evidence['results'].append({'label':label,'conversation':r['conversation']['id'],'status':t['status'],'answer':t.get('answer'),'proposals':t.get('proposals',[]),'usage':t.get('usage')})
 (out/'results.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
 print(json.dumps({'label':label,'status':t['status'],'proposals':len(t.get('proposals',[]))}),flush=True)
 if label=='before_rejection':
  for p in t.get('proposals',[]):chat.decide_proposal(server,{'project':identity,'conversation':r['conversation']['id'],'proposal':p['id'],'decision':'reject'})
print('Rejection-persistence evidence saved.',flush=True)
