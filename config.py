"""Configuration for the piano roll renderer."""

# --- Paging ---
BARS_PER_PAGE = 8          # bars (measures) per output image

# --- Image geometry (A4 portrait) ---
IMAGE_WIDTH = 1748         # px; height is width * sqrt(2) ~ A4 at 150 dpi
A4_RATIO = 2 ** 0.5
# px page margins per side
MARGIN_LEFT = 30
MARGIN_RIGHT = 30
MARGIN_TOP = 30
MARGIN_BOTTOM = 100

# --- Key range ---
# None = use only the octaves actually present in the piece (rounded out to
# full C..B octaves). Or set explicitly, e.g. (21, 108) for a full 88 keys.
KEY_RANGE = None

# --- Direction ---
# "down": time flows downward, first bar at the top (reading order).
# "up": Synthesia-style, first bar at the bottom, later notes higher up.
DIRECTION = "down"

# --- Colors ---
BACKGROUND = (255, 255, 255)
LINE = (0, 0, 0)           # bar lines and B/C, E/F lane lines
TEXT = (0, 0, 0)

# Note colors per hand; "white"/"black" = key color, white keys lighter.
# Hand 0 = right, hand 1 = left, hand 2 = pedal. Determined from kern spines
# / MIDI tracks (the part with the higher average pitch is taken as the right
# hand); single-part files are drawn entirely with RIGHT_HAND colors.
RIGHT_HAND = {"white": (160, 245, 160), "black": (60, 180, 60)}    # green
LEFT_HAND = {"white": (255, 180, 180), "black": (180, 60, 60)}     # red
PEDAL = {"white": (170, 200, 255), "black": (50, 100, 200)}        # blue

# A pedal part is detected automatically: with three or more parts, the
# lowest one is taken to be the pedal (two hands cover two parts; a third
# means feet). Two-part piano music never has one.
#
# Draw the pedal part shifted by this many octaves, to pull it clear of the
# left hand when their ranges overlap. Negative = down. 0 = true pitch.
PEDAL_OCTAVE = 0

# --- Key geometry ---
BLACK_KEY_WIDTH = 0.5      # black key lane width as fraction of a white key

LINE_WIDTH = 1             # bar lines and E|F lane lines
BC_LINE_WIDTH = 5          # the B|C (H|C) lane lines, i.e. octave boundaries
NOTE_RADIUS = 15            # px, rounded corner radius of notes

# --- Output ---
# PDF is written next to the input file as <name>.pdf unless -o is given.
OUTPUT_SUFFIX = ".pdf"

# --- Misc ---
SHOW_BAR_NUMBERS = True
FONT_SIZE = 28
