"""Connected-AI acceptance run: a scripted assistant signs in through a real browser page and works with a copy of the LOG folder.

Usage: python3 run_connection_acceptance.py OUTPUT_FOLDER LOG_FOLDER_COPY
Expects the LOG app on 127.0.0.1:8797 started with --connection --connection-port 8796 on that copy.
"""
import asyncio, json, re, base64, hashlib, secrets, http.client, sys
from urllib.parse import urlencode, urlparse, parse_qs
from pathlib import Path
from playwright.async_api import async_playwright
OUT=sys.argv[1]; ROOT=Path(sys.argv[2]); APP='http://127.0.0.1:8797'; CONN='http://127.0.0.1:8796'
PW='a-long-test-password-123'; REDIRECT='https://assistant.example/callback'
def req(method,path,body=None,headers=None):
    c=http.client.HTTPConnection('127.0.0.1',8796,timeout=15); c.request(method,path,body=body,headers=headers or {}); r=c.getresponse(); d=r.read(); c.close(); return r.status,dict(r.getheaders()),d
def rpc(token,method,params=None,mid=1):
    s,h,d=req('POST','/mcp',json.dumps({'jsonrpc':'2.0','id':mid,'method':method,'params':params or {}}),{'Content-Type':'application/json','Accept':'application/json, text/event-stream','Authorization':'Bearer '+token})
    return s,json.loads(d) if d else None
