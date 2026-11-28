#!/usr/bin/env python3
"""
Teaser Noël UNITED GAMES n°2 — annonce des cartes Robux à gagner.
Même univers que render_teaser.py (décor, neige, logo, bonnet, textes), nouvelle intro glace :
une carte cadeau prisonnière d'un bloc de glace turquoise, fendu verticalement, qui s'ouvre en deux
puis s'effondre par blocs.

Usage :
    python3 render_robux.py                    # -> out/united_games_cartes_robux.mp4
    python3 render_robux.py --preview 1.2 5.0  # images PNG de contrôle
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import render_teaser as B
from render_teaser import (A, W, H, FPS, clamp, lerp, smooth, seg, ease_out_cubic, ease_in_out, ease_out_back,
                           noise, fbm, paste_alpha, transform, text_line, text_block,
                           FONT_BLACK, FONT_XBOLD, FONT_SEMI, FONT_MED_IT, RED, WHITE, GOLD_TOP, GOLD_BOT)

DUR = 18.0
NFRAMES = int(DUR * FPS)
IM = B.IM
IW, IH = B.IW, B.IH
SPLIT_T = 1.55          # ouverture du bloc
CARD_POS = (W / 2, 1180)

EMERALD_A = (16, 122, 78)
EMERALD_B = (3, 38, 28)
GOLD = (232, 186, 92)


# --------------------------------------------------------------------------- carte cadeau


def make_card(width=600, ss=2):
    """Carte cadeau « ROBUX » (design original : vert émeraude, dorure, pièce R$)."""
    w = width * ss
    h = int(w / 1.586)
    r = int(w * 0.06)
    rng = np.random.default_rng(11)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = np.clip((xx / w) * 0.6 + (yy / h) * 0.4, 0, 1)[..., None]
    col = np.array(EMERALD_A, np.float32) * (1 - u) + np.array(EMERALD_B, np.float32) * u
    col += (noise(w, h, 80, 50, rng)[..., None] - 0.5) * 10
    # reflet métallique doux
    col += np.exp(-(((xx * 0.7 - yy * 0.7) - w * 0.15) / (w * 0.12)) ** 2)[..., None] * 40
    face = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(face, "RGBA")
    # flocons en filigrane
    for _ in range(18):
        cx, cy, s = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(14, 42) * ss
        for k in range(6):
            a = k * math.pi / 3
            d.line([(cx, cy), (cx + math.cos(a) * s, cy + math.sin(a) * s)], fill=(255, 255, 255, 12), width=2 * ss)
    # filets dorés
    m = int(w * 0.035)
    d.rounded_rectangle([m, m, w - m, h - m], radius=r - m // 2, outline=GOLD + (255,), width=3 * ss)
    d.rounded_rectangle([m + 9 * ss, m + 9 * ss, w - m - 9 * ss, h - m - 9 * ss], radius=r - m, outline=GOLD + (110,), width=1 * ss)
    # pièce dorée « R$ »
    cr = int(h * 0.2)
    ccx, ccy = int(w * 0.78), int(h * 0.38)
    coin = np.zeros((h, w), np.float32)
    dist = np.sqrt((xx - ccx) ** 2 + (yy - ccy) ** 2) / cr
    shade = np.clip(1.15 - 0.55 * ((xx - ccx + cr) / (2 * cr)) - 0.25 * ((yy - ccy + cr) / (2 * cr)), 0.55, 1.2)
    ccol = np.stack([255 * shade, 205 * shade, 100 * shade], -1)
    ring = (dist > 0.82) & (dist <= 1.0)
    ccol[ring] *= 0.8
    calpha = (np.clip((1.0 - dist) * cr / 1.5, 0, 1) * 255).astype(np.uint8)
    coin_img = Image.fromarray(np.dstack([np.clip(ccol, 0, 255).astype(np.uint8), calpha]), "RGBA")
    face.alpha_composite(coin_img)
    f_coin = ImageFont.truetype(FONT_BLACK, int(cr * 0.95))
    d.text((ccx, ccy + cr * 0.02), "R$", font=f_coin, fill=(150, 98, 20, 255), anchor="mm")
    d.text((ccx - 2 * ss, ccy - 2 * ss), "R$", font=f_coin, fill=(255, 240, 200, 255), anchor="mm")
    # textes
    f_small = ImageFont.truetype(FONT_SEMI, int(h * 0.075))
    f_big = ImageFont.truetype(FONT_BLACK, int(h * 0.25))
    f_amt = ImageFont.truetype(FONT_XBOLD, int(h * 0.12))
    f_ug = ImageFont.truetype(FONT_SEMI, int(h * 0.06))
    x0 = int(w * 0.085)
    d.text((x0, int(h * 0.14)), "CARTE CADEAU", font=f_small, fill=GOLD + (255,))
    d.text((x0 + 3 * ss, int(h * 0.29) + 4 * ss), "ROBUX", font=f_big, fill=(0, 20, 12, 150))
    d.text((x0, int(h * 0.29)), "ROBUX", font=f_big, fill=(255, 255, 255, 255))
    d.text((x0, int(h * 0.70)), "??? R$", font=f_amt, fill=(255, 241, 196, 255))
    d.text((w - x0, int(h * 0.80)), "U N I T E D   G A M E S", font=f_ug, fill=(255, 255, 255, 170), anchor="ra")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    face.putalpha(mask)
    return face.resize((width, int(width / 1.586)), Image.LANCZOS)


def card_frame(t, scale=1.0, yaw=0.0, shine_phase=0.0):
    """Carte orientée (yaw ~ rotation verticale simulée) + reflet balayant."""
    c = A.card
    if abs(yaw) > 0.01:
        k = max(0.15, math.cos(yaw))
        c = c.resize((max(1, int(c.width * k)), c.height), Image.BILINEAR)
        sh = Image.new("RGBA", c.size, (0, 0, 0, int(90 * abs(math.sin(yaw)))))
        sh.putalpha(Image.fromarray((np.asarray(c.getchannel("A"), np.float32) * abs(math.sin(yaw)) * 0.35).astype(np.uint8)))
        c = c.copy()
        c.alpha_composite(sh)
    # reflet
    p = (shine_phase % 1.0)
    if 0 < p < 0.5:
        u = p / 0.5
        ww, hh = c.size
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        pos = lerp(-0.4, 1.4, u) * (ww + hh)
        band = np.exp(-((xx + yy * 0.6 - pos) / (ww * 0.07)) ** 2) * 0.55
        a = (band * np.asarray(c.getchannel("A"), np.float32)).astype(np.uint8)
        hl = Image.new("RGBA", c.size, (255, 255, 240, 255))
        hl.putalpha(Image.fromarray(a))
        c = c.copy()
        c.alpha_composite(hl)
    return transform(c, scale=scale)


def cards_state(t):
    """Liste (x, y, échelle, angle, yaw, opacité, phase reflet), cartes du fond d'abord."""
    out = []
    mx, my = CARD_POS
    # carte principale : sort de la glace
    u0 = seg(t, SPLIT_T, SPLIT_T + 0.9)
    sc = lerp(0.82, 1.0, ease_out_back(u0, 1.8))
    y = my + 10 * math.sin(t * 1.6)
    ang = 3 * math.sin(t * 0.9)
    yaw = 0.28 * math.sin(t * 1.1)
    # scène 3 : remonte un peu, deux autres cartes apparaissent
    u3 = ease_in_out(seg(t, 7.0, 8.0))
    y = lerp(y, 1080 + 8 * math.sin(t * 1.6), u3)
    fan = ease_out_back(seg(t, 7.3, 8.1), 1.6)
    # scène 4 : l'éventail rétrécit sous le logo
    u4 = ease_in_out(seg(t, 12.0, 14.0))
    sc4 = lerp(1.0, 0.52, u4)
    y = lerp(y, 1000 + 5 * math.sin(t * 1.6), u4)
    yaw *= (1 - u4 * 0.6)
    if fan > 0:
        for side in (-1, 1):
            out.append((mx + side * 230 * fan * sc4, y + 40 * fan * sc4, sc * 0.88 * sc4, -side * 13 * fan + ang * 0.5,
                        -side * 0.25 * fan, clamp(fan * 1.5), t * 0.45 + (0.3 if side > 0 else 0.6)))
    out.append((mx, y, sc * sc4, ang, yaw, 1.0, t * 0.45))
    return out


