# media-transcriber

把本地视频或音频整理为完整、易读、可回查的书面稿，同时保留原音轨、未经校订的原始转写，以及实际存在的字幕。视频按内容需要配真实关键帧；纯音频沿用文本结构，跳过图片处理。

这是一个通用的媒体转写与整理技能，包含流程说明和本地处理脚本。脚本负责音轨提取、语音识别、原始稿导出、字幕保全、抓图和结构校验；完整内容理解、书面编辑、关键帧选择与章节索引由执行者结合这些工具完成。仅运行 `prepare` 或 `transcribe` 不会自动生成最终书面稿。

## 1. 快速使用

入口为 [SKILL.md](SKILL.md)。将 `media-transcriber/` 放在工作目录或执行环境支持的技能目录中。支持文件读取、命令执行和内容理解的工具可以读取入口说明并完成流程；也可按第 6 节手动运行脚本，再完成书面编辑和校核。

处理一个视频：

```text
请读取 media-transcriber/SKILL.md，按技能处理：
原视频/示例课程/01.基础概念.mp4
输出到当前项目的 output，完整整理讲解内容并保留原始证据。
```

处理一个课程目录：

```text
请读取 media-transcriber/SKILL.md，处理“原视频/示例课程”
目录下的所有视频，按原目录名加“学习”分组输出到 output。
已有完整结果先核对，不覆盖原始转写和字幕。
```

处理音频：

```text
请读取 media-transcriber/SKILL.md，处理“原音频/课程/讲解.mp3”。
输出完整音频书面稿和带时间戳的原始稿，保留音轨与章节索引，跳过图片目录。
```

以上为通用请求示例。源文件可以是相对工作目录的路径或绝对路径，技能文件路径按实际放置位置调整。

## 2. 功能与整理原则

| 功能 | 实际行为 |
| --- | --- |
| 视频与音频读取 | 支持 FFmpeg 可读取的媒体，常见格式包括 MP4、MOV、MKV、MP3、M4A、WAV、FLAC、OGG、OPUS |
| 原音轨保全 | FFmpeg 以 `-c:a copy` 复制选定音轨，不重新编码；另生成临时 ASR WAV |
| 完整语音转写 | 默认使用本地 faster-whisper，保存完整原始识别 JSON 与带轴 Markdown |
| 原字幕保存 | 已有字幕文件按字节复制；内嵌文本轨按编码提取，必要格式转换记录在索引中 |
| 烧录字幕读取 | 视频有画面字幕时使用 OCR，单独保存其结果及抽样精度 |
| 精选关键帧 | 保留帮助理解的 PPT、图示、代码状态、操作结果等真实画面，不对每句口播截图 |
| 完整书面化 | 清理无意义口语、理顺语法与段落，保留论证、例子、数字、条件、反例及结论 |
| 回查与校核 | 用章节索引关联原始段、正文、字幕和图片，检查文件路径、哈希与覆盖情况 |

书面稿保留讲师原意、判断强度和归属，不添加外部知识或整理者观点。讲师自行纠正的内容在书面稿中采用最终表述，原始稿保留完整过程。无法确认的内容保留 `[听不清]`、`[术语待确认]` 等标记，修订依据写入索引。

最终书面稿不含时间戳、原课位置、处理说明或编辑者附加的总结段落。默认不重复生成学习笔记、TXT、Word 或 ASR 字幕；需要额外格式时须明确提出。

## 3. 输出路径规则

默认输出到项目的 `output/`。媒体名称使用源文件名去掉扩展名，保留其编号与文字。

| 输入位置 | 默认输出位置 |
| --- | --- |
| `原视频/示例课程/01.基础概念.mp4` | `output/示例课程学习/01.基础概念/` |
| `原音频/课程/讲解.mp3` | `output/课程学习/讲解/` |
| 项目根的 `单篇.wav` | `output/单篇/` |
| `课程学习/讲解.mp3` | `output/课程学习/讲解/`，不重复追加“学习” |

默认采用源文件的直接父目录名。多层目录需要按上层课程分组时，可以在请求中指定课程名，或在脚本中使用 `--group`。脚本以输出根 `--root` 的父目录作为项目根；其他位置的散文件可用 `--ungrouped`。

