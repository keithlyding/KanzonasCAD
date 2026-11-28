"""Motor full-load currents and standard overcurrent sizes from the US National Electrical Code
(NFPA 70), for UDT ratings (udts.py): worked out automatically, always overridable (the owner,
Nov 2026: "I'm good with overridable auto calculations"). No Qt.

CHECK AGAINST THE CODE EDITION IN FORCE where the drawing will be used: the values below are
those of NEC 2017, 2020 and 2023 (unchanged across them as far as entered here), typed in by
hand from the tables named. Only values known with confidence are entered: a motor size or
voltage missing from a table gives no current (the rating is left for you to type), never a
guess.

- Table 430.248: full-load current, single-phase AC motors (115, 200, 208, 230 V).
- Table 430.250: full-load current, three-phase AC induction motors, squirrel cage and wound
  rotor (200, 208, 230, 460, 575 V; the 2300 V column and the synchronous motors' columns are
  left out).
- 430.6(A)(1): the tables' currents, not the nameplate's, size conductors and short-circuit
  and ground-fault protection; a motor built for 110-120 V takes the 115 V column, 220-240 V
  the 230 V one, 440-480 V the 460 V one, 550-600 V the 575 V one.
- Table 430.52: the most a motor branch circuit's short-circuit and ground-fault protection may
  be, in percent of the table current (squirrel-cage motors other than Design B energy
  efficient: nontime-delay fuse 300 %, dual-element (time-delay) fuse 175 %, instantaneous-trip
  breaker 800 %, inverse-time breaker 250 %). 430.52(C)(1) Exception No. 1: where that comes
  out between standard sizes, the next size up is allowed. The percent a UDT uses is its own
  (a shop's rule, a drive maker's fuse table): these are where its rules start.
- 240.6(A): the standard ampere ratings of fuses and inverse-time breakers (and, for fuses
  only, 1, 3, 6, 10 and 601 A).
- 430.110(A): a motor's disconnecting means rated at least 115 % of the table current; the
  switch sizes it is rounded up to (30, 60, 100, 200... A) are the common safety-switch sizes,
  not a table of the code.
"""

from fractions import Fraction
import re

# Table 430.248, single-phase AC motors: {HP: {volts column: amps}}
SINGLE_PHASE = {
    Fraction(1, 6): {115: 4.4, 200: 2.5, 208: 2.4, 230: 2.2},
    Fraction(1, 4): {115: 5.8, 200: 3.3, 208: 3.2, 230: 2.9},
    Fraction(1, 3): {115: 7.2, 200: 4.1, 208: 4.0, 230: 3.6},
    Fraction(1, 2): {115: 9.8, 200: 5.6, 208: 5.4, 230: 4.9},
    Fraction(3, 4): {115: 13.8, 200: 7.9, 208: 7.6, 230: 6.9},
    Fraction(1): {115: 16.0, 200: 9.2, 208: 8.8, 230: 8.0},
    Fraction(3, 2): {115: 20.0, 200: 11.5, 208: 11.0, 230: 10.0},
    Fraction(2): {115: 24.0, 200: 13.8, 208: 13.2, 230: 12.0},
    Fraction(3): {115: 34.0, 200: 19.6, 208: 18.7, 230: 17.0},
    Fraction(5): {115: 56.0, 200: 32.2, 208: 30.8, 230: 28.0},
    Fraction(15, 2): {115: 80.0, 200: 46.0, 208: 44.0, 230: 40.0},
    Fraction(10): {115: 100.0, 200: 57.5, 208: 55.0, 230: 50.0},
}

