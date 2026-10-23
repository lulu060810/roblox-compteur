"""Motion-design recut of the Mine to Get Rich trailer, synced to music.py (128 BPM)."""
import sys, subprocess, math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

SRC = sys.argv[1]
LOGO = sys.argv[2]
OUT = sys.argv[3]
PREVIEW = len(sys.argv) > 4 and sys.argv[4]  # e.g. "20-30" seconds range for test renders

W, H, FPS = 1920, 1080, 60
B = 60 / 128
DUR = 43.0
NF = int(DUR * FPS)
rng = np.random.default_rng(3)
FONT_B = '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'
FONT_S = '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, t): return a + (b - a) * t
def ease_out_cubic(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_cubic(t): t = clamp(t); return t ** 3
def ease_out_expo(t): t = clamp(t); return 1 if t >= 1 else 1 - 2 ** (-10 * t)
def ease_in_expo(t): t = clamp(t); return 0 if t <= 0 else 2 ** (10 * t - 10)
def ease_out_back(t, k=1.9): t = clamp(t) - 1; return 1 + (k + 1) * t ** 3 + k * t ** 2
def ease_io(t): t = clamp(t); return t * t * (3 - 2 * t)

# ---------------- grading ----------------
x = np.arange(256) / 255.0
curve = x + 0.10 * np.sin(2 * np.pi * (x - 0.5)) * 0.5 * -1  # gentle S-curve
curve = np.clip((curve - 0.5) * 1.08 + 0.5 + 0.005, 0, 1)
LUT = (curve * 255).astype(np.uint8)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
VIG = (1 - 0.32 * np.clip(r - 0.45, 0, 1) ** 1.6)[..., None].astype(np.float32)

def grade(f):
    f = cv2.LUT(f, LUT)
    g = cv2.cvtColor(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    f = cv2.addWeighted(f, 1.2, g, -0.2, 0)
    bl = cv2.GaussianBlur(f, (0, 0), 1.1)
    return cv2.addWeighted(f, 1.45, bl, -0.45, 0)

# ---------------- source reader ----------------
class Reader:
    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        self.pos = -1
        self.cache = {}

    def frame(self, i):
        i = max(0, min(i, 1346))
        if i in self.cache:
            return self.cache[i]
        if i <= self.pos or i > self.pos + 40:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            self.pos = i - 1
        f = None
        while self.pos < i:
            ok, f = self.cap.read()
            if not ok:
                break
            self.pos += 1
        if f is None:
            return self.frame(i - 1)
        if len(self.cache) > 8:
            self.cache.pop(min(self.cache))
        self.cache[i] = grade(f)
        return self.cache[i]

    def at(self, t):
        fi = t * 30
        i0 = int(math.floor(fi)); a = fi - i0
        if a < 0.2: return self.frame(i0)
        if a > 0.8: return self.frame(i0 + 1)
        return cv2.addWeighted(self.frame(i0), 1 - a, self.frame(i0 + 1), a, 0)

src = Reader(SRC)

# ---------------- camera ----------------
def camera(img, s=1.0, cx=W / 2, cy=H / 2, rot=0.0, dx=0.0, dy=0.0):
    h, w = img.shape[:2]
    s_eff = s * W / w
    half_w, half_h = W / (2 * s_eff), H / (2 * s_eff)
    cx = min(max(cx * w / W, half_w), w - half_w) if s_eff >= W / w else cx * w / W
    cy = min(max(cy * h / H, half_h), h - half_h) if s_eff >= H / h else cy * h / H
    M = cv2.getRotationMatrix2D((cx, cy), rot, s_eff)
    M[0, 2] += W / 2 - cx + dx
    M[1, 2] += H / 2 - cy + dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)

def zoom_blur(img, amount, n=7, cx=W / 2, cy=H / 2):
    if amount < 0.004:
        return img
    acc = np.zeros(img.shape, np.float32)
    for k in range(n):
        s = 1 + amount * k / (n - 1)
        M = cv2.getRotationMatrix2D((cx, cy), 0, s)
        acc += cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return (acc / n).astype(np.uint8)

def chroma(img, d):
    d = int(round(d))
    if d == 0:
        return img
    out = img.copy()
    out[..., 2] = np.roll(img[..., 2], d, 1)
    out[..., 0] = np.roll(img[..., 0], -d, 1)
    return out

def flash(img, a, color=(255, 255, 255)):
    if a <= 0.005:
        return img
    c = np.full_like(img, 0); c[:] = color
    return cv2.addWeighted(img, 1 - a, c, a, 0)

def screen(base, layer, a=1.0):
    b = base.astype(np.float32) / 255; l = layer.astype(np.float32) / 255 * a
    return ((1 - (1 - b) * (1 - l)) * 255).clip(0, 255).astype(np.uint8)

# ---------------- assets ----------------
logo_full = cv2.imread(LOGO)
logo = logo_full[190:1035, 160:1070]

def logo_scaled(height):
    k = height / logo.shape[0]
    return cv2.resize(logo, (int(logo.shape[1] * k), height), interpolation=cv2.INTER_LANCZOS4)

LOGO_BIG = logo_scaled(720)
LOGO_OUT = logo_scaled(560)

def paste_screen(canvas, layer, cx, cy, s=1.0, a=1.0, rot=0.0):
    M = cv2.getRotationMatrix2D((layer.shape[1] / 2, layer.shape[0] / 2), rot, s)
    M[0, 2] += cx - layer.shape[1] / 2
    M[1, 2] += cy - layer.shape[0] / 2
    lay = cv2.warpAffine(layer, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=(0, 0, 0))
    return screen(canvas, lay, a), lay

def text_img(txt, size, font=FONT_B, color=(255, 255, 255), spacing=0):
    f = ImageFont.truetype(font, size)
    widths = [f.getbbox(c)[2] - f.getbbox(c)[0] if c != ' ' else size * 0.3 for c in txt]
    asc, desc = f.getmetrics()
    letters = []
    for c in txt:
        im = Image.new('L', (int(size * 1.4), asc + desc + 10), 0)
        ImageDraw.Draw(im).text((4, 4), c, font=f, fill=255)
        a = np.array(im)
        letters.append((c, a, f.getlength(c)))
    return letters

def draw_letters(canvas, letters, cx, cy, t, spacing0, spacing1, color, stagger=0.045, dur=0.35):
    """Animated tracking-in letters; t in seconds since start."""
    sp = lerp(spacing0, spacing1, ease_out_expo(t / 1.2))
    total = sum(adv for _, _, adv in letters) + sp * (len(letters) - 1)
    x = cx - total / 2
    out = canvas.astype(np.float32)
    for i, (c, a, adv) in enumerate(letters):
        lt = (t - i * stagger) / dur
        al = ease_out_cubic(lt)
        if al > 0 and c != ' ':
            oy = int((1 - al) * 26)
            h, w = a.shape
            x0, y0 = int(x) - 4, int(cy - h / 2 + oy)
            x1, y1 = min(W, x0 + w), min(H, y0 + h)
            m = (a[:y1 - y0, :x1 - x0].astype(np.float32) / 255 * al)[..., None]
            out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - m) + np.array(color, np.float32) * m
        x += adv + sp
    return out.clip(0, 255).astype(np.uint8)

