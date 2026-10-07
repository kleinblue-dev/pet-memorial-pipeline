# -*- coding: utf-8 -*-
"""make_compare.py — 修复前后对比图（1 张，两例）：
A) 模拟微信压缩图 320×212（big_24 降采样+q30）→ 修复
B) 真实低清老照片 768×1024（pdm 授权）→ 修复
面板口径一致：都放大到 1920 宽显示（「修复前」= 原图直接 Lanczos 放大；「修复后」= Real-ESRGAN x4 再缩放）。
"""
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CW, CH, PAD, LBL = 800, 600, 40, 46
FONT = os.environ.get('FONT_PATH', 'C:/Windows/Fonts/msyh.ttc')

cases = [
    ('微信压缩模拟图（原图 320×212）', 'src/raw/wechat_sim.jpg', 'src/restored/wechat_sim_x4.png'),
    ('真实低清老照片（原图 768×1024，公有领域）', 'src/raw/small_06.jpg', 'src/restored/small_06_x4.png'),
]
rows = []
for title, before_p, after_p in cases:
    b = Image.open(os.path.join(BASE, before_p)).convert('RGB')
    a = Image.open(os.path.join(BASE, after_p)).convert('RGB')
    s = 1920 / b.width
    b = b.resize((1920, int(b.height * s)), Image.LANCZOS)
    s2 = 1920 / a.width
    a = a.resize((1920, int(a.height * s2)), Image.LANCZOS)
    rows.append((title, b, a))

f_t = ImageFont.truetype(FONT, 26)
f_l = ImageFont.truetype(FONT, 24)
W = PAD + 2 * (CW + PAD)
H = PAD + sum((PAD + LBL + CH) + 34 for _ in rows)
sheet = Image.new('RGB', (W, H), (24, 24, 26))
d = ImageDraw.Draw(sheet)
y = PAD
for title, b, a in rows:
    d.text((PAD, y), title, fill=(255, 214, 140), font=f_t)
    y += 34
    for i, (im, lab) in enumerate([(b, '修复前：直接放大'), (a, '修复后：Real-ESRGAN x4')]):
        im2 = im.copy()
        im2.thumbnail((CW, CH), Image.LANCZOS)
        x = PAD + i * (CW + PAD)
        d.text((x + 2, y), lab, fill=(200, 220, 255), font=f_l)
        sheet.paste(im2, (x, y + LBL))
    y += PAD + LBL + CH
out = os.path.join(BASE, 'out', '修复前后对比.png')
sheet.save(out)
print(out, sheet.size)
