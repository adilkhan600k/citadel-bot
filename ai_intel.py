#!/usr/bin/env python3
"""Citad3l AI War Room bot. Free sources only.
  python3 ai_intel.py news [--dry]      daily plain-English AI intel briefing -> #ai-intel
  python3 ai_intel.py calendar [--dry]  edit the pinned AI release calendar  -> #ai-calendar
"""
import os, sys, json, re, html, time, datetime as dt, urllib.request, urllib.error, email.utils, hashlib
import xml.etree.ElementTree as ET
D = os.path.dirname(os.path.abspath(__file__))
STATE = f'{D}/ai_intel_state.json'; CAL = f'{D}/ai_calendar.json'; CHS = f'{D}/ai_channels.json'
DRY = '--dry' in sys.argv
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
SILVER = 0xC0C7D0
NOW = dt.datetime.now(dt.timezone.utc)

def load(p, d):
    try: return json.load(open(p))
    except Exception: return d
def save(p, o):
    tmp = p + '.tmp'; json.dump(o, open(tmp, 'w'), indent=1); os.replace(tmp, p)

def dapi(m, p, d=None, tries=6):
    T = os.environ['DISCORD_BOT_TOKEN']
    for i in range(tries):
        r = urllib.request.Request('https://discord.com/api/v10' + p, method=m,
            data=json.dumps(d).encode() if d is not None else None,
            headers={'Authorization': 'Bot ' + T, 'Content-Type': 'application/json', 'User-Agent': 'DiscordBot (citad3l,1)'})
        try:
            with urllib.request.urlopen(r, timeout=30) as x:
                b = x.read(); return json.loads(b) if b else None
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='ignore')
            if e.code == 429:
                try: w = float(json.loads(body).get('retry_after', 2))
                except Exception: w = 2
                time.sleep(w + 0.5); continue
            if e.code >= 500 and i < tries - 1: time.sleep(2 * (i + 1)); continue
            raise RuntimeError(f'Discord {m} {p} -> {e.code} {body[:200]}')
        except urllib.error.URLError:
            if i < tries - 1: time.sleep(2 * (i + 1)); continue
            raise
    raise RuntimeError('Discord: too many retries')

def fetch(u, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA, 'Accept': '*/*'}), timeout=20).read()
        except Exception:
            if i < tries - 1: time.sleep(3 * (i + 1))
    return None

