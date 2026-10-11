#!/usr/bin/env python3
"""Probe media, extract original/ASR audio, and capture source frames from a manifest."""
import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from export_transcript import timestamp


def run(args):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True)


def probe(source):
    return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',source]).stdout)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_component(value):
    return (value not in ('', '.', '..') and
            not any(c in value for c in '/\\') and
            not any(ord(c) < 32 for c in value))


def video_streams(info):
    """Cover art in an audio container is not playable video."""
    return [s for s in info['streams'] if s.get('codec_type') == 'video'
            and not s.get('disposition', {}).get('attached_pic')]


def media_duration(info):
    candidates = [info.get('format', {}).get('duration')]
    candidates.extend(s.get('duration') for s in info['streams'])
    for value in candidates:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(seconds) and seconds > 0:
            return seconds
    raise ValueError('Media has no known positive duration')


def output_directory(source, root, lesson=None, group=None, ungrouped=False):
    """Group files in a source folder; leave workspace-level files ungrouped."""
    root = root.resolve()
    lesson = source.stem if lesson is None else lesson
    if not safe_component(lesson):
        raise ValueError('Lesson must be a single safe directory name')
    if ungrouped:
        return root / lesson
    if group is None and source.parent == root.parent:
        return root / lesson
    group = source.parent.name if group is None else group
    if not safe_component(group):
        raise ValueError('Group must be a single safe directory name')
    if not group.endswith('学习'):
        group += '学习'
    return root / group / lesson