# --------------------------------------------------------------------------- nouvelle glace


def prepare_ice2(rng):
    w, h = IW, IH
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cloud = fbm(w, h, rng, base=2, octaves=6)
    edge = np.minimum(np.minimum(xx, w - xx), np.minimum(yy, h - yy)) / (w * 0.5)
    deep = np.array([6, 46, 64], np.float32)
    mid = np.array([40, 160, 180], np.float32)
    light = np.array([190, 245, 250], np.float32)
    u = np.clip(cloud * 1.4 - 0.32 + (1 - edge) * 0.0, 0, 1)[..., None]
    col = np.where(u < 0.5, deep + (mid - deep) * (u / 0.5), mid + (light - mid) * ((u - 0.5) / 0.5))
    # lueur violette froide en bas, cœur plus sombre derrière la carte
    col += np.clip((yy / h - 0.6), 0, 1)[..., None] * np.array([60, -10, 70])
    core = np.exp(-(((xx - w / 2) / (w * 0.42)) ** 2 + ((yy - CARD_POS[1] - IM) / (h * 0.25)) ** 2))
    col *= (1 - 0.35 * core)[..., None]
    ice = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).convert("RGBA")

    # carte prisonnière de la glace (floue, teintée)
    card = make_card(600).rotate(-6, resample=Image.BICUBIC, expand=True).filter(ImageFilter.GaussianBlur(5))
    ca = np.asarray(card, np.float32)
    ca[..., :3] = ca[..., :3] * np.array([0.55, 0.9, 1.0]) + np.array([10, 40, 50])
    ca[..., 3] *= 0.62
    paste_alpha(ice, Image.fromarray(np.clip(ca, 0, 255).astype(np.uint8), "RGBA"), CARD_POS[0] + IM, CARD_POS[1] + IM)
    A.ice2_card_glow = (CARD_POS[0] + IM, CARD_POS[1] + IM)

    # givre en fougères (dendrites) depuis les bords
    frost = Image.new("L", (w, h), 0)
    fd = ImageDraw.Draw(frost)

    def fern(x, y, ang, length, depth, width):
        if depth == 0 or length < 6:
            return
        steps = int(length / 10)
        for i in range(steps):
            nx, ny = x + math.cos(ang) * 10, y + math.sin(ang) * 10
            fd.line([(x, y), (nx, ny)], fill=200, width=max(1, int(width)))
            if i % 2 == 0:
                for s in (-1, 1):
                    bl = length * 0.32 * (1 - i / steps)
                    fern(nx, ny, ang + s * 1.05, bl, depth - 1, width * 0.6)
            ang += rng.uniform(-0.08, 0.08)
            x, y = nx, ny

    for _ in range(26):
        side = rng.integers(4)
        if side == 0:
            x, y, a = rng.uniform(0, w), 0, math.pi / 2
        elif side == 1:
            x, y, a = rng.uniform(0, w), h, -math.pi / 2
        elif side == 2:
            x, y, a = 0, rng.uniform(0, h), 0
        else:
            x, y, a = w, rng.uniform(0, h), math.pi
        fern(x, y, a + rng.uniform(-0.6, 0.6), rng.uniform(160, 420), 3, 3)
    frost = frost.filter(ImageFilter.GaussianBlur(1.1))
    fl = Image.new("RGBA", (w, h), (235, 252, 255, 255))
    fl.putalpha(frost.point(lambda v: int(v * 0.85)))
    ice.alpha_composite(fl)
    # voile givré sur les bords
    vel = np.clip((0.3 - edge) * 3.2, 0, 1) * fbm(w, h, rng, base=30, octaves=3)
    vl = Image.fromarray(np.dstack([np.full((h, w, 3), 230, np.uint8), (vel * 200).astype(np.uint8)]), "RGBA")
    ice.alpha_composite(vl)
    # reflets
    spec = np.exp(-(((xx * 0.85 - yy * 0.5) - w * 0.1) / (w * 0.06)) ** 2) * 0.28
    spec += np.exp(-(((xx * 0.85 - yy * 0.5) + w * 0.25) / (w * 0.018)) ** 2) * 0.22
    sl = Image.fromarray(np.dstack([np.full((h, w, 3), 255, np.uint8), (spec * 255).astype(np.uint8)]), "RGBA")
    ice.alpha_composite(sl)
    d = ImageDraw.Draw(ice, "RGBA")
    for _ in range(500):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.8, 3.0)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(230, 255, 255, int(rng.uniform(50, 160))))
    A.ice2 = ice.convert("RGB")

    # ---- grande fissure verticale + ramifications (segments horodatés)
    segs = []
    pts = []
    x, y = w / 2 + rng.uniform(-40, 40), -20
    while y < h + 20:
        pts.append((x, y))
        ny = y + rng.uniform(35, 70)
        x = clamp(x + rng.uniform(-38, 38), w / 2 - 110, w / 2 + 110)
        y = ny
    pts.append((x, h + 30))
    A.main_crack = pts

    def appear(yv):  # deux poussées : moitié haute puis moitié basse
        f = yv / h
        return 0.15 + 0.45 * (f / 0.5) if f < 0.5 else 0.8 + 0.45 * ((f - 0.5) / 0.5)

    for i in range(len(pts) - 1):
        segs.append((appear(pts[i][1]), pts[i], pts[i + 1], 6))
        if rng.random() < 0.55:
            side = rng.choice([-1, 1])
            ang = math.pi / 2 + side * rng.uniform(0.6, 1.25)
            bx, by = pts[i]
            t0 = appear(by)
            for k in range(int(rng.integers(4, 14))):
                ang += rng.uniform(-0.3, 0.3)
                ex, ey = bx + math.cos(ang) * 28, by + math.sin(ang) * 28 - 6
                segs.append((t0 + 0.035 * (k + 1), (bx, by), (ex, ey), 3 if k < 4 else 2))
                if rng.random() < 0.18:
                    a2, cx2, cy2 = ang + rng.choice([-1, 1]) * 0.8, ex, ey
                    for j in range(int(rng.integers(2, 6))):
                        a2 += rng.uniform(-0.3, 0.3)
                        fx, fy = cx2 + math.cos(a2) * 22, cy2 + math.sin(a2) * 22
                        segs.append((t0 + 0.035 * (k + j + 2), (cx2, cy2), (fx, fy), 1))
                        cx2, cy2 = fx, fy
                bx, by = ex, ey
    A.crack_segs = sorted(segs, key=lambda s: s[0])

    # glace finale toute fissurée
    full = crack_mask(99)
    A.ice2_cracked = B.composite_cracks(A.ice2, full).convert("RGBA")

    # ---- blocs : deux moitiés découpées en bandes irrégulières
    left_poly = [(-40, -40)] + pts + [(-40, h + 40)]
    half = Image.new("L", (w, h), 0)
    ImageDraw.Draw(half).polygon(left_poly, fill=255)
    half_l = np.asarray(half) > 127
    cuts = sorted(rng.uniform(0.08, 0.94, 6) * h)
    bands = [-50] + list(cuts) + [h + 50]
    pieces = []
    for side, hm in ((-1, half_l), (1, ~half_l)):
        jag = [0] * len(bands)
        for j in range(len(bands) - 1):
            top_pts, bot_pts = [], []
            for xi in np.linspace(-40, w + 40, 18):
                top_pts.append((xi, bands[j] + (rng.uniform(-35, 35) if 0 < j else 0)))
                bot_pts.append((xi, bands[j + 1] + (rng.uniform(-35, 35) if j + 1 < len(bands) - 1 else 0)))
            bm = Image.new("L", (w, h), 0)
            ImageDraw.Draw(bm).polygon(top_pts + bot_pts[::-1], fill=255)
            m = (np.asarray(bm) > 127) & hm
            if not m.any():
                continue
            ys, xs = np.nonzero(m)
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            piece = A.ice2_cracked.crop((x0, y0, x1, y1))
            alpha = Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8))
            inner = alpha.filter(ImageFilter.MinFilter(5))
            pa = np.asarray(piece).copy()
            e = (np.asarray(alpha, np.int16) - np.asarray(inner, np.int16)) > 0
            pa[e, :3] = np.clip(pa[e, :3].astype(np.int16) + 80, 0, 255).astype(np.uint8)
            piece = Image.fromarray(pa, "RGBA")
            piece.putalpha(alpha)
            pieces.append(dict(img=piece, cx=xs.mean(), cy=ys.mean(), side=side, j=j,
                               delay=rng.uniform(0, 0.12) + (1 - ys.mean() / h) * 0.05,
                               rot=rng.uniform(15, 45), vx=rng.uniform(500, 900)))
    A.pieces = pieces
    A.chips = [(rng.uniform(0, h), rng.uniform(-1, 1), rng.uniform(200, 900), rng.uniform(1.5, 5), rng.uniform(0, 0.25)) for _ in range(180)]