PRESENTE = text_img('PRÉSENTE', 54, FONT_S)
TAG_OUT = text_img('MINE TO GET RICH  •  BÊTA SUR ROBLOX', 34, FONT_S)

# smoke texture
def make_smoke(seed):
    g = np.random.default_rng(seed)
    acc = np.zeros((540, 960), np.float32)
    for s, wgt in ((6, .2), (18, .35), (45, .45)):
        acc += cv2.GaussianBlur(g.standard_normal((540, 960)).astype(np.float32), (0, 0), s) * wgt * s ** 0.5
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    return np.clip((acc - 0.35) * 2.2, 0, 1)

SMOKE = [make_smoke(1), make_smoke(2)]
grad_x = np.linspace(0, 1, W, dtype=np.float32)[None, :, None]
ORANGE = np.array([0, 120, 255], np.float32)
GREEN = np.array([30, 255, 120], np.float32)
TINT = (ORANGE * (1 - grad_x) + GREEN * grad_x)

def smoke_bg(t, inten=0.22):
    layers = []
    for k, sm in enumerate(SMOKE):
        M = np.float32([[1.15, 0, -40 - t * (14 if k else -10)], [0, 1.15, -30 + t * (8 if k else 5)]])
        layers.append(cv2.warpAffine(sm, M, (960, 540), borderMode=cv2.BORDER_REFLECT))
    s = cv2.resize(layers[0] * 0.6 + layers[1] * 0.5, (W, H))[..., None]
    glow = np.exp(-(((xx - W / 2) / 900) ** 2 + ((yy - H * 0.62) / 420) ** 2))[..., None]
    return (TINT * s * inten * 0.6 + TINT * glow * 0.07).clip(0, 255).astype(np.uint8)