# Table 430.250, three-phase induction motors (squirrel cage and wound rotor)
_THREE_COLUMNS = (200, 208, 230, 460, 575)
_THREE_ROWS = [
    (Fraction(1, 2), (2.5, 2.4, 2.2, 1.1, 0.9)),
    (Fraction(3, 4), (3.7, 3.5, 3.2, 1.6, 1.3)),
    (Fraction(1), (4.8, 4.6, 4.2, 2.1, 1.7)),
    (Fraction(3, 2), (6.9, 6.6, 6.0, 3.0, 2.4)),
    (Fraction(2), (7.8, 7.5, 6.8, 3.4, 2.7)),
    (Fraction(3), (11.0, 10.6, 9.6, 4.8, 3.9)),
    (Fraction(5), (17.5, 16.7, 15.2, 7.6, 6.1)),
    (Fraction(15, 2), (25.3, 24.2, 22.0, 11.0, 9.0)),
    (Fraction(10), (32.2, 30.8, 28.0, 14.0, 11.0)),
    (Fraction(15), (48.3, 46.2, 42.0, 21.0, 17.0)),
    (Fraction(20), (62.1, 59.4, 54.0, 27.0, 22.0)),
    (Fraction(25), (78.2, 74.8, 68.0, 34.0, 27.0)),
    (Fraction(30), (92.0, 88.0, 80.0, 40.0, 32.0)),
    (Fraction(40), (120.0, 114.0, 104.0, 52.0, 41.0)),
    (Fraction(50), (150.0, 143.0, 130.0, 65.0, 52.0)),
    (Fraction(60), (177.0, 169.0, 154.0, 77.0, 62.0)),
    (Fraction(75), (221.0, 211.0, 192.0, 96.0, 77.0)),
    (Fraction(100), (285.0, 273.0, 248.0, 124.0, 99.0)),
    (Fraction(125), (359.0, 343.0, 312.0, 156.0, 125.0)),
    (Fraction(150), (414.0, 396.0, 360.0, 180.0, 144.0)),
    (Fraction(200), (552.0, 528.0, 480.0, 240.0, 192.0)),
]
THREE_PHASE = {hp: dict(zip(_THREE_COLUMNS, amps)) for hp, amps in _THREE_ROWS}

# 240.6(A) standard ampere ratings
STANDARD = (15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200, 225,
            250, 300, 350, 400, 450, 500, 600, 700, 800, 1000, 1200, 1600, 2000, 2500, 3000,
            4000, 5000, 6000)
FUSE_EXTRA = (1, 3, 6, 10, 601)
# (not the code's: the common sizes of safety switches, for a disconnect at 115 %)
SWITCH = (30, 60, 100, 200, 400, 600, 800, 1200)

# Table 430.52's percents, where a UDT's rules start
PERCENT_DUAL_ELEMENT_FUSE = 175
PERCENT_NONTIME_DELAY_FUSE = 300
PERCENT_INVERSE_TIME_BREAKER = 250
PERCENT_DISCONNECT = 115            # 430.110(A)

ROUNDINGS = {"fuse": "Next standard fuse size (240.6(A))",
             "breaker": "Next standard breaker size (240.6(A))",
             "switch": "Next switch size (30, 60, 100, 200 A...)",
             "none": "As worked out (one decimal)"}

_MIXED = re.compile(r"^\s*(\d+)\s*[- ]\s*(\d+)\s*/\s*(\d+)\s*$")


def horsepower(text):
    """A horsepower typed (5, 7.5, 7-1/2, 1/2, "5HP"), as a Fraction, or None."""
    t = str(text or "").strip().upper().replace("HP", "").strip()
    if not t:
        return None
    m = _MIXED.match(t)
    try:
        if m:
            return Fraction(int(m.group(1))) + Fraction(int(m.group(2)), int(m.group(3)))
        return Fraction(t.replace(" ", ""))
    except (ValueError, ZeroDivisionError):
        return None


def number(text):
    """A plain number typed (460, "460V", "7.6A"), or None."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)", str(text or ""))
    return float(m.group(1)) if m else None


def column(volts, phase):
    """The table's voltage column for a motor of this nameplate voltage (430.6(A)(1)), or
    None."""
    if volts is None:
        return None
    v = round(volts)
    if phase == 1:
        if 110 <= v <= 120:
            return 115
        if v in (200, 208):
            return v
        if 220 <= v <= 240:
            return 230
        return None
    if v in (200, 208):
        return v
    if 220 <= v <= 240:
        return 230
    if 440 <= v <= 480:
        return 460
    if 550 <= v <= 600:
        return 575
    return None


def flc(hp, volts, phase=3):
    """The table full-load current (amps) of a motor (hp and volts as typed), or None when
    the tables don't give one (a size or voltage not in them)."""
    h = horsepower(hp)
    ph = 1 if str(phase).strip() == "1" else 3
    col = column(number(volts), ph)
    if h is None or col is None:
        return None
    row = (SINGLE_PHASE if ph == 1 else THREE_PHASE).get(h)
    return None if row is None else row.get(col)


def round_up(amps, how):
    """amps rounded up as how says (ROUNDINGS): the next standard size at or above it, or as
    it is to one decimal. None past the largest size."""
    if how == "none":
        return round(amps + 1e-9, 1)
    sizes = {"fuse": sorted(STANDARD + FUSE_EXTRA), "breaker": STANDARD,
             "switch": SWITCH}.get(how, STANDARD)
    for s in sizes:
        if s >= amps - 1e-9:
            return s
    return None


def fmt(v):
    """A number as a rating shows it: 15, 7.6."""
    if v is None:
        return ""
    v = round(float(v), 1)
    return ("%d" % v) if v == int(v) else ("%g" % v)
