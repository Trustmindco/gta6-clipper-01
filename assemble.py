#!/usr/bin/env python3
"""assemble.py — clip assembler for the make.fun bounty gta6-clipper-01.

Written by the agent (coral-comet-42) in the recorded build session for the
"Clip GTA 6 for the most YouTube views" bounty. It takes the rendered GTA 6
short's shot clips (Wan 2.2 image-to-video renders of official Rockstar
stills, made in the same session chain), normalises them to a vertical
1080x1920 / 30 fps timeline, burns each shot's on-screen text from the
production script (NASKAH-FINAL.md), mixes the voice-over over a ducked
music bed, appends a 3-second make.fun pitch end-card, loudness-normalises
to the YouTube Shorts level (-14 LUFS) and writes:

    final_short.mp4   the finished vertical clip
    description.txt   the YouTube title + description (carries the bounty's
                      prescribed line word for word, our play code and our
                      referral link)

Python 3 standard library only; ffmpeg/ffprobe are driven via subprocess.
No network access is needed or used.

Run:  python3 assemble.py [--clips-dir DIR] [--audio-dir DIR]
                          [--out-dir DIR] [--font FILE]
                          [--youtube-url URL] [--keep-build]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

# --------------------------------------------------------------------------
# Campaign constants (from the bounty's published requirements, read in
# this session from GET /api/competitions/gta6-clipper-01 and its rules).
# --------------------------------------------------------------------------

# The line the video's YouTube description must carry, word for word.
BOUNTY_LINE = (
    "Made by my AI agent for a $500 bounty on make.fun, where you can earn "
    "money making clips with AI: https://make.fun/bounty/gta6-clipper-01"
)
# Our account's play code in this bounty (code 0 of 4, printed by the kit's
# check command in this session). The gate looks for it, as it stands, in
# the video's description (or the channel's description).
PLAY_CODE = "makefun-jade-saucer-pasta"
REFERRAL_CODE = "h2mmx26f"
REFERRAL_LINK = "https://make.fun/r/h2mmx26f"
BOUNTY_URL_TEXT = "make.fun/bounty/gta6-clipper-01"
# The pitch the clip itself must carry (rules: a part of the clip, on
# screen, spoken or both, tells viewers they can make money on make.fun by
# making cool clips with AI; the rules' own example call to action is used
# verbatim on the end-card).
PITCH_LINE_1 = "Make clips like this with AI"
PITCH_LINE_2 = "and earn money on make.fun"

VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30
ENDCARD_SECONDS = 3

WHITE = "white"
AMBER = "0xFFB300"
MAGENTA = "0xFF2E9E"

# Canonical shot order and on-screen texts (from NASKAH-FINAL.md, the
# production script of the "13 TAHUN" short). Shot 5 is a three-clip quick
# cut (5a/5b/5c) sharing one caption. (file stem, main text, sub text,
# main colour, sub colour)
SHOT_ORDER = [
    ("shot1", "13 TAHUN", None, AMBER, WHITE),
    ("shot2", "2013 \u2192 2026", None, WHITE, WHITE),
    ("shot3", "SELAMAT TINGGAL, LOS SANTOS", None, WHITE, WHITE),
    ("shot4", "SELAMAT DATANG DI LEONIDA", None, WHITE, WHITE),
    ("shot5a", "JASON & LUCIA", None, WHITE, WHITE),
    ("shot5b", "JASON & LUCIA", None, WHITE, WHITE),
    ("shot5c", "JASON & LUCIA", None, WHITE, WHITE),
    ("shot6", "METACRITIC 99", "17 JUTA KOPI HARI PERTAMA", WHITE, AMBER),
    ("shot7", "PENANTIAN SELESAI", None, WHITE, WHITE),
    ("shot8", "GTA VI \u2014 HARI INI", "Kalian main di PS5 atau Xbox?", WHITE, WHITE),
]

TITLE = (
    "13 Years of Waiting \u2014 GTA VI Is Finally Here | "
    "Goodbye Los Santos, Welcome to Leonida"
)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def run(cmd, what):
    """Run a command, raising a readable error on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"{what} failed (exit {proc.returncode}):\n{tail}")
    return proc


def probe_duration(path):
    out = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        f"ffprobe {path}",
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def fit_fontsize(text, cap, box_w=1000):
    """Shrink a caption's font size until it fits the frame width.

    Anton's capitals average roughly half an em of advance width, which is
    close enough for a one-line lower-third caption.
    """
    if not text:
        return cap
    est = int(box_w / (0.50 * len(text)))
    return max(38, min(cap, est))


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def drawtext(textfile, font, size, colour, x, y):
    return (
        f"drawtext=textfile={textfile}:fontfile={font}:fontsize={size}:"
        f"fontcolor={colour}:borderw=6:bordercolor=black@0.85:"
        f"shadowcolor=black@0.55:shadowx=3:shadowy=3:x={x}:y={y}"
    )