def crack_mask(t):
    m = Image.new("L", (IW, IH), 0)
    d = ImageDraw.Draw(m)
    for t0, p0, p1, wd in A.crack_segs:
        if t0 > t:
            break
        d.line([p0, p1], fill=255, width=wd)
    return np.asarray(m, np.float32) / 255.0


def shake2(t):
    s = 0.0
    for t0, amp in ((0.15, 12), (0.8, 16), (1.3, 10), (SPLIT_T, 34)):
        if t >= t0:
            s += amp * math.exp(-(t - t0) * 13)
    return s * math.sin(t * 90), s * math.cos(t * 77)


def gold_leak(img, t, strength):
    """Lumière dorée qui filtre par la fissure principale."""
    if strength <= 0.01:
        return
    m = Image.new("L", (IW, IH), 0)
    ImageDraw.Draw(m).line(A.main_crack, fill=255, width=10)
    g = m.filter(ImageFilter.GaussianBlur(26))
    layer = Image.new("RGBA", (IW, IH), (255, 200, 110, 255))
    layer.putalpha(g.point(lambda v: int(min(255, v * 2.2 * strength))))
    img.alpha_composite(layer)
    core = m.filter(ImageFilter.GaussianBlur(3))
    layer = Image.new("RGBA", (IW, IH), (255, 245, 215, 255))
    layer.putalpha(core.point(lambda v: int(v * strength)))
    img.alpha_composite(layer)


