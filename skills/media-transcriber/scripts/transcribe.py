#!/usr/bin/env python3
"""Local faster-whisper ASR with source-relative timestamps and streamed evidence."""
import argparse
import importlib.metadata
import json
import time
from pathlib import Path


def stamp(seconds, srt=False):
    ms = round(seconds * 1000)
    h, rest = divmod(ms, 3600000)
    m, rest = divmod(rest, 60000)
    s, frac = divmod(rest, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}{"," if srt else "."}{frac:03d}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--model', default='small')
    p.add_argument('--language', default='zh')
    p.add_argument('--device', default='cpu')
    p.add_argument('--compute-type', default='int8')
    p.add_argument('--threads', type=int, default=8)
    p.add_argument('--offset', type=float, default=0)
    p.add_argument('--prompt', default='')
    a = p.parse_args()
    if not a.audio.is_file():
        p.error(f'Audio not found: {a.audio}')
    a.output.mkdir(parents=True, exist_ok=True)
    raw = a.output / 'raw_asr.json'
    partial = a.output / 'segments.partial.jsonl'
    if raw.exists() or partial.exists() or (a.output / 'segments.jsonl').exists():
        p.error(f'Refusing to overwrite existing ASR evidence in {a.output}')
    from faster_whisper import WhisperModel
    started = time.time()
    print(f'Loading model {a.model}', flush=True)
    model = WhisperModel(a.model, device=a.device, compute_type=a.compute_type,
                         cpu_threads=a.threads)
    segments, info = model.transcribe(str(a.audio), language=a.language,
                                     beam_size=5, vad_filter=True,
                                     word_timestamps=True,
                                     initial_prompt=a.prompt or None)
    rows = []
    with partial.open('x', encoding='utf-8') as f:
        for s in segments:
            row = dict(id=s.id, start=round(s.start + a.offset, 3),
                       end=round(s.end + a.offset, 3), text=s.text,
                       avg_logprob=s.avg_logprob, no_speech_prob=s.no_speech_prob,
                       compression_ratio=s.compression_ratio,
                       words=[dict(start=round(w.start+a.offset, 3),
                                   end=round(w.end+a.offset, 3), word=w.word,
                                   probability=w.probability) for w in (s.words or [])])
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False)+'\n')
            f.flush()
            print(f'[{stamp(row["start"])} - {stamp(row["end"])}] {row["text"]}', flush=True)
    data = dict(audio=str(a.audio.resolve()), model=a.model,
                engine='faster-whisper', engine_version=importlib.metadata.version('faster-whisper'),
                device=a.device, compute_type=a.compute_type, cpu_threads=a.threads, beam_size=5,
                vad_filter=True, prompt=a.prompt, offset=a.offset,
                language=info.language, language_probability=info.language_probability,
                duration=info.duration, elapsed_seconds=round(time.time()-started, 2),
                status='machine_transcription_not_verbatim_verified', segments=rows)
    with raw.open('x', encoding='utf-8') as output:
        output.write(json.dumps(data, ensure_ascii=False, indent=2))
    # The full JSON supersedes the streamed recovery data after successful saving.
    partial.unlink()
    print(f'Done: {len(rows)} segments, {data["elapsed_seconds"]} seconds', flush=True)


if __name__ == '__main__':
    main()
