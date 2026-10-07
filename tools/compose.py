# -*- coding: utf-8 -*-
"""compose.py — 阶段④合成：13 条 I2V 片段 → 1080p 成片。

阶段 A（segments）：每条片段抽帧 → Real-ESRGAN x{ESR} 提升 → 30fps 插帧 + 慢放 + 尾帧停留 → seg_NN.mp4
阶段 B（assemble）：title + 13 片段 + 中段静场 + 片尾 用 xfade 串联；字幕 PNG 淡入淡出叠加；配乐 loudnorm+淡入淡出
用法: python -X utf8 tools/compose.py segments | assemble | all
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

from PIL import Image

BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 数据根目录（默认=仓库根）
CLIPS = BASE + '/clips'
WORK = BASE + '/work_frames'
SEGS = BASE + '/segments'
OUT = BASE + '/out'
OVL = OUT + '/overlays'
LOGS = BASE + '/logs'
FF = os.environ.get('FFMPEG', 'ffmpeg')
# 升清引擎：Real-CUGAN x2（noise=-1 保守）。
# 不用 Real-ESRGAN：实测本机 realesrgan-ncnn-vulkan 的 -s 2 输出拼贴错图（-s 4 正常但慢约 15 倍）。
CUGAN_EXE = os.environ.get('REALCUGAN', 'realcugan-ncnn-vulkan')

IDS = ['p%02d' % i for i in range(1, 14)]
ESR = 2                 # 视频帧放大倍数（realesrgan -s）
SLOW = 1.55             # 慢放
TAIL = 1.0              # 尾帧停留（秒）
XF = 0.8                # 交叉溶解
TITLE_D, INTER_D, END_D = 7.0, 5.5, 8.0
FPS = 30
PREVIEW = '--preview' in sys.argv
W, H = (960, 540) if PREVIEW else (1920, 1080)
SRC_FPS = 16.0
NFRAMES = 61
SEG_D = NFRAMES / SRC_FPS * SLOW + TAIL          # 每条片段时长
ORDER = ['title'] + IDS[:6] + ['inter'] + IDS[6:] + ['end']
DUR = {'title': TITLE_D, 'inter': INTER_D, 'end': END_D}
for i in IDS:
    DUR[i] = SEG_D

# 字幕窗口（绝对秒，按 xfade 累积位置计算）
SUBWIN = {'sub_a': ('p02', 1.2, 5.0), 'sub_b': ('p05', 1.2, 5.0),
          'sub_c': ('p10', 1.1, 5.0), 'sub_d': ('p12', 1.1, 5.0)}


def pos_of(elem):
    p = 0.0
    for e in ORDER:
        if e == elem:
            return p
        p += DUR[e] - XF
    raise KeyError(elem)


TOTAL = sum(DUR[e] for e in ORDER) - XF * (len(ORDER) - 1)


def run(cmd, log=None):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('命令失败(%d): %s' % (r.returncode, ' '.join(cmd[:6])), flush=True)
        print((r.stderr or '')[-2500:], flush=True)
        if log:
            open(log, 'a', encoding='utf-8').write((r.stderr or '')[-2500:])
        sys.exit(3)
    return r


def stage_segments():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(SEGS, exist_ok=True)
    times = {}
    for pid in IDS:
        t0 = time.time()
        clip = os.path.join(CLIPS, '%s.mp4' % pid)
        fdir = os.path.join(WORK, pid)
        udir = os.path.join(WORK, pid + '_up')
        seg = os.path.join(SEGS, 'seg_%s.mp4' % pid)
        if os.path.isfile(seg):
            print('%s 已存在，跳过' % pid, flush=True)
            continue
        for d in (fdir, udir):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
        run([FF, '-y', '-hide_banner', '-loglevel', 'error', '-i', clip,
             '-fps_mode', 'passthrough', os.path.join(fdir, 'f%03d.png')])
        fr = sorted(os.listdir(fdir))
        t1 = time.time()
        for f in fr:
            run([CUGAN_EXE, '-i', os.path.join(fdir, f), '-o', os.path.join(udir, f),
                 '-s', str(ESR), '-n', '-1'])
        t2 = time.time()
        vf = ('scale=%d:%d:flags=lanczos,setpts=%.4f*PTS,'
              'minterpolate=fps=%d:mi_mode=mci:mc_mode=aobmc:vsbmc=1,'
              'tpad=stop_mode=clone:stop_duration=%.2f,fps=%d,setsar=1,format=yuv420p'
              % (W, H, SLOW, FPS, TAIL, FPS))
        run([FF, '-y', '-hide_banner', '-loglevel', 'error', '-framerate', str(SRC_FPS),
             '-i', os.path.join(udir, 'f%03d.png'), '-vf', vf,
             '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', seg])
        t3 = time.time()
        times[pid] = {'extract': round(t1 - t0, 1), 'upscale': round(t2 - t1, 1),
                      'rebuild': round(t3 - t2, 1), 'total': round(t3 - t0, 1)}
        print('%s 段完成 extract=%.1fs upscale=%.1fs rebuild=%.1fs (共%.1fs)'
              % (pid, t1 - t0, t2 - t1, t3 - t2, t3 - t0), flush=True)
        shutil.rmtree(fdir, ignore_errors=True)
    with open(LOGS + '/compose_times.json', 'w', encoding='utf-8') as f:
        json.dump({'engine': 'realcugan-s%d-n-1' % ESR, 'slow': SLOW,
                   'seg_sec': round(SEG_D, 3), 'clips': times}, f,
                  ensure_ascii=False, indent=1)


def make_element_pngs():
    src = {'title': 'title', 'inter': 'interlude', 'end': 'end'}
    for name, dur in (('title', TITLE_D), ('inter', INTER_D), ('end', END_D)):
        dst = os.path.join(OVL, name + '_full.png')
        bg = Image.new('RGB', (W, H), (12, 12, 13))
        ov = Image.open(os.path.join(OVL, src[name] + '.png')).convert('RGBA')
        if ov.size != (W, H):          # 预演模式：源图 1920×1080 须先缩到画布，否则被裁掉
            ov = ov.resize((W, H), Image.LANCZOS)
        bg.paste(ov, (0, 0), ov)
        bg.save(dst)
        print('element:', dst, flush=True)


def dur_of(path):
    r = subprocess.run([FF, '-hide_banner', '-i', path], capture_output=True, text=True)
    m = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', r.stderr or '')
    if not m:
        raise RuntimeError('读不到时长: ' + path)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def stage_assemble():
    make_element_pngs()
    # 实际时长（写入成片时间轴；转场位点/字幕窗口都以实测为准）
    adur = {}
    for e in ORDER:
        if e in ('title', 'inter', 'end'):
            adur[e] = DUR[e]
        else:
            adur[e] = dur_of(os.path.join(SEGS, 'seg_%s.mp4' % e))
    total = sum(adur.values()) - XF * (len(ORDER) - 1)

    def pos_act(elem):
        p = 0.0
        for e in ORDER:
            if e == elem:
                return p
            p += adur[e] - XF
        raise KeyError(elem)

    print('实测段长: %s' % {k: round(v, 3) for k, v in adur.items()}, flush=True)
    inputs, fc, labels = [], [], []
    for e in ORDER:
        if e in ('title', 'inter', 'end'):
            inputs += ['-loop', '1', '-framerate', str(FPS), '-t', '%.3f' % adur[e],
                       '-i', os.path.join(OVL, e + '_full.png')]
        else:
            inputs += ['-i', os.path.join(SEGS, 'seg_%s.mp4' % e)]
        i = len(labels)
        fc.append('[%d:v]fps=%d,scale=%d:%d,format=yuv420p,settb=AVTB[v%d]' % (i, FPS, W, H, i))
        labels.append('v%d' % i)
    # xfade 链
    cur, acc = labels[0], 0.0
    for k in range(1, len(labels)):
        prev = ORDER[k - 1]
        acc += adur[prev] - XF
        out = 'vx%d' % k
        fc.append('[%s][%s]xfade=transition=fade:duration=%.3f:offset=%.3f[%s]'
                  % (cur, labels[k], XF, acc, out))
        cur = out
    # 字幕叠加（输入须覆盖到出现时刻 → 全片长；淡入淡出按绝对时间）
    nchain = len(ORDER)  # 前 N 个输入是视频元素
    cur2 = cur
    for j, (name, (elem, off, dur)) in enumerate(SUBWIN.items()):
        inputs += ['-loop', '1', '-framerate', str(FPS), '-t', '%.3f' % total,
                   '-i', os.path.join(OVL, name + '.png')]
        idx = nchain + j
        start = pos_act(elem) + off
        fc.append('[%d:v]scale=%d:%d,format=rgba,fade=t=in:st=%.3f:d=0.7:alpha=1,'
                  'fade=t=out:st=%.2f:d=0.7:alpha=1[s%d]'
                  % (idx, W, H, start, start + dur - 0.7, j))
        out = 'vo%d' % j
        fc.append('[%s][s%d]overlay=0:0:enable=\'between(t,%.3f,%.3f)\'[%s]'
                  % (cur2, j, start, start + dur, out))
        cur2 = out
    # 音频
    inputs += ['-i', BASE + '/audio/gymno1_cc0.ogg']
    aidx = nchain + len(SUBWIN)
    fc.append('[%d:a]loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=2.0,'
              'afade=t=out:st=%.2f:d=3.5,atrim=0:%.3f,asetpts=PTS-STARTPTS[aout]'
              % (aidx, total - 3.5, total))
    script = LOGS + '/compose_filter.txt'
    with open(script, 'w', encoding='utf-8') as f:
        f.write(';\n'.join(fc))
    dst = OUT + ('/样片_preview.mp4' if PREVIEW else '/样片_v1.mp4')
    cmd = [FF, '-y', '-hide_banner', '-loglevel', 'warning', '-stats'] + inputs + [
        '-filter_complex_script', script, '-map', '[%s]' % cur2, '-map', '[aout]',
        '-t', '%.3f' % total, '-r', str(FPS), '-c:v', 'libx264', '-crf', '17',
        '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart', dst]
    print('→ ffmpeg 总装（%d 输入，预计片长 %.1fs）...' % (len(inputs) // 2, total), flush=True)
    t0 = time.time()
    run(cmd)
    print('总装完成 %.1fs → %s (%.1f MB)' % (time.time() - t0, dst,
          os.path.getsize(dst) / 1e6), flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    what = args[0] if args else 'all'
    os.makedirs(LOGS, exist_ok=True)
    if what in ('segments', 'all'):
        stage_segments()
    if what in ('assemble', 'all'):
        stage_assemble()
    print('TOTAL_PLAN=%.1fs  (title %.1f + 13×%.2f + inter %.1f + end %.1f - 15×%.1f)'
          % (TOTAL, TITLE_D, SEG_D, INTER_D, END_D, XF))


if __name__ == '__main__':
    main()