def render_ice2(t):
    img = B.composite_cracks(A.ice2, crack_mask(t)).convert("RGBA")
    gold_leak(img, t, 0.25 * smooth(seg(t, 0.8, 1.2)) + 0.75 * smooth(seg(t, 1.2, SPLIT_T)))
    # pulsation de la carte prisonnière
    p = 0.25 + 0.2 * math.sin(t * 6) * seg(t, 0.4, 1.5)
    paste_alpha(img, A.glow_warm[70].resize((700, 700)), *A.ice2_card_glow, p * seg(t, 0.3, 1.2))
    dx, dy = shake2(t)
    return img.crop((IM + dx, IM + dy, IM + dx + W, IM + dy + H))


def render_split(frame, t):
    tt = t - SPLIT_T
    for pc in A.pieces:
        u = max(0.0, tt - pc["delay"])
        s = pc["side"]
        cx = pc["cx"] - IM + s * (pc["vx"] * 0.35 * u + 1500 * u * u)
        cy = pc["cy"] - IM + 1300 * u * u - 80 * u
        ang = -s * pc["rot"] * u * 1.4
        sc = 1 + 0.18 * u
        if u <= 0:
            paste_alpha(frame, pc["img"], cx, cy)
            continue
        if cx < -900 or cx > W + 900 or cy > H + 900:
            continue
        paste_alpha(frame, transform(pc["img"], scale=sc, angle=ang), cx, cy, 1 - smooth((u - 0.7) / 0.4))
    # éclats le long de la fente
    d = ImageDraw.Draw(frame)
    for y0, dirx, sp, r, dl in A.chips:
        u = tt - dl
        if u <= 0 or u > 1.1:
            continue
        x = W / 2 + dirx * sp * u
        y = y0 - IM + 900 * u * u - 200 * u
        rr = r * (1 + u)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(220, 250, 255, int(235 * (1 - u / 1.1))))
    # flash doré
    fl = math.exp(-max(0, tt) * 6) * 0.8
    if fl > 0.01:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 228, 170, int(255 * fl))))


