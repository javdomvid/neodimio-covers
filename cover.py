#!/usr/bin/env python3
"""YOU CAN'T MISS <MONTH> - portada mensual de la playlist de @javdomvid.

Parte de la foto base (caja de miniCD + fondo, base.jpg). Cada mes SOLO cambia el
arte impreso en el disco; la caja, el fondo, la tipografia y la composicion se quedan.
El color/contorno del texto se adapta al arte para que siempre sea legible (WCAG).

  python3 cover.py --candidates 3 --out out          # mes actual (Madrid), 3 propuestas
  python3 cover.py --month DECEMBER --year 2026 --candidates 3
"""
import argparse, io, json, math, os, random, urllib.request
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.environ.get("COVER_FONTS", os.path.join(HERE, "fonts"))
GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
S = 1280
CX, CY, R = 628.3, 641.5, 513.2          # disco en base.jpg (1280x1280)
R_IN, R_OUT = 0.392, 0.986               # zona imprimible del disco (fraccion de R)
FONTS = {"oswald": ("Oswald[wght].ttf", "oswald/Oswald%5Bwght%5D.ttf", [500]),
         "roboto": ("RobotoCondensed[wght].ttf", "robotocondensed/RobotoCondensed%5Bwght%5D.ttf", [400])}

# ------------------------------------------------------------------ utilidades
def rgb(h):
    h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255

def lin(c):
    c = np.asarray(c, np.float32); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def lum(c):
    c = lin(c); return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]

def contrast(l1, l2):
    return (np.maximum(l1, l2) + 0.05) / (np.minimum(l1, l2) + 0.05)

_fc = {}
def font(key, px):
    fn, path, axes = FONTS[key]; fp = os.path.join(FONT_DIR, fn)
    if not os.path.exists(fp):
        os.makedirs(FONT_DIR, exist_ok=True); urllib.request.urlretrieve(GF + path, fp)
    f = ImageFont.truetype(fp, max(int(px), 4))
    try: f.set_variation_by_axes(axes)
    except Exception: pass
    return f

def cap_ratio(key):
    if key not in _fc:
        b = font(key, 1000).getbbox("H", anchor="ls"); _fc[key] = (b[3] - b[1]) / 1000
    return _fc[key]

def blur(m, s): return cv2.GaussianBlur(m, (0, 0), s) if s > 0 else m

def over(base, color, a):
    a = np.clip(a, 0, 1)[..., None]; return base * (1 - a) + np.asarray(color, np.float32) * a

def fbm(seed, octaves=5, base=3, persist=0.55, size=S):
    rng = np.random.default_rng(seed); acc = np.zeros((size, size), np.float32); amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o; g = rng.random((n + 1, n + 1)).astype(np.float32)
        acc += amp * cv2.resize(g, (size, size), interpolation=cv2.INTER_CUBIC); tot += amp; amp *= persist
    a = acc / tot; return (a - a.mean()) / (a.std() + 1e-6)

def ramp(t, cols):
    """Gradiente continuo a traves de una lista de colores, t en 0..1."""
    cols = np.stack([rgb(c) for c in cols]); t = np.clip(t, 0, 1) * (len(cols) - 1)
    i = np.clip(np.floor(t).astype(int), 0, len(cols) - 2); f = (t - i)[..., None]
    return cols[i] * (1 - f) + cols[i + 1] * f

def step(x, w=0.5):  # escalon suave (antialias)
    return np.clip(x / w + 0.5, 0, 1)

YY, XX = np.mgrid[0:S, 0:S].astype(np.float32)
U, V = (XX - CX) / R, (YY - CY) / R
RR, TH = np.sqrt(U * U + V * V), np.arctan2(V, U)
PX = 1.0 / R                                   # un pixel en unidades de R

# ------------------------------------------------------------------ base y luz
def load_base():
    b = np.asarray(Image.open(os.path.join(HERE, "base.jpg")).convert("RGB"), np.float32) / 255
    assert b.shape[:2] == (S, S), "base.jpg debe ser 1280x1280"
    return b

