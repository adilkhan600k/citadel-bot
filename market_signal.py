#!/usr/bin/env python3
"""Citad3l Watchtower: daily meme-coin market signal for Discord.
Usage: python3 market_signal.py            -> fetch, render card, post to channel
       python3 market_signal.py --dry      -> render preview.png next to this script, no post
       python3 market_signal.py --replace  -> post, then delete the bot's older messages in the channel
Free data only: CoinGecko, alternative.me, DefiLlama. Every source is optional.
"""
import os, sys, json, time, math, uuid, datetime, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CH_FILE = f'{BASE}/market_signal_channel.txt'
STATE = f'{BASE}/market_state.json'
FONTS = f'{BASE}/fonts'
PREVIEW = f'{BASE}/preview.png'
DRY = '--dry' in sys.argv
UA = {'User-Agent': 'Mozilla/5.0', 'accept': 'application/json'}

def log(*a): print(*a, flush=True)

# ---------------------------------------------------------------- data
_last_cg = [0.0]
def get(url, cg=False, timeout=20):
    if cg:  # respect CoinGecko free tier
        wait = 1.6 - (time.time() - _last_cg[0])
        if wait > 0: time.sleep(wait)
    for attempt in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
            data = json.loads(r.read())
            if cg: _last_cg[0] = time.time()
            return data
        except urllib.error.HTTPError as e:
            if cg: _last_cg[0] = time.time()
            if e.code == 429 and attempt == 0: time.sleep(6); continue
            raise

def safe(fn, label):
    try: return fn()
    except Exception as e:
        log(f'[warn] {label} unavailable: {type(e).__name__}')
        return None

CG = 'https://api.coingecko.com/api/v3'
D = {}
fg = safe(lambda: get('https://api.alternative.me/fng/?limit=8')['data'], 'fear&greed')
if fg:
    D['fg'] = int(fg[0]['value']); D['fg_cls'] = fg[0]['value_classification']
    D['fg_y'] = int(fg[1]['value']) if len(fg) > 1 else None
    D['fg_7'] = int(fg[7]['value']) if len(fg) > 7 else None
    D['fg_hist'] = [int(x['value']) for x in reversed(fg)]

coins = safe(lambda: {x['id']: x for x in get(f'{CG}/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana&price_change_percentage=24h,7d&sparkline=true', cg=True)}, 'majors')
for cid, k in (('bitcoin', 'btc'), ('ethereum', 'eth'), ('solana', 'sol')):
    x = (coins or {}).get(cid)
    if x:
        D[k] = x.get('current_price'); D[k+'24'] = x.get('price_change_percentage_24h_in_currency')
        D[k+'7'] = x.get('price_change_percentage_7d_in_currency')
        D[k+'_spark'] = (x.get('sparkline_in_7d') or {}).get('price') or []

gl = safe(lambda: get(f'{CG}/global', cg=True)['data'], 'global')
if gl:
    D['mcap'] = gl.get('total_market_cap', {}).get('usd'); D['mcap24'] = gl.get('market_cap_change_percentage_24h_usd')
    D['btcd'] = gl.get('market_cap_percentage', {}).get('btc')

def _meme_cat():
    for x in get(f'{CG}/coins/categories', cg=True):
        if x.get('id') == 'meme-token': return x
meme = safe(_meme_cat, 'meme category')
if meme: D['meme_mcap'] = meme.get('market_cap'); D['meme24'] = meme.get('market_cap_change_24h'); D['meme_vol'] = meme.get('volume_24h')

def _trending():
    out = []
    for c in get(f'{CG}/search/trending', cg=True).get('coins', [])[:5]:
        it = c['item']; ch = ((it.get('data') or {}).get('price_change_percentage_24h') or {}).get('usd')
        out.append({'sym': it.get('symbol', '?').upper(), 'name': it.get('name', '?'), 'ch': ch, 'rank': it.get('market_cap_rank')})
    return out
D['trending'] = safe(_trending, 'trending') or []

def _memes():
    rows = [r for r in get(f'{CG}/coins/markets?vs_currency=usd&category=meme-token&order=market_cap_desc&per_page=100&page=1&price_change_percentage=24h', cg=True)
            if r.get('price_change_percentage_24h') is not None]
    rows.sort(key=lambda r: r['price_change_percentage_24h'], reverse=True)
    pick = lambda r: {'sym': r['symbol'].upper(), 'ch': r['price_change_percentage_24h'], 'rank': r.get('market_cap_rank')}
    breadth = sum(1 for r in rows if r['price_change_percentage_24h'] > 0) / len(rows) * 100 if rows else None
    return [pick(r) for r in rows[:3]], [pick(r) for r in rows[-3:][::-1]], breadth
