#!/usr/bin/env python3
"""Render a piano MIDI file as Synthesia-style piano roll images.

Notes fall from the top toward the bottom of an A4-shaped page: the earliest
beat of a page sits at the bottom and later notes are higher up. Each page
covers config.BARS_PER_PAGE bars.

Usage:
    python midi_to_piano_roll.py song.mid [-o output_dir]
"""

import argparse
import os
import sys

import mido
from PIL import Image, ImageDraw, ImageFont

import config

BLACK_PCS = {1, 3, 6, 8, 10}  # pitch classes of black keys


def is_black(note):
    return note % 12 in BLACK_PCS


def theme():
    return config.DARK if config.DARK_MODE else config.LIGHT


def extract_notes(mid):
    """Return (notes, ticks_per_beat, bar_starts_ticks).

    notes: list of (start_tick, end_tick, pitch, track_index)
    bar_starts_ticks: tick position of the start of every bar, covering the
    whole file, honoring time signature changes.
    """
    tpb = mid.ticks_per_beat
    notes = []
    max_tick = 0
    timesigs = []  # (tick, numerator, denominator)

    for ti, track in enumerate(mid.tracks):
        t = 0
        active = {}  # pitch -> start ticks
        for msg in track:
            t += msg.time
            if msg.type == "time_signature":
                timesigs.append((t, msg.numerator, msg.denominator))
            elif msg.type == "note_on" and msg.velocity > 0:
                active.setdefault(msg.note, []).append(t)
            elif msg.type in ("note_off", "note_on"):
                starts = active.get(msg.note)
                if starts:
                    start = starts.pop(0)
                    end = max(t, start + 1)
                    notes.append((start, end, msg.note, ti))
        max_tick = max(max_tick, t)

    if not notes:
        sys.exit("No notes found in the MIDI file.")
    max_tick = max(max_tick, max(n[1] for n in notes))

    # Build bar boundaries from time signatures (default 4/4).
    timesigs.sort()
    if not timesigs or timesigs[0][0] > 0:
        timesigs.insert(0, (0, 4, 4))

    bar_starts = []
    tick = 0
    i = 0
    while tick <= max_tick:
        bar_starts.append(tick)
        while i + 1 < len(timesigs) and timesigs[i + 1][0] <= tick:
            i += 1
        num, den = timesigs[i][1], timesigs[i][2]
        bar_len = int(round(num * tpb * 4 / den))
        tick += max(bar_len, 1)

    return notes, tpb, bar_starts


def load_font():
    for path in (
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, config.FONT_SIZE)
    return ImageFont.load_default()


def key_layout(lo, hi, x_left, width):
    """Return dict pitch -> (x0, x1) horizontal span.

    White keys split the width evenly; black keys straddle the boundary
    between their neighbors at ~60% of a white key's width.
    """
    whites = [p for p in range(lo, hi + 1) if not is_black(p)]
    ww = width / max(len(whites), 1)
    wx = {p: x_left + i * ww for i, p in enumerate(whites)}
    spans = {}
    for p in range(lo, hi + 1):
        if not is_black(p):
            x = wx[p]
            spans[p] = (x, x + ww)
        else:
            edge = wx[p - 1] + ww
            bw = ww * 0.6
            spans[p] = (edge - bw / 2, edge + bw / 2)
    return spans, whites, ww


def render_page(page_idx, page_bars, notes, tpb, spans, whites, ww,
                lo, hi, font):
    th = theme()
    W = config.IMAGE_WIDTH
    H = int(round(W * config.A4_RATIO))
    m = config.MARGIN
    x0_page, x1_page = m, W - m
    y_top, y_bot = m, H - m

    start_tick = page_bars[0]
    end_tick = page_bars[-1]
    px_per_tick = (y_bot - y_top) / (end_tick - start_tick)

    def y_of(tick):
        # earliest tick of the page maps to the bottom of the page
        return y_bot - (tick - start_tick) * px_per_tick

    img = Image.new("RGB", (W, H), th["background"])
    draw = ImageDraw.Draw(img)

    # vertical guides only at the B/C and E/F boundaries
    for p in whites:
        if p % 12 in (0, 5):  # C and F: line at their left edge (B|C, E|F)
            x = spans[p][0]
            draw.line([x, y_top, x, y_bot], fill=th["line"],
                      width=config.LINE_WIDTH)

    # bar lines + numbers
    first_bar_number = page_idx * config.BARS_PER_PAGE + 1
    for i, bt in enumerate(page_bars[:-1]):
        y = y_of(bt)
        draw.line([x0_page, y, x1_page, y], fill=th["line"],
                  width=config.LINE_WIDTH)
        if config.SHOW_BAR_NUMBERS:
            draw.text((x0_page + 4, y - config.FONT_SIZE - 4),
                      str(first_bar_number + i), fill=th["text"], font=font)
    y = y_of(end_tick)
    draw.line([x0_page, y, x1_page, y], fill=th["line"],
              width=config.LINE_WIDTH)

    # notes (clipped to page)
    for s, e, p, _ti in notes:
        if e <= start_tick or s >= end_tick or not (lo <= p <= hi):
            continue
        s_c, e_c = max(s, start_tick), min(e, end_tick)
        nx0, nx1 = spans[p]
        ny_top, ny_bot = y_of(e_c), y_of(s_c)
        color = th["black_key_note"] if is_black(p) else th["white_key_note"]
        draw.rounded_rectangle([nx0 + 1, ny_top, nx1 - 1, ny_bot],
                               radius=config.NOTE_RADIUS, fill=color)

    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("midi_file")
    ap.add_argument("-o", "--output", default=None,
                    help="output PDF path (default: <input name>.pdf)")
    args = ap.parse_args()

    mid = mido.MidiFile(args.midi_file)
    notes, tpb, bar_starts = extract_notes(mid)

    if config.KEY_RANGE:
        lo, hi = config.KEY_RANGE
    else:
        pitches = [n[2] for n in notes]
        lo = (min(pitches) // 12) * 12       # round down to C
        hi = (max(pitches) // 12) * 12 + 11  # round up to B

    spans, whites, ww = key_layout(
        lo, hi, config.MARGIN, config.IMAGE_WIDTH - 2 * config.MARGIN)
    font = load_font()

    out_path = args.output or (
        os.path.splitext(args.midi_file)[0] + config.OUTPUT_SUFFIX)

    bpp = config.BARS_PER_PAGE
    n_pages = (len(bar_starts) + bpp - 1) // bpp
    pages = []
    for page in range(n_pages):
        chunk = bar_starts[page * bpp: page * bpp + bpp + 1]
        if len(chunk) < 2:
            last = chunk[0] if chunk else bar_starts[-1]
            chunk = [last, last + tpb * 4]
        pages.append(render_page(page, chunk, notes, tpb, spans, whites, ww,
                                 lo, hi, font))

    # dpi such that the pixel width prints as A4 width (210 mm)
    dpi = config.IMAGE_WIDTH / (210 / 25.4)
    pages[0].save(out_path, save_all=True, append_images=pages[1:],
                  resolution=dpi)
    print(f"wrote {out_path}: {n_pages} page(s), keys {lo}..{hi}, "
          f"{len(notes)} notes")


if __name__ == "__main__":
    main()
