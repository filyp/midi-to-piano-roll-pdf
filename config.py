"""Configuration for the piano roll renderer."""

# --- Paging ---
BARS_PER_PAGE = 8          # bars (measures) per output image

# --- Image geometry (A4 portrait) ---
IMAGE_WIDTH = 1748         # px; height is width * sqrt(2) ~ A4 at 150 dpi
A4_RATIO = 2 ** 0.5
MARGIN = 30                # px page margin on all sides

# --- Key range ---
# None = use only the octaves actually present in the piece (rounded out to
# full C..B octaves). Or set explicitly, e.g. (21, 108) for a full 88 keys.
KEY_RANGE = None

# --- Direction ---
# "down": time flows downward, first bar at the top (reading order).
# "up": Synthesia-style, first bar at the bottom, later notes higher up.
DIRECTION = "down"

# --- Theme ---
DARK_MODE = False

LIGHT = {
    "background": (255, 255, 255),
    "line": (0, 0, 0),             # bar lines and B/C, E/F lane lines
    "white_key_note": (150, 150, 150),
    "black_key_note": (0, 0, 0),
    "text": (0, 0, 0),
}
DARK = {
    "background": (0, 0, 0),
    "line": (255, 255, 255),
    "white_key_note": (255, 255, 255),
    "black_key_note": (150, 150, 150),
    "text": (255, 255, 255),
}

LINE_WIDTH = 1
NOTE_RADIUS = 3            # px, rounded corner radius of notes

# --- Output ---
# PDF is written next to the input file as <name>.pdf unless -o is given.
OUTPUT_SUFFIX = ".pdf"

# --- Misc ---
SHOW_BAR_NUMBERS = True
FONT_SIZE = 16
