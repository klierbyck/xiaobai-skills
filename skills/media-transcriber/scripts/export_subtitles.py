#!/usr/bin/env python3
"""Preserve source media subtitles; burned-caption OCR applies only to video."""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

from export_transcript import check_target, timestamp, write_target
from media import media_duration, probe, run, video_streams


def export_subtitles(media, lesson, ocr=None, stream=0, subtitle_file=None):
    media = media.resolve(strict=True)
    lesson = lesson.resolve(strict=True)
    if not lesson.is_dir():
        raise ValueError('Lesson must be an existing media output directory')
    if ocr is not None and subtitle_file is not None:
        raise ValueError('Select one subtitle source: original file or OCR')
    info = probe(media)
    is_video = bool(video_streams(info))
    prefix = '原视频字幕' if is_video else '原音频字幕'
    source_reference = {'source_video' if is_video else 'source_media': str(media)}
    if ocr is not None and not is_video:
        raise ValueError('Audio and cover art cannot supply burned video captions for OCR')
    output_directory = lesson / '原始层'
    if subtitle_file is not None:
        subtitle_file = subtitle_file.resolve(strict=True)
        if subtitle_file.suffix.lower() not in {'.srt', '.vtt', '.ass', '.ssa'}:
            raise ValueError('Preserve an existing SRT, VTT, ASS, or SSA subtitle file')
        payload = subtitle_file.read_bytes()
        if not payload:
            raise ValueError('Original subtitle file is empty')
        target = output_directory / f'{prefix}{subtitle_file.suffix.lower()}'
        changed = check_target(target, payload)
        if changed:
            write_target(target, payload)
        return {'file': str(target), 'changed': changed, 'source_file': str(subtitle_file),
                'source_type': 'original_subtitle_file', 'original_bytes_unchanged': True,
                'not_audio_transcription': True}
    if ocr is None:
        tracks = [s for s in info['streams'] if s['codec_type'] == 'subtitle']
        if not tracks:
            return {'status': 'no_embedded_subtitle_track', 'file': None,
                    'note': ('Inspect video frames for burned captions; export OCR if present.' if is_video
                             else 'Audio has no embedded subtitles; retain a supplied original subtitle file if available.')}
        if not 0 <= stream < len(tracks):
            raise ValueError('Requested subtitle stream does not exist')
        selected = tracks[stream]
        codec = selected['codec_name']
        if codec not in {'subrip', 'webvtt', 'ass', 'ssa', 'mov_text', 'text'}:
            raise ValueError('Bitmap subtitle tracks require visual OCR')
        ext = {'subrip': 'srt', 'webvtt': 'vtt', 'ass': 'ass', 'ssa': 'ssa'}.get(codec, 'srt')
        muxer = {'srt': 'srt', 'vtt': 'webvtt', 'ass': 'ass', 'ssa': 'ass'}[ext]
        converted = codec in {'mov_text', 'text'}
        contents = run(['ffmpeg', '-v', 'error', '-i', media, '-map',
                        f'0:{selected["index"]}', '-c:s', 'srt' if converted else 'copy',
                        '-f', muxer, 'pipe:1']).stdout
        count = (len(re.findall(r'^Dialogue:', contents, re.M)) if ext in {'ass', 'ssa'}
                 else len(re.findall(r'^.* --> .*$', contents, re.M)))
        if not count:
            raise ValueError('No subtitle cues were extracted; do not create an empty subtitle file')
        target = output_directory / f'{prefix}.{ext}'
        metadata = {'source_type': 'embedded_subtitle_track', **source_reference,
                    'stream_index': selected['index'], 'stream_codec': selected['codec_name'],
                    'status': 'extracted_from_original_subtitle_track', 'cue_count': count,
                    'not_audio_transcription': True,
                    'packaging': 'converted from container text to SRT' if converted else 'stream copied; container serialized by FFmpeg',
                    'no_editorial_corrections': True}
    else:
        ocr = ocr.resolve(strict=True)
        data = json.loads(ocr.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('not_audio_transcription') is not True:
            raise ValueError('OCR JSON must identify itself with not_audio_transcription=true')
        rows = data.get('segments')
        if not isinstance(rows, list) or not rows:
            raise ValueError('OCR JSON needs nonempty deduplicated subtitle segments')
        uncertainty = data.get('timestamp_uncertainty_seconds')
        if (isinstance(uncertainty, bool) or not isinstance(uncertainty, (int, float))
                or not math.isfinite(uncertainty) or uncertainty <= 0):
            raise ValueError('OCR JSON must specify positive timestamp_uncertainty_seconds')
        duration = media_duration(info)
        cues = []
        previous_first = -1
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('text'), str):
                raise ValueError('Every OCR segment must contain a text string')
            first, last = row.get('first_sample_seconds'), row.get('last_sample_seconds')
            if any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in (first, last)):
                raise ValueError('OCR segments need finite first and last sample times')
            if first < 0 or last < first or first < previous_first or last > duration:
                raise ValueError('OCR sample times must be ordered and inside the video')
            previous_first = first
            text = row['text'].strip()
            if not text:
                continue
            start, end = max(0, first - uncertainty), min(duration, last + uncertainty)
            cue_start = timestamp(start).replace('.', ',')
            cue_end = timestamp(end).replace('.', ',')
            cues.append(f'{len(cues)+1}\n{cue_start} --> {cue_end}\n{text}\n\n')
        if not cues:
            raise ValueError('No nonempty OCR subtitle text')
        contents = ''.join(cues)
        target = output_directory / '原视频字幕_OCR.srt'
        metadata = {'source_type': 'burned_subtitle_ocr', **source_reference,
                    'source_file': str(ocr), 'status': 'ocr_extracted_not_fully_verified',
                    'cue_count': len(cues), 'not_audio_transcription': True,
                    'timestamp_uncertainty_seconds': uncertainty,
                    'time_boundary_method': 'first sample minus uncertainty; last sample plus uncertainty; clipped to video',
                    'all_nonempty_ocr_segments_exported': True,
                    'limitations': 'OCR may contain recognition or overlay errors and miss captions between samples; cue times are approximate.'}
    payload = contents.encode('utf-8')
    changed = check_target(target, payload)
    if changed:
        write_target(target, payload)
    return {'file': str(target), 'changed': changed, **metadata}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('--lesson', type=Path, required=True)
    parser.add_argument('--ocr', type=Path, help='Deduplicated burned-caption OCR JSON; never audio ASR')
    parser.add_argument('--subtitle-file', type=Path, help='Copy an existing subtitle file without changing its bytes')
    parser.add_argument('--stream', type=int, default=0, help='Subtitle track ordinal; defaults to first')
    args = parser.parse_args()
    try:
        result = export_subtitles(args.media, args.lesson, args.ocr, args.stream, args.subtitle_file)
    except subprocess.CalledProcessError as error:
        parser.error((error.stderr or str(error)).strip() + '; bitmap subtitle tracks require OCR')
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
