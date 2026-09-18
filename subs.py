#!/usr/bin/env python3
r"""Download missing subtitles for a show folder under the media root.

Wraps subliminal with the fixes this library needs:
  * `-n s/(SxxExx)vN/\1/` so `vN` re-release tags don't make guessit
    classify the file as a movie (which aborts the search entirely).
  * `-R omdb` to silence the dead bundled OMDb key's 401 traceback.

Also reports, before downloading, which episodes already carry the
language embedded in the MKV -- subliminal skips those by design, so
"0 downloaded" is usually correct rather than a failure.
"""
import argparse
import os
import shutil
import subprocess
import sys

# The NAS share, used directly by UNC. No drive letter involved.
MEDIA_ROOT = r"\\192.168.1.80\media\shows"
NAME_FIX = r"s/(S\d\dE\d\d)v\d+/\1/gi"
VIDEO_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".webm", ".wmv"}
SUB_EXT = {".srt", ".ass", ".ssa", ".sub", ".vtt"}


def default_root():
    """Media root: the NAS UNC path, overridable with $SUBS_ROOT."""
    return os.environ.get("SUBS_ROOT") or MEDIA_ROOT

_3TO2 = {
    "eng": "en", "ara": "ar", "fre": "fr", "fra": "fr", "spa": "es",
    "ger": "de", "deu": "de", "jpn": "ja", "ita": "it", "por": "pt",
    "rus": "ru", "chi": "zh", "zho": "zh", "kor": "ko", "tha": "th",
    "vie": "vi", "ind": "id", "dut": "nl", "nld": "nl", "pol": "pl",
    "tur": "tr", "swe": "sv",
}


def norm(code):
    """Reduce a track language tag ('es-419', 'eng') to a bare 2-letter code."""
    if not code:
        return ""
    c = str(code).split("-")[0].strip().lower()
    return _3TO2.get(c, c)


def find_videos(root):
    out = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def embedded_langs(path):
    """Languages of subtitle tracks inside the container. None if unknown."""
    try:
        from pymediainfo import MediaInfo
    except ImportError:
        return None
    try:
        mi = MediaInfo.parse(path)
    except Exception:
        return None
    return {norm(t.language) for t in mi.tracks if t.track_type == "Text"}


def external_langs(path):
    """Languages of sidecar subtitle files sitting next to the video."""
    base = os.path.splitext(os.path.basename(path))[0].lower()
    found = set()
    try:
        siblings = os.listdir(os.path.dirname(path))
    except OSError:
        return found
    for f in siblings:
        stem, ext = os.path.splitext(f)
        if ext.lower() not in SUB_EXT or not stem.lower().startswith(base):
            continue
        tag = stem[len(base):].lstrip(".")
        found.add(norm(tag) if tag else "*")
    return found


def report(videos, langs):
    """Print per-language coverage. Returns {lang: [videos missing it]}."""
    missing = {l: [] for l in langs}
    emb_hits = {l: 0 for l in langs}
    ext_hits = {l: 0 for l in langs}
    unknown = 0

    for v in videos:
        emb = embedded_langs(v)
        if emb is None:
            unknown += 1
            emb = set()
        ext = external_langs(v)
        for l in langs:
            n = norm(l)
            if n in emb:
                emb_hits[l] += 1
            elif n in ext or "*" in ext:
                ext_hits[l] += 1
            else:
                missing[l].append(v)

    total = len(videos)
    for l in langs:
        have = total - len(missing[l])
        print(f"  {l}: {have}/{total} already covered "
              f"({emb_hits[l]} embedded, {ext_hits[l]} external)")
        for v in missing[l][:12]:
            print(f"       missing -> {os.path.basename(v)}")
        if len(missing[l]) > 12:
            print(f"       ... and {len(missing[l]) - 12} more")
    if unknown:
        print(f"  (note: could not inspect {unknown} file(s) for embedded tracks)")
    return missing


def subliminal_cmd():
    exe = shutil.which("subliminal")
    return [exe] if exe else [sys.executable, "-m", "subliminal"]


def resolve(parts, root):
    """Accept a full path, a quoted folder name, or an unquoted one."""
    joined = " ".join(parts)
    for cand in (joined, os.path.join(root, joined)):
        if os.path.isdir(cand):
            return cand
    try:
        entries = os.listdir(root)
    except OSError:
        entries = []
    for e in entries:
        if e.lower() == joined.lower():
            return os.path.join(root, e)
    matches = [e for e in entries if joined.lower() in e.lower()]
    if len(matches) == 1:
        return os.path.join(root, matches[0])
    if matches:
        print(f"'{joined}' is ambiguous under {root}:", file=sys.stderr)
        for m in sorted(matches):
            print(f"  {m}", file=sys.stderr)
    else:
        print(f"No show matching '{joined}' under {root}. "
              f"Use --list to see them.", file=sys.stderr)
    return None


def main():
    p = argparse.ArgumentParser(
        description="Download missing subtitles for a show folder.")
    p.add_argument("show", nargs="*",
                   help="folder name under the media root, or a full path")
    p.add_argument("-l", "--lang", action="append", metavar="CODE",
                   help="language, repeatable (default: en)")
    p.add_argument("-f", "--force", action="store_true",
                   help="download even if a subtitle already exists")
    p.add_argument("-q", "--quick", action="store_true",
                   help="skip the pre-scan and hand straight to subliminal")
    p.add_argument("--root", default=None,
                   help=f"media root (default: {MEDIA_ROOT})")
    p.add_argument("--list", action="store_true", help="list show folders")
    p.add_argument("--dry-run", action="store_true",
                   help="report coverage only, download nothing")
    args = p.parse_args()
    args.root = args.root or default_root()

    if args.list:
        try:
            for e in sorted(os.listdir(args.root)):
                if os.path.isdir(os.path.join(args.root, e)):
                    print(e)
        except OSError as exc:
            print(f"Cannot read {args.root}: {exc}", file=sys.stderr)
            return 1
        return 0

    if not args.show:
        p.error("give a show folder (or --list)")

    path = resolve(args.show, args.root)
    if not path:
        return 1

    langs = args.lang or ["en"]
    videos = find_videos(path)
    if not videos:
        print(f"No video files under {path}")
        return 1

    print(f"{os.path.basename(path.rstrip(os.sep))}: {len(videos)} video file(s)")

    missing = None
    if not args.quick:
        missing = report(videos, langs)
        if not args.force and not any(missing.values()):
            print("\nNothing to download -- every episode already has it.")
            return 0
    if args.dry_run:
        return 0

    cmd = subliminal_cmd() + ["download", "-n", NAME_FIX, "-R", "omdb"]
    for l in langs:
        cmd += ["-l", l]
    if args.force:
        cmd.append("-f")
    cmd.append(path)

    print()
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
