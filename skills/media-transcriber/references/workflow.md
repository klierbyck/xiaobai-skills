# 读取与校核方法

## 输出分组与媒体类型

技能文件夹、frontmatter 名称及调用名统一为 `media-transcriber`。`media.py prepare` 接受视频或音频，返回 `lesson_directory` 与 `media_type`，后续处理使用返回路径。

默认 `--root '/项目/output'`：源文件在项目根时输出 `/项目/output/<文件去扩展名>/`；在课程目录时输出 `/项目/output/<直接父目录名>学习/<文件去扩展名>/`。已有“学习”后缀不重复追加。嵌套课程用 `--group '上层课程名'`，其他位置的散文件或明确指定的平级布局用 `--ungrouped`，单篇名称用 `--lesson`。同名媒体不能跨分组混用输出。

FFprobe 的非 `attached_pic` 视频轨决定是否需要视觉处理；M4A、MP3 的内嵌封面属于音频。源音轨以 FFmpeg `-c:a copy` 保全，不重新编码；AAC/ALAC 保存为 M4A，MP3/FLAC/Opus/Vorbis 保存为对应容器，PCM 保存为 WAV，其他可复制编码使用 MKA。文件封装字节可能不同，不能把容器复制宣称为源文件字节完全一致；记录源哈希并按需核验音轨数据。临时 ASR 音频统一为 16 kHz 单声道 PCM WAV。

纯音频使用与视频相同的转写、原始稿、书面编辑与章节索引流程，跳过抽帧、场景检测、烧录字幕检查、OCR 及正文配图。不创建任何图片目录；有用户提供的原字幕时按字节保全为 `原音频字幕.<原扩展名>`，没有则省略。`keyframes`、各节 `keyframe_ids` 使用空数组，图片或视频字幕资源不写进索引。

## 本地工具与完整时间坐标

先查可用工具和模型。Intel Mac 或普通 CPU 可选择 faster-whisper `small`、`int8`；短片估算速度。Apple Silicon 可使用可用的 MLX Whisper，有 GPU 时使用对应后端。只对困难片段复核，不必重复可靠的全片转写。

```bash
python3 -m venv /tmp/media-asr-env
/tmp/media-asr-env/bin/python -m pip install -r scripts/requirements-asr.txt
```

模型和环境留系统缓存/临时目录。默认依赖为 faster-whisper 1.2.1 与 `av>=11,<17`，版本约束见 `scripts/requirements-asr.txt`；升级依赖后需实际验证转写兼容性。

分块保留重叠并记录 `chunk_start_seconds`，`transcribe.py --offset` 加回源偏移。按文本与重叠时间联合去重，保留有意重复；原始分块数据不可被校订替换。VAD 坐标映射回源时间，检查静音前后关键句。低概率、重复率、长停顿仅提示疑点，模型置信度不证明内容正确。失败或中断时保留有用证据，不能声称读完未读取的内容。

## 原始音频逐字稿

```bash
python3 -B scripts/export_transcript.py '/绝对路径/output/课程学习/教程'
```

固定读取 `temp/transcripts/raw_asr.json`，也可 `--source` 指定另一份完整、未经校订的 ASR JSON。每段显示源媒体 `HH:MM:SS.mmm` 起止时间与原始 `text`。显示语法转义不改变原话，保留空白、繁简字形、重复、口误与自我纠正过程。脚本拒绝校订来源、中断转写和无效时间轴；相同输出不写，不同输出报错，不提供覆盖原始稿的开关。

记录原始 JSON 的 SHA-256、段数、格式、来源、ASR 状态与实际精度。三位小数不意味着人工逐字校准。完整转写仍可能误识别或漏识别，不能把“原始 ASR”宣称为认证原话。

## 字幕来源与保全

使用 `scripts/export_subtitles.py`。视频先查字幕轨，再看原尺寸帧；没有内嵌轨不代表没有烧录字幕。音频有原字幕文件或字幕轨时保留原文，跳过画面检查与 OCR。

- 已有原字幕文件：`--subtitle-file '/原字幕.vtt'` 复制原字节，不转换编码、标点或换行，保留扩展名；支持 SRT、VTT、ASS、SSA。
- 内嵌文本轨：默认首轨，`--stream` 按字幕轨序号选择，记录语言、codec 和轨道。SRT/VTT/ASS/SSA 流尽可能复制为对应格式；mov_text/text 转为 SRT，并记录格式转换。这是容器导出，不承诺与未知外部字幕文件字节一致。
- 烧录或位图字幕：OCR 生成 `原视频字幕_OCR.srt`，不冒充原字幕轨。ASR 与 OCR 文本不混写，疑似错误另存修订依据，不覆盖原始 OCR。

