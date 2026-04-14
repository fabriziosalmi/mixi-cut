"""MIXI-CUT Protocol Constants and Frame Format.

Central source of truth for all protocol parameters.
All other modules import from here — never hardcode these values.

Protocol v0.3.0:
  - CRC-16 parallel to RS for fast-reject
  - Barker-13 sync word for frame acquisition
  - Multi-rate encoding (dense near inner groove)
  - Velocity subcarrier at 500 Hz
"""

# ── Carrier ───────────────────────────────────────────────────

SAMPLE_RATE = 44100           # Hz — CD quality, universal
CARRIER_FREQ = 3000           # Hz — stereo quadrature carrier
AMPLITUDE = 0.85              # linear, ≈ -1.4 dBFS peak

# ── Velocity subcarrier (v0.3) ───────────────────────────────

VELOCITY_SUBCARRIER_FREQ = 500     # Hz — AM-modulated onto carrier
VELOCITY_MODULATION_DEPTH = 0.15   # max ±15% amplitude modulation
VELOCITY_RANGE = (-2.0, 3.0)       # speed mapped to subcarrier amplitude

# ── Timing ────────────────────────────────────────────────────

DEFAULT_DURATION = 15 * 60    # seconds (15 min = full side 12")
LEAD_IN_SECONDS = 2.0         # silence before timecode (needle placement)
LEAD_OUT_SECONDS = 1.0        # silence after timecode (run-out groove)
FADE_SAMPLES = 441            # 10 ms fade in/out at 44.1 kHz

# ── Position encoding ────────────────────────────────────────

POSITION_BITS = 24            # max 167772 seconds ≈ 46 hours
POSITION_CYCLE_INTERVAL = 50  # 1 bit every 50 carrier cycles
RS_PARITY_BYTES = 4           # Reed-Solomon parity symbols
FRAME_DATA_BYTES = 3          # 24-bit position = 3 bytes
CRC_BYTES = 2                 # CRC-16 for fast-reject (v0.3)
FRAME_TOTAL_BYTES = FRAME_DATA_BYTES + CRC_BYTES + RS_PARITY_BYTES  # 9 bytes
FRAME_TOTAL_BITS = FRAME_TOTAL_BYTES * 8                # 72 bits

# ── Sync word (v0.3) ─────────────────────────────────────────

# Barker-13: excellent autocorrelation, sidelobe ≤ 1/13
BARKER_13 = [1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1]
SYNC_WORD_BITS = len(BARKER_13)                          # 13 bits
TOTAL_FRAME_BITS = SYNC_WORD_BITS + FRAME_TOTAL_BITS     # 85 bits

CYCLES_PER_FRAME = POSITION_CYCLE_INTERVAL * TOTAL_FRAME_BITS   # 4250
SECONDS_PER_FRAME = CYCLES_PER_FRAME / CARRIER_FREQ             # 1.417s

# ── Multi-rate encoding (v0.3) ───────────────────────────────

# Frame interval varies by position: dense near inner groove (high position)
# Outer groove (0-300s): every frame_interval cycles (normal)
# Inner groove (>300s): every frame_interval/2 cycles (double rate)
MULTI_RATE_THRESHOLD_SEC = 300   # seconds — switch to dense encoding
MULTI_RATE_DENSE_FACTOR = 2      # 2x frame rate on inner groove

# ── Missing cycle modulation ─────────────────────────────────

MISSING_CYCLE_DEPTH = 0.25    # amplitude dip for bit=1
TRANSITION_SAMPLES = 4        # raised-cosine ramp length (~0.09 ms)

# ── GF(2^8) primitive polynomial ──────────────────────────────

GF_PRIMITIVE_POLY = 0x11D     # x^8 + x^4 + x^3 + x^2 + 1

# ── CRC-16 polynomial (v0.3) ────────────────────────────────

CRC16_POLY = 0x8005           # CRC-16/ARC (USB), standard
CRC16_INIT = 0xFFFF           # initial value

# ── Decoder defaults ─────────────────────────────────────────

PLL_BANDWIDTH_PCT = 0.08      # 8% of carrier = 240 Hz (narrow)
PLL_Q = 2.5                   # bandpass filter quality factor
PLL_LOCK_TAU = 0.05           # lock detector EMA time constant (seconds)
PLL_AMPLITUDE_GATE = 0.005    # coast below this amplitude (≈ -46 dBFS)
PLL_INTEGRAL_DRAIN = 0.98     # integral decay rate when unlocked

# ── Dual-PLL (v0.3.1) ───────────────────────────────────────

PLL_WIDE_BANDWIDTH_PCT = 0.20        # 20% of carrier = 600 Hz (wide)
PLL_HANDOFF_LOCK_THRESHOLD = 0.8     # switch to narrow when lock > this
PLL_HANDOFF_SAMPLES = 2205           # 50 ms at 44100 Hz hold time
PLL_FALLBACK_LOCK_THRESHOLD = 0.3    # fallback to wide when lock < this
PLL_FALLBACK_SAMPLES = 882           # 20 ms at 44100 Hz hold time
PLL_WIDE_SPEED_THRESHOLD = 1.8       # force wide when |speed| > this

# ── Mass-spring damper ───────────────────────────────────────

MASS_SPRING_INERTIA = 0.95    # platter inertia (normal play)
MASS_SPRING_SCRATCH_THRESHOLD = 0.3   # delta threshold for scratch detect
MASS_SPRING_STOP_TRACTION_MULT = 10.0 # traction multiplier near zero speed
MASS_SPRING_DEAD_ZONE = 0.02  # snap to 0 below this speed

# ── Brake regime (v0.3.1) ────────────────────────────────────

MASS_SPRING_BRAKE_EXP_RATE = 3.0          # exponential traction rate
MASS_SPRING_BRAKE_SNAP_THRESHOLD = 0.08   # bypass spring below this speed
MASS_SPRING_BRAKE_RELEASE_SAMPLES = 50    # gradual restore on restart

# ── Lathe cutting parameters ─────────────────────────────────

RPM = 33.333                  # standard DJ turntable speed
GROOVE_LINES_PER_INCH = 200   # wider than music vinyl for robustness
GROOVE_SPACING_M = 1.0 / (GROOVE_LINES_PER_INCH * 39.37)
GROOVE_TIME_SEC = 60.0 / RPM  # time per revolution ≈ 1.8s

# ── Presets ───────────────────────────────────────────────────

PRESETS = {
    "dj-12inch": {"duration": 900, "rpm": 33.333, "riaa": False, "loop": True,
                  "description": "Full side 12\" DJ vinyl (15 min)"},
    "dj-7inch":  {"duration": 240, "rpm": 45, "riaa": False, "loop": True,
                  "description": "Single side 7\" (4 min)"},
    "test-cut":  {"duration": 60, "rpm": 33.333, "riaa": False, "loop": False,
                  "description": "60s test for quick iteration"},
    "phono":     {"duration": 900, "rpm": 33.333, "riaa": True, "loop": True,
                  "description": "Full side with RIAA pre-emphasis"},
    "locked-groove": {"duration": 1.8, "rpm": 33.333, "riaa": False, "loop": True,
                      "description": "Single revolution locked groove"},
}