# ---------------- NEWS ----------------
FEEDS = [  # (name, url, weight)
    ('The Verge', 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml', 3),
    ('TechCrunch', 'https://techcrunch.com/category/artificial-intelligence/feed/', 3),
    ('VentureBeat', 'https://venturebeat.com/category/ai/feed/', 2),
    ('Ars Technica', 'https://arstechnica.com/ai/feed/', 2),
    ('MIT Tech Review', 'https://www.technologyreview.com/topic/artificial-intelligence/feed', 2),
    ('OpenAI', 'https://openai.com/news/rss.xml', 4),
    ('Google', 'https://blog.google/technology/ai/rss/', 3),
    ('Google DeepMind', 'https://deepmind.google/blog/rss.xml', 3),
    ('Hugging Face', 'https://huggingface.co/blog/feed.xml', 1),
    # labs without RSS (Anthropic, xAI, Meta) via Google News search
    ('Google News', 'https://news.google.com/rss/search?q=(Anthropic+OR+Claude+OR+xAI+OR+Grok+OR+%22Meta+AI%22+OR+Llama)+when:1d&hl=en-US&gl=US&ceid=US:en', 1),
]
HN = 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=60'
AI_RE = re.compile(r'\b(ai|a\.i\.|llm|llms|gpt[\w.-]*|chatgpt|openai|anthropic|claude|gemini|deepmind|grok|xai|llama|mistral|copilot|agent|agents|agentic|machine learning|neural|nvidia|model|models|deepseek|qwen|sora|midjourney|perplexity|cursor|chatbot)\b', re.I)
BIG = re.compile(r'\b(openai|chatgpt|gpt[\w.-]*|anthropic|claude|google|gemini|meta|llama|xai|grok|nvidia|apple|microsoft|copilot|amazon|deepseek|tesla|musk|altman)\b', re.I)
TAGS = [  # (regex, label, why-it-matters)
    (r'\b(launch|launches|released?|rolls? out|rolling out|unveil|introduc|debut|now available|new model|available)', '🆕 LAUNCH', 'New tool or feature you can try. Early users get the edge.'),
    (r'\b(raises?|funding|valuation|billion|acqui|ipo|revenue|earnings|deal|invest)', '💰 MONEY', 'Shows where the big money is flowing in AI, and where the next opportunities are.'),
    (r'\b(law|lawsuit|legal|lobby|sue|court|regulat|ban|congress|senate|eu |policy|copyright|ftc|government|scrape|terms)', '⚖️ RULES', 'New rules can change which AI tools you can use and how you can use them.'),
    (r'\b(security|hack|breach|scam|deepfake|safety|jailbreak|privacy|leak)', '🔒 SECURITY', 'Protect yourself. Scams and leaks are getting smarter with AI.'),
    (r'\b(agent|agents|agentic|automat|workflow|coding|code|developer|api)', '🤖 AGENTS', 'AI that does the work for you keeps getting better. That means more automation for less money.'),
    (r'\b(robot|robotaxi|self-driving|humanoid|autonomous)', '🦾 ROBOTS', 'AI is leaving the screen and moving into the real world: cars, robots, deliveries.'),
    (r'\b(chip|gpu|nvidia|data ?center|compute|power|energy)', '⚡ COMPUTE', 'Chips and power decide how cheap and fast AI gets for everyone.'),
    (r'\b(research|paper|study|benchmark|scientists?)', '🔬 RESEARCH', 'An early signal of what everyday AI apps will be able to do next.'),
]
DEFAULT_TAG = ('🧠 AI', 'Worth knowing. This is where the AI space is heading.')

def clean(t):
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t or ''))
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'(The post .*? appeared first on .*?\.?$)|(Continue reading.*$)|(Read more.*$)', '', t).strip()
    return t

def short(t, n=230):
    t = clean(t)
    sents = re.split(r'(?<=[.!?])\s+', t)
    out = ''
    for s in sents:
        if len(out) + len(s) + 1 > n: break
        out = (out + ' ' + s).strip()
        if len(out) > 110: break
    if not out: out = t[:n - 1].rsplit(' ', 1)[0] + '…' if len(t) > n else t
    return out

def pdate(s):
    if not s: return None
    try: return email.utils.parsedate_to_datetime(s).astimezone(dt.timezone.utc)
    except Exception: pass
    try: return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(dt.timezone.utc)
    except Exception: return None

def parse_feed(raw):
    out = []
    try: root = ET.fromstring(raw)
    except Exception: return out
    def txt(e, *names):
        for n in names:
            for c in e:
                if c.tag.split('}')[-1] == n and (c.text or c.get('href')):
                    return c.text if c.text and c.text.strip() else c.get('href')
        return ''
    for e in root.iter():
        tag = e.tag.split('}')[-1]
        if tag not in ('item', 'entry'): continue
        link = txt(e, 'link')
        if tag == 'entry':
            for c in e:
                if c.tag.split('}')[-1] == 'link' and c.get('rel', 'alternate') == 'alternate': link = c.get('href') or link
        out.append({'title': clean(txt(e, 'title')), 'link': (link or '').strip(),
                    'desc': txt(e, 'description', 'summary', 'content', 'encoded'),
                    'date': pdate(txt(e, 'pubDate', 'published', 'updated', 'date'))})
    return out

def norm_title(t): return re.sub(r'[^a-z0-9 ]', ' ', t.lower().replace("’s", '').replace("'s", ''))
STOP = set('with from that this their your will says about after into over more than what when have just they them were been could would should while across using make makes amid like most first back only'.split())
def key(link, title):
    l = re.sub(r'[?#].*$', '', link.lower()).rstrip('/')
    return hashlib.sha1(l.encode()).hexdigest()[:16], hashlib.sha1(norm_title(title).encode()).hexdigest()[:16]
def words(t): return set(w for w in norm_title(t).split() if len(w) > 3 and w not in STOP)