def shading(base):
    """Luz del disco original sin el texto antiguo (convolucion normalizada)."""
    g = base.mean(2)
    loc = cv2.dilate(g, np.ones((37, 37), np.uint8))
    ann = (RR > R_IN - 0.01) & (RR < R_OUT + 0.01)
    text = cv2.dilate(((g < 0.62 * loc) & ann).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    w = (ann & ~text).astype(np.float32)
    sh = blur(g * w, 9) / (blur(w, 9) + 1e-4)
    return np.clip(sh, 0, 1)

# ------------------------------------------------------------------ arte del disco
PALETTES = {
    "JANUARY":   [["#0d1b2a", "#1b4965", "#62b6cb", "#e8f1f2"], ["#22223b", "#4a4e69", "#9a8c98", "#f2e9e4"]],
    "FEBRUARY":  [["#3d0c11", "#b5179e", "#f72585", "#ffd6e8"], ["#590d22", "#c9184a", "#ff8fa3", "#fff0f3"]],
    "MARCH":     [["#1b3a2a", "#3a7d44", "#9dc183", "#f1f7ed"], ["#264653", "#2a9d8f", "#e9c46a", "#f4f1de"]],
    "APRIL":     [["#2d1e4f", "#7b5ea7", "#c8a2c8", "#fdf0ff"], ["#1d3557", "#a8dadc", "#f1a7c5", "#fff7f3"]],
    "MAY":       [["#3c1518", "#d1495b", "#edae49", "#fff1d0"], ["#264027", "#e07a5f", "#f2cc8f", "#f4f1de"]],
    "JUNE":      [["#2b2d42", "#ef8354", "#ffd166", "#fffcf2"], ["#003049", "#f77f00", "#fcbf49", "#eae2b7"]],
    "JULY":      [["#03045e", "#0077b6", "#00b4d8", "#caf0f8"], ["#073b4c", "#118ab2", "#06d6a0", "#ffd166"]],
    "AUGUST":    [["#3d0e3b", "#d1345b", "#ff9f1c", "#ffe8d6"], ["#540d6e", "#ee4266", "#ffd23f", "#f9f7f3"]],
    "SEPTEMBER": [["#283618", "#606c38", "#dda15e", "#fefae0"], ["#3e2723", "#8d6e63", "#d4a373", "#faedcd"]],
    "OCTOBER":   [["#1a0805", "#6e1a0d", "#e85d04", "#ffba08"], ["#2b2118", "#6f1d1b", "#bb9457", "#ffe6a7"]],
    "NOVEMBER":  [["#3b1f0e", "#a3471b", "#e8a33d", "#f4e3c1"], ["#1f2a1d", "#6b4226", "#c97b3a", "#efd9a7"],
                  ["#2b0f14", "#8c2f39", "#e07a5f", "#f2cc8f"]],
    "DECEMBER":  [["#0b2a1f", "#1d6b4a", "#c9a227", "#f3ead3"], ["#3a0d12", "#a4161a", "#e5c07b", "#fbf3e4"],
                  ["#0d1b2a", "#415a77", "#e0e1dd", "#c9a227"]],
}

def art_aura(p, rng):
    col = np.broadcast_to(rgb(p[rng.choice([0, 3])]), (S, S, 3)).copy()
    for _ in range(rng.randint(4, 6)):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0.2, 0.8)
        cx, cy, rad = d * math.cos(a), d * math.sin(a), rng.uniform(0.35, 0.75)
        m = np.exp(-(((U - cx) ** 2 + (V - cy) ** 2) / rad ** 2) * 2.2)
        col = over(col, rgb(p[rng.randint(1, 3)]), m * 0.9)
    return col

