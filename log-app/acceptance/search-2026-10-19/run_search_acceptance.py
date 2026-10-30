import asyncio, sys
from playwright.async_api import async_playwright
OUT=sys.argv[1]
async def search(pg,q):
    await pg.fill('#search-input',q); await pg.press('#search-input','Enter'); await pg.wait_for_timeout(400)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':1300,'height':1100})
        errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
        dialogs=[]; pg.on('dialog',lambda d:(dialogs.append(d.message),asyncio.ensure_future(d.dismiss())))
        await pg.goto('http://127.0.0.1:8798/'); await pg.wait_for_selector('#tree button')
        # 1. Known project name
        await search(pg,'Italy Trip')
        print('1 project results:', await pg.eval_on_selector_all('section.card:has(h2:text("Projects")) .result b','e=>e.map(x=>x.textContent)'))
        print('1 meta:', await pg.text_content('.search-meta'))
        await pg.screenshot(path=f'{OUT}/1-project-name.png',full_page=False)
        await pg.click('button.result[data-project="Family Holidays/Italy Trip"]'); await pg.wait_for_timeout(300)
        print('1 opened project:', await pg.text_content('h1'))
        # 2. Unique phrase in a control file, then open the result
        await search(pg,'fictional household, consisting of two adults')
        files=await pg.eval_on_selector_all('button.result[data-file]','e=>e.map(x=>x.dataset.file)')
        print('2 files:',files, '| hit:', await pg.text_content('button.result[data-file] .hit'))
        await pg.screenshot(path=f'{OUT}/2-phrase.png')
        await pg.click('button.result[data-file]'); await pg.wait_for_timeout(400)
        print('2 opened:', await pg.text_content('#crumb'), '| contains phrase:', 'consisting of two adults' in (await pg.text_content('article.document')))
        # 3. Nonexistent term -> explicit empty state
        await search(pg,'zebra-free phrase')
        print('3 empty:', await pg.text_content('.empty h2'), '| note:', (await pg.text_content('.footer-note'))[:80])
        await pg.screenshot(path=f'{OUT}/3-empty.png')
        # 4. Too short
        await search(pg,'a'); print('4 hint:', await pg.text_content('#search-hint'))
        # 5. Unsaved draft is protected
        await pg.click('button[data-project="Family Holidays/Italy Trip"]'); await pg.wait_for_timeout(300)
        await pg.click('button.file-button[data-file="Family Holidays/Italy Trip/LOG_STATUS.md"]'); await pg.wait_for_timeout(400)
        await pg.click('#edit'); await pg.fill('#editor','unsaved draft'); 
        await search(pg,'Rome'); print('5 dialog:', dialogs[-1:] , '| still editing:', await pg.is_visible('#editor'))
        # 6. Phone width
        pg2=await b.new_page(viewport={'width':390,'height':900}); await pg2.goto('http://127.0.0.1:8798/'); await pg2.wait_for_selector('#tree button')
        await pg2.fill('#search-input','four nights in Rome'); await pg2.press('#search-input','Enter'); await pg2.wait_for_timeout(500)
        sw=await pg2.evaluate('document.documentElement.scrollWidth'); print('6 phone scrollWidth:',sw)
        await pg2.screenshot(path=f'{OUT}/6-phone.png',full_page=True)
        print('errors:',errs)
        await b.close()
asyncio.run(main())