mm = safe(_memes, 'meme movers')
D['gainers'], D['losers'], D['breadth'] = mm if mm else ([], [], None)

def _soldex():
    d = get('https://api.llama.fi/overview/dexs/solana?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true')
    pump = sum((p.get('total24h') or 0) for p in d.get('protocols', []) if 'pump' in (p.get('name') or '').lower())
    return d.get('total24h'), d.get('change_1d'), pump or None
sd = safe(_soldex, 'solana dex')
if sd: D['soldex'], D['soldex1d'], D['pump'] = sd

# ---------------------------------------------------------------- score (math, not vibes)
def v(k): return D.get(k)
score, inputs = 0, 0
def add(val, fn):
    global score, inputs
    if val is not None: score += fn(val); inputs += 1
add(v('fg'),     lambda x: 2 if x >= 55 else (1 if x >= 40 else (-1 if x >= 25 else -2)))
add(v('btc7'),   lambda x: 1 if x > 2 else (-1 if x < -3 else 0))
add(v('sol7'),   lambda x: 2 if x > 5 else (1 if x > 0 else (-1 if x > -8 else -2)))
add(v('sol24'),  lambda x: 1 if x > 1 else (-1 if x < -3 else 0))
add(v('meme24'), lambda x: 2 if x > 3 else (1 if x > 0 else (-1 if x > -5 else -2)))
add(v('mcap24'), lambda x: 1 if x > 1 else (-1 if x < -2 else 0))
add(v('breadth'),  lambda x: 1 if x >= 60 else (-1 if x <= 35 else 0))
add(v('soldex1d'), lambda x: 1 if x > 10 else (-1 if x < -15 else 0))
SMIN, SMAX = -11, 11

if inputs < 3:
    TIER = dict(key='OFFLINE', emo='⚫', gate='WATCH OFFLINE', mood='NO SIGNAL', color=0x5B6170, rgb=(150, 158, 172),
                play=['Data feeds are down today. No call made.', 'Trade only your own plan.', 'When in doubt, stay out.'])
elif score >= 3:
    TIER = dict(key='GREEN', emo='🟢', gate='GATES OPEN', mood='RISK ON', color=0x2ECC71, rgb=(46, 230, 140),
                play=['Conditions favor meme plays. Size normally.', 'Take profits into strength, scale out.', 'Stops on every entry. Greed kills.'])
elif score >= -1:
    TIER = dict(key='YELLOW', emo='🟡', gate='GATES GUARDED', mood='CHOPPY', color=0xF5B82E, rgb=(255, 184, 46),
                play=['Trade small. Half size or less.', 'Only the cleanest setups. Quick in, quick out.', 'No bag holding. Cut losers fast.'])
else:
    TIER = dict(key='RED', emo='🔴', gate='GATES SEALED', mood='RISK OFF', color=0xE5484D, rgb=(255, 72, 77),
                play=['Sit out or trade tiny.', 'Protect capital. Cash is a position.', 'Wait for the turn. The citadel holds.'])

# ---------------------------------------------------------------- since yesterday
try:
    from zoneinfo import ZoneInfo
    now_ct = datetime.datetime.now(ZoneInfo('America/Chicago'))
except Exception:
    now_ct = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)
today = now_ct.strftime('%Y-%m-%d')
snap = {'date': today, 'score': score, 'tier': TIER['key'], 'fg': v('fg'), 'btc': v('btc'), 'sol': v('sol'),
        'meme_mcap': v('meme_mcap'), 'mcap': v('mcap'), 'btcd': v('btcd')}
st = safe(lambda: json.load(open(STATE)), 'state') or {}
prev = st.get('prev') if st.get('last', {}).get('date') == today else st.get('last')
since = None
if prev:
    def pct(a, b): return (a / b - 1) * 100 if a and b else None
    since = {'tier': prev.get('tier'), 'score': prev.get('score'), 'fg': prev.get('fg'),
             'btc': pct(v('btc'), prev.get('btc')), 'sol': pct(v('sol'), prev.get('sol')),
             'meme': pct(v('meme_mcap'), prev.get('meme_mcap')), 'date': prev.get('date')}
