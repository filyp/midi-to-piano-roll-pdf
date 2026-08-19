#!/usr/bin/env python3
"""Render a piano MIDI or **kern file as piano roll pages in a printable PDF.

Each page covers config.BARS_PER_PAGE bars on an A4-shaped page. Left/right
hand are colored differently (determined from the file's parts/tracks).

Usage:
    python midi_to_piano_roll.py song.mid|song.krn [-o out.pdf]
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

import config

BLACK_PCS = {1, 3, 6, 8, 10}  # pitch classes of black keys
TPB = 480  # internal ticks per quarter note for kern input


def is_black(note):
    return note % 12 in BLACK_PCS


def assign_hands(part_notes):
    """part_notes: list of note lists, one per part/track.

    Returns flat note list with hand index set: the part with the highest
    mean pitch becomes hand 0 (right), all others hand 1 (left).
    """
    parts = [pn for pn in part_notes if pn]
    if not parts:
        sys.exit("No notes found in the input file.")
    means = [sum(n[2] for n in pn) / len(pn) for pn in parts]
    right = means.index(max(means))
    notes = []
    for i, pn in enumerate(parts):
        hand = 0 if (i == right or len(parts) == 1) else 1
        notes += [(s, e, p, hand) for s, e, p, _ in pn]
    return notes


def load_midi(path):
    import mido
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat
    part_notes = []
    max_tick = 0
    timesigs = []

    for track in mid.tracks:
        t = 0
        active = {}
        pn = []
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
                    pn.append((start, max(t, start + 1), msg.note, None))
        max_tick = max(max_tick, t)
        part_notes.append(pn)

    notes = assign_hands(part_notes)
    max_tick = max(max_tick, max(n[1] for n in notes))

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
        tick += max(int(round(num * tpb * 4 / den)), 1)

    return notes, tpb, bar_starts


def load_kern(path):
    # music21's own humdrum parser drops notes on mid-piece spine splits
    # (*^), so go kern -> MEI via verovio, then parse the MEI.
    import verovio
    from music21 import converter
    from music21.mei import base as mei_base
    # music21's MEI importer crashes on beam groups ending in a rest
    # (Rest has no .beams); beaming is irrelevant for a piano roll.
    mei_base.beamTogether = lambda things, *a, **kw: things
    tk = verovio.toolkit()
    if not tk.loadFile(path):
        sys.exit(f"verovio could not parse {path}")
    score = converter.parse(tk.getMEI(), format="mei")

    # Single-spine files (e.g. Bach WTC) have no staff separation; fall
    # back to the notated voices so hands can still be told apart.
    note_parts = list(score.parts)
    if len(note_parts) == 1:
        voiced = note_parts[0].voicesToParts()
        if len(voiced.parts) > 1:
            note_parts = list(voiced.parts)

    part_notes = []
    bar_offsets = set()
    for part in note_parts:
        pn = []
        open_ties = {}  # pitch -> index into pn of the note awaiting its tail
        elems = sorted(part.flatten().notes, key=lambda n: n.offset)
        for n in elems:
            s = int(float(n.offset) * TPB)
            e = int((float(n.offset) + float(n.duration.quarterLength)) * TPB)
            e = max(e, s + 1)
            for comp in (n.notes if n.isChord else [n]):
                p = comp.pitch.midi
                tie = comp.tie.type if comp.tie else None
                prev = open_ties.get(p)
                if tie in ("stop", "continue") and prev is not None:
                    ps, pe, pp, ph = pn[prev]
                    pn[prev] = (ps, max(pe, e), pp, ph)
                    if tie == "stop":
                        del open_ties[p]
                else:
                    pn.append((s, e, p, None))
                    if tie in ("start", "continue"):
                        open_ties[p] = len(pn) - 1
        part_notes.append(pn)
        for m in part.recurse().getElementsByClass("Measure"):
            bar_offsets.add(int(float(m.getOffsetInHierarchy(part)) * TPB))

    notes = assign_hands(part_notes)
    bar_starts = sorted(bar_offsets)
    if not bar_starts:
        bar_starts = [0]
    return notes, TPB, bar_starts


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
    between their neighbors at config.BLACK_KEY_WIDTH of a white key.
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
            bw = ww * config.BLACK_KEY_WIDTH
            spans[p] = (edge - bw / 2, edge + bw / 2)
    return spans, whites, ww


def render_page(bar_number_first, page_bars, notes, spans, whites,
                lo, hi, font):
    W = config.IMAGE_WIDTH
    H = int(round(W * config.A4_RATIO))
    x0_page, x1_page = config.MARGIN_LEFT, W - config.MARGIN_RIGHT
    y_top, y_bot = config.MARGIN_TOP, H - config.MARGIN_BOTTOM

    start_tick = page_bars[0]
    end_tick = page_bars[-1]
    px_per_tick = (y_bot - y_top) / (end_tick - start_tick)
    downward = config.DIRECTION == "down"

    def y_of(tick):
        if downward:
            return y_top + (tick - start_tick) * px_per_tick
        return y_bot - (tick - start_tick) * px_per_tick

    img = Image.new("RGB", (W, H), config.BACKGROUND)
    draw = ImageDraw.Draw(img)

    # vertical guides only at the B/C and E/F boundaries
    for p in whites:
        if p % 12 in (0, 5):  # C and F: line at their left edge (B|C, E|F)
            x = spans[p][0]
            w = config.BC_LINE_WIDTH if p % 12 == 0 else config.LINE_WIDTH
            draw.line([x, y_top, x, y_bot], fill=config.LINE, width=w)

    # bar lines + numbers
    for i, bt in enumerate(page_bars[:-1]):
        y = y_of(bt)
        draw.line([x0_page, y, x1_page, y], fill=config.LINE,
                  width=config.LINE_WIDTH)
        if config.SHOW_BAR_NUMBERS:
            # place the number inside the bar it labels
            ty = y + 4 if downward else y - config.FONT_SIZE - 4
            draw.text((x0_page + 4, ty),
                      str(bar_number_first + i), fill=config.TEXT, font=font)
    y = y_of(end_tick)
    draw.line([x0_page, y, x1_page, y], fill=config.LINE,
              width=config.LINE_WIDTH)

    # notes (clipped to page)
    for s, e, p, hand in notes:
        if e <= start_tick or s >= end_tick or not (lo <= p <= hi):
            continue
        s_c, e_c = max(s, start_tick), min(e, end_tick)
        nx0, nx1 = spans[p]
        ya, yb = y_of(s_c), y_of(e_c)
        palette = config.LEFT_HAND if hand == 1 else config.RIGHT_HAND
        color = palette["black"] if is_black(p) else palette["white"]
        draw.rounded_rectangle([nx0 + 1, min(ya, yb), nx1 - 1, max(ya, yb)],
                               radius=config.NOTE_RADIUS, fill=color)

    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input_file", help="MIDI (.mid/.midi) or kern (.krn)")
    ap.add_argument("-o", "--output", default=None,
                    help="output PDF path (default: <input name>.pdf)")
    args = ap.parse_args()

    ext = os.path.splitext(args.input_file)[1].lower()
    if ext == ".krn":
        notes, tpb, bar_starts = load_kern(args.input_file)
    else:
        notes, tpb, bar_starts = load_midi(args.input_file)

    if config.KEY_RANGE:
        lo, hi = config.KEY_RANGE
    else:
        pitches = [n[2] for n in notes]
        lo = (min(pitches) // 12) * 12       # round down to C
        hi = (max(pitches) // 12) * 12 + 11  # round up to B

    spans, whites, _ww = key_layout(
        lo, hi, config.MARGIN_LEFT,
        config.IMAGE_WIDTH - config.MARGIN_LEFT - config.MARGIN_RIGHT)
    font = load_font()

    out_path = args.output or (
        os.path.splitext(args.input_file)[0] + config.OUTPUT_SUFFIX)

    bpp = config.BARS_PER_PAGE
    n_pages = max(1, (len(bar_starts) - 1 + bpp - 1) // bpp)
    pages = []
    for page in range(n_pages):
        chunk = bar_starts[page * bpp: page * bpp + bpp + 1]
        if len(chunk) < 2:
            last = chunk[0] if chunk else bar_starts[-1]
            chunk = [last, last + tpb * 4]
        pages.append(render_page(page * bpp + 1, chunk, notes, spans, whites,
                                 lo, hi, font))

    # dpi such that the pixel width prints as A4 width (210 mm)
    dpi = config.IMAGE_WIDTH / (210 / 25.4)
    pages[0].save(out_path, save_all=True, append_images=pages[1:],
                  resolution=dpi)
    print(f"wrote {out_path}: {n_pages} page(s), keys {lo}..{hi}, "
          f"{len(notes)} notes")


if __name__ == "__main__":
    main()