def gather(hours=26):
    items, used = [], []
    cutoff = NOW - dt.timedelta(hours=hours)
    for name, url, w in FEEDS:
        raw = fetch(url)
        if not raw: continue
        n = 0
        for it in parse_feed(raw):
            if not it['title'] or not it['link'] or (it['date'] and it['date'] < cutoff) or not it['date']: continue
            src = name
            if name == 'Google News':  # titles look like "Headline - Publisher"
                m = re.match(r'(.*) - ([^-]+)$', it['title'])
                if m: it['title'], src = m.group(1).strip(), m.group(2).strip()
                it['desc'] = ''
            if name in ('Hugging Face', 'Google News') or not name in ('OpenAI', 'Google', 'Google DeepMind'):
                if name in ('Hugging Face', 'Google News') and not AI_RE.search(it['title']): continue
            it.update(source=src, feed=name, weight=w); items.append(it); n += 1
        if n: used.append(name)
    raw = fetch(HN)
    if raw:
        n = 0
        for h in json.loads(raw).get('hits', []):
            t = h.get('title') or ''
            d = dt.datetime.fromtimestamp(h.get('created_at_i', 0), dt.timezone.utc)
            if d < cutoff or not AI_RE.search(t): continue
            link = h.get('url') or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            items.append({'title': clean(t), 'link': link, 'desc': '', 'date': d, 'source': 'Hacker News', 'feed': 'Hacker News',
                          'weight': 1 + min((h.get('points') or 0) / 150, 3)}); n += 1
        if n: used.append('Hacker News')
    return items, used

def similar(a, b):
    n = len(a & b)
    return n >= 3 or (n >= 2 and n >= 0.3 * max(1, min(len(a), len(b))))

def pick(items, seen, k=6):
    seen_l, seen_t = set(seen.get('links', [])), set(seen.get('titles', []))
    recent_words = [set(x) for x in seen.get('recent_words', [])]
    for it in items:
        it['score'] = it['weight'] + (2 if BIG.search(it['title']) else 0) + (1 if AI_RE.search(it['title']) else 0)
        it['score'] += max(0, 1 - (NOW - it['date']).total_seconds() / 86400)
        it['w'] = words(it['title'])
    for a in items:  # cross-source buzz boost
        a['score'] += 1.5 * len({b['feed'] for b in items if b['feed'] != a['feed'] and len(a['w'] & b['w']) >= 3})
        if clean(a['desc']): a['score'] += 1  # prefer items we can summarize
    chosen = []
    for it in sorted(items, key=lambda x: -x['score']):
        kl, kt = key(it['link'], it['title'])
        if kl in seen_l or kt in seen_t: continue
        if any(similar(it['w'], c['w']) for c in chosen): continue
        if any(similar(it['w'], r) for r in recent_words): continue
        if sum(1 for c in chosen if c['feed'] == it['feed']) >= 2: continue
        chosen.append(it)
        if len(chosen) >= k: break
    return chosen

def tag_of(it):
    for blob in (it['title'], clean(it['desc'])[:300]):
        for rx, label, why in TAGS:
            if re.search(rx, blob, re.I): return label, why
    return DEFAULT_TAG