if not DRY:
    try: json.dump({'last': snap, 'prev': prev}, open(STATE, 'w'), indent=1)
    except Exception as e: log('[warn] state not saved', e)

# ---------------------------------------------------------------- formatting helpers
def pc(x, d=1): return 'n/a' if x is None else f"{'+' if x >= 0 else ''}{x:.{d}f}%"
def usd(x):
    if x is None: return 'n/a'
    if x >= 1e12: return f'${x/1e12:.2f}T'
    if x >= 1e9: return f'${x/1e9:.1f}B'
    if x >= 1e6: return f'${x/1e6:.0f}M'
    if x >= 100: return f'${x:,.0f}'
    return f'${x:,.2f}'
def bar(val, lo, hi, n=10):
    if val is None: return '▱' * n
    k = round((min(max(val, lo), hi) - lo) / (hi - lo) * n)
    return '▰' * k + '▱' * (n - k)
def arrow(x): return '' if x is None else ('▲' if x >= 0 else '▼')

# ---------------------------------------------------------------- image card
def render(path):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    S = 2; W, H = 1600, 1000
    def s(x): return int(round(x * S))
    _fc = {}
    def F(name, size, wght):
        key = (name, size, wght)
        if key not in _fc:
            try:
                f = ImageFont.truetype(f'{FONTS}/{name}.ttf', s(size))
                try:
                    axes = f.get_variation_axes()
                    f.set_variation_by_axes([min(32, max(14, size)) if a['name'] == b'Optical size' else wght for a in axes])
                except Exception: pass
            except Exception:
                f = ImageFont.load_default(size=s(size))
            _fc[key] = f
        return _fc[key]

    SILVER = (200, 206, 216); WHITE = (244, 246, 250); MUTED = (122, 130, 145); DIM = (70, 76, 88)
    UP = (52, 224, 140); DOWN = (255, 86, 92); GLOW = TIER['rgb']
    def chc(x): return MUTED if x is None else (UP if x >= 0 else DOWN)

    # background: deep gradient + faint fortress masonry + signal glow
    img = Image.new('RGB', (s(W), s(H)), (8, 9, 12))
    px = Image.linear_gradient('L').resize((s(W), s(H)))
    top = Image.new('RGB', img.size, (6, 7, 10)); bot = Image.new('RGB', img.size, (19, 21, 27))
    img = Image.composite(bot, top, px)
    mason = Image.new('RGBA', img.size, (0, 0, 0, 0)); md = ImageDraw.Draw(mason)
    bh, bw = 46, 120
    for r in range(0, H // bh + 2):
        y = r * bh; off = (bw // 2) if r % 2 else 0
        md.line([(0, s(y)), (s(W), s(y))], fill=(255, 255, 255, 9), width=S)
        for c in range(-1, W // bw + 2):
            x = c * bw + off
            md.line([(s(x), s(y)), (s(x), s(y + bh))], fill=(255, 255, 255, 9), width=S)
    img = Image.alpha_composite(img.convert('RGBA'), mason)
    glow = Image.new('RGBA', img.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([s(-120), s(60), s(620), s(800)], fill=GLOW + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(s(140)))
    img = Image.alpha_composite(img, glow)
    # vignette
    vig = Image.new('L', img.size, 0); vd = ImageDraw.Draw(vig)
    vd.ellipse([s(-300), s(-260), s(W + 300), s(H + 260)], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(s(160)))
    img = Image.composite(img, Image.new('RGBA', img.size, (3, 3, 5, 255)), vig)
    d = ImageDraw.Draw(img)

    def text(xy, t, f, fill, anchor='la', spacing=0):
        if spacing:
            x, y = xy
            if anchor[0] in 'rm':
                tw = sum(d.textlength(ch, font=f) for ch in t) + s(spacing) * (len(t) - 1)
                x = x * S - (tw if anchor[0] == 'r' else tw / 2); x /= S
            cx = s(x)
            for ch in t:
                d.text((cx, s(y)), ch, font=f, fill=fill, anchor='l' + anchor[1]); cx += d.textlength(ch, font=f) + s(spacing)
        else:
            d.text((s(xy[0]), s(xy[1])), t, font=f, fill=fill, anchor=anchor)
    def card(x, y, w, h, r=18, fill=(16, 18, 24, 215), outline=(255, 255, 255, 22)):
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle([s(x), s(y), s(x + w), s(y + h)], s(r), fill=fill, outline=outline, width=S)
        ld.line([(s(x + r), s(y) + S), (s(x + w - r), s(y) + S)], fill=(255, 255, 255, 30), width=S)  # top sheen
        img.alpha_composite(layer)

    # ---- header
    text((60, 52), 'CITAD3L', F('Cinzel', 58, 900), SILVER, 'lm', spacing=10)
    tw = sum(d.textlength(c, font=F('Cinzel', 58, 900)) for c in 'CITAD3L') / S + 60
    d.line([(s(60 + tw + 22), s(36)), (s(60 + tw + 22), s(70))], fill=DIM, width=S)
    text((60 + tw + 44, 42), 'THE WATCHTOWER', F('SpaceGrotesk', 22, 700), WHITE, 'lm', spacing=4)
    text((60 + tw + 44, 66), 'DAILY MEME MARKET REPORT', F('JetBrainsMono', 14, 500), MUTED, 'lm', spacing=2)
    text((W - 60, 42), now_ct.strftime('%a %b %d, %Y').upper(), F('JetBrainsMono', 20, 700), WHITE, 'rm', spacing=1)
    text((W - 60, 66), now_ct.strftime('%I:%M %p').lstrip('0') + ' CT  ·  LIVE SNAPSHOT', F('JetBrainsMono', 14, 500), MUTED, 'rm', spacing=1)
    # silver rule with fade
    for i in range(W - 120):
        a = int(120 * math.sin(math.pi * i / (W - 120)))
        d.point((s(60 + i), s(98)), fill=(200, 206, 216, a))

    # ---- signal tower (3 lamps)
    tx, ty, twd, tht = 70, 130, 150, 400
    # battlements (merlons) fused to the tower top
    for i in range(4):
        bx = tx + 8 + i * 36
        card(bx, ty - 24, 26, 40, r=4, fill=(14, 15, 20, 255), outline=(200, 206, 216, 95))
    card(tx, ty, twd, tht, r=18, fill=(14, 15, 20, 255), outline=(200, 206, 216, 95))
    d.line([(s(tx + 20), s(ty + tht - 14)), (s(tx + twd - 20), s(ty + tht - 14))], fill=(255, 255, 255, 18), width=S)
    lamps = [('GREEN', (46, 230, 140)), ('YELLOW', (255, 184, 46)), ('RED', (255, 72, 77))]
    for i, (k, col) in enumerate(lamps):
        cx, cy, rad = tx + twd / 2, ty + 75 + i * 125, 46
        on = (k == TIER['key'])
        if on:
            gl2 = Image.new('RGBA', img.size, (0, 0, 0, 0)); g2 = ImageDraw.Draw(gl2)
            g2.ellipse([s(cx - rad * 2.2), s(cy - rad * 2.2), s(cx + rad * 2.2), s(cy + rad * 2.2)], fill=col + (150,))
            gl2 = gl2.filter(ImageFilter.GaussianBlur(s(36))); img.alpha_composite(gl2)
            d.ellipse([s(cx - rad), s(cy - rad), s(cx + rad), s(cy + rad)], fill=col)
            d.ellipse([s(cx - rad * 0.55), s(cy - rad * 0.7), s(cx + rad * 0.15), s(cy - rad * 0.15)], fill=tuple(min(255, c + 70) for c in col))
        else:
            d.ellipse([s(cx - rad), s(cy - rad), s(cx + rad), s(cy + rad)], fill=tuple(int(c * 0.16) + 8 for c in col), outline=(255, 255, 255, 25), width=S)

    # ---- verdict
    vx = 270
    text((vx, 150), 'SIGNAL  //  MEME COINS', F('JetBrainsMono', 16, 700), MUTED, 'la', spacing=3)
    text((vx - 4, 172), TIER['gate'], F('SpaceGrotesk', 92, 700), GLOW, 'la')
    # watch level dial
    dcx, dcy, dr = 1430, 222, 92
    frac = (min(max(score, SMIN), SMAX) - SMIN) / (SMAX - SMIN)
    bb = [s(dcx - dr), s(dcy - dr), s(dcx + dr), s(dcy + dr)]
    d.arc(bb, 135, 405, fill=(34, 37, 45), width=s(14))
    dg = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(dg).arc(bb, 135, 135 + 270 * frac, fill=GLOW + (160,), width=s(26))
    img.alpha_composite(dg.filter(ImageFilter.GaussianBlur(s(10))))
    d.arc(bb, 135, 135 + 270 * frac, fill=GLOW, width=s(14))
    for t in range(0, 11):  # tick marks
        a = math.radians(135 + 27 * t); r1, r2 = dr + 14, dr + 22
        d.line([(s(dcx + r1 * math.cos(a)), s(dcy + r1 * math.sin(a))), (s(dcx + r2 * math.cos(a)), s(dcy + r2 * math.sin(a)))], fill=DIM, width=S)
    text((dcx, dcy - 8), f'{score:+d}', F('SpaceGrotesk', 60, 700), WHITE, 'mm')
    text((dcx, dcy + 36), 'WATCH LEVEL', F('JetBrainsMono', 12, 700), MUTED, 'mm', spacing=2)
    text((dcx, dcy + dr + 4), TIER['mood'], F('JetBrainsMono', 13, 800), GLOW, 'mm', spacing=3)
    text((vx, 290), f"{TIER['mood']}   ·   {TIER['play'][0]}", F('SpaceGrotesk', 28, 500), WHITE, 'la')

    def gauge(x, y, w, label, val, lo, hi, valtxt, sub, cols):
        text((x, y), label, F('JetBrainsMono', 14, 700), MUTED, 'la', spacing=2)
        text((x + w, y), valtxt, F('SpaceGrotesk', 20, 700), WHITE, 'ra')
        n, gap = 20, 5; segw = (w - gap * (n - 1)) / n
        k = 0 if val is None else round((min(max(val, lo), hi) - lo) / (hi - lo) * n)
        for i in range(n):
            sx = x + i * (segw + gap); t = i / (n - 1)
            c = cols[0] if t < 0.33 else (cols[1] if t < 0.66 else cols[2])
            fill = c if i < k else (34, 37, 45)
            d.rounded_rectangle([s(sx), s(y + 34), s(sx + segw), s(y + 52)], s(3), fill=fill)
        text((x, y + 64), sub, F('JetBrainsMono', 13, 500), MUTED, 'la')
    tri = [(255, 72, 77), (255, 184, 46), (46, 230, 140)]
    gauge(vx, 350, 560, 'SIGNAL SCORE', score, SMIN, SMAX, f'{score:+d}', f'range {SMIN:+d} to {SMAX:+d}  ·  {inputs} inputs  ·  +3 opens the gates', tri)
    fgsub = f"yesterday {v('fg_y') if v('fg_y') is not None else 'n/a'}  ·  7d ago {v('fg_7') if v('fg_7') is not None else 'n/a'}"
    gauge(vx + 620, 350, 560, 'FEAR & GREED', v('fg'), 0, 100, f"{v('fg') if v('fg') is not None else 'n/a'}  {(v('fg_cls') or '').upper()}", fgsub, tri)

    # The Play box
    card(vx, 450, 1180, 80, r=16, fill=(GLOW[0] // 9, GLOW[1] // 9, GLOW[2] // 9, 220), outline=GLOW + (90,))
    text((vx + 24, 490), 'THE PLAY', F('JetBrainsMono', 15, 800), GLOW, 'lm', spacing=3)
    text((vx + 160, 490), '   ·   '.join(TIER['play'][1:]), F('SpaceGrotesk', 23, 500), WHITE, 'lm')

    # ---- metrics grid
    metrics = [
        ('BITCOIN', usd(v('btc')), v('btc24'), v('btc7')),
        ('ETHEREUM', usd(v('eth')), v('eth24'), v('eth7')),
        ('SOLANA', usd(v('sol')), v('sol24'), v('sol7')),
        ('MEME SECTOR', usd(v('meme_mcap')), v('meme24'), None),
        ('TOTAL MARKET', usd(v('mcap')), v('mcap24'), None),
        ('BTC DOMINANCE', 'n/a' if v('btcd') is None else f"{v('btcd'):.1f}%", None, None),
        ('SOL DEX VOL 24H', usd(v('soldex')), v('soldex1d'), None),
        ('MEME BREADTH', 'n/a' if v('breadth') is None else f"{v('breadth'):.0f}% green", None, None),
    ]
    gx, gy, cw, chh, gap = 60, 560, 245, 112, 14
    for i, (lab, val, c24, c7) in enumerate(metrics):
        r, c = divmod(i, 4); x = gx + c * (cw + gap); y = gy + r * (chh + gap)
        card(x, y, cw, chh, r=14)
        text((x + 18, y + 16), lab, F('JetBrainsMono', 13, 700), MUTED, 'la', spacing=2)
        text((x + 18, y + 38), val, F('SpaceGrotesk', 34 if len(val) < 11 else 27, 700), WHITE, 'la')
        cx = x + 18
        for tag, ch in (('24H', c24), ('7D', c7)):
            if ch is None: continue
            t = f'{arrow(ch)} {pc(ch)} {tag}'
            text((cx, y + 88), t, F('JetBrainsMono', 14, 700), chc(ch), 'la')
            cx += d.textlength(t, font=F('JetBrainsMono', 14, 700)) / S + 14
        if c24 is None and c7 is None:
            sub = {'BTC DOMINANCE': 'share of total cap', 'MEME BREADTH': 'top 100 memes up 24h'}.get(lab, '')
            text((x + 18, y + 88), sub, F('JetBrainsMono', 13, 500), DIM, 'la')

    # ---- sparkline panel
    px0, py0, pw, ph = 1100, 560, 440, 238
    card(px0, py0, pw, ph, r=14)
    text((px0 + 18, py0 + 16), '7D PERFORMANCE', F('JetBrainsMono', 13, 700), MUTED, 'la', spacing=2)
    series = [('BTC', v('btc_spark') or [], SILVER), ('SOL', v('sol_spark') or [], (176, 120, 255))]
    norm = [(n, [(p / sp[0] - 1) * 100 for p in sp], col) for n, sp, col in series if len(sp) > 2]
    lx = px0 + pw - 18
    for n, sp, col in reversed(norm):
        t = f'{n} {pc(sp[-1])}'
        text((lx, py0 + 16), t, F('JetBrainsMono', 13, 700), col, 'ra')
        lx -= d.textlength(t, font=F('JetBrainsMono', 13, 700)) / S + 18
    if norm:
        allv = [x for _, sp, _ in norm for x in sp]; lo, hi = min(allv + [0]), max(allv + [0])
        if hi - lo < 1e-9: hi = lo + 1
        ax, ay, aw, ah = px0 + 18, py0 + 48, pw - 36, ph - 70
        zy = ay + ah - (0 - lo) / (hi - lo) * ah
        for i in range(0, int(aw), 8): d.line([(s(ax + i), s(zy)), (s(ax + i + 4), s(zy))], fill=DIM, width=S)
        for n, sp, col in norm:
            pts = [(s(ax + i / (len(sp) - 1) * aw), s(ay + ah - (val - lo) / (hi - lo) * ah)) for i, val in enumerate(sp)]
            fill_l = Image.new('RGBA', img.size, (0, 0, 0, 0)); fd = ImageDraw.Draw(fill_l)
            fd.polygon(pts + [(pts[-1][0], s(zy)), (pts[0][0], s(zy))], fill=col + (14,)); img.alpha_composite(fill_l)
            d.line(pts, fill=col, width=s(2.6), joint='curve')
            d.ellipse([pts[-1][0] - s(5), pts[-1][1] - s(5), pts[-1][0] + s(5), pts[-1][1] + s(5)], fill=col)
        text((ax, ay + ah + 8), '7 DAYS AGO', F('JetBrainsMono', 11, 500), DIM, 'la')
        text((ax + aw, ay + ah + 8), 'NOW', F('JetBrainsMono', 11, 500), DIM, 'ra')
    else:
        text((px0 + pw / 2, py0 + ph / 2), 'n/a', F('SpaceGrotesk', 28, 600), MUTED, 'mm')

    # ---- trending chips
    ty2 = 832
    text((60, ty2 + 20), 'TRENDING', F('JetBrainsMono', 14, 800), MUTED, 'lm', spacing=3)
    cx = 190
    for t in D['trending'][:5] or [{'sym': 'n/a', 'ch': None}]:
        lab = f"{t['sym']}"; chs = pc(t['ch']) if t['ch'] is not None else ''
        f1, f2 = F('SpaceGrotesk', 20, 700), F('JetBrainsMono', 15, 700)
        w = d.textlength(lab, font=f1) / S + (d.textlength(chs, font=f2) / S + 12 if chs else 0) + 36
        if cx + w > W - 60: break
        card(cx, ty2, w, 40, r=20, fill=(22, 24, 31, 230))
        text((cx + 18, ty2 + 20), lab, f1, WHITE, 'lm')
        if chs: text((cx + 18 + d.textlength(lab, font=f1) / S + 12, ty2 + 20), chs, f2, chc(t['ch']), 'lm')
        cx += w + 12

    # since yesterday strip
    if since:
        parts = []
        if since.get('tier') and since['tier'] != TIER['key']: parts.append(f"SIGNAL {since['tier']} → {TIER['key']}")
        elif since.get('tier'): parts.append(f"SIGNAL HELD {TIER['key']}")
        if since.get('fg') is not None and v('fg') is not None: parts.append(f"F&G {since['fg']} → {v('fg')}")
        for k, n in (('btc', 'BTC'), ('sol', 'SOL'), ('meme', 'MEMES')):
            if since.get(k) is not None: parts.append(f'{n} {pc(since[k])}')
        stxt = 'SINCE LAST REPORT   ' + '   ·   '.join(parts)
    else:
        stxt = 'SINCE LAST REPORT   first watch logged. comparisons start tomorrow.'
    text((60, 900), stxt, F('JetBrainsMono', 14, 600), SILVER, 'lm')

    # footer
    d.line([(s(60), s(932)), (s(W - 60), s(932))], fill=(255, 255, 255, 18), width=S)
    text((60, 962), 'CITAD3L  ·  MOVE IN SILENCE', F('Cinzel', 18, 700), SILVER, 'lm', spacing=3)
    text((W - 60, 962), 'NOT FINANCIAL ADVICE  ·  DATA: COINGECKO · ALTERNATIVE.ME · DEFILLAMA', F('JetBrainsMono', 12, 500), DIM, 'rm', spacing=1)

    img = img.convert('RGB').resize((W, H), Image.LANCZOS)
    img.save(path, 'PNG', optimize=True)
    return path

card_ok = safe(lambda: render(PREVIEW), 'image card')

# ---------------------------------------------------------------- embed
def movers(lst):
    return '\n'.join(f"`{i+1}` **{m['sym']}**  {arrow(m['ch'])} {pc(m['ch'])}" for i, m in enumerate(lst)) or 'n/a'
fgline = 'n/a' if v('fg') is None else f"{bar(v('fg'), 0, 100)}  **{v('fg')}** {v('fg_cls')}\nyesterday **{v('fg_y')}**  ·  7d ago **{v('fg_7')}**"
if since:
    sl = []
    if since.get('tier'): sl.append(f"Signal **{since['tier']} → {TIER['key']}**" if since['tier'] != TIER['key'] else f"Signal held **{TIER['key']}**")
    if since.get('score') is not None: sl.append(f"score {since['score']:+d} → {score:+d}")
    if since.get('fg') is not None and v('fg') is not None: sl.append(f"F&G {since['fg']} → {v('fg')}")
    for k, n in (('btc', 'BTC'), ('sol', 'SOL'), ('meme', 'Memes')):
        if since.get(k) is not None: sl.append(f'{n} {pc(since[k])}')
    since_txt = '  ·  '.join(sl)
else:
    since_txt = 'First watch logged. Comparisons start with the next report.'
trend_txt = '  '.join(f"**{t['sym']}** {pc(t['ch'])}" if t['ch'] is not None else f"**{t['sym']}**" for t in D['trending'][:5]) or 'n/a'
dex_txt = 'n/a' if v('soldex') is None else f"{usd(v('soldex'))} 24h  ({pc(v('soldex1d'))} vs prior day)" + (f"\npump.fun + PumpSwap {usd(v('pump'))}" if v('pump') else '')
desc = (f"## {TIER['emo']}  {TIER['gate']}\n"
        f"**{TIER['mood']}**  ·  {TIER['play'][0]}\n\n"
        f"`SIGNAL` {bar(score, SMIN, SMAX)}  **{score:+d}**\n"
        f"`F & G ` {bar(v('fg'), 0, 100)}  **{v('fg') if v('fg') is not None else 'n/a'}**")
breadth_txt = 'n/a' if v('breadth') is None else f"{v('breadth'):.0f}% green"
btcd_txt = 'n/a' if v('btcd') is None else f"{v('btcd'):.1f}%"
fields = [
    {'name': '⚔️ The Play', 'value': '\n'.join(f'▸ {p}' for p in TIER['play']), 'inline': False},
    {'name': '₿ Bitcoin', 'value': f"{usd(v('btc'))}\n24h {pc(v('btc24'))}\n7d {pc(v('btc7'))}", 'inline': True},
    {'name': '◆ Ethereum', 'value': f"{usd(v('eth'))}\n24h {pc(v('eth24'))}\n7d {pc(v('eth7'))}", 'inline': True},
    {'name': '◎ Solana', 'value': f"{usd(v('sol'))}\n24h {pc(v('sol24'))}\n7d {pc(v('sol7'))}", 'inline': True},
    {'name': '🐸 Meme sector', 'value': f"{usd(v('meme_mcap'))}\n24h {pc(v('meme24'))}\nbreadth {breadth_txt}", 'inline': True},
    {'name': '🌐 Total market', 'value': f"{usd(v('mcap'))}\n24h {pc(v('mcap24'))}\nBTC dom {btcd_txt}", 'inline': True},
    {'name': '😱 Fear & Greed', 'value': fgline, 'inline': True},
    {'name': '🚀 Top meme gainers 24h', 'value': movers(D['gainers']), 'inline': True},
    {'name': '🩸 Top meme losers 24h', 'value': movers(D['losers']), 'inline': True},
    {'name': '⚡ Solana DEX volume', 'value': dex_txt, 'inline': True},
    {'name': '🔥 Trending now', 'value': trend_txt, 'inline': False},
    {'name': '🕰️ Since last report', 'value': since_txt, 'inline': False},
]
emb = {'author': {'name': 'CITAD3L  ·  THE WATCHTOWER'}, 'title': f"🏰 Daily Meme Market Report  ·  {now_ct.strftime('%a %b %d')}",
       'description': desc, 'color': TIER['color'], 'fields': fields,
       'footer': {'text': 'Citad3l • move in silence  ·  not financial advice  ·  data: CoinGecko, alternative.me, DefiLlama'},
       'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()}
if card_ok: emb['image'] = {'url': 'attachment://signal.png'}

if DRY:
    log(json.dumps(emb, indent=1, ensure_ascii=False)); log('preview:', PREVIEW if card_ok else 'image failed', '| score', score, TIER['key']); sys.exit()

# ---------------------------------------------------------------- post
T = os.environ['DISCORD_BOT_TOKEN']
def dapi(m, p, d=None, raw=None, ctype='application/json'):
    body = raw if raw is not None else (json.dumps(d).encode() if d is not None else None)
    r = urllib.request.Request('https://discord.com/api/v10' + p, method=m, data=body,
                               headers={'Authorization': 'Bot ' + T, 'Content-Type': ctype, 'User-Agent': 'DiscordBot (citad3l, 2)'})
    with urllib.request.urlopen(r, timeout=30) as x:
        b = x.read(); return json.loads(b) if b else None
ch = open(CH_FILE).read().strip()
payload = {'embeds': [emb]}
if card_ok:
    bnd = uuid.uuid4().hex
    payload['attachments'] = [{'id': 0, 'filename': 'signal.png'}]
    body = (f'--{bnd}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n'.encode()
            + json.dumps(payload).encode()
            + f'\r\n--{bnd}\r\nContent-Disposition: form-data; name="files[0]"; filename="signal.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
            + open(PREVIEW, 'rb').read() + f'\r\n--{bnd}--\r\n'.encode())
    try:
        msg = dapi('POST', f'/channels/{ch}/messages', raw=body, ctype=f'multipart/form-data; boundary={bnd}')
    except Exception as e:
        log('[warn] image post failed, sending embed only:', type(e).__name__)
        emb.pop('image', None); msg = dapi('POST', f'/channels/{ch}/messages', {'embeds': [emb]})
else:
    msg = dapi('POST', f'/channels/{ch}/messages', {'embeds': [emb]})
log('posted', TIER['key'], score, msg.get('id') if msg else '')
if '--replace' in sys.argv and msg:
    me = dapi('GET', '/users/@me')['id']
    for m in dapi('GET', f'/channels/{ch}/messages?limit=50') or []:
        if m['author']['id'] == me and m['id'] != msg['id']:
            try: dapi('DELETE', f"/channels/{ch}/messages/{m['id']}"); log('deleted old', m['id']); time.sleep(0.6)
            except Exception as e: log('[warn] delete failed', type(e).__name__)
