# -*- coding: utf-8 -*-
"""make_sheet.py — 把 src/raw 里的候选图拼成总览图（带文件名），供人工目检筛选。"""
import glob
import os
import sys

from PIL import Image, ImageDraw

BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(BASE, 'src', 'raw')
OUT = os.path.join(BASE, 'src')
COLS, CELL, PAD = 6, 320, 24
files = sorted(glob.glob(os.path.join(RAW, '*.jpg')) + glob.glob(os.path.join(RAW, '*.png')))
per = int(sys.argv[1]) if len(sys.argv) > 1 else 24
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
sel = files[start:start + per]
rows = (len(sel) + COLS - 1) // COLS
W = COLS * (CELL + PAD) + PAD
H = rows * (CELL + PAD + 22) + PAD
sheet = Image.new('RGB', (W, H), (28, 28, 30))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(sel):
    try:
        im = Image.open(f).convert('RGB')
    except Exception as e:
        print('skip', f, e)
        continue
    im.thumbnail((CELL, CELL), Image.LANCZOS)
    x = PAD + (i % COLS) * (CELL + PAD) + (CELL - im.width) // 2
    y = PAD + (i // COLS) * (CELL + PAD + 22) + (CELL - im.height) // 2
    sheet.paste(im, (x, y))
    cx = PAD + (i % COLS) * (CELL + PAD)
    cy = PAD + (i // COLS) * (CELL + PAD + 22) + CELL + 4
    d.text((cx + 2, cy), os.path.basename(f), fill=(230, 230, 230))
out = os.path.join(OUT, 'sheet_%d.png' % start)
sheet.save(out)
print(out, sheet.size, 'imgs=%d' % len(sel))
