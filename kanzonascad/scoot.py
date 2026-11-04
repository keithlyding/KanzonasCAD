"""Sliding devices along their own wires (no Qt): AutoCAD Electrical's Scoot and Align.

A device's wire runs the way its pins face each other: across for a horizontal rung (pins on
the left and right), up and down for a vertical wire. Sliding it that way, the wires on its
pins stretch on one side and shorten on the other (wires.follow_pins, at the end of the edit),
staying straight. It can slide only as far as the wire on each pin reaches before a corner or
its far end, less a little (it never folds a wire back on itself).
"""

import math

from .model import Insert, Wire

TOL = 1e-6
MARGIN = 0.0625                 # left of a wire's piece between a pin and the next corner


def axis(ins):
    """(1, 0) when the device's wire runs across, (0, 1) up and down, None without two pins."""
    pins = [p for _n, p in ins.pin_points()]
    if len(pins) < 2:
        return None
    dx = max(p[0] for p in pins) - min(p[0] for p in pins)
    dy = max(p[1] for p in pins) - min(p[1] for p in pins)
    return (1.0, 0.0) if dx >= dy else (0.0, 1.0)


def limits(sheet, ins, ax):
    """(how far back, how far forward) the device can slide along ax: each pin's wire piece
    running away from it limits the slide toward that piece's far end; a wire piece running
    toward the device limits nothing (it gets longer). Infinite when nothing limits."""
    back = fwd = math.inf
    for _n, p in ins.pin_points():
        for e in sheet.query((p[0] - TOL, p[1] - TOL, p[0] + TOL, p[1] + TOL)):
            if not isinstance(e, Wire):
                continue
            pts = e.points
            for i in (0, -1):
                if abs(pts[i][0] - p[0]) > TOL or abs(pts[i][1] - p[1]) > TOL:
                    continue
                q = pts[1] if i == 0 else pts[-2]           # the next corner or the far end
                along = (q[0] - p[0]) * ax[0] + (q[1] - p[1]) * ax[1]
                across = abs((q[0] - p[0]) * ax[1] - (q[1] - p[1]) * ax[0])
                if across > TOL:
                    continue            # (a piece leaving at a right angle: no limit along)
                room = max(0.0, abs(along) - MARGIN)
                if along > 0:
                    fwd = min(fwd, room)
                elif along < 0:
                    back = min(back, room)
    return back, fwd


def clamp(sheet, ins, ax, d):
    """The slide d (signed distance along ax) cut to what the wires allow."""
    back, fwd = limits(sheet, ins, ax)
    return max(-back, min(fwd, d))


def devices(ents):
    """The block references among ents that have a wire direction."""
    return [e for e in ents if isinstance(e, Insert) and axis(e) is not None]