# --------------------------------------------------------------------------- logo + cartes (remplace celles du teaser 1)


def logo_state(t):
    blur = 30.0
    if t >= 12.0:
        blur = lerp(30, 1.2, ease_in_out(seg(t, 12.0, 13.8)))
    if t < 7.0:
        sc, y = 1.0, 840
    elif t < 12.0:
        sc, y = lerp(1.0, 1.2, ease_in_out(seg(t, 7, 12))), 800
    else:
        u = ease_in_out(seg(t, 12.0, 14.2))
        sc, y = lerp(1.2, 0.66, u), lerp(800, 610, u)
    op = 0.6 if t < 12 else lerp(0.6, 1.0, seg(t, 12, 13.6))
    halo = 0.35 + 0.15 * math.sin(t * 2.0) + 0.25 * seg(t, 13.0, 14.0)
    return blur, sc, y, op, halo


_orig_draw_logo = B.draw_logo


def draw_logo_and_cards(frame, t):
    _orig_draw_logo(frame, t)
    if t < SPLIT_T:
        return
    # halo doré derrière les cartes
    st = cards_state(t)
    mx, my = st[-1][0], st[-1][1]
    ga = 0.55 + 0.15 * math.sin(t * 2.4)
    paste_alpha(frame, A.big_glow, mx, my, ga * (1 - 0.4 * seg(t, 12, 14)))
    for x, y, sc, ang, yaw, op, ph in st:
        c = card_frame(t, scale=sc, yaw=yaw, shine_phase=ph)
        sh = Image.new("RGBA", c.size, (0, 0, 0, 255))
        sh.putalpha(c.getchannel("A").point(lambda v: int(v * 0.55)))
        sh = transform(sh, angle=ang, blur=14)
        paste_alpha(frame, sh, x + 10, y + 26, op)
        paste_alpha(frame, transform(c, angle=ang), x, y, op)