不同课程中的同名媒体会分开保存。同一课程内若视频和音频去扩展名后同名，需用 `--lesson` 指定不同的单篇目录名。更新技能不会自动迁移历史交付；迁移资料时还要调整索引里的源文件路径。

## 4. 最终目录结构

### 视频

```text
output/
└── 课程学习/
    └── 教程/
        ├── 音频书面稿.md
        ├── images/                        仅实际引用图片时创建
        ├── 原始层/
        │   ├── 原始音频逐字稿.md
        │   ├── 原视频字幕.srt              可选，保留原来源扩展名
        │   ├── 原视频字幕_OCR.srt          可选，仅画面字幕 OCR
        │   └── 关键帧截图/                仅有精选信息画面时创建
        └── temp/
            ├── chapters.json
            ├── audio/
            │   └── original_audio.m4a     扩展名按原音频编码选择
            ├── transcripts/
            │   └── raw_asr.json
            └── process/
                └── media_info.json
```

### 纯音频

```text
output/
└── 课程学习/
    └── 讲解/
        ├── 音频书面稿.md
        ├── 原始层/
        │   ├── 原始音频逐字稿.md
        │   └── 原音频字幕.srt              可选，有原字幕才保留
        └── temp/
            ├── chapters.json
            ├── audio/
            │   └── original_audio.mp3     扩展名按原音频编码选择
            ├── transcripts/
            │   └── raw_asr.json
            └── process/
                └── media_info.json
```

纯音频不生成 `images/`、`关键帧截图/` 或 OCR 图片目录。MP3、M4A 中的封面不会被当成视频画面。有用的校订依据、OCR 数据可另保留在 `transcripts/`；不创建空文件或空目录。

### 各种文字资源的区别

| 文件 | 来源与用途 | 编辑规则 |
| --- | --- | --- |
| `音频书面稿.md` | 用于连续阅读的完整书面化讲解，无时间轴 | 清理口语、修复语法，忠实保留实质信息 |
| `原始音频逐字稿.md` | 原始 ASR 文字与段级起止时间，用于定位回听 | 只排版和转义显示语法，不纠错、润色或繁简转换 |
| `raw_asr.json` | 完整机器识别数据，含时间轴、识别参数等 | 保全原始结果，不用校订稿替换 |
| `原视频字幕.*` / `原音频字幕.*` | 实际存在的字幕文件或媒体字幕轨 | 已有文件按字节复制，内嵌轨的必要转换另作记录 |
| `原视频字幕_OCR.srt` | 从画面字幕识别得到的文字与估算时间轴 | 与 ASR 分开保存，不用音频识别结果补写 |
| `chapters.json` | 章节、原始段与正文对应关系，图片关联、修订依据及校核记录 | 放在 `temp/`，用于检索和后期校对 |

“原始逐字稿”表示未经编辑的机器识别结果，仍可能存在错字或漏识别；OCR 字幕也可能有识别误差，时间边界受抽样间隔影响。已有原字幕文件的字节保全、ASR 未编辑和内容逐字准确是不同的检查事项。

## 5. 依赖与技术

| 组件 | 用途 |
| --- | --- |
| Python 3 | 运行辅助脚本，建议使用 Python 3.12 并检查 ASR 依赖兼容性 |
| FFmpeg、FFprobe | 检查媒体轨道、提取音轨、转换 ASR 音频、导出字幕和抓图 |
| faster-whisper | 默认本地 ASR 引擎；依赖见 `scripts/requirements-asr.txt` |
| macOS Vision、AppKit、Swift 工具链 | 仅内置画面字幕 OCR 脚本需要 |
| 内容理解与编辑能力 | 由执行者或所用工具完成全文理解、文本校核、书面编辑、画面选择和索引建立 |

音轨提取和默认 ASR 在本机执行。首次使用 Whisper 模型通常需要下载模型，已有缓存时可复用。转写脚本默认配置为 `small`、`cpu`、`int8`、中文、8 线程；语言、模型和计算参数可通过命令行调整，困难内容可用更合适的模型或片段复核。

原音轨采用 stream copy。AAC/ALAC 保存为 M4A，MP3、FLAC、Opus、Vorbis 使用对应容器，PCM 保存为 WAV，其他可复制编码使用 MKA。输出容器的文件字节可能与源文件不同，原编码音频数据不作二次压缩。