def news():
    ch = load(CHS, {})['news']
    st = load(STATE, {})
    items, used = gather()
    chosen = pick(items, st.get('news', {}))
    if not chosen:
        print('no new AI stories; nothing posted'); return
    fields = []
    for i, it in enumerate(chosen, 1):
        label, why = tag_of(it)
        summ = short(it['desc']) if clean(it['desc']) and norm_title(clean(it['desc'])[:60]) != norm_title(it['title'][:60]) else ''
        val = (f"{summ}\n" if summ else '') + f"> **Why it matters:** {why}\n[Read on {it['source']} →]({it['link']})"
        fields.append({'name': f"{label}  ·  {it['title']}"[:250], 'value': val[:1020], 'inline': False})
    day = NOW.astimezone(dt.timezone(dt.timedelta(hours=-5))).strftime('%a %b %d, %Y')
    emb = {'author': {'name': 'CITAD3L  ·  WATCHTOWER'},
           'title': f'🧠  AI INTEL BRIEFING  ·  {day}',
           'description': "The top AI moves from the last 24h, in plain English.\nRead it, use it, **move in silence.** 🥷\n\u200b",
           'color': SILVER, 'fields': fields,
           'footer': {'text': f"Citad3l AI War Room · sources: {', '.join(sorted(set(c['source'] for c in chosen)))}"[:2000]},
           'timestamp': NOW.isoformat()}
    if DRY:
        print(json.dumps(emb, indent=1, ensure_ascii=False)); print('feeds ok:', used); return
    dapi('POST', f'/channels/{ch}/messages', {'embeds': [emb]})
    n = st.setdefault('news', {})
    for it in chosen:
        kl, kt = key(it['link'], it['title'])
        n.setdefault('links', []).append(kl); n.setdefault('titles', []).append(kt)
        n.setdefault('recent_words', []).append(sorted(it['w']))
    n['links'] = n['links'][-3000:]; n['titles'] = n['titles'][-3000:]; n['recent_words'] = n['recent_words'][-60:]
    n['last_post'] = NOW.isoformat(); save(STATE, st)
    print(f'posted {len(chosen)} stories; feeds ok: {used}')

# ---------------- CALENDAR ----------------
def fmt_range(a, b):
    A = dt.date.fromisoformat(a); B = dt.date.fromisoformat(b) if b else None
    if not B or B == A: return A.strftime('%b %-d')
    if A.month == B.month: return f"{A.strftime('%b %-d')}–{B.day}"
    return f"{A.strftime('%b %-d')} – {B.strftime('%b %-d')}"

def calendar():
    ch = load(CHS, {})['calendar']
    cal = load(CAL, {'items': []}); st = load(STATE, {})
    today = NOW.astimezone(dt.timezone(dt.timedelta(hours=-6))).date()
    live = [x for x in cal['items'] if dt.date.fromisoformat(x.get('end_date') or x['date']) >= today]
    live.sort(key=lambda x: (x['date'], x['name']))
    fields = []
    for x in live[:24]:
        A = dt.date.fromisoformat(x['date']); B = dt.date.fromisoformat(x.get('end_date') or x['date'])
        badge = '🟡 RUMORED' if x.get('status') == 'rumored' else '🟢 CONFIRMED'
        now = ' · 🔥 **LIVE NOW**' if A <= today <= B else (f' · ⏳ in {(A - today).days}d' if (A - today).days <= 14 else '')
        fields.append({'name': f"📅 {fmt_range(x['date'], x.get('end_date'))}  ·  {x['name']}"[:250],
                       'value': f"{badge}{now}\n{x['why']}\n[source]({x['source']})"[:1020], 'inline': False})
    if not fields:
        fields = [{'name': 'All quiet on the horizon', 'value': 'No upcoming dates logged yet.', 'inline': False}]
    emb = {'author': {'name': 'CITAD3L  ·  WATCHTOWER'},
           'title': '🗓️  AI RELEASE CALENDAR',
           'description': "What's dropping in AI, when, and why you should care.\n🟢 confirmed · 🟡 rumored/estimate (not official)\n\u200b",
           'color': SILVER, 'fields': fields,
           'footer': {'text': 'Citad3l AI War Room · auto-updated daily · last update'}, 'timestamp': NOW.isoformat()}
    if DRY:
        print(json.dumps(emb, indent=1, ensure_ascii=False)); return
    mid = st.get('calendar_message_id')
    if mid:
        try:
            dapi('PATCH', f'/channels/{ch}/messages/{mid}', {'embeds': [emb]}); print('calendar edited', mid, len(live), 'items'); return
        except RuntimeError as e:
            if '404' not in str(e): raise
    m = dapi('POST', f'/channels/{ch}/messages', {'embeds': [emb]})
    try: dapi('PUT', f"/channels/{ch}/pins/{m['id']}")
    except Exception as e: print('pin failed:', e)
    st['calendar_message_id'] = m['id']; save(STATE, st)
    print('calendar posted+pinned', m['id'], len(live), 'items')

if __name__ == '__main__':
    mode = next((a for a in sys.argv[1:] if not a.startswith('-')), '')
    if mode == 'news': news()
    elif mode == 'calendar': calendar()
    else: print(__doc__); sys.exit(2)
