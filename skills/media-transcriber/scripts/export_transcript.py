#!/usr/bin/env python3
"""Export untouched ASR segment text and timestamps to 原始层/原始音频逐字稿.md."""
import argparse
import hashlib
import html
import json
import math
import re
from pathlib import Path


def check_target(target, payload, replace=False):
    if target.exists():
        if target.read_bytes() == payload:
            return False
        if not replace:
            raise FileExistsError(f'{target} differs; preserve the original and inspect its source')
    return True


def write_target(target, payload):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.write_bytes(payload)
    else:
        with target.open('xb') as output:
            output.write(payload)


def timestamp(seconds):
    milliseconds = round(seconds * 1000)
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, fraction = divmod(rest, 1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{fraction:03d}'


def markdown_text(text):
    # Only escape display syntax. Do not strip, normalize, correct, or omit text.
    escaped = html.escape(text, quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~\-])', r'\\\1', escaped)


def raw_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('segments'), list):
        raise ValueError('Raw ASR JSON must contain a segments array')
    status = str(data.get('status', '')).lower()
    if 'partial' in status or 'corrected' in status or 'orthography' in data:
        raise ValueError('Use a complete, untouched ASR result, not a corrected transcript')
    rows = data['segments']
    if not rows:
        raise ValueError('No raw ASR segments; do not create a fake transcript')
    blocks = []
    previous_start = -1
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('text'), str):
            raise ValueError('Each raw ASR segment needs its original text string')
        start, end = row.get('start'), row.get('end')
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in (start, end)):
            raise ValueError('ASR start and end must be finite numeric timestamps')
        if start < 0 or end < start or start < previous_start:
            raise ValueError('Raw timestamps must be nonnegative and in source order')
        previous_start = start
        blocks.append(f'**{timestamp(start)}–{timestamp(end)}**\n\n{markdown_text(row["text"])}')
    return ('# 原始音频逐字稿\n\n' + '\n\n'.join(blocks) + '\n').encode('utf-8')


def export_raw_transcript(lesson, source=None):
    lesson = lesson.resolve(strict=True)
    if not lesson.is_dir():
        raise ValueError('Lesson must be an existing media output directory')
    source = (source or lesson / 'temp/transcripts/raw_asr.json').resolve(strict=True)
    if 'corrected' in source.name.lower():
        raise ValueError('A corrected transcript cannot be the raw ASR source')
    source_bytes = source.read_bytes()
    data = json.loads(source_bytes)
    payload = raw_payload(data)
    target = lesson / '原始层/原始音频逐字稿.md'
    changed = check_target(target, payload)
    if changed:
        write_target(target, payload)
    return {'file': str(target), 'source_file': str(source), 'changed': changed,
            'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
            'segment_count': len(data['segments']),
            'transcription_status': data.get('status', 'unspecified'),
            'raw_text_unchanged': True, 'not_certified_verbatim': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lesson', type=Path)
    parser.add_argument('--source', type=Path, help='Untouched full ASR JSON; defaults to raw_asr.json')
    args = parser.parse_args()
    try:
        result = export_raw_transcript(args.lesson, args.source)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
