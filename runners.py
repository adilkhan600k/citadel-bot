#!/usr/bin/env python3
"""Citad3l Runners of the Day: Solana coins LAUNCHED in the last 24h that hit $1M market cap, with dev + why-it-ran intel.
Usage: python3 runners.py          -> fetch, render card, post to channel in runners_channel.txt
       python3 runners.py --dry    -> render runners_preview.png + print embed, no post, no state write
Free + keyless: GeckoTerminal, DexScreener, pump.fun frontend API (coins-v3, user-created-coins), Google News RSS.
Deps: Python 3.9+ stdlib + Pillow (optional: without it, posts text-only). Token: env DISCORD_BOT_TOKEN.
"""
import os, sys, json, time, uuid, datetime, re, html, urllib.request, urllib.parse, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
CH_FILE = os.path.join(BASE, 'runners_channel.txt')
STATE = os.path.join(BASE, 'runners_state.json')
FONTS = os.path.join(BASE, 'fonts')
PREVIEW = os.path.join(BASE, 'runners_preview.png')
DRY = '--dry' in sys.argv
UA = {'User-Agent': 'Mozilla/5.0 (citad3l-runners)', 'accept': 'application/json'}
GT = 'https://api.geckoterminal.com/api/v2/networks/solana'
DS = 'https://api.dexscreener.com'
T0 = time.time(); BUDGET = 170  # seconds before we stop enriching
NOW = time.time()
MAX_COINS = 10
THRESH = 1_000_000
SKIP_BASE = {'So11111111111111111111111111111111111111112', 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
             'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'}
QUOTES = {'So11111111111111111111111111111111111111112', 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
          'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'}

def log(*a): print(*a, flush=True)

_last = {'gt': 0.0, 'ds': 0.0, 'pf': 0.0}
GAP = {'gt': 2.2, 'ds': 0.35}  # GeckoTerminal ~30/min, DexScreener 60-300/min
def get(url, src, timeout=15):
    for attempt in range(2):
        w = GAP[src] - (time.time() - _last[src])
        if w > 0: time.sleep(w)
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
            _last[src] = time.time(); return json.loads(r.read())
        except urllib.error.HTTPError as e:
            _last[src] = time.time()
            if e.code == 429 and attempt == 0: time.sleep(8); continue
            raise
        except Exception:
            _last[src] = time.time()
            if attempt == 0: time.sleep(2); continue
            raise

def safe(fn, label):
    try: return fn()
    except Exception as e:
        log(f'[warn] {label} unavailable: {type(e).__name__} {str(e)[:80]}')
        return None

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

# ---------------------------------------------------------------- formatting
try:
    from zoneinfo import ZoneInfo
    now_ct = datetime.datetime.now(ZoneInfo('America/Chicago'))
except Exception:
    now_ct = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)

def usd(x):
    if x is None: return 'n/a'
    if x >= 1e9: return f'${x/1e9:.2f}B'
    if x >= 1e6: return f'${x/1e6:.2f}M' if x < 1e7 else f'${x/1e6:.1f}M'
    if x >= 1e3: return f'${x/1e3:.0f}K'
    return f'${x:,.0f}'
def pc(x):
    if x is None: return 'n/a'
    return f"{'+' if x >= 0 else ''}{x:,.0f}%" if abs(x) >= 100 else f"{'+' if x >= 0 else ''}{x:.1f}%"
def dur(h):
    if h is None: return 'n/a'
    if h < 1: return '<1h'
    if h < 48: return f'{h:.0f}h'
    return f'{h / 24:.0f}d'
def clean(s, n=22, alt=None):
    s = re.sub(r'[^\x20-\x7E]', '', s or '').strip()
    if not s and alt: s = re.sub(r'[^A-Za-z0-9]', '', re.sub(r'[^\x20-\x7E]', '', alt)).upper()
    return (s or '?')[:n]
def md(s): return re.sub(r'([\\*_`~|>\[\]()#@])', r'\\\1', s)

def short(a): return f'{a[:4]}…{a[-4:]}' if a and len(a) > 10 else (a or 'n/a')
def first_sentence(t, n=150):
    t = re.sub(r'https?://\S+|@\w+', '', re.sub(r'\s+', ' ', t or '')).strip()
    m = re.match(r'(.{20,}?[.!?])(\s|$)', t)
    t = m.group(1) if m else t
    return (t[:n - 1].rsplit(' ', 1)[0] + '…') if len(t) > n else t
def dev_flag(h):
    if not h: return None
    if h['others'] == 0: return '✅ first pump.fun launch'
    if h['others'] >= 10 or h['week'] >= 5: return '🚩 serial launcher'
    if h['others'] >= 3 and h['dead'] / h['others'] >= 0.7: return '⚠️ mostly dead launches'
    if h['hit1m']: return '✅ has a prior $1M+ launch'
    return 'ℹ️ few prior launches'