临时 `asr_audio.wav` 为 16 kHz、单声道、16-bit PCM，仅供识别。完成后可删除；用于保全原音轨的 `original_audio.wav` 应保留。

macOS 缺少 FFmpeg 时，可用 Homebrew 安装：

```bash
brew install ffmpeg
```

在项目根目录建立独立 ASR 环境：

```bash
python3 -m venv /tmp/media-asr-env
/tmp/media-asr-env/bin/python -m pip install -r media-transcriber/scripts/requirements-asr.txt
```

该路径位于系统临时目录，环境被清理后需要重新创建。模型和环境不放进每篇交付目录。

## 6. 手动运行辅助脚本

以下命令在包含 `media-transcriber/` 的项目根目录运行。先替换源文件与输出根的示例路径。

### 6.1 准备媒体与确认输出路径

```bash
media_source='/项目/原视频/课程/教程.mp4'
media_output_root='/项目/output'

media_preparation_json=$(python3 -B media-transcriber/scripts/media.py prepare \
  "$media_source" --root "$media_output_root")

lesson_dir=$(printf '%s' "$media_preparation_json" | python3 -c \
  'import json, sys; print(json.load(sys.stdin)["lesson_directory"])')
```

`prepare` 只生成原音轨、临时 ASR WAV 与媒体信息 JSON。其返回值还包含 `media_type`、音轨选择、源哈希和时长。后续命令使用返回的 `lesson_dir`，避免重新猜测课程目录名称。

| 参数 | 用途 |
| --- | --- |
| `--root` | 指定输出根，必填 |
| `--group '课程名'` | 指定课程分组名，自动处理“学习”后缀 |
| `--ungrouped` | 直接输出到输出根下，不建立课程分组；与 `--group` 互斥 |
| `--lesson '单篇名称'` | 自定义单篇目录名，不可包含路径分隔符 |
| `--audio-index 0` | 选择音频轨，按音频轨从 0 编号，默认第一条 |

音频使用同一条命令，将 `media_source` 换为 MP3、WAV 等文件即可。

### 6.2 转写并导出原始稿

```bash
/tmp/media-asr-env/bin/python -B media-transcriber/scripts/transcribe.py \
  "$lesson_dir/temp/audio/asr_audio.wav" \
  --output "$lesson_dir/temp/transcripts" \
  --model small --language zh --device cpu --compute-type int8 --threads 8

python3 -B media-transcriber/scripts/export_transcript.py "$lesson_dir"
```

`transcribe.py` 输出 `raw_asr.json`；原始稿导出固定读取此文件。长媒体分块时，`--offset` 用于加回源媒体偏移，重叠段还需按文字和时间联合核对；脚本本身不自动完成分块合并。`--prompt` 可提供识别提示，但不等于术语校核。

脚本不覆盖已有原始 ASR；原始稿相同则不重写，内容不同时拒绝覆盖。完整 ASR 保存成功后，会删除用于中断恢复的重复分段 JSONL。

### 6.3 按来源保存字幕

已有原字幕文件：

```bash
python3 -B media-transcriber/scripts/export_subtitles.py "$media_source" \
  --lesson "$lesson_dir" --subtitle-file '/项目/原视频/课程/教程.vtt'
```

视频内嵌文本字幕轨：

```bash
python3 -B media-transcriber/scripts/export_subtitles.py "$media_source" \
  --lesson "$lesson_dir" --stream 0
```

烧录字幕需先确认字幕区域、完成 OCR 和连续字幕去重，再导出：

```bash
python3 -B media-transcriber/scripts/export_subtitles.py "$media_source" \
  --lesson "$lesson_dir" \
  --ocr "$lesson_dir/temp/transcripts/deduplicated_subtitle_ocr.json"
```

OCR 输入格式和内置 macOS 脚本使用见 [读取与校核方法](references/workflow.md)。其他系统可使用可用的 OCR 工具生成同一格式的输入，再用 `export_subtitles.py --ocr` 导出。纯音频跳过 OCR；没有字幕时不造空字幕文件，不把 ASR 输出冒充原字幕。

### 6.4 视频按需抓图

