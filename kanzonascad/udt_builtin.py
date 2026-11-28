"""The program's own UDTs (no Qt), read-only as its blocks and parts are (one of yours with the
same name takes its place; editing one saves your own copy): two motor circuits, the owner's
two styles of motor circuit (Nov 2026: "If I have two different style motor circuits, I would
use two different UDTs"). Drawn from the JIC symbols for horizontal power: L1, L2, L3 left to
right at y = 0, -1/2 and -1 from the base point (the incoming end of L1), 1/2 inch apart as
the 3-pole symbols' poles are.

- Motor circuit, VFD: disconnect, manual motor starter or fuses (a choice), line reactor
  (optional), PowerFlex 525-style drive, load reactor (optional), terminals, motor.
- Motor circuit, full-voltage starter: disconnect, fuses or a circuit breaker (a choice),
  contactor, overload, terminals, motor, and its control rung (the contactor's coil and the
  overload's contact), linked to them.

Their rating rules start from NEC Table 430.52's percents (nec_tables.py); each UDT's own
percents can be changed in the UDT editor, and each placed one's in UDT properties.
"""

from . import model as M
from . import nec_tables as NEC
from .udts import INCLUDED, LEFT_OUT, MOTOR_VALUES, Udt

POWER = (0.0, -0.5, -1.0)       # L1, L2, L3
MIDDLE = -0.5                   # a 3-pole symbol's insertion point (its L2)


class _Drawing:
    """Members of a built-in UDT, drawn in code."""

    def __init__(self, blocks):
        self.blocks = blocks
        self.members = []
        self.used = {}

    def _add(self, e, slot, alt):
        d = e.to_dict()
        d.pop("id", None)
        self.members.append({"role": "r%d" % (len(self.members) + 1), "slot": slot,
                             "alt": alt, "entity": d})

    def symbol(self, name, x, y=MIDDLE, slot="", alt="", **attrs):
        d = self.blocks[name]
        self.used[name] = d
        self._add(M.Insert(name, (x, y), defn=d, attrs=attrs, layer="SYMBOLS"), slot, alt)
        return self.members[-1]["role"]

    def wires(self, x0, x1, slot="", alt="", ys=POWER):
        for y in ys:
            self._add(M.Wire([(x0, y), (x1, y)], layer="WIRES"), slot, alt)

    def udt(self, name, description, slots, ratings):
        return Udt(name, "Motor circuits", description, self.members,
                   [d.to_dict() for d in self.used.values()],
                   [M.Layer("SYMBOLS").to_dict(), M.Layer("WIRES", "#ff3030").to_dict()],
                   slots, MOTOR_VALUES, ratings, builtin=True)


def _rule(role, attr, rule, of="", percent=100.0, rnd="none"):
    return {"role": role, "attr": attr, "rule": rule, "of": of, "percent": percent,
            "round": rnd}


def _motor_rules(role):
    return [_rule(role, "HP", "value", "HP"), _rule(role, "VOLTS", "value", "VOLTS"),
            _rule(role, "FLA", "fla")]


def _disconnect_rules(role):
    # (430.110(A): at least 115 % of the table current; rounded up to a switch size)
    return [_rule(role, "AMPS", "percent", "FLC", NEC.PERCENT_DISCONNECT, "switch"),
            _rule(role, "VOLTS", "value", "VOLTS")]


def _terminals(d, x):
    """A terminal on each phase at x, its wires in from x - 1/4 and out to x + 1/2."""
    for y in POWER:
        d.symbol("Terminal", x, y)
    d.wires(x - 0.25, x - 0.03125)
    d.wires(x + 0.03125, x + 0.5)