def dev_hist_txt(h):
    if not h: return 'launch history n/a'
    if h['others'] == 0: return 'no other launches'
    tot = (h['count'] - 1) if h['count'] else h['others']
    samp = f"in a {h['others']}-coin sample: " if tot > h['others'] else ''
    return f"{tot} other launches · {samp}{h['week']} this week, {h['hit1m']} hit $1M, {h['dead']} died <$50K"
def hold_txt(x): return 'dev holds n/a' if x is None else 'dev hold unclear (sources conflict)' if x == 'conflict' else (f'dev holds {x:.1f}%' if x > 0 else 'dev holds 0% (sold or never bought)')
def why_txt(r, link=True):
    parts = []
    if r['desc']: parts.append(f'Pitch: "{md(first_sentence(r["desc"]))}"')
    if r['news']:
        t = md(r['news']['title'][:120])
        parts.append(f"In the news: [{t}]({r['news']['link']}) ({md(r['news']['src'][:30])})" if link else f"In the news: {t}")
    if not r['news']: parts.append('No clear news, likely pure meme/social momentum.')
    return ' '.join(parts)

SRC_OK = set()
PF = 'https://frontend-api-v3.pump.fun'
PFH = {'Origin': 'https://pump.fun', 'Referer': 'https://pump.fun/'}
def getpf(url):
    w = 0.6 - (time.time() - _last.get('pf', 0))
    if w > 0: time.sleep(w)
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **PFH}), timeout=12)
        b = r.read(); return json.loads(b) if b else None
    finally: _last['pf'] = time.time()
DAY = 24 * 3600

# ---------------------------------------------------------------- 1. candidate token addresses
cand = {}  # addr -> {'pool', 'src', 'pf'}
def add_gt(data, tag):
    for p in (data or {}).get('data', []):
        rel = p.get('relationships', {})
        base = ((rel.get('base_token') or {}).get('data') or {}).get('id', '').replace('solana_', '')
        quote = ((rel.get('quote_token') or {}).get('data') or {}).get('id', '').replace('solana_', '')
        if not base or base in SKIP_BASE or quote not in QUOTES: continue
        a = p.get('attributes', {})
        cap = f(a.get('market_cap_usd')) or f(a.get('fdv_usd')) or 0
        if cap < 100_000: continue
        cand.setdefault(base, {'pool': a.get('address'), 'src': set()})['src'].add(tag)

for url, tag in [(f'{GT}/trending_pools?page=1&duration=24h', 'gt-trending'),
                 (f'{GT}/trending_pools?page=2&duration=24h', 'gt-trending'),
                 (f'{GT}/trending_pools?page=1&duration=6h', 'gt-trending'),
                 (f'{GT}/pools?page=1&sort=h24_volume_usd_desc', 'gt-top'),
                 (f'{GT}/pools?page=2&sort=h24_volume_usd_desc', 'gt-top'),
                 (f'{GT}/new_pools?page=1', 'gt-new'),
                 (f'{GT}/new_pools?page=2', 'gt-new')]:
    d = safe(lambda: get(url, 'gt'), tag)
    if d: add_gt(d, tag); SRC_OK.add('GeckoTerminal')

prof = safe(lambda: get(f'{DS}/token-profiles/latest/v1', 'ds'), 'ds-profiles')
if isinstance(prof, list):
    SRC_OK.add('DexScreener')
    for p in prof:
        if p.get('chainId') == 'solana' and p.get('tokenAddress') and p['tokenAddress'] not in SKIP_BASE:
            cand.setdefault(p['tokenAddress'], {'pool': None, 'src': set()})['src'].add('ds-profiles')

pfcache = {}
for off in (0, 50, 100):  # pump.fun's own board: launched <24h and ATH >= $1M
    lst = safe(lambda: getpf(f'{PF}/coins?offset={off}&limit=50&sort=market_cap&order=DESC&includeNsfw=false'), 'pump.fun board')
    if not isinstance(lst, list): break
    SRC_OK.add('pump.fun')
    for c in lst:
        if (c.get('created_timestamp') or 0) / 1000 > NOW - DAY and (f(c.get('ath_market_cap')) or 0) >= THRESH and c.get('mint'):
            pfcache[c['mint']] = c
            cand.setdefault(c['mint'], {'pool': None, 'src': set()})['src'].add('pump.fun')
log(f'candidates: {len(cand)}')