def art_marble(p, rng):
    s = rng.randint(0, 10 ** 6)
    n1 = fbm(s, 5, 2); n2 = fbm(s + 1, 5, 2)
    x = U * 1.4 + 0.55 * n1; y = V * 1.4 + 0.55 * n2
    t = np.sin(x * rng.uniform(2.5, 4) + y * rng.uniform(1, 2) + 1.2 * fbm(s + 2, 5, 3)) * 0.5 + 0.5
    return ramp(t, [p[0], p[1], p[2], p[3], p[2]])

def art_sunburst(p, rng):
    n = rng.choice([12, 16, 20, 24]); twist = rng.choice([0, 0, 1.2, -1.2])
    a = (TH + twist * RR) * n / (2 * math.pi)
    rays = step(np.sin(a * 2 * math.pi) / (2 * math.pi * n * PX * np.maximum(RR, 0.3) / 1.0) * 1.0, 1.0)
    col = over(np.broadcast_to(rgb(p[1]), (S, S, 3)).copy(), rgb(p[2]), rays)
    return over(col, rgb(p[3]), np.clip(1 - (RR - 0.3) / 0.5, 0, 1) ** 2 * 0.55)

def art_rings(p, rng):
    edges = np.cumsum([rng.uniform(0.04, 0.14) for _ in range(14)]) + R_IN
    col = np.broadcast_to(rgb(p[0]), (S, S, 3)).copy(); order = [1, 2, 3, 2, 0, 3, 1, 2]
    k = rng.randint(0, 7)
    for i, e in enumerate(edges):
        col = over(col, rgb(p[order[(i + k) % 8]]), step((RR - e) / PX, 1.2))
    return col

def art_halftone(p, rng):
    ang = rng.uniform(0, math.pi); per = rng.uniform(0.045, 0.07)
    ru, rv = U * math.cos(ang) - V * math.sin(ang), U * math.sin(ang) + V * math.cos(ang)
    g = np.clip((ru + 1) / 2, 0, 1) if rng.random() < 0.5 else np.clip(1 - RR, 0, 1) * 1.2
    fu, fv = (ru / per) % 1 - 0.5, (rv / per) % 1 - 0.5
    d = np.sqrt(fu ** 2 + fv ** 2) * per
    rad = per * 0.62 * np.clip(g, 0.05, 1)
    dots = step((rad - d) / PX, 1.2)
    bg, fg = (p[3], p[1]) if rng.random() < 0.5 else (p[0], p[2])
    return over(np.broadcast_to(rgb(bg), (S, S, 3)).copy(), rgb(fg), dots)

def art_checker(p, rng):
    n = rng.choice([12, 16, 20]); m = rng.uniform(10, 16); tw = rng.uniform(-2.5, 2.5)
    a = (TH / (2 * math.pi) * n + tw * np.log(np.maximum(RR, 0.05)) * 2)
    b = RR * m
    c = np.sin(a * math.pi * 2) * np.sin(b * math.pi)
    k = step(c / (np.abs(np.gradient(c)[0]) + np.abs(np.gradient(c)[1]) + 1e-4), 1.0)
    return over(np.broadcast_to(rgb(p[0]), (S, S, 3)).copy(), rgb(p[3]), k)

def art_gradient(p, rng):
    t = ((TH - rng.uniform(-3, 3)) / (2 * math.pi)) % 1
    t = 0.5 - 0.5 * np.cos(t * 2 * math.pi)
    return ramp(t * 0.85 + 0.15 * RR, [p[0], p[1], p[2], p[3]])

def art_waves(p, rng):
    f = rng.uniform(7, 12); ang = rng.uniform(0, math.pi)
    x, y = U * math.cos(ang) - V * math.sin(ang), U * math.sin(ang) + V * math.cos(ang)
    w = np.sin(y * f + rng.uniform(0.6, 1.4) * np.sin(x * rng.uniform(2, 4)))
    band = np.floor((w + 1) * 2).astype(int) % 4
    cols = np.stack([rgb(c) for c in p]); out = cols[band]
    return blur(out, 0.8)