```bash
python3 -B scripts/export_subtitles.py '/课程/教程.mp4' --lesson '/output/课程学习/教程'
python3 -B scripts/export_subtitles.py '/课程/教程.mp4' --lesson '/output/课程学习/教程' --subtitle-file '/课程/教程.vtt'
python3 -B scripts/export_subtitles.py '/课程/讲解.mp3' --lesson '/output/课程学习/讲解' --subtitle-file '/课程/讲解.srt'
```

烧录字幕先确认字幕区，避免白板和广告水印混入。以下 850×480 的裁剪参数只适用于已确认的样本：

```bash
ffmpeg -i '/教程.mp4' -vf 'fps=1,crop=850:40:0:395' -q:v 2 '/临时目录/sub_%04d.jpg'
swift scripts/ocr_subtitles.swift '/临时目录' '/output/课程学习/教程/temp/transcripts/subtitle_ocr.jsonl' 1
```

内置 Swift OCR 脚本需要 macOS Vision、AppKit 和工具链，是可选实现；其他系统可用可用的 OCR 工具识别同一字幕区，并生成下面约定的去重 JSON。连续相同字幕去重时保留首次/末次采样坐标，不合并被其他内容或空白隔开的重复。抽样中点坐标至少约有半个间隔误差；短暂字幕可能遗漏，关键边界要回看原帧。

去重 JSON 使用 `not_audio_transcription: true`、正数 `timestamp_uncertainty_seconds`，每个 `segments` 元素含 `first_sample_seconds`、`last_sample_seconds`、`text`。

```bash
python3 -B scripts/export_subtitles.py '/课程/教程.mp4' --lesson '/output/课程学习/教程' --ocr '/output/课程学习/教程/temp/transcripts/deduplicated_subtitle_ocr.json'
```

字幕边界为首次采样减误差、末次采样加误差，裁到源时长内。记录抽样间隔、未完整人工核验、识别错字/广告污染/短字幕遗漏等实际限制。现有 OCR SRT 迁移只移动并校验哈希，不重新编辑其文字或时间。

## 精选画面与正文图片

此节只适用于视频，纯音频及其封面不执行。无有用关键画面就省略 `关键帧截图/`；无正文配图就省略 `images/`，不留空目录。

定时抽样和场景检测用于发现候选。只保留有信息的图示完成状态、PPT 主题、代码关键状态、运行结果、重要条件或操作界面，避免对每句口播截图。正文不因为一句“看这里”强行配图。

`media.py frames` 原图写 `原始层/关键帧截图/HH-MM-SS.mmm_核心内容.png`，抓图清单默认写 `temp/process/keyframe_manifest.json`。`--manifest-output` 可覆盖清单位置；合入章节索引后，已无独立用途的重复清单删除。

类别可使用 code、architecture、diagram、keypoints、operation-result，只在 JSON 分类，不创建空分类目录。记录源时间、实际精度、画面内容、保留理由和章节。图片应为真实原帧，模糊处不臆造；裁剪或标注图另存并关联原图。

在原始图中选择书面稿实际用到的图片，按原字节复制到 `images`；其余有回查价值的帧仅留原始层。正文使用 `![具体内容](./images/实际文件名.png)`，图片独立成行，图注不写“图1”或来源时间。`images` 中每个文件都应有正文引用，来源图和正文副本应一致。

## 书面稿的人工式内容复核

全文书面化与摘要是不同工作。按原顺序逐节核对观点、理由、数值、例子、适用范围、反例及结束结论，不以篇幅短或术语丰富替代完整性。保留限定语与说话者；原文的强判断不能静默改弱，个人经验也不能改成整理者确认的事实。

字幕可能简写口语、OCR 可能错识别，不能看到字幕就直接覆盖音频。证据冲突处回听原音频；无法确认则留 `[听不清]`、`[术语待确认]` 或具体待确认标记，JSON 记相应原始段与各方证据。只有讲师主动纠正的地方，书面稿使用最终说法；不擅自修正举例中的算术或条件。

修复语法只理顺已知信息；代词需能从邻近上下文唯一确定。图片中的字、数字与箭头只有清楚可见才写入正文。没有截图时去掉空泛的视觉指代，不补画面事实。段落长度按语义，标题按讲师实际话题，禁止新增百科扩展、模板、自测或总结论断。

## chapters.json：schema 3.0