# ---------------------------------------------------------------- 2. live pair data (DexScreener, 30 per call)
pairs, first_pair = {}, {}
addrs = list(cand)
for i in range(0, len(addrs), 30):
    chunk = addrs[i:i + 30]
    d = safe(lambda: get(f'{DS}/tokens/v1/solana/' + ','.join(chunk), 'ds'), 'ds-tokens')
    if not isinstance(d, list): continue
    SRC_OK.add('DexScreener')
    for p in d:
        b = (p.get('baseToken') or {}).get('address')
        if b not in cand: continue
        if p.get('pairCreatedAt'): first_pair[b] = min(first_pair.get(b, 9e15), p['pairCreatedAt'] / 1000)
        if (p.get('quoteToken') or {}).get('address') not in QUOTES: continue
        liq = f((p.get('liquidity') or {}).get('usd')) or 0
        if b not in pairs or liq > (f((pairs[b].get('liquidity') or {}).get('usd')) or 0): pairs[b] = p

def gt_fallback(addr):  # if DexScreener is down, use GeckoTerminal pool data for the candidate
    pool = cand[addr].get('pool')
    if not pool: return None
    a = get(f'{GT}/pools/{pool}', 'gt')['data']['attributes']
    return {'baseToken': {'address': addr, 'name': a.get('name', '?').split(' / ')[0], 'symbol': a.get('name', '?').split(' / ')[0]},
            'pairAddress': pool, 'url': f'https://dexscreener.com/solana/{pool}',
            'priceUsd': a.get('base_token_price_usd'), 'marketCap': f(a.get('market_cap_usd')), 'fdv': f(a.get('fdv_usd')),
            'priceChange': {'h24': f((a.get('price_change_percentage') or {}).get('h24'))},
            'volume': {'h24': f((a.get('volume_usd') or {}).get('h24'))}, 'liquidity': {'usd': f(a.get('reserve_in_usd'))},
            'pairCreatedAt': int(datetime.datetime.fromisoformat(a['pool_created_at'].replace('Z', '+00:00')).timestamp() * 1000) if a.get('pool_created_at') else None}
if not pairs and cand:
    log('[warn] no DexScreener pair data, falling back to GeckoTerminal pools')
    for addr in list(cand)[:12]:
        p = safe(lambda: gt_fallback(addr), 'gt-pool')
        if p: pairs[addr] = p; first_pair[addr] = (p.get('pairCreatedAt') or 0) / 1000 or None

# ---------------------------------------------------------------- 3. qualify: launched <24h, safety filters
state = safe(lambda: json.load(open(STATE)), 'state') if os.path.exists(STATE) else {}
posted = (state or {}).get('posted', {})
recent = {a for a, ts in posted.items() if NOW - ts < 5 * 86400}
SKIPPED = {'launch_unknown': 0, 'old': 0}

rows = []
for addr, p in pairs.items():
    cap = f(p.get('marketCap')) or f(p.get('fdv'))
    price = f(p.get('priceUsd'))
    h24 = f((p.get('priceChange') or {}).get('h24'))
    vol = f((p.get('volume') or {}).get('h24')) or 0
    liq = f((p.get('liquidity') or {}).get('usd')) or 0
    fp = first_pair.get(addr)
    if not cap or not price or addr in recent: continue
    if fp and fp < NOW - DAY: SKIPPED['old'] += 1; continue   # first pool older than 24h -> launched earlier
    if liq < 8_000 or vol < 50_000: continue
    if liq and cap / liq > 80: continue                      # thin/fake float
    pfc = pfcache.get(addr) or {}
    rows.append({'addr': addr, 'p': p, 'name': pfc.get('name') or (p.get('baseToken') or {}).get('name', '?'),
                 'sym': pfc.get('symbol') or (p.get('baseToken') or {}).get('symbol', '?'),
                 'cap': cap, 'price': price, 'supply': cap / price, 'h24': h24, 'vol': vol, 'liq': liq,
                 'pair': p.get('pairAddress'), 'url': p.get('url') or f'https://dexscreener.com/solana/{addr}', 'info': p.get('info') or {},
                 'pf': pfc or None, 'created': None, 'age_h': None, 'peak': None, 't1m_h': None, 'holders': None, 'top10': None,
                 'dev': None, 'dev_hold': None, 'dev_hist': None, 'socials': {}, 'desc': None, 'news': None})
rows.sort(key=lambda r: r['cap'], reverse=True)
log(f'pre-qualified: {len(rows)}')

def launch_time(r):
    if r['addr'].endswith('pump'):  # pump.fun mint: true launch = pump.fun created_timestamp
        c = r['pf'] or safe(lambda: getpf(f"{PF}/coins-v3/{r['addr']}"), f"pump.fun coin {r['sym']}")
        if isinstance(c, dict) and c.get('created_timestamp'):
            r['pf'] = c; SRC_OK.add('pump.fun'); return c['created_timestamp'] / 1000
        return None   # pair creation = migration time, not launch: can't verify
    return first_pair.get(r['addr'])  # non-pump launch: first DEX pool is the launch