def tool(token,name,**a):
    s,r=rpc(token,'tools/call',{'name':name,'arguments':a}); res=r['result']; return res, res['content'][0]['text']
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); app=await b.new_page(viewport={'width':1300,'height':1100})
        errs=[]; app.on('pageerror',lambda e:errs.append('app:'+str(e))); app.on('console',lambda m: errs.append('app console:'+m.text) if m.type=='error' else None)
        app.on('dialog',lambda d: asyncio.ensure_future(d.accept()))
        await app.goto(APP); await app.wait_for_selector('#tree button')
        await app.click('#open-connection'); await app.wait_for_selector('#password-form')
        await app.screenshot(path=f'{OUT}/c1-first-visit.png')
        await app.fill('#conn-password',PW); await app.fill('#conn-password2',PW); await app.click('#password-form button[type=submit]')
        await app.wait_for_selector('text=Connection password saved.')
        await app.check('[data-grant="Family Holidays/Italy Trip"]'); await app.click('#save-access'); await app.wait_for_selector('text=Project access saved.')
        print('access file:', json.loads((ROOT/'LOG-ACCESS.json').read_text())['connectedAI'])
        # An AI assistant connects.
        s,h,d=req('POST','/register',json.dumps({'redirect_uris':[REDIRECT],'client_name':'Test Assistant','token_endpoint_auth_method':'none'}),{'Content-Type':'application/json'})
        client=json.loads(d)['client_id']; print('registered:',s)
        verifier=secrets.token_urlsafe(48); challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        q={'response_type':'code','client_id':client,'redirect_uri':REDIRECT,'code_challenge':challenge,'code_challenge_method':'S256','state':'st8','scope':'log','resource':CONN+'/mcp'}
        sign=await b.new_page(viewport={'width':520,'height':760}); sign.on('pageerror',lambda e:errs.append('signin:'+str(e)))
        captured=[]
        sign.on('request',lambda r: captured.append(r.url) if r.url.startswith('https://assistant.example/') else None)
        await sign.goto(CONN+'/authorize?'+urlencode(q)); await sign.screenshot(path=f'{OUT}/s1-signin.png')
        await sign.fill('#pw',PW); await sign.click('button[value=password]'); await sign.wait_for_selector('#code')
        await sign.screenshot(path=f'{OUT}/s2-code-entry.png')
        await app.wait_for_selector('.big-code',timeout=12000); code=(await app.text_content('.big-code')).strip()
        await app.screenshot(path=f'{OUT}/c2-signin-code.png'); print('code shown in app:', bool(re.fullmatch(r'\d{6}',code)))
        await sign.fill('#code',code); await sign.click('button[value=code]'); await sign.wait_for_timeout(800)
        back=parse_qs(urlparse(captured[0]).query); print('redirect state ok:', back['state']==['st8'])
        s,h,d=req('POST','/token',urlencode({'grant_type':'authorization_code','code':back['code'][0],'redirect_uri':REDIRECT,'client_id':client,'code_verifier':verifier,'resource':CONN+'/mcp'}),{'Content-Type':'application/x-www-form-urlencoded'})
        tok=json.loads(d); token=tok['access_token']; print('token:',s)
        # Security checks added after the review: deceptive return addresses are refused, and strangers leave no sign-in cards.
        s2,h2,d2=req('POST','/register',json.dumps({'redirect_uris':['https://evil.example\\@claude.ai/api/mcp/auth_callback'],'client_name':'Claude'}),{'Content-Type':'application/json'})
        print('deceptive return address refused:',s2==400)
        for _ in range(5): req('GET','/authorize?'+urlencode(dict(q,state='x')))
        await app.wait_for_timeout(4500); print('stranger visits shown as sign-in cards:', await app.locator('.big-code').count())
        await app.wait_for_selector('#conn-clients [data-disconnect]',timeout=6000); print('assistant listed without reload: True')
        s,r=rpc(token,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}}); print('initialize:',r['result']['protocolVersion'],'| rules included:','LOG rules for AI assistants' in r['result']['instructions'])
        res,text=tool(token,'list_projects'); print('list_projects:',[x['project'] for x in res['structuredContent']['projects']])
        res,text=tool(token,'open_project',project='Family Holidays'); print('ungranted parent refused:',res['isError'])
        res,text=tool(token,'read_file',path='Family Holidays/Italy Trip/LOG_STATUS.md'); version=res['structuredContent']['version']; before=res['structuredContent']['text']
        res,text=tool(token,'search',query='consisting of two adults'); print('search outside grant hidden:',res['structuredContent']['files']==[])
        new=before.replace('## Recently Updated','## Notes\n\nAim for mid-May.\n\n## Recently Updated')
        res,text=tool(token,'propose_change',project='Family Holidays/Italy Trip',path='Family Holidays/Italy Trip/LOG_STATUS.md',content=new,reason='User asked to aim for mid-May.',base_version=version)
        print('propose_change:',text[:90]); print('file unchanged before approval:',(ROOT/'Family Holidays/Italy Trip/LOG_STATUS.md').read_text()==before)
        await app.wait_for_selector('[data-approval]',timeout=12000); await app.screenshot(path=f'{OUT}/c3-waiting.png')
        print('badge:', await app.text_content('#approval-count'))
        await app.click('[data-approval="0"]'); await app.wait_for_timeout(1500)
        print('dialog open:', await app.evaluate("document.querySelector('#proposal-dialog').open"), '| message:', await app.evaluate("(document.getElementById('connection-message')||{}).textContent"), '| errors:', errs)
        await app.wait_for_selector('#proposal-dialog[open]',timeout=5000)
        await app.screenshot(path=f'{OUT}/c4-review.png')
        print('grant option hidden for a file change:', not await app.is_visible('#grant-row'))
        await app.click('#approve-proposal'); await app.wait_for_selector('#proposal-dialog',state='hidden'); await app.wait_for_selector('#password-form')
        print('approved & saved:',(ROOT/'Family Holidays/Italy Trip/LOG_STATUS.md').read_text()==new)
        res,text=tool(token,'list_pending'); print('AI sees decision:',[d['status'] for d in res['structuredContent']['decided']])
        res,text=tool(token,'propose_project',parent='Family Holidays/Italy Trip',title='Rome Hotels',purpose='Compare hotels in Rome for the four nights.',reason='Hotel research is its own workstream.')
        await app.wait_for_selector('text=New project: Family Holidays/Italy Trip/Rome Hotels',timeout=12000)
        await app.click('[data-approval="0"]'); await app.wait_for_selector('#grant-row:not([hidden])'); await app.screenshot(path=f'{OUT}/c5-project-review.png')
        print('grant option shown for a new project:', await app.is_visible('#grant-row'))
        await app.click('#approve-proposal'); await app.wait_for_selector('#proposal-dialog',state='hidden'); await app.wait_for_timeout(600)
        print('project created:',(ROOT/'Family Holidays/Italy Trip/Rome Hotels/LOG_README.md').exists(),'| granted:','Family Holidays/Italy Trip/Rome Hotels' in json.loads((ROOT/'LOG-ACCESS.json').read_text())['connectedAI']['projects'])
        res,text=tool(token,'propose_session_record',project='Family Holidays/Italy Trip',title='Planning chat',summary='Talked through the route after Rome.',decisions=['Aim for mid-May'],open_questions=['Venice or not?'],next_steps=['Compare train fares'],files_consulted=['Family Holidays/Italy Trip/LOG_STATUS.md'])
        spath=res['structuredContent']['path']; print('session record proposed, not saved:', not (ROOT/spath).exists())
        await app.wait_for_selector('text=Session record:',timeout=12000); await app.screenshot(path=f'{OUT}/c7-session-waiting.png')
        await app.click('[data-approval="0"]'); await app.wait_for_selector('#proposal-dialog[open]',timeout=5000)
        print('dialog explains session record:', 'conversations folder' in (await app.text_content('#proposal-status')))
        await app.screenshot(path=f'{OUT}/c8-session-review.png')
        print('grant option hidden for a session record:', not await app.is_visible('#grant-row'))
        await app.click('#approve-proposal'); await app.wait_for_selector('#proposal-dialog',state='hidden'); await app.wait_for_timeout(600)
        print('session record saved:', (ROOT/spath).exists() and 'Aim for mid-May' in (ROOT/spath).read_text())
        await app.wait_for_selector('[data-disconnect]'); await app.screenshot(path=f'{OUT}/c6-connected.png',full_page=True)
        await app.click('[data-disconnect]'); await app.wait_for_selector('text=Disconnected.')
        s,r=rpc(token,'ping'); print('after disconnect:',s)
        # phone width
        ph=await b.new_page(viewport={'width':390,'height':900}); await ph.goto(APP); await ph.wait_for_selector('#tree button'); await ph.click('#open-connection'); await ph.wait_for_selector('#password-form')
        print('phone scrollWidth:',await ph.evaluate('document.documentElement.scrollWidth'))
        print('errors:',errs)
        await b.close()
asyncio.run(main())