# --------------------------------------------------------------------------
# Build steps
# --------------------------------------------------------------------------

def normalise_clip(src, stem, main, sub, main_colour, sub_colour,
                   workdir, font):
    """One shot -> 1080x1920, 30 fps, caption burned, silent AAC track."""
    dur = probe_duration(src)
    filters = [
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase",
        f"crop={VIDEO_W}:{VIDEO_H}",
        f"fps={FPS}",
        "setsar=1",
    ]
    main_y = int(VIDEO_H * 0.74)
    if main:
        cap = os.path.join(workdir, f"{stem}_main.txt")
        write_text(cap, main)
        size = fit_fontsize(main, 96)
        filters.append(drawtext(cap, font, size, main_colour,
                                "(w-text_w)/2", main_y))
        if sub:
            subfile = os.path.join(workdir, f"{stem}_sub.txt")
            write_text(subfile, sub)
            ssize = fit_fontsize(sub, 54)
            filters.append(drawtext(subfile, font, ssize, sub_colour,
                                    "(w-text_w)/2", main_y + size + 34))
    graph = "[0:v]" + ",".join(filters) + "[vout]"
    script = os.path.join(workdir, f"{stem}_filter.txt")
    write_text(script, graph)
    out = os.path.join(workdir, f"{stem}_norm.mp4")
    run(
        ["ffmpeg", "-y", "-v", "error", "-i", src,
         "-f", "lavfi", "-i", "anullsrc=cl=stereo:r=48000",
         "-filter_complex_script", script,
         "-map", "[vout]", "-map", "1:a",
         "-t", f"{dur:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-ar", "48000", "-ac", "2", out],
        f"normalise {stem}",
    )
    return out


def build_endcard(workdir, font):
    """The 3-second make.fun pitch card, same shape as the intermediates."""
    lines = [
        # (text, size, colour, y)
        ("make.fun", 172, WHITE, 690),
        (PITCH_LINE_1, 66, WHITE, 950),
        (PITCH_LINE_2, 66, AMBER, 1044),
        (BOUNTY_URL_TEXT, 46, "white@0.85", 1180),
        (f"Referral code: {REFERRAL_CODE}", 46, MAGENTA, 1252),
    ]
    filters = []
    for i, (text, size, colour, y) in enumerate(lines):
        tf = os.path.join(workdir, f"card_{i}.txt")
        write_text(tf, text)
        filters.append(drawtext(tf, font, size, colour, "(w-text_w)/2", y))
    graph = "[0:v]" + ",".join(filters) + "[vout]"
    script = os.path.join(workdir, "card_filter.txt")
    write_text(script, graph)
    out = os.path.join(workdir, "endcard_norm.mp4")
    run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i",
         f"color=c=0x0B0E1A:s={VIDEO_W}x{VIDEO_H}:r={FPS}:d={ENDCARD_SECONDS}",
         "-f", "lavfi", "-i", "anullsrc=cl=stereo:r=48000",
         "-filter_complex_script", script,
         "-map", "[vout]", "-map", "1:a",
         "-t", str(ENDCARD_SECONDS),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-ar", "48000", "-ac", "2", out],
        "end-card",
    )
    return out


def concat_all(parts, workdir):
    listfile = os.path.join(workdir, "concat.txt")
    with open(listfile, "w", encoding="utf-8") as fh:
        for part in parts:
            fh.write(f"file '{part}'\n")
    master = os.path.join(workdir, "master.mp4")
    run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", listfile, "-c", "copy", master],
        "concat",
    )
    return master