def ohlcv(r):
    lst = get(f"{GT}/pools/{r['pair']}/ohlcv/minute?aggregate=15&limit=100&currency=usd", 'gt')['data']['attributes']['ohlcv_list']
    lst = sorted(lst, key=lambda c: c[0])
    if not lst: return
    sup = r['supply']; top = lambda c: max(c[1], c[4])  # candle body top: ignores single-trade wicks
    r['peak'] = max(max(top(c) for c in lst) * sup, r['cap'])
    first = next((c for c in lst if top(c) * sup >= THRESH), None)
    if first and r['created']: r['t1m_h'] = max(0.25, (first[0] + 900 - r['created']) / 3600)

out = []
for r in rows:
    if len(out) >= MAX_COINS + 3 or time.time() - T0 > BUDGET: break
    r['created'] = launch_time(r)
    if r['created'] is None: SKIPPED['launch_unknown'] += 1; continue
    if r['created'] < NOW - DAY: SKIPPED['old'] += 1; continue
    r['age_h'] = (NOW - r['created']) / 3600
    if r['pair']: safe(lambda: ohlcv(r), f"ohlcv {r['sym']}")
    ath = f((r['pf'] or {}).get('ath_market_cap'))
    if ath and ath < r['cap'] * 20: r['peak'] = max(r['peak'] or 0, ath)
    if (r['peak'] or r['cap']) < THRESH: continue
    out.append(r)

# ---------------------------------------------------------------- 4. who's behind it + why it ran
def handle(u):
    m = re.search(r'(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(/status/\d+)?', u or '')
    return (m.group(1), bool(m.group(2))) if m else (None, False)
def dev_history(dev, mint):
    d = getpf(f'{PF}/coins-v2/user-created-coins/{dev}?limit=50&offset=0&includeNsfw=true')
    if not isinstance(d, dict): return None
    others = [c for c in d.get('coins', []) if c.get('mint') != mint]
    wk = [c for c in others if (c.get('created_timestamp') or 0) / 1000 > NOW - 7 * DAY]
    aths = [f(c.get('ath_market_cap')) or f(c.get('usd_market_cap')) or 0 for c in others]
    return {'count': d.get('count', len(others) + 1), 'others': len(others), 'week': len(wk),
            'hit1m': sum(1 for a in aths if a >= THRESH), 'grad': sum(1 for c in others if c.get('complete')),
            'dead': sum(1 for a in aths if a < 50_000), 'best': max(aths) if aths else None}
STOP = {'coin', 'token', 'the', 'sol', 'solana', 'official', 'meme', 'inu', 'ai'}
def news(r):
    words = [w for w in re.findall(r'[A-Za-z0-9]+', clean(r['name'], 60)) if w.lower() not in STOP]
    q = ' '.join(words[:4])
    if len(q) < 4: return None
    url = 'https://news.google.com/rss/search?q=' + urllib.parse.quote(f'"{q}" when:2d') + '&hl=en-US&gl=US&ceid=US:en'
    x = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=12).read().decode('utf-8', 'ignore')
    SRC_OK.add('Google News')
    for t, link, pub, src in re.findall(r'<item><title>(.*?)</title><link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>.*?<source[^>]*>(.*?)</source>', x, re.S):
        t = html.unescape(t)
        if all(w.lower() in t.lower() for w in words[:4]):
            return {'title': re.sub(r'\s+-\s+[^-]+$', '', t), 'link': link, 'src': html.unescape(src)}
    return None

for r in out[:MAX_COINS]:
    if time.time() - T0 > BUDGET + 40: break
    info = safe(lambda: get(f"{GT}/tokens/{r['addr']}/info", 'gt')['data']['attributes'], f"info {r['sym']}") or {}
    if info.get('holders'):
        r['holders'] = info['holders'].get('count')
        r['top10'] = f((info['holders'].get('distribution_percentage') or {}).get('top_10'))
    if info.get('is_honeypot') in (True, 'yes'): r['bad'] = True
    if (r['holders'] is not None and r['holders'] < 150) or (r['top10'] or 0) >= 90: r['bad'] = True
    pf = r['pf'] or {}
    r['dev'] = pf.get('creator') or info.get('developer_address')
    r['dev_hold'] = f(info.get('developer_holding_percentage'))
    if r['dev_hold'] is not None and r['top10'] is not None and r['dev_hold'] > r['top10'] + 0.5:
        r['dev_hold'] = 'conflict'  # GT dev % exceeds the whole top-10 share: data can't both be right
    if r['dev'] and r['addr'].endswith('pump'):
        r['dev_hist'] = safe(lambda: dev_history(r['dev'], r['addr']), f"dev history {r['sym']}")
    so = {}
    tw = pf.get('twitter') or next((x.get('url') for x in r['info'].get('socials', []) if x.get('type') in ('twitter', 'x')), None) \
         or (f"https://x.com/{info['twitter_handle']}" if info.get('twitter_handle') else None)
    tg = pf.get('telegram') or next((x.get('url') for x in r['info'].get('socials', []) if x.get('type') == 'telegram'), None) \
         or (f"https://t.me/{info['telegram_handle']}" if info.get('telegram_handle') else None)
    web = pf.get('website') or next((x.get('url') for x in r['info'].get('websites', [])), None) or next(iter(info.get('websites') or []), None)
    for k, v in (('x', tw), ('tg', tg), ('web', web)):
        if v and re.match(r'https?://', v): so[k] = v.strip()
    r['socials'] = so
    r['desc'] = (pf.get('description') or info.get('description') or '').strip() or None
    r['news'] = safe(lambda: news(r), f"news {r['sym']}")
