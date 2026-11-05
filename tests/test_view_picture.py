"""The view keeps a picture of the drawing: a mouse move (crosshair, snap marker, rubber
band) doesn't draw every object again, and anything that changes what the drawing looks like
draws it again (never a stale picture)."""
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class ViewPictureTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = True
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("lines") as ed:
            self.ln = ed.add(self.s, M.Line((2, 2), (6, 4)))
        self.draws = 0
        r = self.v.renderer()
        real = r.paint

        def counted(*a, **k):
            self.draws += 1
            return real(*a, **k)
        r.paint = counted
        self.v.repaint()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def move(self, x, y):
        q = QPointF(x, y)
        APP.sendEvent(self.v, QMouseEvent(QEvent.MouseMove, q, q, Qt.NoButton, Qt.NoButton,
                                          Qt.NoModifier))
        self.v.repaint()

    def redrawn(self, step):
        before = self.draws
        step()
        self.v.repaint()
        return self.draws > before

    def test_mouse_moves_reuse_the_picture(self):
        self.v.run(C.LineCmd)
        type_in(self.v, "1,1")
        self.v.repaint()
        before = self.draws
        for i in range(20):
            self.move(200 + i * 9, 200 + i * 4)        # a rubber band and snap markers
        self.assertEqual(self.draws, before)
        self.v.cancel()
        before = self.draws
        for i in range(10):
            self.move(300 + i * 5, 250)                 # hover, no command
        self.assertEqual(self.draws, before)

    def test_every_change_draws_it_again(self):
        def add():
            with self.p.edit("add") as ed:
                ed.add(self.s, M.Circle((5, 5), 1))
        self.assertTrue(self.redrawn(add))
        self.assertTrue(self.redrawn(self.p.undo))
        self.assertTrue(self.redrawn(self.p.redo))

        def layer_off():                                # (Layers..., the layer tools)
            before = self.p.layers["0"].to_dict()
            after = dict(before, visible=False)
            with self.p.edit("layer") as ed:
                ed.layer("0", before, after)
        self.assertTrue(self.redrawn(layer_off))
        self.assertFalse(self.p.layers["0"].visible)
        self.assertTrue(self.redrawn(lambda: self.v.set_dark(not self.v.dark)))
        self.assertTrue(self.redrawn(lambda: setattr(self.v, "scale", self.v.scale * 2)))
        self.assertTrue(self.redrawn(lambda: setattr(self.v, "center", (3.0, 3.0))))
        self.assertTrue(self.redrawn(lambda: setattr(self.v, "grid_on", not self.v.grid_on)))
        self.assertTrue(self.redrawn(lambda: self.v.resize(self.v.width() - 40,
                                                            self.v.height())))

        def rotate():
            from kanzonascad import scalefit
            scalefit.rotate(self.p, self.s, True)
        self.assertTrue(self.redrawn(rotate))

    def test_picture_matches_a_fresh_drawing(self):
        with self.p.edit("add") as ed:
            ed.add(self.s, M.Text((3, 6), "PICTURE", 0.3))
        self.move(250, 250)
        cached = self.v.grab().toImage()
        self.v._picture = None
        fresh = self.v.grab().toImage()
        self.assertEqual(cached, fresh)


if __name__ == "__main__":
    unittest.main()
