#!/usr/bin/env python3
"""Check raw-ASR fidelity, source integrity, resource links, and written-section coverage."""
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from export_transcript import raw_payload, timestamp
from media import probe, video_streams


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_lesson(lesson):
    lesson = lesson.resolve(strict=True)
    index = lesson / 'temp/chapters.json'
    data = json.loads(index.read_text(encoding='utf-8'))
    base = index.parent
    raw = lesson / 'temp/transcripts/raw_asr.json'
    raw_data = json.loads(raw.read_bytes())
    original_md = lesson / '原始层/原始音频逐字稿.md'
    if original_md.read_bytes() != raw_payload(raw_data):
        raise ValueError('Raw Markdown differs from the untouched ASR segment text/timestamps')
    checks = data['processing_evidence']
    recorded = checks['raw_transcript_export']['source_sha256']
    if digest(raw) != recorded:
        raise ValueError('Raw ASR JSON differs from its recorded source SHA-256')
    refs = []

    def visit(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {'file', 'source_file', 'source_video', 'source_media', 'subtitle_file', 'published_file', 'image_file'} and isinstance(value, str):
                    refs.append(value)
                if key == 'artifact_files' and isinstance(value, dict):
                    refs.extend(v for v in value.values() if isinstance(v, str))
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(data)
    for ref in refs:
        if not (base / ref).is_file():
            raise ValueError(f'Missing JSON resource: {ref}')
    for entry in checks.get('preserved_files', []):
        if digest(base / entry['file']) != entry['sha256']:
            raise ValueError(f'Preserved evidence was changed: {entry["file"]}')
    source_path = (base / data['source']['file']).resolve()
    if digest(source_path) != data['source']['sha256']:
        raise ValueError('Source media SHA-256 changed')
    detected_type = 'video' if video_streams(probe(source_path)) else 'audio'
    media_type = data['source'].get('media_type', detected_type)
    if media_type not in {'video', 'audio'} or media_type != detected_type:
        raise ValueError('Recorded media_type does not match the source media streams')

    linked_images = set()
    document_texts = {}
    for document in [lesson / '音频书面稿.md']:
        text = document.read_text(encoding='utf-8')
        document_texts[document.name] = text
        if re.search(r'\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b|原课位置', text):
            raise ValueError(f'Unexpected timestamp/navigation in {document.name}')
        for ref in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text):
            ref = ref.strip('<>')
            if not ref.startswith('./images/'):
                raise ValueError(f'Unexpected body image location: {ref}')
            resolved = (lesson / ref).resolve()
            if resolved.parent != lesson / 'images' or not resolved.is_file():
                raise ValueError(f'Missing or invalid body image: {ref}')
            linked_images.add(resolved)

    written = data['written_manuscript']
    written_text = document_texts['音频书面稿.md']
    assigned = []
    section_ids = []
    chapter_ids = {chapter['id'] for chapter in data['chapters']}
    for section in written['sections']:
        section_ids.append(section['id'])
        heading = '#' * section.get('heading_level', 2) + ' ' + section['heading']
        if heading not in written_text.splitlines():
            raise ValueError(f'Written section heading not found: {heading}')
        if any(ident not in chapter_ids for ident in section['chapter_ids']):
            raise ValueError('Written section refers to an unknown chapter')
        assigned.extend(section['raw_segment_ids'])
    if len(section_ids) != len(set(section_ids)):
        raise ValueError('Duplicate written-section IDs')
    actual_ids = [row['id'] for row in raw_data['segments']]
    if Counter(assigned) != Counter(actual_ids) or assigned != actual_ids:
        raise ValueError('Every raw segment must be assigned once in source order')
    for chapter in data['chapters']:
        if any(ident not in section_ids for ident in chapter.get('written_section_ids', [])):
            raise ValueError('Chapter refers to a missing written section')

    last_end = 0.0
    for chapter in data['chapters']:
        start, end = chapter['start_seconds'], chapter['end_seconds']
        if not math.isclose(start, last_end, abs_tol=0.001) or end <= start:
            raise ValueError('Chapter ranges have a gap, overlap, or invalid duration')
        last_end = end
    if not math.isclose(last_end, data['source']['duration_seconds'], abs_tol=0.001):
        raise ValueError('Chapters do not cover the complete source duration')

    raw_images = {}
    frames = data.get('keyframes', [])
    if media_type == 'audio':
        if frames or linked_images or (lesson / 'images').exists() or (lesson / '原始层/关键帧截图').exists():
            raise ValueError('Audio output must not contain images, keyframes, or image directories')
        if any(section.get('keyframe_ids') for section in written['sections']):
            raise ValueError('Audio written sections must not refer to video frames')
        if list((lesson / '原始层').glob('原视频字幕*')):
            raise ValueError('Audio output must not contain video subtitles')
    for frame in frames:
        source = (base / frame['file']).resolve()
        expected = f'{timestamp(frame["time_seconds"]).replace(":", "-")}_{frame["title"]}.png'
        if source.parent != lesson / '原始层/关键帧截图' or source.name != expected:
            raise ValueError(f'Unexpected original frame location/name: {source}')
        raw_images[source.name] = source
    for copied in linked_images:
        original = raw_images.get(copied.name)
        if original is None or digest(copied) != digest(original):
            raise ValueError(f'Body image does not match a genuine source frame: {copied}')
    stored_images = {p.resolve() for p in (lesson / 'images').glob('*') if p.is_file() and p.name != '.DS_Store'}
    if stored_images != linked_images:
        raise ValueError('images must contain exactly the images referenced by the body documents')
    expected_roots = {'音频书面稿.md', '原始层', 'temp'}
    if linked_images:
        expected_roots.add('images')
    roots = {p.name for p in lesson.iterdir() if p.name != '.DS_Store'}
    if roots != expected_roots:
        raise ValueError(f'Unexpected root items: {sorted(roots ^ expected_roots)}')
    return {'lesson': lesson.name, 'raw_segments_verified': len(actual_ids),
            'media_type': media_type,
            'written_sections': len(section_ids), 'indexed_original_frames': len(frames),
            'referenced_body_images': len(linked_images), 'valid_json_references': len(refs),
            'source_integrity_verified': True,
            'semantic_fidelity': 'Requires content review; structural checks do not prove meaning.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lesson', type=Path)
    args = parser.parse_args()
    try:
        result = validate_lesson(args.lesson)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
