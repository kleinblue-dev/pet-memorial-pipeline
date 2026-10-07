# pet-memorial-pipeline

把 15–30 张宠物照片做成一支 1.5–3 分钟的 1080p 纪念短片。
全流程本地运行：照片修复 → AI 让照片轻微动起来 → 升清/插帧/慢放 → 配乐与字幕合成。

> A fully-local pipeline for making pet memorial videos from photos
> (restoration → subtle AI motion via Wan2.1-VACE → upscale/interpolate → score & subtitles).

演示样片（13 张公开授权素材，96.9 秒）：B站 [BV16bHy6mEqn](https://www.bilibili.com/video/BV16bHy6mEqn)

## 实测数据（2026-10-07，Windows / RTX 4050 Laptop 6GB）

| 阶段 | 单件实测 | 13 张合计 |
|---|---|---|
| 1 选图（Openverse API，42 张里挑 13） | — | 189 秒 |
| 2 修复（Real-ESRGAN x4） | ~7 秒/张 | 106 秒 |
| 3 活化（Wan2.1-VACE-1.3B，每张 61 帧微动） | 551–603 秒/张 | 123 分钟 |
| 4 升清+插帧+慢放（Real-CUGAN x2 → 1080p/30fps） | 118–127 秒/张 | 26 分钟 |
| 5 总装（ffmpeg 一次成型） | — | 54.2 秒 |

**每张照片全流程约 11.7 分钟机器时间**（其中第 3 步占八成以上），单条片段显存峰值 5697/6141 MiB。
完整过程与翻车记录见 [docs/measured-2026-10-07.md](docs/measured-2026-10-07.md)。

## 管线五阶段

| 阶段 | 脚本 | 输入 → 输出 |
|---|---|---|
| 1 素材采集 | `tools/fetch_photos.py`、`tools/search_music.py` | Openverse / Wikimedia Commons → `src/raw/` + 来源清单 |
| 1.5 人工挑选 | `tools/make_sheet.py` | 总览拼图（目检筛选） |
| 2 修复与规格化 | （放大工具，见下）+ `tools/prep_masters.py` | `src/restored/` → `prepped/*_1080.png` + `prepped/vace/*_832.jpg` |
| 3 AI 活化 | `tools/pet_run.py`（调 ComfyUI API） | `prepped/vace/` → `clips/pNN.mp4`（61 帧 @16fps） |
| 3.5 质检 | `tools/qc_clip.py`、`tools/qc_all.py` | 帧序条 + 相邻帧差 + 首帧锚定 → `out/qc/` |
| 4 升清/插帧/合成 | `tools/compose.py`（segments / assemble） | `clips/` → `segments/` → 成片 mp4 |
| 字幕与片头片尾 | `tools/make_overlays.py` | 透明 PNG 贴图 |
| 5 交付 | `tools/deliver.py` | 成片 + 附件 + 耗时记录 → 桌面 |

数据目录（默认=仓库根，可用 `PETDEMO_DIR` 覆盖）：

    src/raw/          原图（下载）
    src/restored/     修复后图
    prepped/          1920x1080 规格图 + vace/ 832x480 输入
    clips/            I2V 片段
    segments/         升清插帧后的片段
    out/              成片与质检图
    logs/             运行记录 JSON

仓库本体只含 `tools/` 与 `docs/`，数据目录按需生成。

## 环境依赖

- **ComfyUI**（需含以下节点）：`WanVACEFirstMiddleLast`、`WanVaceToVideo`、
  `VHS_VideoCombine`（VideoHelperSuite）、`UnetLoaderGGUF` / `CLIPLoaderGGUF`（ComfyUI-GGUF）
- **模型三件**（放入 ComfyUI 对应目录）：
  - `models/diffusion_models/Wan2.1-VACE-1.3B-Q4_K_M.gguf`
  - `models/text_encoders/umt5-xxl-encoder-Q4_K_M.gguf`
  - `models/vae/wan_2.1_vae.safetensors`
- **ffmpeg**（可用 `FFMPEG` 指完整路径）
- **Python**：仅需 `Pillow`，其余为标准库
- **升清工具**（二选一或都装）：
  - 照片修复：`realesrgan-ncnn-vulkan -i in.jpg -o out.png -s 4`（**必须 -s 4**，原因见坑表）
  - 视频逐帧升清：`realcugan-ncnn-vulkan -i f.png -o u.png -s 2 -n -1`

## 环境变量

| 变量 | 默认 | 用途 |
|---|---|---|
| `PETDEMO_DIR` | 仓库根目录 | 数据根目录 |
| `FFMPEG` | `ffmpeg` | ffmpeg 可执行文件 |
| `REALCUGAN` | `realcugan-ncnn-vulkan` | 视频升清引擎 |
| `COMFYUI_DIR` | `D:/ComfyUI_windows_portable/ComfyUI` | ComfyUI 安装目录 |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | ComfyUI API 地址 |
| `NVIDIA_SMI` | `nvidia-smi` | 显存采样 |
| `FETCH_PROXY` | 空（直连） | 境外素材站代理，如 `http://127.0.0.1:7892` |
| `DESKTOP_DIR` | `~/Desktop` | 交付输出目录 |
| `FONT_PATH` | `C:/Windows/Fonts/msyh.ttc` | 对比图字体 |

## 快速开始

```bash
# 0) 启动 ComfyUI（装好上面的节点与模型三件）
# 1) 采集候选素材（先改 fetch_photos.py 顶部 QUERIES 为你的检索词）
python tools/fetch_photos.py
python tools/make_sheet.py        # 看总览拼图，人工挑图
# 2) 修复每张图（Real-ESRGAN x4），产物放 src/restored/
realesrgan-ncnn-vulkan -i src/raw/big_04.jpg -o src/restored/big_04_x4.png -s 4
# 3) 规格化 + 生成 832x480 的 VACE 输入（先改 prep_masters.py 里的 JOBS）
python tools/prep_masters.py
# 4) 逐张活化（每条约 10 分钟）；JOBS 里改图片清单与提示词
python tools/pet_run.py all
python tools/qc_all.py            # 质检，应全部 PASS
# 5) 字幕/片头片尾贴图（改 make_overlays.py 里的文字）
python tools/make_overlays.py
# 6) 升清 + 插帧 + 总装
python tools/compose.py segments
python tools/compose.py assemble
# 7) 交付包（成片 + 附件 + 耗时记录）
python tools/deliver.py
```

## 坑与经验（都是实测踩出来的）

1. **Real-ESRGAN 的 `-s 2` 会输出「拼贴错图」**（画面被切成错位拼贴块，`-t 256` 同样坏），
   `-s 4` 正常但慢约 15 倍。影片逐帧升清建议改用 Real-CUGAN `-s 2 -n -1`
   （约 1.2 秒/帧；三路目检：CUGAN ≈ ESRGAN x4 > Lanczos）。
2. **minterpolate 重建会丢尾帧**：计划 6.91 秒的片段实测成 6.80 秒。
   转场偏移、字幕窗口、音画总长必须以**实测时长**驱动，否则全片逐段漂移
   （见 `compose.py` 的 `dur_of()`）。
3. **喂给 VACE 的图先降到 832x480**（lanczos + center）。
   6GB 显存跑 61 帧 / 20 步 / CFG 5 稳定，显存峰值约 5.7GB。
4. **源图越"空"越容易脑补**：纯白、无纹理的图容易生成不存在的内容，
   挑素材时避开大面积纯色背景。
5. **VACE 的 GGUF 必须校验张量齐全**：曾遇到第三方转换缺 `vace_patch_embedding.weight`
   （437 个张量全丢）——加载"成功"但画面全是噪声。文件大小吻合 ≠ 张量齐全。
6. **Openverse 直连可能不通**（境外）→ 设 `FETCH_PROXY`；
   配乐站 FreePD 已关站，可改用 Wikimedia Commons（公有领域，含 Satie《Gymnopedie No.1》）。
7. **不要写夸张动作提示词**：纪念片要的是"呼吸感"——眨眼、耳朵轻颤、毛发被风轻拂。
   动作幅度一小，画面才稳。（`pet_run.py` 的 NEG 负面词表可直接复用）
8. **批量渲染要串行**：每条约 9–10 分钟、显存峰值 ~5.7/6GB，别开并发。

## 许可

- 代码：MIT License（见 LICENSE）。模型与依赖各自遵循其发布许可（如 Wan2.1 为 Apache-2.0）。
- 本仓库不含任何模型文件与素材；示例运行所用照片来自 CC0/公有领域图库、音乐为公有领域作品。
- 用途提醒：请仅用于合法、正当的纪念类用途；不要用于未经许可的真人/名人活化，
  勿用于侵权或引人误导的场景。