class Particles:
    def __init__(self, n, colors, speed=(30, 110), size=(1.2, 3.5)):
        self.n = n
        self.p = np.c_[rng.uniform(0, W, n), rng.uniform(0, H, n)]
        self.v = np.c_[rng.uniform(-15, 15, n), -rng.uniform(*speed, n)]
        self.sz = rng.uniform(*size, n)
        self.col = [colors[i % len(colors)] for i in range(n)]
        self.ph = rng.uniform(0, 6.28, n)

    def render(self, t, a=1.0):
        c = np.zeros((H // 2, W // 2, 3), np.uint8)
        pos = self.p + self.v * t
        pos[:, 0] += 20 * np.sin(t * 1.3 + self.ph)
        pos[:, 0] %= W; pos[:, 1] %= H
        for i in range(self.n):
            fl = 0.55 + 0.45 * math.sin(t * 6 + self.ph[i] * 3)
            col = tuple(int(v * fl * a) for v in self.col[i])
            cv2.circle(c, (int(pos[i, 0] / 2), int(pos[i, 1] / 2)), max(1, int(self.sz[i])), col, -1, cv2.LINE_AA)
        g = cv2.GaussianBlur(c, (0, 0), 3)
        c = cv2.add(c, cv2.add(g, g))
        return cv2.resize(c, (W, H), interpolation=cv2.INTER_LINEAR)

EMBERS = Particles(110, [(40, 150, 255), (60, 230, 120), (30, 200, 255)])
DUST = Particles(70, [(90, 210, 255), (200, 230, 255)], speed=(15, 45), size=(1, 2.6))

# light rays
ry, rx = np.mgrid[-700:700, -700:700].astype(np.float32)
ang = np.arctan2(ry, rx); rad = np.sqrt(rx ** 2 + ry ** 2)
RAYS = ((0.5 + 0.5 * np.cos(ang * 14)) ** 6 * np.exp(-rad / 520)).astype(np.float32)

def rays_layer(t, color, a):
    M = cv2.getRotationMatrix2D((700, 700), t * 25, 1.6)
    M[0, 2] += W / 2 - 700; M[1, 2] += H / 2 - 700
    rr = cv2.warpAffine(RAYS, M, (W, H))[..., None]
    return (rr * np.array(color, np.float32) * a).clip(0, 255).astype(np.uint8)

# pickaxe cards
forge = src.frame(int(9.6 * 30)).copy()
CARD_X = [(898, 1174), (1186, 1461), (1473, 1748)]
CARD_Y = [(151, 544), (556, 949)]
CARDS = []
for (y0, y1) in CARD_Y:
    for (x0, x1) in CARD_X:
        c = forge[y0:y1, x0:x1]
        k = 820 / c.shape[0]
        c = cv2.resize(c, (int(c.shape[1] * k), 820), interpolation=cv2.INTER_LANCZOS4)
        m = np.zeros(c.shape[:2], np.uint8)
        rr_ = 40
        cv2.rectangle(m, (rr_, 0), (c.shape[1] - rr_, c.shape[0]), 255, -1)
        cv2.rectangle(m, (0, rr_), (c.shape[1], c.shape[0] - rr_), 255, -1)
        for (px, py) in ((rr_, rr_), (c.shape[1] - rr_, rr_), (rr_, c.shape[0] - rr_), (c.shape[1] - rr_, c.shape[0] - rr_)):
            cv2.circle(m, (px, py), rr_, 255, -1, cv2.LINE_AA)
        CARDS.append((c, m))
CARD_COL = [(40, 190, 255), (255, 210, 60), (110, 230, 60), (90, 60, 255), (255, 110, 70), (255, 70, 200)]  # BGR glow
FORGE_BG = (cv2.GaussianBlur(forge, (0, 0), 28) * 0.35).astype(np.uint8)
NUMS = [text_img(f'0{i + 1} / 06', 40, FONT_B) for i in range(6)]

# ---------------- timeline (beats) ----------------
# clip: (b0, b1, src_start, speed, zoom0, zoom1, cx, cy)
CLIPS = [
    (8, 12, 0.40, 1.0, 1.00, 1.05, 960, 540),       # prêt à faire fortune
    (12, 16, 2.95, 1.15, 1.04, 1.00, 960, 540),     # gameplay - chaque bloc compte
    (16, 20, 5.10, 0.65, 1.55, 1.62, 1100, 390),     # gameplay close-up slow-mo
    (20, 22, 8.75, 1.0, 1.00, 1.03, 960, 540),      # forge overview
    (28, 32, 11.45, 0.85, 1.00, 1.05, 960, 540),    # boots
    (32, 36, 13.45, 1.0, 1.05, 1.00, 960, 540),     # prestige
    (36, 40, 16.20, 1.0, 1.00, 1.05, 960, 540),     # midas
    (40, 44, 19.00, 0.75, 1.00, 1.10, 960, 560),    # obsidienne (breakdown)
    (44, 48, 21.80, 1.0, 1.00, 1.06, 960, 540),     # butin
    (48, 52, 24.60, 1.0, 1.05, 1.00, 960, 540),     # roue
    (52, 56, 27.40, 1.0, 1.00, 1.05, 960, 540),     # collectionne
    (56, 60, 30.30, 1.0, 1.05, 1.00, 960, 540),     # 10 000 blocs
    (60, 64, 34.00, 0.80, 1.00, 1.05, 960, 540),    # défis
    (64, 66, 35.85, 1.0, 1.03, 1.00, 960, 540),     # minerai
    (66, 68, 5.00, 1.5, 1.56, 1.66, 1100, 390),      # gameplay flash
    (68, 72, 37.70, 1.0, 1.00, 1.06, 960, 540),     # la mine t'attend
    (72, 80, 40.30, 0.98, 1.00, 1.07, 960, 540),    # rejoins la bêta
]
CUTS = {8: 'flash', 12: 'zoom', 16: 'punch', 20: 'whip', 22: 'flash', 28: 'zoom', 32: 'whip', 36: 'zoom',
        40: 'flash', 44: 'zoom', 48: 'flash', 52: 'whip', 56: 'zoom', 60: 'whip', 64: 'zoom', 66: 'punch',
        68: 'zoom', 72: 'flash', 80: 'flash'}
HITS = [(4, 22), (8, 26), (16, 14), (40, 18), (48, 26), (72, 26), (80, 20)]
KICKS = [b for b in range(8, 40)] + [b for b in range(48, 72)] + [72, 74.5, 76, 78.5]

def kick_pulse(beat):
    v = 0
    for k in KICKS:
        if 0 <= beat - k < 1:
            v = max(v, math.exp(-(beat - k) * B / 0.11))
    return v

NOISE = rng.standard_normal((NF + 10, 3))
from scipy.ndimage import gaussian_filter1d
NOISE = gaussian_filter1d(NOISE, 1.2, axis=0) * 1.8

def shake(beat, fi):
    amp = 0
    for b, a in HITS:
        dt = (beat - b) * B
        if 0 <= dt < 0.6:
            amp += a * math.exp(-dt / 0.14)
    return NOISE[fi, 0] * amp, NOISE[fi, 1] * amp, NOISE[fi, 2] * amp * 0.04

# ---------------- shot renderers ----------------
def render_intro(t, fi):
    beat = t / B
    f = smoke_bg(t, 0.12 + 0.18 * ease_io(t / 1.9) + (0.12 if beat > 4 else 0))
    f = cv2.add(f, EMBERS.render(t, 0.25 + 0.75 * ease_io(t / 2)))
    hit = beat >= 4
    # reveal wipe before hit, full after
    s = lerp(1.06, 1.0, ease_out_cubic(t / 1.875)) if not hit else 1.0 + 0.03 * ease_io((t - 1.875) / 1.4)
    lg = LOGO_BIG
    if not hit:
        wipe = ease_io((t - 0.25) / 1.55) * 1.4 - 0.2
        h, w = lg.shape[:2]
        gx = (np.arange(w)[None, :] / w + np.arange(h)[:, None] / h * 0.35) / 1.35
        m = np.clip((wipe - gx) / 0.12, 0, 1)
        edge = np.exp(-((gx - wipe) / 0.03) ** 2)
        lay = (lg.astype(np.float32) * (m * 0.42)[..., None] + edge[..., None] * np.array([120, 230, 255]) * (lg.max(2, keepdims=True) > 25)).clip(0, 255).astype(np.uint8)
        a = 1.0
    else:
        lay = lg
        a = 1.0
        flick = 1.0
    sx, sy, sr = shake(beat, fi)
    zt = (t - 7.1 * B) / (0.9 * B)
    zs = 1 + 2.6 * ease_in_expo(zt) if zt > 0 else 1
    f, placed = paste_screen(f, lay, 960 + sx, 470 + sy, s * zs, a, sr)
    # bloom
    glow_a = 0.35 + (1.2 * math.exp(-(t - 1.875) / 0.35) if hit else 0.25 * ease_io(t / 1.8))
    glow = cv2.GaussianBlur(cv2.resize(placed, (W // 4, H // 4)), (0, 0), 9)
    f = cv2.addWeighted(f, 1, cv2.resize(glow, (W, H)), glow_a, 0)
    if beat >= 5:
        f = draw_letters(f, PRESENTE, 960 + sx, 935 + sy, t - 5 * B, 70, 22, (235, 240, 245))
    if zt > 0:
        f = zoom_blur(f, 0.25 * ease_in_cubic(zt), cy=470)
    if hit:
        dt = t - 1.875
        f = chroma(f, 14 * math.exp(-dt / 0.12))
        f = flash(f, 0.85 * math.exp(-dt / 0.09))
    if zt > 0.55:
        f = flash(f, ease_in_cubic((zt - 0.55) / 0.45) * 0.95)
    return f

def render_clip(c, beat, fi):
    b0, b1, s0, sp, z0, z1, cx, cy = c
    lt = (beat - b0) * B
    span = (b1 - b0) * B
    st = s0 + lt * sp
    if b0 == 44:  # butin build: accelerating micro-zooms on the roll
        sub = 0.5 if beat < 46 else 0.25
        ph = ((beat - 44) % sub) / sub
        extra = 0.025 * (1 + (beat - 44) / 4) * math.exp(-ph * 4)
    else:
        extra = 0
    img = src.at(st)
    z = lerp(z0, z1, ease_io(lt / span)) + 0.018 * kick_pulse(beat) + extra
    sx, sy, sr = shake(beat, fi)
    z += 0.03 if abs(sx) > 1 else 0
    f = camera(img, z, cx, cy, sr, sx, sy)
    if b0 == 44:
        f = flash(f, 0.25 * clamp((beat - 46.5) / 1.5) ** 2)
    if b0 == 40:
        f = cv2.add(f, DUST.render(beat * B, 0.6))
    return f

def render_cards(beat, fi):
    i = min(5, int(beat - 22))
    lt = (beat - 22 - i) * B
    card, mask = CARDS[i]
    col = CARD_COL[i]
    f = FORGE_BG.copy()
    f = cv2.add(f, rays_layer(beat * B, col, 0.55))
    f = cv2.add(f, DUST.render(beat * B, 0.8))
    sgn = -1 if i % 2 else 1
    p = ease_out_back(lt / 0.24, 1.6)
    s = lerp(0.55, 1.0, p) + 0.04 * lt
    rot = sgn * lerp(10, 2, ease_out_cubic(lt / 0.3)) - sgn * 1.5 * lt
    cx = 960 + sgn * lerp(260, 0, ease_out_expo(lt / 0.28))
    # glow behind card
    ch, cw = card.shape[:2]
    gl = np.zeros_like(card); gl[:] = col
    gl = (gl * (mask[..., None] / 255.0)).astype(np.uint8)
    M = cv2.getRotationMatrix2D((cw / 2, ch / 2), rot, s)
    M[0, 2] += cx - cw / 2; M[1, 2] += 540 - ch / 2
    glow = cv2.warpAffine(gl, M, (W, H))
    glow = cv2.resize(cv2.GaussianBlur(cv2.resize(glow, (W // 4, H // 4)), (0, 0), 14), (W, H))
    f = cv2.addWeighted(f, 1, glow, 1.6, 0)
    cw_img = cv2.warpAffine(card, M, (W, H), flags=cv2.INTER_CUBIC)
    mw = cv2.warpAffine(mask, M, (W, H), flags=cv2.INTER_LINEAR)[..., None].astype(np.float32) / 255
    f = (f * (1 - mw) + cw_img * mw).astype(np.uint8)
    f = draw_letters(f, NUMS[i], 1700, 990, 10, 4, 4, (255, 255, 255))
    f = chroma(f, 10 * math.exp(-lt / 0.06))
    f = flash(f, 0.4 * math.exp(-lt / 0.05), col)
    sx, sy, _ = shake(beat, fi)
    return f

def render_outro(t, fi):
    beat = t / B
    lt = t - 80 * B
    f = smoke_bg(t, 0.22)
    f = cv2.add(f, EMBERS.render(t, 0.9))
    sx, sy, sr = shake(beat, fi)
    s = lerp(1.12, 1.0, ease_out_expo(lt / 0.8)) + 0.012 * lt
    f, placed = paste_screen(f, LOGO_OUT, 960 + sx, 450 + sy, s, 1.0, sr)
    glow = cv2.GaussianBlur(cv2.resize(placed, (W // 4, H // 4)), (0, 0), 9)
    f = cv2.addWeighted(f, 1, cv2.resize(glow, (W, H)), 0.35 + 0.9 * math.exp(-lt / 0.4), 0)
    if lt > 0.6:
        f = draw_letters(f, TAG_OUT, 960, 880, lt - 0.6, 30, 8, (225, 230, 235), stagger=0.02)
    f = chroma(f, 12 * math.exp(-lt / 0.12))
    f = flash(f, 0.8 * math.exp(-lt / 0.1))
    fade = clamp((t - (DUR - 1.3)) / 1.2)
    if fade > 0:
        f = (f * (1 - ease_io(fade))).astype(np.uint8)
    return f

def base_frame(t, fi):
    beat = t / B
    if beat < 8:
        return render_intro(t, fi)
    if beat >= 80:
        return render_outro(t, fi)
    if 22 <= beat < 28:
        return render_cards(beat, fi)
    for c in CLIPS:
        if c[0] <= beat < c[1]:
            return render_clip(c, beat, fi)
    return np.zeros((H, W, 3), np.uint8)

def transitions(f, t):
    beat = t / B
    for cb, kind in CUTS.items():
        dt = t - cb * B  # seconds since cut (negative = before)
        if -0.09 < dt < 0 and cb not in (8, 80):  # outgoing
            k = 1 - (-dt / 0.09)
            if kind in ('zoom', 'punch'):
                f = zoom_blur(camera(f, 1 + 0.12 * ease_in_cubic(k)), 0.18 * k)
            elif kind == 'whip':
                sh = int(-420 * ease_in_cubic(k))
                f = cv2.blur(np.roll(f, sh, 1), (int(1 + 140 * k), 1))
            elif kind == 'flash':
                f = flash(f, 0.6 * ease_in_cubic(k))
        if 0 <= dt < 0.16:
            k = 1 - dt / 0.16
            if kind == 'zoom':
                f = zoom_blur(camera(f, 1 + 0.10 * ease_out_cubic(k) ** 2), 0.16 * k ** 2)
                f = chroma(f, 9 * k)
            elif kind == 'punch':
                f = camera(f, 1 + 0.15 * k ** 3)
                f = flash(f, 0.55 * k ** 3)
                f = chroma(f, 12 * k)
            elif kind == 'whip':
                sh = int(420 * k ** 2)
                f = cv2.blur(np.roll(f, sh, 1), (int(1 + 140 * k ** 2), 1))
            elif kind == 'flash' and cb not in (8, 80):
                f = flash(f, 0.85 * k ** 2.5)
                f = chroma(f, 10 * k)
    return f

def finish(f):
    out = f.astype(np.float32) * VIG
    return out.clip(0, 255).astype(np.uint8)

# ---------------- main ----------------
f0, f1 = 0, NF
if PREVIEW:
    a, b = PREVIEW.split('-'); f0, f1 = int(float(a) * FPS), int(float(b) * FPS)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS),
                        '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-pix_fmt', 'yuv420p',
                        '-tune', 'film', '-x264-params', 'keyint=60', OUT], stdin=subprocess.PIPE)
for fi in range(f0, f1):
    t = fi / FPS
    f = base_frame(t, fi)
    f = transitions(f, t)
    f = finish(f)
    enc.stdin.write(f.tobytes())
    if fi % 120 == 0:
        print('frame', fi, '/', f1, flush=True)
enc.stdin.close(); enc.wait()
print('done')