def mux_audio(master, audio_dir, total_dur, out_path, workdir):
    """Mix VO over ducked music (or fall back), loudnorm, mux with video.

    Returns a note describing what the audio bed actually is.
    """
    vo = os.path.join(audio_dir, "vo.mp3")
    music = os.path.join(audio_dir, "music.mp3")
    has_vo = os.path.isfile(vo)
    has_music = os.path.isfile(music)
    dur = f"{total_dur:.3f}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", master]
    if has_vo:
        cmd += ["-i", vo]
    if has_music:
        cmd += ["-stream_loop", "-1", "-i", music]
    if not has_vo and not has_music:
        cmd += ["-f", "lavfi", "-i", "anullsrc=cl=stereo:r=48000"]

    if has_vo and has_music:
        graph = (
            f"[1:a]aresample=48000,apad,atrim=0:{dur},"
            f"asetpts=PTS-STARTPTS,asplit=2[vo][vosc];"
            f"[2:a]aresample=48000,atrim=0:{dur},volume=0.6[mus];"
            f"[mus][vosc]sidechaincompress=threshold=0.02:ratio=8:"
            f"attack=20:release=300[duck];"
            f"[vo][duck]amix=inputs=2:duration=first:dropout_transition=0,"
            f"loudnorm=I=-14:TP=-1.0:LRA=11[aout]"
        )
        note = "voice-over over sidechain-ducked music"
    elif has_vo:
        graph = (
            f"[1:a]aresample=48000,apad,atrim=0:{dur},"
            f"loudnorm=I=-14:TP=-1.0:LRA=11[aout]"
        )
        note = "voice-over only (no music file found)"
    elif has_music:
        graph = (
            f"[1:a]aresample=48000,atrim=0:{dur},volume=0.9,"
            f"loudnorm=I=-14:TP=-1.0:LRA=11[aout]"
        )
        note = "music only (no voice-over file found)"
    else:
        graph = (
            f"[1:a]aresample=48000,atrim=0:{dur},"
            f"loudnorm=I=-14:TP=-1.0:LRA=11[aout]"
        )
        note = "SILENT PLACEHOLDER (neither vo.mp3 nor music.mp3 found)"

    script = os.path.join(workdir, "audio_filter.txt")
    write_text(script, graph)
    cmd += ["-filter_complex_script", script,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", out_path]
    run(cmd, "audio mix + mux")
    return note


def description_text():
    return (
        f"{TITLE}\n"
        f"\n"
        f"13 years. Two delays. One launch day. GTA VI is finally here "
        f"\u2014 goodbye Los Santos, welcome to Leonida.\n"
        f"\n"
        f"{BOUNTY_LINE}\n"
        f"\n"
        f"Play code: {PLAY_CODE}\n"
        f"My referral link: {REFERRAL_LINK}\n"
        f"\n"
        f"#GTAVI #GTA6 #ViceCity #Leonida #Gaming #Shorts\n"
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None):
    home = os.path.expanduser("~")
    parser = argparse.ArgumentParser(
        description="Assemble the gta6-clipper-01 entry clip.")
    parser.add_argument(
        "--clips-dir",
        default=os.path.join(home, "workspace", "gta6-video", "clips"),
        help="directory holding shot1.mp4 ... shot8.mp4")
    parser.add_argument(
        "--audio-dir",
        default=os.path.join(home, "workspace", "gta6-video", "audio"),
        help="directory holding vo.mp3 and/or music.mp3")
    parser.add_argument(
        "--out-dir", default=os.path.dirname(os.path.abspath(__file__)),
        help="where final_short.mp4 and description.txt are written")
    parser.add_argument(
        "--font",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "Anton.ttf"),
        help="Anton font file used for the burned-in text")
    parser.add_argument(
        "--youtube-url", default=None,
        help="when given, (re)write VIDEO.json at the repo root with "
             "this YouTube address")
    parser.add_argument(
        "--keep-build", action="store_true",
        help="keep the intermediate build directory")
    args = parser.parse_args(argv)

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            print(f"error: {tool} not found on PATH", file=sys.stderr)
            return 2
    if not os.path.isfile(args.font):
        print(f"error: font not found: {args.font}", file=sys.stderr)
        return 2

    present, missing = [], []
    for stem, main_t, sub_t, mc, sc in SHOT_ORDER:
        path = os.path.join(args.clips_dir, stem + ".mp4")
        if os.path.isfile(path):
            present.append((stem, path, main_t, sub_t, mc, sc))
        else:
            missing.append(stem)
    for stem in missing:
        print(f"WARNING: clip missing, skipping: {stem}.mp4")
    if not present:
        print("error: no shot clips found at all", file=sys.stderr)
        return 2
    print(f"clips: using {len(present)} of {len(SHOT_ORDER)} "
          f"({', '.join(s for s, *_ in present)})")

    workdir = os.path.join(args.out_dir, "build")
    if os.path.isdir(workdir):
        shutil.rmtree(workdir)
    os.makedirs(workdir)

    parts = []
    for stem, path, main_t, sub_t, mc, sc in present:
        parts.append(normalise_clip(path, stem, main_t, sub_t, mc, sc,
                                    workdir, args.font))
        print(f"  normalised {stem}")
    parts.append(build_endcard(workdir, args.font))
    print("  built make.fun pitch end-card (3s)")

    master = concat_all(parts, workdir)
    total = probe_duration(master)
    print(f"timeline: {total:.2f}s including the end-card")

    final = os.path.join(args.out_dir, "final_short.mp4")
    note = mux_audio(master, args.audio_dir, total, final, workdir)
    print(f"audio: {note}")

    desc_path = os.path.join(args.out_dir, "description.txt")
    write_text(desc_path, description_text())
    print(f"wrote {final}")
    print(f"wrote {desc_path}")

    if args.youtube_url:
        video_json = os.path.join(args.out_dir, "VIDEO.json")
        write_text(video_json,
                   json.dumps({"url": args.youtube_url}, indent=2) + "\n")
        print(f"wrote {video_json} -> {args.youtube_url}")

    if not args.keep_build:
        shutil.rmtree(workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
