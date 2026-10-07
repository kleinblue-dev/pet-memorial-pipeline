# -*- coding: utf-8 -*-
"""pet_run.py — 宠物纪念样片 I2V 运行器（Wan2.1-VACE-1.3B 修复版 GGUF）。

配方与 2026-10-06《沉入光里》净版重建（gen_i2v.py）同源：
  832×480 / 63 帧 / 16fps / 20 步 / cfg 5.0 / euler+simple / WanVACEFirstMiddleLast(first=图)
输入换成 prepped/vace/pNN_832.jpg（16:9 宠物照）。
用法: python -X utf8 tools/pet_run.py p05 [p06 ...] | all
产出: clips/<id>.mp4 + logs/pet_runs.json（逐条追加：状态/耗时/显存/md5）
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

# 全部路径可用环境变量覆盖（见 README「环境变量」表）
COMFY_DIR = os.environ.get('COMFYUI_DIR', 'D:/ComfyUI_windows_portable/ComfyUI')
COMFY_IN = COMFY_DIR + '/input'
COMFY_OUT = COMFY_DIR + '/output'
PET = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLIPS = PET + '/clips'
VACE_DIR = PET + '/prepped/vace'
RUNS = PET + '/logs/pet_runs.json'
COMFY = os.environ.get('COMFYUI_URL', 'http://127.0.0.1:8188')
NVIDIA = os.environ.get('NVIDIA_SMI', 'nvidia-smi')

UNET = 'Wan2.1-VACE-1.3B-Q4_K_M.gguf'
TE = 'umt5-xxl-encoder-Q4_K_M.gguf'
VAE = 'wan_2.1_vae.safetensors'
WIDTH, HEIGHT, LENGTH, FPS = 832, 480, 63, 16.0
STEPS, CFG = 20, 5.0

NEG = ('色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，'
       '最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，'
       '画得不好的脸部，畸形的，毁容的，形态畸形的肢体，静止不动的画面，'
       '杂乱的背景，三条腿，倒着走，猫，变形，扭曲，融化，重影，模糊，多余的腿，'
       '多余的动物，脸部变形，多只动物，画面晃动，镜头抖动')

JOBS = {
    'p01': ('big_04_x4 幼犬趴白毯睡觉', 71001,
            '镜头完全固定；白色毛毯上的金色幼犬安静趴着睡觉，胸口随呼吸轻微起伏，'
            '耳朵轻轻颤动一下，眼睛缓慢眨一次；毛发柔软自然，动作幅度极小，画面平稳无跳变。'),
    'p02': ('big_25_x4 幼犬绿背景坐像', 71002,
            '镜头完全固定；金色幼犬面向镜头安静坐着，缓缓眨一次眼，耳朵轻轻抖动，'
            '嘴边绒毛被微风轻拂；动作幅度极小，画面平稳无跳变。'),
    'p03': ('big_22_x4 沙滩上走来', 71003,
            '镜头完全固定；小狗踩着沙滩慢慢向前走了一小段，尾巴轻轻摆动，'
            '身后细浪缓缓漫上又退下，毛发被海风轻轻吹动；动作舒缓自然，画面平稳。'),
    'p04': ('big_06_x4 成年犬侧脸', 71004,
            '镜头完全固定；小狗侧脸安静站着，轻轻喘气，舌头微微晃动，缓缓眨一次眼，'
            '耳朵轻轻动了一下；动作幅度极小，画面平稳无跳变。'),
    'p05': ('big_01_x4 庭前坐像', 71005,
            '镜头完全固定；小狗安静坐着看向镜头，缓缓眨一次眼，头轻轻偏了一下，'
            '耳朵微微抖动；动作幅度极小，画面平稳无跳变。'),
    'p06': ('big_13_x4 林间回望', 71006,
            '镜头完全固定；小狗坐在林地里，慢慢转头望向一侧，耳朵轻轻抖动，'
            '树叶间光斑轻轻闪烁，毛发被微风轻吹；动作舒缓自然。'),
    'p07': ('big_14_x4 草地奔跑', 71007,
            '镜头缓慢跟随；小狗在草地上奔跑追逐，四肢动作自然舒展，草地随风轻摆；'
            '动作流畅舒缓，画面平稳。'),
    'p08': ('big_12_x4 草地趴卧', 71008,
            '镜头完全固定；小狗趴在草地上轻轻喘气，尾巴尖缓缓摆动，草叶被微风轻晃，'
            '毛发轻轻浮动；动作舒缓自然，画面平稳。'),
    'p09': ('big_19_x4 干草旁休息', 71009,
            '镜头完全固定；小狗趴在干草堆旁休息，胸口随呼吸轻微起伏，耳朵轻轻动了一下，'
            '尾巴尖缓慢摆动；动作幅度极小，画面平稳。'),
    'p10': ('big_24_x4 低头抬眼', 71010,
            '镜头完全固定；小狗趴着，缓缓低下头又轻轻抬眼看了一下，眨了一次眼，'
            '毛发被风轻吹；动作舒缓轻柔，画面平稳。'),
    'p11': ('big_33_x4 年老坐像', 71011,
            '镜头完全固定；年长的小狗趴在石阶上晒太阳，缓慢眨了一次眼，耳朵轻轻动了一下，'
            '胸口随呼吸轻轻起伏，毛发被微风轻拂；动作幅度极小，画面平稳。'),
    'p12': ('big_23_x4 落日海滩', 71012,
            '镜头缓慢向前推近；小狗静静站在落日海滩上望着海面，尾巴轻轻摆动，'
            '海浪缓缓来去，逆光下毛发边缘轻轻闪动；动作舒缓，画面平稳。'),
    'p13': ('big_32_x4 暖光仰头', 71013,
            '镜头缓慢向前推近；小狗仰起头沐浴在暖光里，毛发被风轻轻吹动，'
            '缓缓闭上眼睛再睁开，光线柔和流动；动作轻柔舒缓，画面平稳。'),
}

vram_samples = []
stop_ev = threading.Event()


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def get(url):
    return urllib.request.urlopen(url, timeout=30)


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=30)


def build_wf(prefix, seed, prompt, image_name):
    return {
        '1': {'class_type': 'LoadImage', 'inputs': {'image': image_name}},
        '2': {'class_type': 'ImageScale', 'inputs': {
            'image': ['1', 0], 'upscale_method': 'lanczos',
            'width': WIDTH, 'height': HEIGHT, 'crop': 'center'}},
        '3': {'class_type': 'WanVACEFirstMiddleLast', 'inputs': {
            'width': WIDTH, 'height': HEIGHT, 'length': LENGTH,
            'middle_position': 0.5, 'first': ['2', 0]}},
        '6': {'class_type': 'CLIPLoaderGGUF', 'inputs': {'clip_name': TE, 'type': 'wan'}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['6', 0], 'text': prompt}},
        '8': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['6', 0], 'text': NEG}},
        '9': {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': UNET}},
        '10': {'class_type': 'VAELoader', 'inputs': {'vae_name': VAE}},
        '11': {'class_type': 'WanVaceToVideo', 'inputs': {
            'positive': ['7', 0], 'negative': ['8', 0], 'vae': ['10', 0],
            'width': ['3', 2], 'height': ['3', 3], 'length': ['3', 4],
            'batch_size': 1, 'strength': 1.0,
            'control_video': ['3', 0], 'control_masks': ['3', 1]}},
        '12': {'class_type': 'KSampler', 'inputs': {
            'model': ['9', 0], 'positive': ['11', 0], 'negative': ['11', 1],
            'latent_image': ['11', 2], 'seed': seed, 'steps': STEPS, 'cfg': CFG,
            'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        '13': {'class_type': 'VAEDecode', 'inputs': {'samples': ['12', 0], 'vae': ['10', 0]}},
        '14': {'class_type': 'VHS_VideoCombine', 'inputs': {
            'images': ['13', 0], 'frame_rate': FPS, 'loop_count': 0,
            'filename_prefix': prefix, 'format': 'video/h264-mp4',
            'pingpong': False, 'save_output': True}},
    }


def precheck():
    problems = []
    for f in (COMFY_DIR + '/models/diffusion_models/' + UNET,
              COMFY_DIR + '/models/text_encoders/' + TE,
              COMFY_DIR + '/models/vae/' + VAE):
        if not os.path.isfile(f):
            problems.append('缺模型文件: ' + f)
    try:
        json.loads(get(COMFY + '/object_info/WanVACEFirstMiddleLast').read())
        json.loads(get(COMFY + '/object_info/WanVaceToVideo').read())
        json.loads(get(COMFY + '/object_info/VHS_VideoCombine').read())
    except Exception as e:
        problems.append('预检请求失败: %s' % e)
    return problems


def sample_thread():
    while not stop_ev.is_set():
        try:
            line = subprocess.run(
                [NVIDIA, '--query-gpu=memory.used,memory.total,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception as e:
            line = 'ERR,' + str(e)
        vram_samples.append((time.time(), line))
        time.sleep(0.5)


def collect_files(done):
    out = []
    for nid, o in (done.get('outputs') or {}).items():
        for k, v in o.items():
            if isinstance(v, list):
                for it in v:
                    if isinstance(it, dict) and 'filename' in it:
                        out.append((nid, it))
    return out


def run_one(pid):
    name, seed, prompt = JOBS[pid]
    src = os.path.join(VACE_DIR, '%s_832.jpg' % pid)
    dest = os.path.join(CLIPS, '%s.mp4' % pid)
    if not os.path.isfile(src):
        print('[!] 缺输入图: ' + src, flush=True)
        return {'id': pid, 'status': 'NO-INPUT'}
    t0 = time.time()
    in_name = 'pet_%s.jpg' % pid
    shutil.copy(src, os.path.join(COMFY_IN, in_name))
    rec = {'id': pid, 'name': name, 'seed': seed, 'prompt': prompt,
           'input_src': src, 'input_md5': md5(src), 'started': time.strftime('%Y-%m-%d %H:%M:%S')}
    wf = build_wf('pet_i2v_%s' % pid, seed, prompt, in_name)
    print('=== %s（%s）seed=%s 提交 %s' % (pid, name, seed, time.strftime('%H:%M:%S')), flush=True)
    try:
        r = post(COMFY + '/prompt', {'prompt': wf, 'client_id': 'pet-demo'})
        resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        print('   提交被拒 HTTP %s %s' % (e.code, body[:1500]), flush=True)
        rec.update(status='SUBMIT-REJECTED', error=body[:1500], elapsed_sec=round(time.time() - t0, 1))
        return rec
    if resp.get('node_errors'):
        print('   node_errors:', json.dumps(resp['node_errors'], ensure_ascii=False)[:1500], flush=True)
    pidp = resp.get('prompt_id')
    rec['prompt_id'] = pidp
    done, last = None, 0
    while time.time() - t0 < 2400:
        time.sleep(3)
        try:
            h = json.loads(get(COMFY + '/history/' + pidp).read())
        except Exception:
            continue
        if pidp in h and h[pidp].get('status', {}).get('completed'):
            done = h[pidp]
            break
        el = time.time() - t0
        if el - last > 60:
            last = el
            print('   ...%s 进行中 %.0fs' % (pid, el), flush=True)
    elapsed = time.time() - t0
    rec['elapsed_sec'] = round(elapsed, 1)
    if done is None:
        rec['status'] = 'TIMEOUT'
        print('   [!] %s 超时' % pid, flush=True)
        return rec
    st = done.get('status', {})
    rec['status'] = st.get('status_str')
    err = ''
    for m in st.get('messages', []):
        if m[0] in ('execution_error', 'execution_interrupted'):
            err += json.dumps(m[1], ensure_ascii=False)[:2000] + '\n'
    rec['error'] = err or None
    files = [it for n, it in collect_files(done) if it.get('filename', '').lower().endswith('.mp4')]
    print('   status = %s, 耗时 %.1fs' % (rec['status'], elapsed), flush=True)
    if err:
        print('   [!] 错误:', err[:1200], flush=True)
    if rec['status'] == 'success' and files:
        s = os.path.join(COMFY_OUT, files[0].get('subfolder') or '', files[0]['filename'])
        shutil.copy(s, dest)
        rec['copied'] = {'file': dest, 'bytes': os.path.getsize(dest), 'md5': md5(dest),
                         'md5_eq_comfy': md5(s) == md5(dest)}
        print('   已复制 → %s (%d B)' % (dest, os.path.getsize(dest)), flush=True)
    else:
        rec['status'] = rec['status'] or 'NO-OUTPUT'
    return rec


def main():
    os.makedirs(CLIPS, exist_ok=True)
    args = sys.argv[1:]
    if not args:
        print('用法: pet_run.py p05 | all')
        sys.exit(2)
    ids = list(JOBS) if args[0] == 'all' else args
    problems = precheck()
    if problems:
        print('[0] 预检未通过:')
        for p in problems:
            print('   -', p)
        sys.exit(2)
    print('[0] 预检通过（模型三件 + VACE 节点）', flush=True)
    th = threading.Thread(target=sample_thread, daemon=True)
    th.start()
    results = []
    for pid in ids:
        rec = run_one(pid)
        results.append(rec)
        old = []
        if os.path.isfile(RUNS):
            try:
                old = json.load(open(RUNS, encoding='utf-8')).get('runs', [])
            except Exception:
                pass
        old = [r for r in old if r.get('id') != pid] + [rec]
        uses = []
        for ts, line in vram_samples:
            try:
                uses.append(int(line.split(',')[0]))
            except Exception:
                pass
        json.dump({'runs': old, 'vram_max_mib': max(uses) if uses else None},
                  open(RUNS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('   [累计] vram_max=%s MiB' % (max(uses) if uses else '?'), flush=True)
    stop_ev.set()
    th.join(timeout=2)
    print('PET-RUN-DONE ' + ' '.join('%s=%s(%.0fs)' % (r['id'], r.get('status'), r.get('elapsed_sec', -1))
                                     for r in results), flush=True)


if __name__ == '__main__':
    main()