def main():
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest='command', required=True)
    prep = subs.add_parser('prepare')
    prep.add_argument('media', type=Path)
    prep.add_argument('--root', type=Path, required=True, help='Output root, usually <workspace>/output')
    prep.add_argument('--lesson', help='Single directory name; defaults to the media filename stem')
    grouping = prep.add_mutually_exclusive_group()
    grouping.add_argument('--group', help='Source folder name; appends 学习 unless already present')
    grouping.add_argument('--ungrouped', action='store_true', help='Write directly under root for loose files or an explicit existing layout')
    prep.add_argument('--audio-index', type=int, default=0, help='Audio stream index among audio streams')
    sample = subs.add_parser('sample')
    sample.add_argument('media', type=Path)
    sample.add_argument('--output', type=Path, required=True)
    sample.add_argument('--interval', type=float, default=30)
    frames = subs.add_parser('frames')
    frames.add_argument('media', type=Path)
    frames.add_argument('--manifest', type=Path, required=True)
    frames.add_argument('--output', type=Path, required=True)
    frames.add_argument('--manifest-output', type=Path,
                        help='Defaults to <lesson>/temp/process/keyframe_manifest.json for 原始层/关键帧截图 output')
    a = p.parse_args()
    source = a.media.resolve(strict=True)
    info = probe(source)
    try:
        duration = media_duration(info)
    except ValueError as error:
        p.error(str(error))
    videos = video_streams(info)
    media_type = 'video' if videos else 'audio'
    if a.command == 'prepare':
        try:
            lesson_dir = output_directory(source, a.root, a.lesson, a.group, a.ungrouped)
        except ValueError as error:
            p.error(str(error))
        audio = [s for s in info['streams'] if s['codec_type']=='audio']
        if a.audio_index < 0 or a.audio_index >= len(audio):
            p.error('Requested audio stream does not exist')
        codec = audio[a.audio_index]['codec_name']
        # These containers preserve these codecs without re-encoding.
        ext = {'aac':'m4a','alac':'m4a','mp3':'mp3','opus':'opus','vorbis':'ogg','flac':'flac'}.get(codec)
        if ext is None:
            ext = 'wav' if codec.startswith('pcm_') else 'mka'
        out = lesson_dir/'temp'/'audio'
        process = lesson_dir/'temp'/'process'
        original = out/f'original_audio.{ext}'
        wav = out/'asr_audio.wav'
        if original.exists() or wav.exists() or (process/'media_info.json').exists():
            p.error('Audio output already exists; use a new lesson/output directory')
        out.mkdir(parents=True, exist_ok=True)
        process.mkdir(parents=True, exist_ok=True)
        mapping = f'0:a:{a.audio_index}'
        run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',source,'-map',mapping,'-vn','-c:a','copy',original])
        run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',source,'-map',mapping,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',wav])
        audio_duration = float(probe(wav)['format']['duration'])
        info['provenance'] = {'source_sha256':digest(source),'selected_audio_stream':mapping,
                              'media_type':media_type,'duration_seconds':duration,
                              'source_file':str(source),
                              'source_directory':str(source.parent),
                              'output_root':str(a.root.resolve()),
                              'output_group':lesson_dir.parent.name if lesson_dir.parent != a.root.resolve() else None,
                              'lesson_directory':str(lesson_dir),
                              'original_audio':str(original),'asr_audio':str(wav),
                              'audio_duration_seconds':audio_duration,
                              'duration_difference_seconds':audio_duration-duration}
        (process/'media_info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(info['provenance'],ensure_ascii=False,indent=2))
    else:
        if not videos:
            p.error('Frame capture requires playable video; audio and cover art have no video frames')
        if a.command=='sample':
            if a.interval <= 0:
                p.error('Interval must be positive')
            rows=[]; t=0.0
            while t < duration:
                rows.append({'id':f'sample_{len(rows)+1:04d}','time_seconds':round(t,3),'category':'preview','title':'preview'})
                t+=a.interval
        else:
            rows=json.loads(a.manifest.read_text(encoding='utf-8'))
            if not isinstance(rows, list) or not rows:
                p.error('Frame plan must be a nonempty JSON array; omit image directories when no frames are selected')
        lesson_dir = a.output.parent.parent if a.output.parent.name == '原始层' else a.output.parent
        manifest_output = (a.output/'manifest.json' if a.command=='sample' else
                           a.manifest_output or lesson_dir/'temp'/'process'/'keyframe_manifest.json')
        if manifest_output.exists():
            p.error(f'Manifest output already exists: {manifest_output}')
        ids=set()
        targets=[]
        for row in rows:
            ident=row['id']; t=float(row['time_seconds']); category=row.get('category','keypoints')
            if not re.fullmatch(r'[A-Za-z0-9_-]+',ident) or ident in ids:
                p.error(f'Invalid/duplicate frame id: {ident}')
            if not re.fullmatch(r'[\w\u4e00-\u9fff-]+',category):
                p.error(f'Invalid frame category: {category}')
            if not 0 <= t < duration:
                p.error(f'Timestamp outside video: {t}')
            ids.add(ident)
            title = str(row.get('title', '')).strip()
            if a.command == 'frames' and not safe_component(title):
                p.error('Selected frames need a nonempty, safe content title')
            frame_name = f'{timestamp(t).replace(":", "-")}_{title}.png'
            target=(a.output/category/f'{ident}.png' if a.command=='sample' else a.output/frame_name)
            if target.exists():
                p.error(f'Frame output already exists: {target}')
            targets.append(target)
        a.output.mkdir(parents=True,exist_ok=True)
        for row, target in zip(rows, targets):
            t=float(row['time_seconds'])
            target.parent.mkdir(parents=True,exist_ok=True)
            run(['ffmpeg','-hide_banner','-loglevel','error','-n','-ss',f'{t:.3f}','-i',source,
                 '-map',f'0:{videos[0]["index"]}','-frames:v','1',target])
            row['file']=str(target.relative_to(a.output))
            row['source_sha256']=digest(source) if len(rows)==1 else None
        manifest_output.parent.mkdir(parents=True,exist_ok=True)
        manifest_output.write_text(json.dumps({'source':str(source),'source_sha256':digest(source),
                'frame_directory':str(a.output.resolve()),
                'duration_seconds':duration,'frames':rows},ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Captured {len(rows)} frames')


if __name__=='__main__':
    main()
