"""Acceptance run for MVP-07 (browse folders), MVP-03 (README identity) and MVP-10 (pending decisions).

Usage: python3 accept_mvp.py OUTPUT_FOLDER LOG_FOLDER_COPY
Expects the LOG app on 127.0.0.1:8797, started on that copy. Creates its fixtures in the copy only.
"""
import asyncio, re, sys
from pathlib import Path
from playwright.async_api import async_playwright
OUT = sys.argv[1]; ROOT = Path(sys.argv[2]); APP = 'http://127.0.0.1:8797'
def fixtures():
    italy = ROOT / 'Family Holidays/Italy Trip'
    (italy / 'documents').mkdir(exist_ok=True); (italy / 'research/2026').mkdir(parents=True, exist_ok=True)
    (italy / 'documents/booking-notes.md').write_text('# Booking notes\n\nAsk about late check-in in Rome.\n')
    (italy / 'documents/flight.pdf').write_bytes(b'%PDF-1.4 sample')
    (italy / 'research/2026/fares.csv').write_text('route,price\nRome-Florence,35\n')
    (italy / 'research/setup.command').write_text('#!/bin/sh\necho test\n')
    d = ROOT / 'Decision Test'; d.mkdir(exist_ok=True)
    (d / 'LOG_README.md').write_text('# Decision Test\n\n## Purpose\n\nFixture for MVP-10.\n')
    (d / 'LOG_STATUS.md').write_text('# Decision Test — Current Status\n\n## Lifecycle\n\nActive.\n\n## Suggestions\n\n- Maybe hire a van instead.\n\n## Pending Decisions\n\n- Which weekend should the move happen?\n')
    (d / 'LOG_PROJECT.md').write_text('# Decision Test — Durable Memory\n\n## Decisions\n\n### 2026-10-23: Use a removal company\n\nDecision: Book a removal company rather than moving ourselves.\n')
async def main():
    fixtures()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 1300, 'height': 1000}); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(APP); await pg.wait_for_selector('#tree button')
        # MVP-07
        await pg.click('#tree button[data-project="Family Holidays/Italy Trip"]'); await pg.wait_for_timeout(400)
        print('07 overview mentions folders:', await pg.locator('button[data-tab="files"].file-button').count() == 1)
        await pg.click('button.tab[data-tab="files"]'); await pg.wait_for_timeout(300)
        await pg.click('details[data-folder="Family Holidays/Italy Trip/documents"] > summary')
        await pg.click('details[data-folder="Family Holidays/Italy Trip/research"] > summary')
        await pg.click('details[data-folder="Family Holidays/Italy Trip/research/2026"] > summary')
        await pg.screenshot(path=f'{OUT}/1-folders.png', full_page=True)
        print('07 open offered for the PDF, not for the script:', await pg.locator('button[data-open="Family Holidays/Italy Trip/documents/flight.pdf"]').count() == 1,
              await pg.locator('button[data-open="Family Holidays/Italy Trip/research/setup.command"]').count() == 0)
        await pg.click('button[data-file="Family Holidays/Italy Trip/documents/booking-notes.md"]'); await pg.wait_for_timeout(400)
        print('07 preview of a file in documents/:', 'late check-in' in await pg.text_content('article.document'))
        await pg.screenshot(path=f'{OUT}/2-preview.png')
        await pg.click('#back'); await pg.wait_for_timeout(300)
        print('07 back to the folder list with folders still open:', await pg.locator('details[data-folder="Family Holidays/Italy Trip/research/2026"][open]').count() == 1)
        await pg.click('button[data-file="Family Holidays/Italy Trip/research/2026/fares.csv"]'); await pg.wait_for_timeout(400)
        print('07 preview of a file in research/2026/:', 'Rome-Florence' in await pg.text_content('article.document'))
        await pg.click('#back'); await pg.wait_for_timeout(300)
        await pg.click('button[data-open="Family Holidays/Italy Trip/documents/flight.pdf"]'); await pg.wait_for_timeout(500)
        print('07 open in its own app answered:', await pg.text_content('#open-message'))
        await pg.click('button[data-reveal="Family Holidays/Italy Trip/research/setup.command"]'); await pg.wait_for_timeout(500)
        print('07 show in Finder answered:', await pg.text_content('#open-message'))
        # MVP-03
        await pg.click('#tree button[data-project="."]'); await pg.wait_for_timeout(300)
        await pg.click('#new-project'); await pg.wait_for_selector('#project-dialog[open]')
        await pg.select_option('#project-parent', '')
        print('03 owner prefilled from the root project:', await pg.input_value('#project-owner'))
        await pg.fill('input[name=title]', 'Taxes 2026'); await pg.fill('textarea[name=purpose]', 'File the 2026 tax return on time.')
        await pg.click('.more-fields > summary'); await pg.fill('textarea[name=collaborators]', 'Accountant (by email)')
        await pg.fill('textarea[name=scope]', 'Forms, receipts and correspondence for the 2026 return.')
        await pg.screenshot(path=f'{OUT}/3-new-project.png')
        await pg.click('#create-submit'); await pg.wait_for_selector('#project-dialog', state='hidden'); await pg.wait_for_timeout(400)
        readme = (ROOT / 'Taxes 2026/LOG_README.md').read_text()
        print('03 README sections:', re.findall(r'^## (.+)$', readme, re.M))
        print('03 README owner/collaborators/parent:', [l for l in readme.splitlines() if l.startswith(('Loghlen', 'Accountant', '[LOG]'))])
        (Path(OUT) / '3-README-created.md').write_text(readme)
        # MVP-10
        await pg.click('#open-decisions'); await pg.wait_for_selector('h1:text("Pending decisions")')
        card = pg.locator('section.card', has=pg.locator('h2:text("Decision Test")'))
        text = await card.text_content()
        print('10 unanswered choice pending:', 'Which weekend should the move happen?' in text)
        print('10 suggestion not shown:', 'hire a van' not in await pg.text_content('#content'))
        await card.locator('details > summary').click()
        print('10 approved decision shown as decided:', 'Use a removal company' in await card.locator('details').text_content())
        print('10 pending count in sidebar:', await pg.text_content('#decision-count'))
        await pg.screenshot(path=f'{OUT}/4-pending-decisions.png', full_page=True)
        ph = await b.new_page(viewport={'width': 390, 'height': 900}); await ph.goto(APP); await ph.wait_for_selector('#tree button')
        await ph.click('#open-decisions'); await ph.wait_for_selector('h1:text("Pending decisions")')
        print('phone width:', await ph.evaluate('document.documentElement.scrollWidth'))
        print('errors:', errs); await b.close()
asyncio.run(main())