def art_tiedye(p, rng):
    s = rng.randint(0, 10 ** 6); k = rng.choice([3, 4, 5])
    t = (TH / (2 * math.pi) * k + RR * rng.uniform(2.5, 4) + 0.25 * fbm(s, 5, 3)) % 1
    return ramp(np.abs(t * 2 - 1), [p[0], p[1], p[2], p[3]])

ARTS = {"aura": art_aura, "marble": art_marble, "sunburst": art_sunburst, "rings": art_rings,
        "halftone": art_halftone, "checker": art_checker, "gradient": art_gradient,
        "waves": art_waves, "tiedye": art_tiedye}

# ------------------------------------------------------------------ texto
def glyph(text, key, cap, ox, oy, rot=0.0):
    f = font(key, cap / cap_ratio(key)); n = int(cap * 3)
    g = Image.new("L", (2 * n, 2 * n), 0)
    ImageDraw.Draw(g).text((n, n), text, font=f, fill=255, anchor="ms")
    if rot: g = g.rotate(rot, resample=Image.BICUBIC, center=(n, n))
    m = np.zeros((S, S), np.float32); a = np.asarray(g, np.float32) / 255
    x0, y0 = int(round(ox)) - n, int(round(oy)) - n
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + 2 * n, S), min(y0 + 2 * n, S)
    m[ya:yb, xa:xb] = a[ya - y0:yb - y0, xa - x0:xb - x0]
    return m

def arc_mask(text, cap, r_base, span_deg, center_deg=-89.0, key="oswald"):
    f = font(key, cap / cap_ratio(key)); ws = [f.getlength(c) for c in text]
    r_ref = r_base + cap * 0.5; span = math.radians(span_deg) * r_ref
    track = (span - sum(ws)) / (len(text) - 1); m = np.zeros((S, S), np.float32); s = 0.0
    for ch, w in zip(text, ws):
        mid = s + w / 2; s += w + track
        if ch == " ": continue
        a = math.radians(center_deg) + (mid - span / 2) / r_ref
        m = np.maximum(m, glyph(ch, key, cap, CX + r_base * math.cos(a), CY + r_base * math.sin(a),
                                rot=-(math.degrees(a) + 90)))
    return m

def line_mask(text, key, cap, y_base, max_w=None, track=0.0, dx=0.0):
    f = font(key, cap / cap_ratio(key))
    nat = sum(f.getlength(c) for c in text) + track * cap * (len(text) - 1)
    if max_w and nat > max_w:  # meses largos (SEPTEMBER): reduce para no salirse del disco
        y_top = y_base - cap; cap *= max_w / nat; f = font(key, cap / cap_ratio(key))
        y_base = y_top + cap + (y_base - y_top - cap) / 2
    ws = [f.getlength(c) for c in text]; tot = sum(ws) + track * cap * (len(text) - 1)
    x = CX + dx - tot / 2; m = np.zeros((S, S), np.float32)
    for ch, w in zip(text, ws):
        m = np.maximum(m, glyph(ch, key, cap, x + w / 2, y_base)); x += w + track * cap
    return m, cap

def dilate(m, px):
    if px <= 0: return m
    k = int(math.ceil(px)) * 2 + 1
    return blur(cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))), 0.7)