out = [r for r in out if not r.get('bad')]
rank = lambda r: (r['peak'] or r['cap'])
out.sort(key=rank, reverse=True)
out = out[:MAX_COINS]
log(f'runners: {len(out)}  skipped {SKIPPED}  ({time.time() - T0:.0f}s)')

# ---------------------------------------------------------------- image card
def render(path):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import math
    S = 2; W = 1600; n = max(1, len(out)); RH = 104
    H = 360 + (n * RH if out else 160) + 140
    def s(x): return int(round(x * S))
    _fc = {}
    def F(name, size, wght):
        key = (name, size, wght)
        if key not in _fc:
            try:
                fo = ImageFont.truetype(os.path.join(FONTS, f'{name}.ttf'), s(size))
                try:
                    axes = fo.get_variation_axes()
                    fo.set_variation_by_axes([min(32, max(14, size)) if a['name'] == b'Optical size' else wght for a in axes])
                except Exception: pass
            except Exception:
                fo = ImageFont.load_default(size=s(size))
            _fc[key] = fo
        return _fc[key]
    SILVER = (200, 206, 216); WHITE = (244, 246, 250); MUTED = (122, 130, 145); DIM = (70, 76, 88)
    UP = (52, 224, 140); DOWN = (255, 86, 92); GLOW = (176, 120, 255); GOLD = (255, 196, 70)
    def chc(x): return MUTED if x is None else (UP if x >= 0 else DOWN)
    img = Image.composite(Image.new('RGB', (s(W), s(H)), (19, 21, 27)), Image.new('RGB', (s(W), s(H)), (6, 7, 10)),
                          Image.linear_gradient('L').resize((s(W), s(H))))
    mason = Image.new('RGBA', img.size, (0, 0, 0, 0)); mdd = ImageDraw.Draw(mason)
    bh, bw = 46, 120
    for rr in range(0, H // bh + 2):
        y = rr * bh; off = (bw // 2) if rr % 2 else 0
        mdd.line([(0, s(y)), (s(W), s(y))], fill=(255, 255, 255, 9), width=S)
        for c in range(-1, W // bw + 2):
            x = c * bw + off; mdd.line([(s(x), s(y)), (s(x), s(y + bh))], fill=(255, 255, 255, 9), width=S)
    img = Image.alpha_composite(img.convert('RGBA'), mason)
    glow = Image.new('RGBA', img.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([s(W - 700), s(-300), s(W + 200), s(500)], fill=GLOW + (60,))
    gd.ellipse([s(-300), s(H - 400), s(500), s(H + 300)], fill=UP + (30,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(s(150))))
    vig = Image.new('L', img.size, 0); ImageDraw.Draw(vig).ellipse([s(-300), s(-260), s(W + 300), s(H + 260)], fill=255)
    img = Image.composite(img, Image.new('RGBA', img.size, (3, 3, 5, 255)), vig.filter(ImageFilter.GaussianBlur(s(160))))
    d = ImageDraw.Draw(img)
    def text(xy, t, fo, fill, anchor='la', spacing=0):
        if spacing:
            x, y = xy
            if anchor[0] in 'rm':
                tw = sum(d.textlength(ch, font=fo) for ch in t) + s(spacing) * (len(t) - 1)
                x = (x * S - (tw if anchor[0] == 'r' else tw / 2)) / S
            cx = s(x)
            for ch in t:
                d.text((cx, s(y)), ch, font=fo, fill=fill, anchor='l' + anchor[1]); cx += d.textlength(ch, font=fo) + s(spacing)
        else:
            d.text((s(xy[0]), s(xy[1])), t, font=fo, fill=fill, anchor=anchor)
    def card(x, y, w, h, r=18, fill=(16, 18, 24, 215), outline=(255, 255, 255, 22)):
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle([s(x), s(y), s(x + w), s(y + h)], s(r), fill=fill, outline=outline, width=S)
        ld.line([(s(x + r), s(y) + S), (s(x + w - r), s(y) + S)], fill=(255, 255, 255, 30), width=S)
        img.alpha_composite(layer)
    # header
    text((60, 52), 'CITAD3L', F('Cinzel', 58, 900), SILVER, 'lm', spacing=10)
    tw = sum(d.textlength(c, font=F('Cinzel', 58, 900)) for c in 'CITAD3L') / S + 60
    d.line([(s(60 + tw + 22), s(36)), (s(60 + tw + 22), s(70))], fill=DIM, width=S)
    text((60 + tw + 44, 42), 'THE WATCHTOWER', F('SpaceGrotesk', 22, 700), WHITE, 'lm', spacing=4)
    text((60 + tw + 44, 66), 'SOLANA RUNNERS RECAP', F('JetBrainsMono', 14, 500), MUTED, 'lm', spacing=2)
    text((W - 60, 42), now_ct.strftime('%a %b %d, %Y').upper(), F('JetBrainsMono', 20, 700), WHITE, 'rm', spacing=1)
    text((W - 60, 66), now_ct.strftime('%I:%M %p').lstrip('0') + ' CT  ·  LAST 24 HOURS', F('JetBrainsMono', 14, 500), MUTED, 'rm', spacing=1)
    for i in range(W - 120):
        a = int(120 * math.sin(math.pi * i / (W - 120))); d.point((s(60 + i), s(98)), fill=(200, 206, 216, a))
    # title + stats
    text((60, 128), 'RECAP  //  LAUNCHED <24H AND HIT $1M', F('JetBrainsMono', 16, 700), MUTED, 'la', spacing=3)
    text((56, 150), 'RUNNERS OF THE DAY', F('SpaceGrotesk', 84, 700), WHITE, 'la')
    stats = [('RUNNERS', str(len(out)) if out else '0'),
             ('BIGGEST PEAK', f"${clean(max(out, key=rank)['sym'], 10, max(out, key=rank)['name'])}" if out else '—'),
             ('FASTEST TO $1M', (lambda q: f"${clean(q['sym'], 10, q['name'])} {dur(q['t1m_h'])}" if q else '—')(min([r for r in out if r['t1m_h'] is not None], key=lambda r: r['t1m_h'], default=None))),
             ('TOP 24H MOVE', (lambda q: f"{pc(q['h24'])}" if q else '—')(max([r for r in out if r['h24'] is not None], key=lambda r: r['h24'], default=None)))]
    cw = (W - 120 - 3 * 14) / 4
    for i, (lab, val) in enumerate(stats):
        x = 60 + i * (cw + 14); card(x, 262, cw, 74, r=14)
        text((x + 18, 280), lab, F('JetBrainsMono', 12, 700), MUTED, 'la', spacing=2)
        text((x + 18, 298), val, F('SpaceGrotesk', 26, 700), GOLD if i == 1 else WHITE, 'la')
    # table
    cols = [('#', 60), ('COIN', 104), ('MCAP', 520), ('PEAK', 660), ('AGE', 820), ('TO $1M', 920), ('24H', 1040),
            ('VOL 24H', 1170), ('LIQ', 1300), ('HOLDERS', 1420)]
    y0 = 362
    for lab, x in cols: text((x + 14, y0 + 8), lab, F('JetBrainsMono', 12, 700), MUTED, 'la', spacing=2)
    y = y0 + 32
    if not out:
        card(60, y, W - 120, 130, r=16)
        text((W / 2, y + 48), 'QUIET DAY ON THE WALLS', F('SpaceGrotesk', 34, 700), SILVER, 'mm')
        text((W / 2, y + 90), 'no solana coin launched in the last 24h reached $1M. patience is a position.', F('JetBrainsMono', 15, 500), MUTED, 'mm')
    for i, r in enumerate(out):
        yy = y + i * RH
        card(60, yy, W - 120, RH - 10, r=12, fill=(16, 18, 24, 225) if i % 2 == 0 else (21, 23, 30, 225),
             outline=(GOLD + (90,)) if i == 0 else (255, 255, 255, 22))
        cy = yy + 30
        text((88, cy + 4), f'{i + 1:02d}', F('JetBrainsMono', 18, 800), GOLD if i == 0 else SILVER, 'mm')
        text((118, cy - 6), f"${clean(r['sym'], 12, r['name'])}", F('SpaceGrotesk', 23, 700), WHITE, 'lm')
        text((118, cy + 17), clean(r['name'], 30), F('JetBrainsMono', 12, 500), MUTED, 'lm')
        h = r['dev_hist']
        flag = None if not h else ('FIRST LAUNCH' if h['others'] == 0 else ('SERIAL LAUNCHER' if h['others'] >= 10 or h['week'] >= 5 else f"{h['others']} PRIOR LAUNCHES"))
        dl = [f"DEV {short(r['dev']).replace('…', '..')}", ('HOLDS ' + ('N/A' if r['dev_hold'] in (None, 'conflict') else f"{r['dev_hold']:.1f}%")), flag or 'HISTORY N/A',
              ' '.join(k.upper() for k in ('x', 'tg', 'web') if k in r['socials']) or 'NO SOCIALS']
        dl.append(('NEWS: ' + clean(r['news']['title'], 70)) if r['news'] else 'NO NEWS, MEME/SOCIAL MOMENTUM')
        fcol = DOWN if flag == 'SERIAL LAUNCHER' else MUTED
        x3 = 118; fo3 = F('JetBrainsMono', 12, 600)
        for j, t in enumerate(dl):
            col = fcol if j == 2 else ((GLOW if j == 4 and r['news'] else MUTED) if j >= 3 else SILVER)
            if x3 + d.textlength(t, font=fo3) / S > W - 80: t = t[:max(0, int((W - 80 - x3) / 7.4))] + '…'
            text((x3, yy + 74), t, fo3, col, 'lm'); x3 += d.textlength(t, font=fo3) / S + 14
            if j < len(dl) - 1: text((x3 - 7, yy + 74), '·', fo3, DIM, 'mm'); x3 += 6
        vals = [(usd(r['cap']), WHITE), (usd(r['peak']), GOLD), (dur(r['age_h']), SILVER), (dur(r['t1m_h']), SILVER),
                (pc(r['h24']), chc(r['h24'])), (usd(r['vol']), SILVER), (usd(r['liq']), SILVER),
                (f"{r['holders']:,}" if r['holders'] else 'n/a', SILVER)]
        for (lab, x), (v, col) in zip(cols[2:], vals):
            text((x + 14, cy), v, F('SpaceGrotesk' if lab in ('MCAP', 'PEAK 24H', '24H') else 'JetBrainsMono', 21 if lab in ('MCAP', 'PEAK 24H', '24H') else 17, 700), col, 'lm')
    fy = H - 70
    d.line([(s(60), s(fy - 30)), (s(W - 60), s(fy - 30))], fill=(255, 255, 255, 18), width=S)
    text((60, fy), 'CITAD3L  ·  MOVE IN SILENCE', F('Cinzel', 18, 700), SILVER, 'lm', spacing=3)
    text((W - 60, fy), 'RECAP ONLY  ·  NOT FINANCIAL ADVICE  ·  MOST RUNNERS DUMP  ·  DATA: ' + ' · '.join(sorted(SRC_OK)).upper(), F('JetBrainsMono', 12, 500), DIM, 'rm', spacing=1)
    img.convert('RGB').resize((W, H), Image.LANCZOS).save(path, 'PNG', optimize=True)
    return path

card_ok = safe(lambda: render(PREVIEW), 'image card')

# ---------------------------------------------------------------- embed
srcs = ', '.join(sorted(SRC_OK)) or 'none reachable'
fields = []
DETAIL = 6
for i, r in enumerate(out[:DETAIL]):
    l1 = f"MC **{usd(r['cap'])}** · peak **{usd(r['peak'])}** · 24h **{pc(r['h24'])}**"
    l2 = f"⏱️ launched {dur(r['age_h'])} ago" + (f" · $1M in {'' if r['t1m_h'] < 1 else '~'}{dur(r['t1m_h'])}" if r['t1m_h'] is not None else '') + \
         f" · vol {usd(r['vol'])} · liq {usd(r['liq'])}" + (f" · 👥 {r['holders']:,}" if r['holders'] else '') + \
         (f" (top10 {r['top10']:.0f}%)" if r['top10'] is not None else '')
    dev = f"[{short(r['dev'])}](https://solscan.io/account/{r['dev']})" if r['dev'] else 'n/a'
    soc = ' · '.join(f"[{lab}]({r['socials'][k]})" for k, lab in (('x', 'X'), ('tg', 'TG'), ('web', 'Web')) if k in r['socials']) or 'no socials'
    flag = dev_flag(r['dev_hist'])
    l3 = f"🥷 **Who:** dev {dev} · {hold_txt(r['dev_hold'])} · {dev_hist_txt(r['dev_hist'])}" + (f" · {flag}" if flag else '') + f" · {soc}"
    l4 = f"🧭 **Why:** {why_txt(r)}"
    l5 = f"[📈 chart]({r['url']}) · `{r['addr']}`"
    body = '\n'.join([l1, l2, l3, l4, l5])
    if len(body) > 1024: body = '\n'.join([l1, l2, l3, f"🧭 **Why:** {why_txt(r, link=False)}"[:1024 - len(l1 + l2 + l3 + l5) - 8], l5])
    fields.append({'name': f"`{i + 1:02d}` {md(clean(r['name'], 40))}  (${md(clean(r['sym'], 14, r['name']))})", 'value': body[:1024], 'inline': False})
if len(out) > DETAIL:
    rest = '\n'.join(f"`{i + 1:02d}` **${md(clean(r['sym'], 14, r['name']))}** peak {usd(r['peak'])} · MC {usd(r['cap'])} · dev {short(r['dev'])} · [chart]({r['url']})"
                     for i, r in enumerate(out[DETAIL:], DETAIL))
    fields.append({'name': '➕ Also ran', 'value': rest[:1024], 'inline': False})
if out:
    desc = (f"**{len(out)} Solana coin{'s' if len(out) != 1 else ''}** launched in the last 24h and hit **$1M**.\n"
            "A recap of what already ran, *not* picks. Dev history from pump.fun; news from Google News (48h).")
else:
    desc = ("## 🌑 Quiet day on the walls\nNo Solana coin launched in the last 24h reached **$1M**.\n"
            "Patience is a position. The watch resumes tomorrow.")
emb = {'author': {'name': 'CITAD3L  ·  THE WATCHTOWER'}, 'title': f"🏃 RUNNERS OF THE DAY  ·  {now_ct.strftime('%a %b %d')}",
       'description': desc, 'color': 0xB078FF if out else 0x5B6170, 'fields': fields,
       'footer': {'text': f'Citad3l • move in silence  ·  recap only · not financial advice · most runners dump  ·  data: {srcs}'},
       'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()}
if card_ok: emb['image'] = {'url': 'attachment://runners.png'}
def emb_len(e): return len(e['title']) + len(e['description']) + len(e['footer']['text']) + len(e['author']['name']) + sum(len(x['name']) + len(x['value']) for x in e['fields'])
while emb_len(emb) > 5800 and len(emb['fields']) > 1:  # Discord: 6000 chars per embed
    emb['fields'].pop(-2 if emb['fields'][-1]['name'].startswith('➕') else -1)

if DRY:
    log(json.dumps(emb, indent=1, ensure_ascii=False))
    log('preview:', PREVIEW if card_ok else 'image failed', '| runners', len(out), '| sources', srcs, f'| {time.time() - T0:.0f}s')
    sys.exit()

# ---------------------------------------------------------------- post
TOKEN = os.environ['DISCORD_BOT_TOKEN']
def dapi(m, p, d=None, raw=None, ctype='application/json'):
    body = raw if raw is not None else (json.dumps(d).encode() if d is not None else None)
    for i in range(4):
        r = urllib.request.Request('https://discord.com/api/v10' + p, method=m, data=body,
                                   headers={'Authorization': 'Bot ' + TOKEN, 'Content-Type': ctype, 'User-Agent': 'DiscordBot (citad3l, 2)'})
        try:
            with urllib.request.urlopen(r, timeout=30) as x:
                b = x.read(); return json.loads(b) if b else None
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 3:
                try: time.sleep(float(json.loads(e.read()).get('retry_after', 2)) + 0.5)
                except Exception: time.sleep(3)
                continue
            if e.code >= 500 and i < 3: time.sleep(2); continue
            raise RuntimeError(f'discord {m} -> {e.code}')
ch = os.environ.get('RUNNERS_CHANNEL_ID') or open(CH_FILE).read().strip()
payload = {'embeds': [emb], 'allowed_mentions': {'parse': []}}
msg = None
if card_ok:
    bnd = uuid.uuid4().hex
    payload['attachments'] = [{'id': 0, 'filename': 'runners.png'}]
    body = (f'--{bnd}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n'.encode()
            + json.dumps(payload).encode()
            + f'\r\n--{bnd}\r\nContent-Disposition: form-data; name="files[0]"; filename="runners.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
            + open(PREVIEW, 'rb').read() + f'\r\n--{bnd}--\r\n'.encode())
    try: msg = dapi('POST', f'/channels/{ch}/messages', raw=body, ctype=f'multipart/form-data; boundary={bnd}')
    except Exception as e: log('[warn] image post failed, sending text-only:', type(e).__name__)
if msg is None:
    emb.pop('image', None); payload.pop('attachments', None)
    msg = dapi('POST', f'/channels/{ch}/messages', payload)
log('posted', len(out), 'runners', (msg or {}).get('id', ''))
for r in out: posted[r['addr']] = int(NOW)
posted = {a: t for a, t in posted.items() if NOW - t < 14 * 86400}
try: json.dump({'posted': posted, 'last_run': int(NOW), 'last_count': len(out)}, open(STATE, 'w'), indent=1)
except Exception as e: log('[warn] state not saved', e)