# --------------------------------------------------------------------------- textes


def prepare_texts2():
    T = {}
    glow_r = (255, 70, 80)
    T["d1"] = text_block([text_line("DES CARTES", FONT_BLACK, 104, WHITE, tracking=0.02)], glow=glow_r, glow_radius=24)
    T["d2"] = text_block([text_line("ROBUX", FONT_BLACK, 190, gradient=(GOLD_TOP, GOLD_BOT), tracking=0.02)], glow=(255, 190, 90), glow_radius=34)
    T["d3"] = text_block([text_line("À GAGNER !", FONT_BLACK, 112, RED, stroke=5, stroke_fill=WHITE, tracking=0.02, emoji="🎁")], glow=(255, 60, 70), glow_radius=26)
    T["sous"] = text_block([text_line("Le cadeau de Noël de United Games", FONT_MED_IT, 46, (245, 245, 245), emoji="🎄")], shadow=0.95)
    T["combien"] = text_block([text_line("Combien de cartes ?", FONT_XBOLD, 88, WHITE, tracking=0.02, emoji="👀")], shadow=0.9, glow=(255, 214, 150), glow_radius=22)
    T["qui"] = text_block([text_line("Qui va les remporter ?", FONT_SEMI, 74, WHITE, tracking=0.03, emoji="🏆")], shadow=0.9, glow=(255, 214, 150), glow_radius=20)
    T["f1"] = text_block([text_line("CARTES ROBUX", FONT_BLACK, 124, gradient=(GOLD_TOP, GOLD_BOT), tracking=0.03)], shadow=0.9, glow=(255, 190, 90), glow_radius=30)
    T["f2"] = text_block([text_line("À GAGNER CHEZ UNITED GAMES", FONT_BLACK, 58, WHITE, tracking=0.04, emoji="🎄")], shadow=0.9, glow=(255, 60, 70), glow_radius=18)
    T["f3"] = text_block([text_line("Abonne-toi pour ne rien rater", FONT_SEMI, 48, (250, 245, 235), tracking=0.03, emoji="🔔")], shadow=0.95)
    T["legal"] = text_block([text_line("Concours non affilié à Roblox Corporation.", FONT_SEMI, 24, (220, 220, 220), tracking=0.02)], shadow=0.9)
    A.T2 = T