先根据实际内容建立 `temp/process/frame_plan.json`，例如：

```json
[
  {
    "id": "K01",
    "time_seconds": 125.4,
    "category": "architecture",
    "title": "完成后的数据流图",
    "reason": "模块和箭头已写全"
  }
]
```

时间和标题必须对应实际视频；没有有用画面就跳过此步骤。

```bash
python3 -B media-transcriber/scripts/media.py frames "$media_source" \
  --manifest "$lesson_dir/temp/process/frame_plan.json" \
  --output "$lesson_dir/原始层/关键帧截图"
```

原始帧按 `HH-MM-SS.mmm_核心内容.png` 命名。只有正文引用的帧才按原字节复制到 `images/`，正文使用相对路径：

```markdown
![完成后的数据流图](./images/00-02-05.400_完成后的数据流图.png)
```

`media.py sample` 可做定时预览以寻找候选，预览不属于最终精选截图。音频请求抓图会报错，且不会创建图片目录。

### 6.5 编辑、索引、验证与清理

按 [SKILL.md](SKILL.md) 通读原始稿、回听疑点，并结合实际字幕和视频画面生成 `音频书面稿.md`。同时建立 `temp/chapters.json`，记录源文件、完整章节、正文节与原始段的对应关系、必要修订证据和原始导出哈希；详细字段见 [读取与校核方法](references/workflow.md) 中的 `chapters.json：schema 3.0`。

索引完成后运行：

```bash
python3 -B media-transcriber/scripts/validate_lesson.py "$lesson_dir"
```

验证脚本检查原始稿与 ASR 一致、源文件和保全证据哈希、引用路径、章节时间覆盖、原始段编辑归属，以及实际图片与原帧的一致性。纯音频会额外检查图片目录和视频截图关联不存在。结构检查通过后仍需核对语义完整性。

最终 `temp/` 仅保留原音轨、原始 ASR、必要字幕/OCR 与修订数据、章节索引和媒体信息。删除不再使用的 ASR WAV、预览、试跑、日志、重复清单和空目录；保留源媒体、原字幕与独有证据。

## 7. 常见情况

| 情况 | 处理方式 |
| --- | --- |
| 没有字幕轨 | 视频继续检查烧录字幕；没有任何字幕则只使用音频与真实画面，省略字幕文件 |
| 音频带封面 | 仍按纯音频处理，跳过截图、配图和 OCR |
| 视频没有音轨 | `prepare` 无法提取音频；按视觉材料处理并记录情况，不伪造音频稿 |
| ASR 术语或数字不清楚 | 回听并交叉核对；只在书面编辑层校订，原始层保留不动 |
| 提示输出或原始数据已存在 | 核对已有结果，继续尚未完成的步骤；需要独立重跑时指定新目录 |
| 移动后找不到索引资源 | 重算 `chapters.json` 的源文件和资源相对路径，再验证；不能只移动目录 |
| 希望输出 TXT、Word 或 ASR 字幕 | 明确提出额外需求，默认交付保持当前 Markdown 与证据结构 |

## 8. 技能文件说明

| 文件 | 职责 |
| --- | --- |
| [SKILL.md](SKILL.md) | 通用执行入口、交付约定与书面编辑规则 |
| [references/workflow.md](references/workflow.md) | ASR、字幕/OCR、关键帧、索引与校核细节 |
| [scripts/media.py](scripts/media.py) | 媒体探测、输出分组、音轨准备、预览与精选抓图 |
| [scripts/transcribe.py](scripts/transcribe.py) | 本地 faster-whisper 原始转写 |
| [scripts/export_transcript.py](scripts/export_transcript.py) | 保持原始文字与时间轴的 Markdown 导出 |
| [scripts/export_subtitles.py](scripts/export_subtitles.py) | 原字幕文件、文本字幕轨与视频 OCR 字幕导出 |
| [scripts/ocr_subtitles.swift](scripts/ocr_subtitles.swift) | macOS Vision 画面文字识别辅助工具 |
| [scripts/validate_lesson.py](scripts/validate_lesson.py) | 交付结构、资源链接与证据完整性检查 |
| [scripts/requirements-asr.txt](scripts/requirements-asr.txt) | 默认 ASR 环境依赖 |
