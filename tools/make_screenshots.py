"""Make the README's screenshots (docs/screenshot-*.png) from a demo project built through the
app's own commands, as a user would: a pump station's motor starter (three-phase power, a
control circuit with field devices through terminals, cross-references and wire numbers), its
panel layout with footprints on DIN rail, and the Cables between locations window.

    QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 python tools/make_screenshots.py [OUT_DIR]

OUT_DIR defaults to docs/. Settings, library and recovery copies go to scratch folders (as in
the tests), so nothing of yours is read or changed. Run it again when the app's look changes.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import tests  # noqa: E402,F401  (scratch settings, library and recovery folders)
from tests.util import APP, window, type_in  # noqa: E402

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from kanzonascad import commands as C  # noqa: E402
from kanzonascad import model as M  # noqa: E402

W, H = 1600, 960                        # the window, logical pixels (QT_SCALE_FACTOR doubles)


class Demo:
    def __init__(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
        self.p = v.project
        self.lib = self.win.library

    # ---- drawing, as a user would ----------------------------------------------------------
    def place(self, name, at, attrs=None, kind="symbol"):
        v = self.v
        before = set(v.sheet().entities)
        v.run(C.InsertCmd, self.lib.get(kind, name), attrs or {})
        type_in(v, "%g,%g" % at)
        if v.cmd is not None:
            v.input_text("")
        if v.cmd is not None:
            v.cancel()
        got = [e for i, e in v.sheet().entities.items()
               if i not in before and isinstance(e, M.Insert)]
        return got[0].id

    def pin(self, iid, name):
        return dict(self.v.sheet().entities[iid].pin_points())[name]

    def wire(self, *pts):
        v = self.v
        v.run(C.WireCmd)
        type_in(v, *["%g,%g" % q for q in pts])
        if v.cmd is not None:
            v.cmd.enter()
        if v.cmd is not None:
            v.cancel()

    def text(self, at, s):
        v = self.v
        v.run(C.TextCmd)
        type_in(v, "%g,%g" % at)
        if v.cmd is not None:
            v.input_text(s)
        if v.cmd is not None:
            v.cmd.enter()
        if v.cmd is not None:
            v.cancel()

    # ---- the project -----------------------------------------------------------------------
    def fields(self):
        with self.p.edit("Project properties") as ed:
            ed.project_fields(dict(self.p.fields, **{
                "Project": "Pump station 3", "Customer": "Acme Water", "Drawn by": "KL",
                "Checked by": "JD", "Drawing number": "E-101"}))

    def power_sheet(self):
        """Sheet 1: the incoming three-phase power, disconnect, breaker, starter and the motor
        in the field through terminals; the control transformer."""
        v, p = self.v, self.p
        s = v.sheet()
        with p.edit("Sheet properties") as ed:
            ed.sheet_meta(s, title="Power distribution", location="MCP")
        ys = (9.0, 8.5, 8.0)
        for y, name in zip(ys, ("L1", "L2", "L3")):
            self.wire((1.6, y), (12.6, y))
            self.text((1.0, y - 0.05), name)
        self.place("Disconnect 3-pole", (2.6, 8.5))
        self.place("Circuit breaker 3-pole", (4.4, 8.5))
        self.place("Contactor power contacts 3-pole", (7.6, 8.5), {"TAG": "M1"})
        self.place("Overload heaters 3-pole", (9.4, 8.5))
        self.place("Terminal strip", (11.2, 9.8))
        for y in ys:
            self.place("Terminal", (11.2, y))
        mtr = self.place("Motor 3-phase", (13.1, 8.5), {"LOC": "WET WELL", "DESC": "PUMP 1"})
        for y in ys:
            self.wire((12.6, y), (12.85, y))
        # control transformer from L1 and L2 after the breaker
        t = self.place("Control transformer", (6.0, 6.6))
        h1, h2 = self.pin(t, "H1"), self.pin(t, "H2")
        self.wire((5.5, 9.0), (5.5, h1[1] + 0.6), (h1[0], h1[1] + 0.6), h1)
        self.wire((5.9, 8.5), (5.9, h1[1] + 0.35), (h2[0], h1[1] + 0.35), h2)
        x1, x2 = self.pin(t, "X1"), self.pin(t, "X2")
        fu = self.place("Fuse", (7.4, x1[1] - 0.6))
        self.wire(x1, (x1[0], x1[1] - 0.6), self.pin(fu, "1"))
        self.wire(self.pin(fu, "2"), (8.6, x1[1] - 0.6))
        self.wire(x2, (x2[0], x2[1] - 1.0), (8.6, x2[1] - 1.0))
        self.place("Off-sheet connector", (8.6, x1[1] - 0.6), {"TAG": "X1"})
        self.place("Off-sheet connector", (8.6, x2[1] - 1.0), {"TAG": "X2"})
        self.text((8.85, x1[1] - 0.65), "120 VAC TO SHEET 2")
        self.text((8.85, x2[1] - 1.05), "NEUTRAL TO SHEET 2")
        # a 24 VDC supply
        ps = self.place("Power supply AC/DC", (3.0, 4.2))
        return s, mtr

    def control_sheet(self):
        """Sheet 2: the 120 VAC control circuit: E-stop, the field station's stop and start
        through terminals, the starter coil with its seal-in, run and overload lights, a high
        level float in the wet well with its relay, and hand/auto."""
        v, p = self.v, self.p
        with p.edit("Add sheet") as ed:
            s = p.make_sheet("Motor control")
            ed.add_sheet(s)
        v.show_sheet(s.id)
        with p.edit("Sheet properties") as ed:
            ed.sheet_meta(s, location="MCP")
        L, R = 1.4, 14.4
        rungs = [9.0, 8.0, 7.0, 6.0, 5.0, 4.0]
        self.place("Off-sheet connector", (L, 9.6), {"TAG": "X1"})
        self.place("Off-sheet connector", (R, 9.6), {"TAG": "X2"})
        self.wire((L, 9.6), (L, 3.6))
        self.wire((R, 9.6), (R, 3.6))
        for y in rungs:
            self.wire((L, y), (R, y))
        # the terminal strip first: the terminals placed after take its tag (TB201-1, -2...)
        self.place("Terminal strip", (9.6, 3.2))
        # rung 1: E-stop, the station's stop and start through terminals, OL, M1 coil
        self.place("Emergency stop NC", (2.4, 9.0), {"DESC": "E-STOP"})
        self.place("Terminal", (3.6, 9.0))
        self.place("Pushbutton NC", (4.8, 9.0), {"LOC": "PS-1", "DESC": "STOP"})
        self.place("Terminal", (6.0, 9.0))
        self.place("Pushbutton NO", (7.5, 9.0), {"LOC": "PS-1", "DESC": "START"})
        self.place("Terminal", (9.0, 9.0))
        self.place("Overload contact NC", (10.8, 9.0), {"TAG": "OL101"})
        self.place("Contactor coil", (12.8, 9.0), {"TAG": "M1", "DESC": "PUMP 1"})
        # seal-in: an M1 contact around the start button, terminal to terminal
        self.wire((6.6, 9.0), (6.6, 8.5), (8.4, 8.5), (8.4, 9.0))
        self.place("Contact NO", (7.5, 8.5), {"TAG": "M1"})
        # rung 2: run light at the station
        self.place("Contact NO", (4.8, 8.0), {"TAG": "M1"})
        self.place("Terminal", (9.0, 8.0))
        self.place("Pilot light", (12.8, 8.0), {"LOC": "PS-1", "DESC": "RUNNING"})
        # rung 3: overload light on the door
        self.place("Overload contact NC", (4.8, 7.0), {"TAG": "OL101"})
        self.place("Pilot light", (12.8, 7.0), {"DESC": "OVERLOAD"})
        # rung 4: high level float in the wet well, its relay
        self.place("Terminal", (3.6, 6.0))
        self.place("Float switch NO", (4.8, 6.0), {"LOC": "WET WELL", "DESC": "HIGH LEVEL"})
        self.place("Terminal", (6.0, 6.0))
        self.place("Relay coil", (12.8, 6.0), {"DESC": "HIGH LEVEL"})
        # rung 5: high level alarm light
        self.place("Contact NO", (4.8, 5.0), {"TAG": "CR201"})
        self.place("Pilot light", (12.8, 5.0), {"DESC": "HIGH LEVEL ALARM"})
        # rung 6: hand/auto
        self.place("Selector switch 2-position", (2.4, 4.0), {"DESC": "HAND/AUTO"})
        self.place("Contact NO", (4.8, 4.0), {"TAG": "CR201"})
        self.place("Relay coil", (12.8, 4.0), {"DESC": "AUTO RUN"})
        self.text((1.4, 10.2), "120 VAC CONTROL")
        return s

    def footprints(self):
        """Footprints at real size, as Make block makes them (KanzonasCAD has none built in)."""
        out = {}

        def fp(name, w, h, label, cat="", mfr="AB"):
            hw, hh = w / 2.0, h / 2.0
            ents = [M.Polyline([(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)], True)]
            if w > 0.5:
                ents.append(M.Polyline([(-hw + 0.1, -hh + 0.25), (hw - 0.1, -hh + 0.25),
                                        (hw - 0.1, hh - 0.25), (-hw + 0.1, hh - 0.25)], True))
            d = M.BlockDef(name, "footprint", ents)
            d.tag_pos = (0.0, hh - 0.55)        # (its label near the top, clear of the rail)
            d.manufacturer, d.catalog, d.description = mfr, cat, label
            out[name] = d
        fp("Disconnect 30A", 3.5, 4.4, "DISCONNECT", "194R-NN030P3")
        fp("Breaker 3P", 2.1, 3.6, "BREAKER", "1489-M3C150")
        fp("Fuse block", 0.75, 3.2, "FUSE", "1492-FB1C30")
        fp("Transformer 250VA", 4.2, 3.6, "TRANSFORMER", "1497A-A2-M15")
        fp("Contactor 9A", 1.8, 3.4, "CONTACTOR", "100-C09D10")
        fp("Overload 9A", 1.8, 2.6, "OVERLOAD", "193-1EEDB")
        fp("Relay", 1.1, 3.0, "RELAY", "700-HK32A1")
        fp("Power supply 24V", 1.9, 4.2, "24 VDC PS", "1606-XLE120E")
        fp("Terminal 2.5", 0.24, 2.0, "TERMINAL", "1492-J3")
        return out

    def panel_sheet(self):
        v, p = self.v, self.p
        fps = self.footprints()
        with p.edit("Add sheet") as ed:
            s = p.make_sheet("Panel layout")
            ed.add_sheet(s)
        v.show_sheet(s.id)
        with p.edit("Panel") as ed:
            ed.sheet_meta(s, kind="panel", location="MCP")
            ed.sheet_scale(s, 0.25)
        th = 0.085 * s.k()                      # labels, paper-sized (Footprint label)
        with p.edit("Panel") as ed:
            for d in fps.values():
                ed.block(d)
            # a 24 x 30 back panel; wire duct around and between three DIN rails
            ed.add(s, M.Polyline([(6, 6), (30, 6), (30, 36), (6, 36)], True))
            for y in (33.5, 25.5, 17.5, 9.5):
                ed.add(s, M.Duct((9.0, y), (27.0, y), "", 2, 3))
            ed.add(s, M.Duct((7.5, 8.5), (7.5, 34.5), "", 2, 3))
            ed.add(s, M.Duct((28.5, 8.5), (28.5, 34.5), "", 2, 3))
            prof = M.RAIL_PROFILES["TS35x7.5"]
            for y in (29.5, 21.5, 13.5):
                ed.add(s, M.Rail((9.4, y), (26.6, y), "TS35x7.5", *prof[1:]))

            def put(name, x, y, tag, label="tag"):
                d = p.blocks[name]
                ed.add(s, M.Insert(name, (x, y), defn=d, label=label, tag_h=th,
                                   attrs={"TAG": tag, "MFR": d.manufacturer,
                                          "CAT": d.catalog, "DESC": d.description}))
            # top rail: disconnect, breaker, fuse, transformer
            put("Disconnect 30A", 11.8, 29.5, "DS101")
            put("Breaker 3P", 15.0, 29.5, "CB101")
            put("Fuse block", 17.6, 29.5, "FU101")
            put("Transformer 250VA", 22.6, 29.5, "T101")
            # middle rail: the starter (contactor and overload), relays, power supply
            put("Contactor 9A", 11.0, 21.5, "M1")
            put("Overload 9A", 13.2, 21.5, "OL101")
            put("Relay", 15.8, 21.5, "CR201")
            put("Relay", 18.0, 21.5, "CR202")
            put("Power supply 24V", 22.6, 21.5, "PS101")
            # bottom rail: 24 terminal blocks
            for i in range(24):
                put("Terminal 2.5", 11.0 + i * 0.26, 13.5, "TB201", label="")
            ed.add(s, M.Text((14.0, 15.2), "TB201", th, 0.0, "center"))
            ed.add(s, M.Dimension((6, 6), (30, 6), (18, 2.4), height=0.1 * s.k()))
            ed.add(s, M.Dimension((30, 6), (30, 36), (34.0, 21), height=0.1 * s.k()))
        return s

    # ---- pictures --------------------------------------------------------------------------
    def settle(self):
        for _i in range(5):
            APP.processEvents()

    def shot(self, path, widget=None):
        self.settle()
        (widget or self.win).grab().save(path)
        print("saved", path)


def main(argv):
    out = argv[1] if len(argv) > 1 else os.path.join(HERE, "docs")
    os.makedirs(out, exist_ok=True)
    d = Demo()
    win, v, p = d.win, d.v, d.p
    win.resize(W, H)
    win.show()
    d.fields()
    d.power_sheet()
    ctl = d.control_sheet()
    panel = d.panel_sheet()
    # the pull list's cables, as typed in Cables between locations
    from kanzonascad import pull
    cables = {}
    for r in pull.runs(p)[0]:
        if r["locs"][1] == "WET WELL":
            cables[r["key"]] = {"tag": "W101", "type": "7C #14 TC-ER", "marking": "numbered",
                                "colors": {}}
        else:
            cables[r["key"]] = {"tag": "W102", "type": "7C #14 TC-ER, ICEA colors",
                                "marking": "colors", "colors": dict(zip(
                                    [c["num"] for c in r["conductors"]],
                                    ["BLK", "WHT", "RED", "GRN", "ORG", "BLU", "WHT/BLK"]))}
    with p.edit("Cables between locations") as ed:
        ed.project_settings({"cables": cables})
    # saved under its name (the tab shows it), the command line as after opening it
    doc = win.tabs.currentWidget()
    win._save_to(doc, os.path.join(tempfile.mkdtemp(), "Pump station 3.kzcad"))
    from kanzonascad.commandline import CommandLine
    for c in win.findChildren(CommandLine):
        c.history.setPlainText("OPEN\nPump station 3.kzcad: 3 sheets")
    win.statusBar().clearMessage()
    # the schematic, on the Schematic tab
    v.show_sheet(ctl.id)
    v.zoom("sheet")
    d.shot(os.path.join(out, "screenshot-schematic.png"))
    # the panel, zoomed to the back panel and its dimensions
    v.show_sheet(panel.id)
    v.zoom("sheet")
    cx = v.center[0]
    v.zoom("extents")
    v.center = (cx, v.center[1])        # (the whole width: zones and title block uncut)
    v.update()
    d.shot(os.path.join(out, "screenshot-panel.png"))
    # the pull list
    from kanzonascad import dialogs
    from unittest import mock

    def run(dlg):
        dlg.resize(1000, 400)
        dlg.show()
        lst = [c for c in dlg.children() if c.objectName() == "runs"] or None
        d.shot(os.path.join(out, "screenshot-cables.png"), dlg)
        return QDialog.Rejected
    with mock.patch.object(QDialog, "exec", run):
        dialogs.cables_dialog(win, p, out)
    p.saved_at = len(p.undo_stack)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