def draw_texts2(frame, t):
    T = A.T2
    if 2.35 <= t < 7.1:
        out = seg(t, 6.55, 7.0)
        for i, (key, y) in enumerate((("d1", 520), ("d2", 680), ("d3", 850))):
            t0 = 2.45 + i * 0.17
            u = seg(t, t0, t0 + 0.45)
            if u <= 0:
                continue
            sc = lerp(1.9, 1.0, ease_out_back(u, 2.2)) * (1 + 0.012 * math.sin((t - t0) * 2.2))
            if key == "d2" and t > 3.3:
                sc *= 1 + 0.035 * math.exp(-(t - 3.3) * 5) * math.sin((t - 3.3) * 25)
            sc *= 1 + 0.12 * out
            img = transform(T[key], scale=sc, blur=8 * (1 - smooth(u * 1.6)) + 14 * out)
            paste_alpha(frame, img, W / 2, y - 40 * out, smooth(u * 2.2) * (1 - out))
        u = seg(t, 3.7, 4.2)
        if u > 0:
            img = transform(T["sous"], scale=lerp(0.85, 1.0, ease_out_back(u)))
            paste_alpha(frame, img, W / 2, lerp(1470, 1440, ease_out_cubic(u)), smooth(u) * (1 - out))
    for key, a, b, y in (("combien", 7.4, 9.65, 1380), ("qui", 9.85, 11.85, 1380)):
        if a <= t < b:
            u_in, u_out = seg(t, a, a + 0.7), seg(t, b - 0.55, b)
            img = transform(T[key], scale=lerp(1.12, 1.0, ease_out_cubic(u_in)) * lerp(1, 1.04, seg(t, a, b)),
                            blur=16 * (1 - ease_out_cubic(u_in)) + 12 * u_out)
            paste_alpha(frame, img, W / 2, y - 30 * u_out, smooth(u_in) * (1 - smooth(u_out)))
    if t >= 13.9:
        fade = 1 - seg(t, 17.0, 17.85)
        u = seg(t, 13.9, 14.55)
        paste_alpha(frame, transform(T["f1"], scale=lerp(1.35, 1.0, ease_out_cubic(u)), blur=10 * (1 - ease_out_cubic(u))),
                    W / 2, 1250, smooth(u * 1.5) * fade)
        u2 = seg(t, 14.25, 14.85)
        paste_alpha(frame, transform(T["f2"], scale=lerp(0.85, 1.0, ease_out_back(u2)), blur=6 * (1 - ease_out_cubic(u2))),
                    W / 2, lerp(1375, 1350, ease_out_cubic(u2)), smooth(u2 * 1.4) * fade)
        u3 = seg(t, 15.2, 15.9)
        if u3 > 0:
            paste_alpha(frame, transform(T["f3"], blur=6 * (1 - ease_out_cubic(u3))), W / 2, lerp(1460, 1435, ease_out_cubic(u3)), smooth(u3) * fade)
            paste_alpha(frame, T["legal"], W / 2, 1500, smooth(u3) * 0.8 * fade)


# --------------------------------------------------------------------------- assemblage


def prepare2():
    B.prepare()
    rng = np.random.default_rng(1225)
    A.card = make_card(600)
    A.big_glow = A.glow_warm[70].resize((1000, 1000), Image.BICUBIC)
    prepare_ice2(rng)
    prepare_texts2()
    B.logo_state = logo_state
    B.draw_logo = draw_logo_and_cards


def render_frame(t):
    if t < SPLIT_T:
        frame = render_ice2(t)
    else:
        frame = B.render_scene(t)
        draw_texts2(frame, t)
        if t < SPLIT_T + 1.4:
            render_split(frame, t)
    fb = seg(t, 17.0, 17.9)
    if fb > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * smooth(fb)))))
    return frame.convert("RGB")


def _render_idx(i):
    return render_frame(i / FPS).tobytes()


def main():
    os.makedirs(B.OUT, exist_ok=True)
    prepare2()
    if len(sys.argv) > 2 and sys.argv[1] == "--preview":
        for ts in sys.argv[2:]:
            render_frame(float(ts)).save(os.path.join(B.OUT, f"robux_preview_{float(ts):05.2f}.png"))
        return
    out = os.path.join(B.OUT, "united_games_cartes_robux.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(_render_idx, range(NFRAMES), chunksize=2)):
            proc.stdin.write(buf)
            if i % 60 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("OK ->", out)


if __name__ == "__main__":
    main()
