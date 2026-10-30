"""MVP-10: find each project's pending decisions, read straight from its files.

A decision is pending only if it is listed under "Pending Decisions" in the project's LOG_STATUS.md.
Confirmed decisions are the "### ..." entries under "Decisions" or "Confirmed Decisions" in LOG_PROJECT.md.
Suggestions and proposals elsewhere are never counted as either. A pending item worded like a confirmed
decision is flagged, because the status file may not have caught up.
"""
import re
import lifecycle

STOP = set('a an and any are as at be been before by can could do does for from had has have how i if in into is it its '
           'keep more not now of on or our should so than that the their there these this to too was we were what when '
           'whether which who will with would yet after them they us use'.split())


def section_items(text, name):
    """Top-level list items under '## name', with continuation lines joined. Returns (items, note)."""
    spans, lines = lifecycle.sections(text or '', name)
    items, prose = [], []
    for a, b in spans:
        current = None
        for i in range(a + 1, b):
            line = lines[i].rstrip('\n')
            m = re.match(r'^(?:[-*+]|\d+[.)])\s+(.*\S)', line)
            if m:
                current = {'text': m.group(1).strip(), 'line': i + 1}
                items.append(current)
            elif line.strip() and current is not None and line[:1] in (' ', '\t'):
                current['text'] += ' ' + line.strip()
            elif line.strip():
                current = None
                prose.append(line.strip())
    return items, ' '.join(prose)


def confirmed(text):
    """Entries under '## Decisions' or '## Confirmed Decisions' in LOG_PROJECT.md."""
    out = []
    for name in ('Decisions', 'Confirmed Decisions'):
        spans, lines = lifecycle.sections(text or '', name)
        for a, b in spans:
            entry = None
            for i in range(a + 1, b):
                line = lines[i].rstrip('\n')
                m = re.match(r'^###\s+(.*\S)', line)
                if m:
                    heading = m.group(1)
                    d = re.match(r'(\d{4}-\d{2}-\d{2})\s*[:—–-]\s*(.*)', heading)
                    entry = {'date': d.group(1) if d else '', 'title': (d.group(2) if d else heading).strip(), 'decision': '', 'line': i + 1}
                    out.append(entry)
                elif entry and not entry['decision'] and line.startswith('Decision:'):
                    entry['decision'] = line[len('Decision:'):].strip()
    return out


def words(text):
    found = set()
    for w in re.findall(r'[a-z0-9£$€]+', text.lower()):
        if w in STOP or len(w) < 2: continue
        found.add(w[:-1] if len(w) > 3 and w.endswith('s') else w)
    return found


def similar(pending, decision):
    a = words(pending)
    best = 0
    for candidate in (decision['title'], decision['decision']):
        b = words(candidate)
        if a and b: best = max(best, len(a & b) / len(a | b))
    return best


def project(p):
    status = p['docs'].get('LOG_STATUS.md', '')
    durable = p['docs'].get('LOG_PROJECT.md', '')
    items, note = section_items(status, 'Pending Decisions')
    done = confirmed(durable)
    for item in items:
        match = max(done, key=lambda d: similar(item['text'], d), default=None)
        item['possiblyDecided'] = ({'date': match['date'], 'title': match['title']}
                                   if match and similar(item['text'], match) >= 0.5 else None)
    recent = sorted(done, key=lambda d: d['date'], reverse=True)
    return {'id': p['id'], 'name': p['name'], 'lifecycle': (p.get('lifecycle') or {}).get('value'),
            'pending': items, 'note': note if not items else '', 'confirmed': recent[:5], 'confirmedCount': len(done)}


def overview(s, show_archived=False):
    projects = [p for p in s.catalog()['projects']
                if show_archived or (p.get('lifecycle') or {}).get('value') != 'archived']
    result = [project(p) for p in projects]
    return {'projects': result, 'pendingCount': sum(len(p['pending']) for p in result)}
