---
name: anatomy-video
description: 把 Anatomy 等距物件图做成带配音、字幕、配乐的讲解视频，主要用于芯片硬件拆解系列（GPU、CPU、TPU、XPU 等，例如“硬核拆解英伟达 GPU”）。包含参数核对、配音（豆包语音合成，自带字级时间）、读音表、成片页时间轴、预检、低清预览、分块并行渲染、只重渲改动片段、检查合一、抽帧自评、封面片头和最终合成。用户要做或修改这类视频的任何一集、提到分镜、配音、读法、渲染、出框、静止段、封面、片头时使用。画物件图本身用 anatomy skill。
---

# Anatomy 物件图讲解视频

画法交给 `anatomy` skill（物件图 `build.mjs`，每张都过 `--audit` 和 `lines.mjs`）；本 skill 管从参数到成片的整条流水线。
规矩的分工：AGENTS.md 管时间和呈现，Anatomy 管画法，每集的《参数口径表》管内容。细则见 `references/视频版规范.md`。

## 原则

1. 问题在便宜的阶段发现：能在稿子和时间轴上查出来的不等渲染；能在低清预览上查出来的不等高清。
2. 一轮查全、一轮修全：每次检查都跑完全部项目，全部修完再往下走。
3. 用户不做质检：给用户看的东西必须已经过了全部自动检查。
4. 整片高清只渲一次；之后只重渲变了的块。
5. 预计超过 5 分钟的渲染、合成，先告诉用户原因和时长。
6. 一切文件、缓存、临时目录都在 F 盘。

## 用户只看两次（参数由我核对后直接用）

| 关口 | 给用户看什么 | 用户定什么 |
|---|---|---|
| 1 文稿 + 试读 | 配音稿、约 30 秒试读音频（只含新术语）、《读法对照》、低清预览 | 读法定死（写回读音表）、内容 |
| 2 成片 | 成片、封面、抽帧图、六项自评和最严重的 3 个问题 | 是否发布、修改意见 |

## 流程（命令都在 `scripts/`，用 `S=<本 skill 所在目录>/scripts`）

浏览器工具统一用 `uv run --with playwright==1.63.0 [--with pillow --with numpy] python …`（版本号不能省，见已知坑）。断网时加 `--offline`（包都缓存在 F 盘）。

0. **开工自检**：`doctor.py --tts`。全部通过再开始。
1. **参数**：资料和参考图可交给子 agent 搜集（只收链接，下载前问用户）；调研完把 C 盘 tool-results 里缓存的 PDF 移到 `research/pdf` → 自己核对、复算后直接采用（用户 2026-10-15 定：核对过就用，不用问）；只有会改变讲法的官方冲突才找用户。
2. **配音稿**：读法写法写进 `voice/script.txt`（H一百、吉字节……）。
   `terms.py voice/script.txt build/terms` → 禁用写法必须改完；新术语自动生成 `_试读.txt`。
   `tts.py build/terms_试读.txt build/trial` → 试读音频 + 读法对照 → 关口 1。确认后写回 `references/读音表.md`。
3. **整片配音**：`tts.py voice/script.txt voice/voice`（一次合成，约 1–2 分钟）→ 看 `voice.readings.txt`。
   之后配音锁定；再改配音要先告诉用户“从这一步重来、约多少分钟”。
4. **时间轴**：`make_timeline.py voice/voice.timing.json voice/script.txt voice/voice.mp3 cut/timeline.js`
5. **成片页**：照 `templates/composer_example.html` 写 `cut/index.html`，遵守 `references/成片页约定.md`。
   每句话都要有“画面上出现什么”（镜头、点亮、文字），写进镜头代码。
6. **预检**（几十秒，不渲染）：`preflight.py --root 系列目录 --page ep/cut/index.html --params ep/参数口径表.md`
   错误归零；提醒逐条看（空拍、重复锚点、找不到出处的数字）。
7. **低清预览**（约 1 分钟）：`render.py --root … --page … --dir ep/build/preview --preview`
   **检查合一**（约 5 分钟）：`checks.py --root … --page … --video ep/build/preview/out.mp4`
   出框、静止 > 4 秒、文字叠字、文字压物件、孤字折行、有状态 → 全部修完；修完用 `--diff` 重跑预览，只看变了的区间。
   预览发给用户（关口 1 一起看）。
8. **高清**（约 5 分钟，4 路并行）：`render.py --root … --page … --dir ep/build/hd`
   `checks.py --video ep/build/hd/out.mp4`（最后防线，应当全过）。
9. **配乐**：`mix.py voice/voice.mp3 build/mix.wav --lead 3 --pad 0.5`（--pad 与 make_timeline 的 --lead 相同）
   **封面和片头**：`cover.py --root … --figsrc anatomy/<物件>/<物件>-light.html --pose '{…}' --series … --ep … --name … --sub … --meta … --png 封面.png --intro build/intro.mp4`
   **合成**：`final.py --intro build/intro.mp4 --video build/hd/out.mp4 --audio build/mix.wav --out 成片.mp4 --lead 3`
10. **自评**：`sheet.py 成片.mp4 build/sheet --cuts <预检打印的切点> --lead 3` → 抽帧、转场中点、手机样张。
    按 AGENTS.md 六项打分，列最严重的 3 个问题；任一项低于 8 分回到第 7 步改相关片段 → 关口 2。

## 改动分档（不要小改也走全套）

| 改了什么 | 从哪一步重来 |
|---|---|
| 文字栏措辞、点亮、镜头推拉 | 预检 → 预览 `--diff` → 高清 `--only <变了的区间>` → final |
| 物件图（build.mjs） | audit → 预览 `--diff` → 高清 `--only` → final |
| 配音稿 | 第 2 步（只试读新词）→ 之后全部；整片重渲，先告诉用户 |
| 参数 | 自己重新核对，再看影响到稿子还是只影响文字栏 |

## 参考

- `references/视频版规范.md`：画面、指认、读数、动作节奏、配音、不出框、质检、文件组织
- `references/成片页约定.md`：成片页必须提供的接口和写镜头的 8 条规矩
- `references/读音表.md`：全系列共用读法；每集新增写回
- `references/已知坑.md`：踩过的坑和拦它的检查；新坑写在最上面，尽量配一项自动检查
- `templates/composer_example.html`：第 01 集 H100 成片页；`templates/cover.html`：系列封面模板
