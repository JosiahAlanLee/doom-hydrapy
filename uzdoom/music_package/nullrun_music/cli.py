# SPDX-License-Identifier: GPL-2.0-or-later
"""Command line: export the pattern bank, run fixtures, render previews."""
import argparse
import json
import sys
from pathlib import Path

from .engine import Engine
from .events import Cue, read_cues, TICKS
from .profiles import PROFILES, load_profile, PROFILE_NAMES
from .export_tracker import export_all, story_stitch
from .synth import render_schedule, tempo_map, ticks_to_seconds, markers

ROOT = Path(__file__).resolve().parent.parent


def ticks_for_seconds(profile, seconds):
    return int(round(seconds * profile['tempo'] / 60 * TICKS))


def cmd_export(args):
    out = Path(args.out)
    written, index = export_all(PROFILES, args.seed, out)
    print(f'wrote {len(written)} validated tracker3 documents to {out}')
    for p in written:
        print(' ', p.name)


def cmd_fixtures(args):
    """Realize each fixture and write its canonical schedule + expected receipts."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in sorted(args.fixture):
        fixture = Path(args.fixture_dir) / f'{name}.jsonl'
        cues = read_cues(fixture)
        engine = Engine(args.seed, args.env)
        schedule = engine.offline(cues)
        folder = out / name
        schedule.write(folder, 'canonical')
        expected = [r.to_json() for r in schedule.receipts]
        (folder / 'expected_receipts.json').write_text(json.dumps(expected, indent=2) + '\n')
        print(f'{name}: {len(schedule.notes)} notes, {len(expected)} receipts -> {folder}')


def _render(args, cues, name, seconds, profiles=None, tail_bars=2, env=None):
    profiles = profiles or PROFILES
    engine = Engine(args.seed, env or args.env, profiles=profiles)
    schedule = engine.offline(cues, tail_bars=tail_bars)
    end_tick = schedule.meta['end_tick']
    segments = tempo_map(schedule.controls, profiles, schedule.profile, end_tick)
    duration = ticks_to_seconds(segments, end_tick) if seconds is None else seconds
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f'{name}.wav'
    left, right, stats = render_schedule(schedule, profiles, duration, out_path=wav)
    marks = markers(schedule, profiles, segments)
    (out_dir / f'{name}_markers.json').write_text(json.dumps(marks, indent=2) + '\n')
    (out_dir / f'{name}_loudness.json').write_text(json.dumps(stats, indent=2) + '\n')
    schedule.write(out_dir / name, 'canonical')
    print(f'{name}: {wav} {stats["duration_seconds"]}s '
          f'peak {stats["peak_after_master"]} rms {stats["rms_left"]:.4f} '
          f'clipped {stats["clipped_samples"]} dc {stats["dc_left"]:+.6f}')
    return schedule


def cmd_preview(args):
    """Three 30-second profile previews (exploration loops)."""
    for profile_id in PROFILE_NAMES:
        profile = PROFILES[profile_id]
        schedule = _render(args, [], f'preview_{profile_id}_30s', 30.0, tail_bars=100,
                          env=profile_id)
        end_tick = ticks_for_seconds(profile, 30.0)
        segments = tempo_map(schedule.controls, PROFILES, profile_id, end_tick)
        print(f'preview_{profile_id}: ok')


def cmd_story(args):
    cues = read_cues(args.fixture)
    # tail_bars=4: the floor bridge ends at 82.5 s and four 128 BPM bars of
    # switchyard exploration take the story to exactly 90.0 s.
    schedule = _render(args, cues, 'story_90s', 90.0, tail_bars=4)
    stitch = story_stitch(PROFILES, schedule, args.seed)
    out_dir = Path(args.out)
    (out_dir / 'story_stitch.tracker3.json').write_text(json.dumps(stitch) + '\n')
    entries = len(stitch['chain'])
    distinct = sum(1 for p in stitch['patterns'] if p and p.get('name', '').startswith('story-'))
    print(f'story stitch: chain {entries} entries, {distinct} story patterns, '
          f'loop {stitch["loop"]}, bpm {stitch["bpm"]}')


def cmd_selftest(args):
    from .engine import Engine
    engine = Engine(args.seed, args.env)
    schedule = engine.offline([])
    assert schedule.notes, 'no notes realized'
    print('selftest ok:', len(schedule.notes), 'notes,',
          len(schedule.receipts), 'receipts')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='nullrun_music', description=__doc__)
    parser.add_argument('--seed', type=int, default=20261031,
                        help='deterministic run seed (default 20261031)')
    parser.add_argument('--env', default='drowned_records', choices=PROFILE_NAMES)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('export', help='write the validated tracker3 pattern bank')
    p.add_argument('--out', default=str(ROOT / 'exports'))
    p.set_defaults(func=cmd_export)
    p = sub.add_parser('fixtures', help='realize fixtures -> canonical schedules + expected receipts')
    p.add_argument('--fixture-dir', default=str(ROOT / 'fixtures'))
    p.add_argument('--out', default=str(ROOT / 'fixtures' / 'expected'))
    p.add_argument('fixture', nargs='*')
    p.set_defaults(func=cmd_fixtures)
    p = sub.add_parser('preview', help='three 30s profile previews')
    p.add_argument('--out', default=str(ROOT / 'renders'))
    p.set_defaults(func=cmd_preview)
    p = sub.add_parser('story', help='90s story render + static stitch export')
    p.add_argument('--fixture', type=Path, default=ROOT / 'fixtures' / 'story.jsonl')
    p.add_argument('--out', default=str(ROOT / 'renders'))
    p.set_defaults(func=cmd_story)
    p = sub.add_parser('selftest', help='smoke run of the whole pipeline')
    p.set_defaults(func=cmd_selftest)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