def vfd_circuit(blocks):
    d = _Drawing(blocks)
    d.wires(0.0, 0.75)
    ds = d.symbol("Disconnect 3-pole", 1.0)
    d.wires(1.25, 1.75)
    prot = "Protection"
    mms = d.symbol("Motor protection circuit breaker 3-pole", 2.0, slot=prot,
                   alt="Manual motor starter")
    fu = d.symbol("Fuses 3-pole", 2.0, slot=prot, alt="Fuses")
    d.wires(2.25, 2.75, slot=prot, alt="Fuses")
    d.wires(2.75, 3.25)
    lr = d.symbol("Reactor 3-pole", 3.5, slot="Line reactor", alt=INCLUDED)
    d.wires(3.25, 3.75, slot="Line reactor", alt=LEFT_OUT)
    d.wires(3.75, 4.25)
    vfd = d.symbol("Variable frequency drive", 4.5)
    d.wires(5.75, 6.25)
    ld = d.symbol("Reactor 3-pole", 6.5, slot="Load reactor", alt=INCLUDED)
    d.wires(6.25, 6.75, slot="Load reactor", alt=LEFT_OUT)
    d.wires(6.75, 7.25)
    _terminals(d, 7.5)
    mtr = d.symbol("Motor 3-phase", 8.25)
    slots = [{"name": prot, "alternatives": ["Manual motor starter", "Fuses"],
              "default": "Manual motor starter"},
             {"name": "Line reactor", "alternatives": [INCLUDED, LEFT_OUT],
              "default": LEFT_OUT, "optional": True},
             {"name": "Load reactor", "alternatives": [INCLUDED, LEFT_OUT],
              "default": LEFT_OUT, "optional": True}]
    ratings = _disconnect_rules(ds) + [
        # (a manual motor starter set at the motor's FLA; fuses ahead of a drive at the
        # UDT's percent of the table current: the drive maker's table may ask for less)
        _rule(mms, "AMPS", "fla"), _rule(mms, "HP", "value", "HP"),
        _rule(fu, "RATING", "percent", "FLC", NEC.PERCENT_DUAL_ELEMENT_FUSE, "fuse"),
        _rule(fu, "VOLTS", "value", "VOLTS"),
        _rule(lr, "AMPS", "fla"), _rule(ld, "AMPS", "fla"),
        _rule(vfd, "HP", "value", "HP"), _rule(vfd, "VOLTS", "value", "VOLTS")] + \
        _motor_rules(mtr)
    return d.udt("Motor circuit, VFD", "Disconnect, manual motor starter or fuses, line "
                 "reactor (optional), variable frequency drive, load reactor (optional), "
                 "terminals, three-phase motor", slots, ratings)


def starter_circuit(blocks):
    d = _Drawing(blocks)
    d.wires(0.0, 0.75)
    ds = d.symbol("Disconnect 3-pole", 1.0)
    d.wires(1.25, 1.75)
    prot = "Protection"
    fu = d.symbol("Fuses 3-pole", 2.0, slot=prot, alt="Fuses")
    cb = d.symbol("Circuit breaker 3-pole", 2.0, slot=prot, alt="Circuit breaker")
    d.wires(2.25, 2.75)
    d.symbol("Contactor power contacts 3-pole", 3.0, PARENT="coil")
    d.wires(3.25, 3.75)
    ol = d.symbol("Overload heaters 3-pole", 4.0, DEV="ol")
    d.wires(4.25, 4.75)
    _terminals(d, 5.0)
    mtr = d.symbol("Motor 3-phase", 5.75)
    # the control rung under it: the coil, then the overload's contact
    rung = (-2.25,)
    d.wires(1.5, 2.75, ys=rung)
    d.symbol("Contactor coil", 3.0, rung[0], DEV="coil")
    d.wires(3.25, 3.75, ys=rung)
    d.symbol("Overload contact NC", 4.0, rung[0], PARENT="ol")
    d.wires(4.25, 5.0, ys=rung)
    slots = [{"name": prot, "alternatives": ["Fuses", "Circuit breaker"], "default": "Fuses"}]
    ratings = _disconnect_rules(ds) + [
        _rule(fu, "RATING", "percent", "FLC", NEC.PERCENT_DUAL_ELEMENT_FUSE, "fuse"),
        _rule(fu, "VOLTS", "value", "VOLTS"),
        _rule(cb, "AMPS", "percent", "FLC", NEC.PERCENT_INVERSE_TIME_BREAKER, "breaker"),
        _rule(cb, "VOLTS", "value", "VOLTS"),
        _rule(ol, "AMPS", "fla")] + _motor_rules(mtr)
    return d.udt("Motor circuit, full-voltage starter", "Disconnect, fuses or a circuit "
                 "breaker, contactor, overload, terminals, three-phase motor, and the "
                 "contactor's coil and overload contact on a control rung", slots, ratings)


def builtin_udts(blocks):
    """The program's own UDTs, drawn with these blocks ({name: BlockDef}: the library's
    built-in symbols)."""
    return [vfd_circuit(blocks), starter_circuit(blocks)]
