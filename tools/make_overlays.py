# -*- coding: utf-8 -*-
"""make_overlays.py — 片头/字幕/片尾 透明 PNG 贴图（1920×1080，柔影，暖白色）。
语气纪律：平静、不煽情；不用「爆哭/破防/泪目/复活/看哭了/戳心/治愈」。
"""
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = BASE + '/out/overlays'
os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080

for cand in ('C:/Windows/Fonts/msyhl.ttc', 'C:/Windows/Fonts/msyh.ttc'):
    if os.path.isfile(cand):
        FONT = cand
        break
F_T = ImageFont.truetype(FONT, 58)
F_T2 = ImageFont.truetype(FONT, 33)
F_T3 = ImageFont.truetype(FONT, 28)
F_S = ImageFont.truetype(FONT, 46)
F_E = ImageFont.truetype(FONT, 46)
F_E2 = ImageFont.truetype(FONT, 30)

TXT = (252, 248, 242)
DIM = (208, 202, 194)

def make(name, lines, cy_off=0):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hs, total = [], 0
    for txt, font, color in lines:
        bb = d.textbbox((0, 0), txt, font=font)
        hs.append((txt, font, color, bb[2] - bb[0], bb[3] - bb[1]))
        total += (bb[3] - bb[1]) + 26
    y = (H - total) // 2 + cy_off
    for txt, font, color, tw, th in hs:
        x = (W - tw) // 2
        bb = d.textbbox((x, y), txt, font=font)
        # 柔影：先画到影子层
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        ds.text((x + 3, y + 3), txt, font=font, fill=(0, 0, 0, 205))
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        im.alpha_composite(sh)
        d = ImageDraw.Draw(im)
        d.text((x, y), txt, font=font, fill=color)
        y += th + 26
    im.save(os.path.join(OUT, name + '.png'))
    return name, [t for t, _, _ in lines]

meta = []
meta.append(make('title', [
    ('样片', F_T, TXT),
    ('照片来自公开授权图库（CC0 / 公有领域）', F_T2, DIM),
    ('演示风格与技术 · 非真实客户素材', F_T3, DIM)]))
meta.append(make('sub_a', [('有些照片，已经不太清楚了。', F_S, TXT)], 300))
meta.append(make('sub_b', [('模糊的、旧的、在手机里存了很久的，都可以。', F_S, TXT)], 300))
meta.append(make('interlude', [('修好之后，还是原来的样子。', F_T2, (226, 220, 212))]))
meta.append(make('sub_c', [('我会把它们修好，放慢一点。', F_S, TXT)], 300))
meta.append(make('sub_d', [('正式的视频里，画面会全部换成你自己的照片。', F_S, TXT)], 300))
meta.append(make('end', [
    ('样片结束', F_E, TXT),
    ('不着急，需要的时候再来找我。', F_E2, DIM)]))
with open(os.path.join(OUT, 'overlays.json'), 'w', encoding='utf-8') as f:
    json.dump([{'name': n, 'lines': l} for n, l in meta], f, ensure_ascii=False, indent=1)
print('overlays done:', [m[0] for m in meta])