索引位于 `temp/chapters.json`，所有内部文件路径相对此文件夹。源媒体路径根据实际源文件与索引位置计算，不能固定层级：使用 `os.path.relpath(source, index.parent)`。例如 `/项目/output/课程学习/教程/temp/chapters.json` 对应 `/项目/原视频/课程/教程.mp4` 时，源路径是 `../../../../原视频/课程/教程.mp4`。章节使用源媒体秒坐标，按 `[start_seconds, end_seconds)` 覆盖完整时长，最后结束值等于源时长。时间字符串只便于检索，不提高精度。

新索引在 `source` 中记录 `media_type: "video" | "audio"`，以及源文件 `file`、`sha256`、`duration_seconds`。输出分组与原目录定位可从 `temp/process/media_info.json` 的 `provenance` 回查。旧索引缺少 `media_type` 时，验证脚本从源媒体轨道检测以兼容既有交付。

保留原有 `source`、`time_precision`、`chapters`、`keyframes`、`verified_locations` 与 `processing_evidence`，通过 `written_manuscript` 关联书面稿。正文解释与整理者补充区分归属；已删除正文节需同步删除关联。

新增 `written_manuscript`：

```json
{
  "file": "../音频书面稿.md",
  "source_file": "transcripts/raw_asr.json",
  "subtitle_file": "../原始层/原视频字幕_OCR.srt",
  "sections": [
    {
      "id": "W01",
      "heading": "实际正文标题",
      "heading_level": 2,
      "file": "../音频书面稿.md",
      "raw_segment_ids": [1, 2, 3],
      "source_ranges": [{"start_seconds": 0, "end_seconds": 30}],
      "chapter_ids": ["C01"],
      "keyframe_ids": ["K01"]
    }
  ],
  "coverage_scope": "每个原始段均有编辑归属；语义完整性另需内容复核"
}
```

开头无二级标题的导语可用一级标题对应 W01。各节原始段 ID 按源顺序恰好覆盖一次，包含被清洗的口语段。每个章节补 `written_section_ids`，与各节 `chapter_ids` 双向对应。不能只填连续编号就声称人工逐字核验完成。

`keyframes[].file` 指原始帧，`published_file` 指正文副本，`document_usage` 记录实际引用文件。`artifact_files` 指向最终书面稿、原始稿、原字幕、音轨和必要 JSON，不留旧成品失效路径。

音频的 `keyframes` 与各节 `keyframe_ids` 为 `[]`。没有原字幕时省略 `written_manuscript.subtitle_file` 和字幕成品路径；有音频原字幕时指向 `../原始层/原音频字幕.<原扩展名>`，不填原视频字幕或 OCR 路径。

`processing_evidence.raw_transcript_export` 记录原始稿文件、source_file、source_sha256、segment_count、文字未编辑与 ASR 状态。新字幕记录可用 `original_media_subtitle_export` 保留实际来源与精度，旧 `original_video_subtitle_export` 保持兼容；`preserved_files` 是有必要保全的源 ASR、OCR、字幕、音轨和原帧的文件与 SHA-256，支持迁移后验证。

## 检查与清理

运行 `validate_lesson.py`，检查原始稿与 ASR 全段文字/时间一致、源证据哈希、JSON 路径、原始段编辑归属和章节完整时间轴。按真实媒体轨道验证类型：视频检查实际图片与原帧，图片目录只放正文用图；音频拒绝图片目录、截图关联及原视频字幕。根目录必须包含 `音频书面稿.md`、`原始层/`、`temp/`，仅有实际正文配图的视频才包含 `images/`。检查成功仅确认结构与保全事实，不证明转写正确或书面稿语义无遗漏。

旧的同源纯文字、带轴校订稿、ASR 字幕在新书面稿与原始层核对完成后删除；校订 JSON 和修订日志若支撑当前编辑，则继续保留。不备份已经无用途的成品，不留空目录。原音轨保留，可重新生成的 ASR WAV 在不再处理时删除，不能删除作为原音轨保全成品的 `original_audio.wav`。不要删除用户源视频、源音频、原字幕或独有资料。

技能改动后检查入口名称与描述、相对资源链接及示例命令；修改的脚本实际执行。验证源目录分组、散文件、不重复“学习”、音频识别及封面排除、原音轨保全和 ASR WAV 格式。原始导出应拒绝校订输入与不同内容覆盖，字幕验证原字节复制、视频内嵌轨和 OCR 路径，抓图验证时间命名与实际帧，并确认音频请求抓图时失败且不创建图片目录。失败时报告实际原因，不能用语法检查代替结果检查。