def choose_ink(under_lum, palette, prefer_color, rnd):
    """Elige relleno/contorno con el peor caso (percentil 5) de contraste >= 4.5."""
    p5, p95 = np.percentile(under_lum, 5), np.percentile(under_lum, 95)
    worst = lambda c: float(min(contrast(lum(rgb(c)), p5), contrast(lum(rgb(c)), p95)))
    opts = ["#111111", "#f7f3ee"] + list(palette)
    scored = sorted(((worst(c), c) for c in opts), reverse=True)
    colored = [(s, c) for s, c in scored if c in palette and s >= 4.5]
    if prefer_color and colored: return {"fill": colored[0][1], "stroke": None, "score": colored[0][0]}
    if scored[0][0] >= 4.5:
        bw = [(s, c) for s, c in scored if c in ("#111111", "#f7f3ee") and s >= 4.5]
        pick = bw[0] if bw else scored[0]
        return {"fill": pick[1], "stroke": None, "score": pick[0]}
    # arte muy cargado: relleno + contorno opuesto (legible por construccion)
    med = float(np.median(under_lum))
    fill = "#111111" if contrast(lum(rgb("#111111")), med) >= contrast(lum(rgb("#f7f3ee")), med) else "#f7f3ee"
    stroke = "#f7f3ee" if fill == "#111111" else "#111111"
    if prefer_color and colored == [] and rnd.random() < 0.5:
        best = max(palette, key=lambda c: contrast(lum(rgb(c)), lum(rgb(stroke))))
        if contrast(lum(rgb(best)), lum(rgb(stroke))) >= 4.5: fill = best
    mode = "halo" if rnd.random() < 0.5 else "stroke"
    return {"fill": fill, "stroke": stroke, "mode": mode,
            "score": float(contrast(lum(rgb(fill)), lum(rgb(stroke))))}

def paint(img, m, ink, cap, sh):
    if ink["stroke"]:
        if ink.get("mode") == "halo":     # halo suave del color opuesto
            ring = np.clip(blur(dilate(m, 0.07 * cap), 0.05 * cap) * 1.35, 0, 0.92)
        else:                             # contorno duro tipo pegatina
            ring = dilate(m, 0.06 * cap)
        img = over(img, rgb(ink["stroke"]) * sh[..., None] ** 0.25, ring)
    return over(img, np.clip(rgb(ink["fill"]) * (0.80 + 0.25 * sh[..., None]), 0, 1), m)

# ------------------------------------------------------------------ composicion
def render(month, style, seed):
    rnd = random.Random(f"{month}-{style}-{seed}")
    pal = rnd.choice(PALETTES.get(month, PALETTES["OCTOBER"]))
    if rnd.random() < 0.5: pal = pal[::-1]
    base = load_base(); sh = shading(base)
    art = ARTS[style](pal, rnd).astype(np.float32)
    art = art * (1 + 0.025 * fbm(seed + 9, 2, 300))[..., None]                         # grano de impresion
    # luz del disco original + brillo especular suave + microsurcos
    s = sh; light = 0.70 + 0.42 * (s - 0.55)
    spec = np.clip((s - 0.70) / 0.22, 0, 1) * 0.30
    rings = np.sin(RR * 2 * math.pi * 260) * 0.012
    disc = np.clip(art * (light + rings)[..., None], 0, 1)
    disc = 1 - (1 - disc) * (1 - spec[..., None])
    a = step((RR - R_IN) / PX, 1.5) * step((R_OUT - RR) / PX, 1.5)
    img = over(base, disc, a)
    edge = np.exp(-((RR - R_IN) / (1.2 * PX)) ** 2) * 0.35                             # canto interior
    img = over(img, (1, 1, 1), edge)
    # texto con la misma composicion que el original
    under = lum(img)
    cap = 0.262 * R
    m_arc = arc_mask("YOU CAN’T MISS", cap, 0.594 * R + 0.0 * R, 173.0)
    m_mon, mcap = line_mask(month, "oswald", 0.258 * R, CY + 0.710 * R, max_w=1.27 * R, track=0.025)
    m_sig, scap = line_mask("@javdomvid", "roboto", 0.068 * R, CY + 0.862 * R)
    prefer = rnd.random() < 0.55
    report, inks = {}, {}
    for name, m, c in (("arc", m_arc, cap), ("month", m_mon, mcap)):
        zone = dilate(m, 0.12 * c) > 0.3
        inks[name] = choose_ink(under[zone], pal, prefer, rnd)
    if inks["arc"]["fill"] != inks["month"]["fill"] and not (inks["arc"]["stroke"] or inks["month"]["stroke"]):
        both = dilate(np.maximum(m_arc, m_mon), 0.12 * cap) > 0.3                     # mismo color si se puede
        inks["arc"] = inks["month"] = choose_ink(under[both], pal, prefer, rnd)
    if inks["arc"]["stroke"] and inks["month"]["stroke"]:
        inks["month"] = dict(inks["month"], mode=inks["arc"]["mode"])               # mismo tratamiento
    for name, m, c in (("arc", m_arc, cap), ("month", m_mon, mcap)):
        img = paint(img, m, inks[name], c, sh); report[name] = round(inks[name]["score"], 2)
    zone = dilate(m_sig, 6) > 0.3
    sig = choose_ink(under[zone], [], False, rnd)
    img = paint(img, m_sig, sig, scap, sh); report["sig"] = round(sig["score"], 2)
    report["ok"] = report["arc"] >= 4.5 and report["month"] >= 4.5 and report["sig"] >= 4.5
    out = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).resize((640, 640), Image.LANCZOS)
    meta = {"month": month, "art": style, "seed": seed, "palette": pal, "ink": inks, "sig": sig}
    return out, report, meta

