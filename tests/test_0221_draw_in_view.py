"""Texts and pictures out of view aren't drawn on the screen (a sheet of 10,000 texts drew every
one at every zoom: the Windows build's ten zoomed repaints of the self-test's notes sheet took
2.2 s, over its 2 s budget): what is drawn is the same, pixel for pixel, as drawing them all,
zoomed in and out, panned, texts turned, with pictures; printing still draws every one."""
import unittest

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QTransform

from tests.util import APP

from kanzonascad import model as M
from kanzonascad import render



def png():
    """A small picture, red over blue, as a PNG in base64 (as a Picture keeps it)."""
    import base64
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    img = QImage(8, 4, QImage.Format_ARGB32)
    img.fill(QColor("#2040ff"))
    for x in range(8):
        for y in range(2):
            img.setPixelColor(x, y, QColor("#ff2020"))
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return base64.b64encode(bytes(data)).decode("ascii")


def project():
    pic = png()
    p = M.Project.new()
    s = p.sheets[0]
    with p.edit("notes") as ed:
        for i in range(400):
            x, y = 1.0 + (i % 20) * 0.8, 1.0 + (i // 20) * 0.45
            ed.add(s, M.Text((x, y), "NOTE %d gq" % i, 0.08, angle=(i % 4) * 30.0))
        for i in range(40):
            ed.add(s, M.MText((2.0 + (i % 8) * 1.9, 9.5 - (i // 8) * 0.6),
                              text="FIELD WIRING\nBY OTHERS", height=0.1))
        for i in range(30):
            ed.add(s, M.Picture((1.0 + (i % 10) * 1.6, 4.0 + (i // 10) * 1.2), 0.6, 0.3, pic,
                                "png", (i % 2) * 90.0))
    return p, s


def draw(s, p, scale, cx, cy):
    img = QImage(400, 300, QImage.Format_ARGB32)
    img.fill(QColor("#000000"))
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing, True)
    q.setTransform(QTransform(scale, 0, 0, -scale, 200 - cx * scale, 150 + cy * scale))
    render.SheetRenderer(p, s, dark=True).paint(q)
    q.end()
    return img


class DrawInViewTest(unittest.TestCase):
    def test_the_same_as_drawing_everything(self):
        p, s = project()
        real = render.visible_rect
        seen = []
        reds = 0
        try:
            # (each view centered on something drawn there: a note's start, a picture. The
            # Windows build runs these tests offscreen, where Qt has no fonts and draws no text
            # at all (the whole sheet: 7,542 pixels lit there, 29,408 here), so the 900 view is
            # on a picture's edge, drawn everywhere; the texts are checked where there are
            # fonts, pixel for pixel in every view)
            for scale, cx, cy in ((25.0, 8.5, 5.5), (120.0, 4.0, 3.0), (400.0, 4.5, 4.15),
                                  (400.0, 1.1, 1.04), (900.0, 4.25, 4.1), (60.0, 15.0, 2.0)):
                render.visible_rect = real
                got = draw(s, p, scale, cx, cy)
                render.visible_rect = lambda painter: None        # (every one drawn)
                want = draw(s, p, scale, cx, cy)
                self.assertTrue(got == want, (scale, cx, cy))
                seen.append(sum(1 for x in range(400) for y in range(300)
                                if got.pixel(x, y) != 0xff000000))
                reds += sum(1 for x in range(0, 400, 3) for y in range(0, 300, 3)
                            if QColor(got.pixel(x, y)).red() > 200 and
                            QColor(got.pixel(x, y)).blue() < 100)
        finally:
            render.visible_rect = real
        self.assertTrue(all(seen), seen)                # (something drawn in every view)
        self.assertGreater(reds, 0)                     # (the pictures drawn too)

    def test_texts_out_of_view_left_out(self):
        p, s = project()
        img = QImage(400, 300, QImage.Format_ARGB32)
        q = QPainter(img)
        q.setTransform(QTransform(900.0, 0, 0, -900.0, 200 - 9.0 * 900, 150 + 9.4 * 900))
        view = render.visible_rect(q)
        q.end()
        items = [render.text_item(t) for t in s.entities.values() if isinstance(t, M.Text)]
        shown = [it for it in items if view.intersects(it[2])]
        self.assertLess(len(shown), len(items) // 10)
        self.assertTrue(view.contains(QRectF(8.9, 9.3, 0.2, 0.2)))

    def test_printed_all(self):
        # (a printer's painter: every text, no view worked out)
        p, s = project()
        calls = []
        real = render.visible_rect
        render.visible_rect = lambda painter: calls.append(1) or real(painter)
        try:
            img = QImage(200, 150, QImage.Format_ARGB32)
            q = QPainter(img)
            q.setTransform(QTransform(10.0, 0, 0, -10.0, 0, 150))
            render.SheetRenderer(p, s, mono=True).paint(q, pen_width=0.01)
            q.end()
        finally:
            render.visible_rect = real
        self.assertEqual(calls, [])
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
