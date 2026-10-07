# -*- coding: utf-8 -*-
"""prep_masters.py — 阶段②统一处理：13 张入选素材 → 1920×1080 统一规格（裁切 or 竖图模糊填充）
+ 生成 832×480 的 VACE 输入图 + 总览拼图供目检。
裁切 bias：0=保留上部 / 0.5=居中 / 1=保留下部（按主体位置设）。
"""
import os
import time

from PIL import Image, ImageDraw, ImageFilter

BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = BASE + '/src/restored'          # 读 Real-ESRGAN x4 修复后的图
OUT = BASE + '/prepped'
VIN = OUT + '/vace'
os.makedirs(VIN, exist_ok=True)

# (id, 文件名, 模式, bias)   crop=裁成16:9   fill=竖图模糊填充
JOBS = [
    ('p01', 'big_04_x4.png', 'crop', 0.50),
    ('p02', 'big_25_x4.png', 'crop', 0.57),
    ('p03', 'big_22_x4.png', 'crop', 0.55),
    ('p04', 'big_06_x4.png', 'crop', 0.45),
    ('p05', 'big_01_x4.png', 'crop', 0.45),
    ('p06', 'big_13_x4.png', 'crop', 0.50),
    ('p07', 'big_14_x4.png', 'crop', 0.55),
    ('p08', 'big_12_x4.png', 'fill', 0.50),
    ('p09', 'big_19_x4.png', 'crop', 0.50),
    ('p10', 'big_24_x4.png', 'crop', 0.50),
    ('p11', 'big_33_x4.png', 'crop', 0.55),
    ('p12', 'big_23_x4.png', 'crop', 0.50),
    ('p13', 'big_32_x4.png', 'crop', 0.50),
]
W, H = 1920, 1080

t0 = time.time()
for pid, fn, mode, bias in JOBS:
    im = Image.open(os.path.join(RAW, fn)).convert('RGB')
    if mode == 'crop':
        ar = W / H
        if im.width / im.height > ar:              # 过宽 → 裁两侧
            nh = im.height
            nw = int(round(nh * ar))
            left = (im.width - nw) // 2
            im = im.crop((left, 0, left + nw, nh))
        else:                                       # 过高 → 裁上下
            nw = im.width
            nh = int(round(nw / ar))
            top = int(round((im.height - nh) * bias))
            im = im.crop((0, top, nw, top + nh))
        canvas = im.resize((W, H), Image.LANCZOS)
    else:                                           # fill：模糊背景 + 居中前景
        bg = im.copy()
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s + 1), int(bg.height * s + 1)), Image.LANCZOS)
        l = (bg.width - W) // 2
        t = (bg.height - H) // 2
        bg = bg.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(48))
        bg = Image.eval(bg, lambda v: int(v * 0.72))
        fg = im.copy()
        s2 = H / fg.height
        fg = fg.resize((int(fg.width * s2 + 1), H), Image.LANCZOS)
        canvas = bg
        canvas.paste(fg, ((W - fg.width) // 2, 0))
    canvas.save(os.path.join(OUT, '%s_1080.png' % pid))
    vin = canvas.resize((832, 480), Image.LANCZOS)
    vin.save(os.path.join(VIN, '%s_832.jpg' % pid), quality=95)
    print('%s ← %s (%s, bias=%.2f) src=%dx%d' % (pid, fn, mode, bias, im.width, im.height))

# 总览拼图（供目检裁切是否切头）
files = sorted(f for f in os.listdir(OUT) if f.endswith('_1080.png'))
COLS, CW, CH, PAD = 4, 440, 248, 26
rows = (len(files) + COLS - 1) // COLS
sheet = Image.new('RGB', (COLS * (CW + PAD) + PAD, rows * (CH + PAD + 20) + PAD), (26, 26, 28))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(os.path.join(OUT, f)).convert('RGB')
    im.thumbnail((CW, CH), Image.LANCZOS)
    x = PAD + (i % COLS) * (CW + PAD)
    y = PAD + (i // COLS) * (CH + PAD + 20)
    sheet.paste(im, (x, y))
    d.text((x + 2, y + CH + 2), f, fill=(230, 230, 230))
sheet.save(os.path.join(OUT, 'masters_sheet.png'))
print('masters_sheet.png', sheet.size, '| %.1fs' % (time.time() - t0))