# ------------------------------------------------------------------ rotacion mensual
MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
          "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
STYLES = list(ARTS)  # 9 estilos

def rotation(year, month_num, n=3):
    """Candidatos del mes: la base avanza 3 (mod 9) cada mes, asi dos meses seguidos
    nunca comparten estilo."""
    b = ((year * 12 + month_num - 1) * 3) % len(STYLES)
    return [STYLES[(b + j) % len(STYLES)] for j in range(n)]

def save_jpeg(im, path, limit=250_000):
    for q in (92, 88, 84, 80, 75, 70):
        b = io.BytesIO(); im.save(b, "JPEG", quality=q, optimize=True)
        if len(b.getvalue()) * 4 / 3 < limit: break
    open(path, "wb").write(b.getvalue()); return q, len(b.getvalue())

def contact_sheet(files, labels, path, W=420, G=10):
    cols = min(3, len(files)); rows = (len(files) + cols - 1) // cols
    sh = Image.new("RGB", (cols * W + (cols + 1) * G, rows * W + (rows + 1) * G), (240, 240, 240))
    d = ImageDraw.Draw(sh); f = font("oswald", 34)
    for i, (p, t) in enumerate(zip(files, labels)):
        x, y = G + (i % cols) * (W + G), G + (i // cols) * (W + G)
        sh.paste(Image.open(p).resize((W, W), Image.LANCZOS), (x, y))
        d.rounded_rectangle([x + 8, y + 8, x + 24 + d.textlength(t, font=f), y + 56], 8, fill=(255, 255, 255))
        d.text((x + 16, y + 8), t, font=f, fill=(17, 17, 17))
    sh.save(path, quality=88)

if __name__ == "__main__":
    import datetime, zoneinfo
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="auto"); ap.add_argument("--year", type=int, default=0)
    ap.add_argument("--candidates", type=int, default=3)
    ap.add_argument("--styles", default="", help="lista separada por comas, ignora la rotacion")
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--out", default="out")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    now = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Madrid"))
    month = MONTHS[now.month - 1] if a.month == "auto" else a.month.upper()
    year = a.year or now.year
    styles = [s for s in a.styles.split(",") if s] or rotation(year, MONTHS.index(month) + 1, a.candidates)
    files, labels = [], []
    for j, st in enumerate(styles):
        seed = a.seed or (year * 100 + MONTHS.index(month) * 7 + j)
        im, rep, meta = render(month, st, seed)
        p = os.path.join(a.out, f"{month.lower()}_c{j}.jpg"); q, n = save_jpeg(im, p)
        json.dump(meta, open(p[:-4] + ".json", "w"), indent=1)
        files.append(p); labels.append(f"c{j} {st}")
        print(json.dumps({"file": p, "art": st, "bytes": n, "legibility": rep}))
    if len(files) > 1:
        contact_sheet(files, labels, os.path.join(a.out, f"{month.lower()}_sheet.jpg"))
        print(json.dumps({"sheet": os.path.join(a.out, f"{month.lower()}_sheet.jpg")}))
