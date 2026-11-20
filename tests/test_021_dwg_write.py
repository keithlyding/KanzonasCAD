"""DWG files KanzonasCAD writes itself (dwgwrite.py, AutoCAD 2000): read back by ezdwg (an
independent reader) and by KanzonasCAD's own DWG reading, and their structures checked here
with our own bit reader: the file header and its checksum, the sections' sentinels, sizes and
checksums, every object's checksum and handle, the object map."""
import datetime
import importlib.util
import os
import struct
import tempfile
import unittest

from kanzonascad import dwgbits as D
from kanzonascad import dwgwrite as W

WHEN = datetime.datetime(2026, 11, 20, 9, 30)


def read_ms(data, pos):
    """A modular short at pos: (value, position after it)."""
    v, shift = 0, 0
    while True:
        w = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        v |= (w & 0x7FFF) << shift
        shift += 15
        if not w & 0x8000:
            return v, pos


def read_mc(data, pos):
    """A signed modular char at pos: (value, position after it)."""
    v, shift = 0, 0
    while True:
        b = data[pos]
        pos += 1
        if b & 0x80:
            v |= (b & 0x7F) << shift
            shift += 7
            continue
        v |= (b & 0x3F) << shift
        return (-v if b & 0x40 else v), pos


def read_map(data, at, size):
    """The object map's [(handle, offset)], checking each piece's size and checksum."""
    out, pos, end = [], at, at + size
    while pos < end:
        n = struct.unpack_from(">H", data, pos)[0]
        crc = struct.unpack_from(">H", data, pos + n)[0]
        if crc != D.crc8(0xC0C1, data[pos:pos + n]):
            raise AssertionError("object map checksum wrong at %d" % pos)
        if n > 2032:
            raise AssertionError("object map piece of %d bytes" % n)
        if n == 2:
            return out, pos + 4
        p, h, at_ = pos + 2, 0, 0
        while p < pos + n:
            dh, p = read_mc(data, p)
            da, p = read_mc(data, p)
            h, at_ = h + dh, at_ + da
            out.append((h, at_))
        pos += n + 2
    raise AssertionError("object map without its empty last piece")


def framed(data, at, start, end):
    """A section framed by sentinels at at: its data, after checking sentinels, size and
    checksum."""
    if data[at:at + 16] != start:
        raise AssertionError("no start sentinel at %d" % at)
    n = struct.unpack_from("<I", data, at + 16)[0]
    body = data[at + 16:at + 20 + n]
    crc = struct.unpack_from("<H", data, at + 20 + n)[0]
    if crc != D.crc8(0xC0C1, body):
        raise AssertionError("section checksum wrong at %d" % at)
    if data[at + 22 + n:at + 38 + n] != end:
        raise AssertionError("no end sentinel at %d" % at)
    return body[4:], 38 + n


class DwgFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.folder.name, "line.dwg")
        W.write_dwg(cls.path, [((0, 0), (10, 5))])
        with open(cls.path, "rb") as f:
            cls.data = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def locators(self):
        d = self.data
        n = struct.unpack_from("<I", d, 0x15)[0]
        return [struct.unpack_from("<BII", d, 0x19 + 9 * i) for i in range(n)]

    def test_file_header(self):
        d = self.data
        self.assertEqual(d[:6], b"AC1015")
        self.assertEqual(d[6:13], bytes(6) + b"\x01")
        self.assertEqual(struct.unpack_from("<H", d, 0x13)[0], 30)
        locs = self.locators()
        self.assertEqual([nr for nr, _a, _s in locs], [0, 1, 2, 3, 4])
        end = 0x19 + 9 * len(locs)
        crc = struct.unpack_from("<H", d, end)[0]
        self.assertEqual(crc, D.crc8(0, d[:end]) ^ 0x3CC4)
        self.assertEqual(d[end + 2:end + 18], W.S_FILE_HEADER_END)
        self.assertEqual(locs[0][1], end + 18)

    def test_sections_are_framed_and_checked(self):
        locs = self.locators()
        _hv, size = framed(self.data, locs[0][1], W.S_HEADER, W.E_HEADER)
        self.assertEqual(size, locs[0][2])
        classes, size = framed(self.data, locs[1][1], W.S_CLASSES, W.E_CLASSES)
        self.assertEqual(size, locs[1][2])
        r = D.BitReader(classes)
        names = []
        for i in range(3):
            self.assertEqual(r.BS(), 500 + i)
            r.BS()
            r.T()
            r.T()
            names.append(r.T())
            r.B()
            self.assertEqual(r.BS(), 0x1F3)
        self.assertEqual(names, ["ACDBDICTIONARYWDFLT", "ACDBPLACEHOLDER", "LAYOUT"])
        # (the objects start after 0x200 bytes of padding)
        self.assertEqual(self.data[locs[1][1] + locs[1][2]:][:0x200], bytes(0x200))
        # (section 3, the object free space: 53 bytes; section 4, the template: 4)
        self.assertEqual((locs[3][2], locs[4][2]), (53, 4))

    def test_second_header_and_preview(self):
        d = self.data
        locs = self.locators()
        at = locs[4][1] + locs[4][2]
        self.assertEqual(d[at:at + 16], W.S_SECOND)
        r = D.BitReader(d[at + 20:])
        self.assertEqual(r.BL(), at)
        self.assertEqual(r.raw(6), b"AC1015")
        image = struct.unpack_from("<I", d, 0x0D)[0]
        self.assertEqual(d[image:image + 16], W.S_IMAGE)
        self.assertEqual(d[-16:], W.E_IMAGE)

    def objects(self):
        locs = self.locators()
        entries, end = read_map(self.data, locs[2][1], locs[2][2])
        self.assertEqual(end - locs[2][1], locs[2][2])
        return entries

    def test_every_object_in_the_map_is_whole(self):
        d = self.data
        entries = self.objects()
        self.assertEqual([h for h, _a in entries], sorted(h for h, _a in entries))
        types = {}
        for h, at in entries:
            n, p = read_ms(d, at)
            crc = struct.unpack_from("<H", d, p + n)[0]
            self.assertEqual(crc, D.crc8(0xC0C1, d[at:p + n]), "object %X" % h)
            r = D.BitReader(d[p:p + n])
            t = r.BS()
            bits = r.RL()
            self.assertLessEqual(bits, 8 * n)
            self.assertEqual(r.H(), (0, h))
            types[h] = t
        # (every object the header and the others point at is in the map)
        self.assertEqual(set(W.H.values()) - set(types), set())
        self.assertEqual(sorted(types.values()).count(W.T_LINE), 1)
        self.assertEqual(types[W.H["MODEL"]], W.T_LAYOUT)

    def test_the_line_comes_back_through_ezdwg(self):
        try:
            import ezdwg
        except ImportError:
            self.skipTest("ezdwg isn't installed")
        doc = ezdwg.read(self.path)
        lines = [e for e in doc.entities().query() if e.dxftype == "LINE"]
        self.assertEqual(len(lines), 1)
        self.assertEqual(tuple(lines[0].dxf["start"]), (0.0, 0.0, 0.0))
        self.assertEqual(tuple(lines[0].dxf["end"]), (10.0, 5.0, 0.0))
        names = dict(ezdwg.raw.decode_layer_names(self.path))
        self.assertEqual(names[lines[0].dxf["layer_handle"]], "0")
        self.assertEqual(ezdwg.raw.detect_version(self.path), "AC1015")
        self.assertEqual(doc.header_variables()["insunits"], 1)
        self.assertEqual(doc.header_variables()["extmax"], (10.0, 5.0, 0.0))
        self.assertEqual(set(doc.layouts()), {"Model", "Layout1"})
        self.assertEqual(set(doc.linetypes()), {"ByBlock", "ByLayer", "Continuous"})

    def test_the_line_comes_back_through_kanzonascad(self):
        if importlib.util.find_spec("ezdwg") is None:     # (KanzonasCAD reads DWG with it)
            self.skipTest("ezdwg isn't installed")
        from kanzonascad import fileio
        from kanzonascad import model as M
        ents, rep = fileio.read_dwg(self.path)
        self.assertEqual(rep["reader"], "KanzonasCAD")
        self.assertEqual(len(ents), 1)
        self.assertIsInstance(ents[0], M.Line)
        self.assertEqual((tuple(ents[0].p1), tuple(ents[0].p2)), ((0.0, 0.0), (10.0, 5.0)))
        self.assertEqual(ents[0].layer, "0")


class DwgPiecesTest(unittest.TestCase):
    def test_object_map_splits_in_pieces(self):
        entries = [(h, 1000 + 37 * h) for h in range(1, 3001)]
        data = W.object_map(entries)
        back, end = read_map(data, 0, len(data))
        self.assertEqual(back, entries)
        self.assertEqual(end, len(data))

    def test_many_lines_and_3d_points(self):
        lines = [((i, 0, 0), (i, 1, 2.5)) for i in range(300)]
        data = W.dwg_bytes(lines, WHEN, ["{A}", "{B}"])
        n = struct.unpack_from("<I", data, 0x15)[0]
        locs = [struct.unpack_from("<BII", data, 0x19 + 9 * i) for i in range(n)]
        entries, _end = read_map(data, locs[2][1], locs[2][2])
        self.assertEqual(len(entries), W.FIRST_ENTITY - 2 + 300)    # (handle 4 isn't used)
        # (the same drawing, written at the same time, is the same file)
        self.assertEqual(data, W.dwg_bytes(lines, WHEN, ["{A}", "{B}"]))


if __name__ == "__main__":
    unittest.main()
