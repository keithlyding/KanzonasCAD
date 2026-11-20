"""The bit-level codes of a DWG file (AutoCAD 2000, AC1015), written by KanzonasCAD itself (the
owner, Nov 2026: "You write it. Don't rely on some third party tool"), as the Open Design
Alliance's Open Design Specification for .dwg files describes them (its section 2, bit codes and
data definitions). Written from that description; no code or text of it is copied here.

BitWriter packs values most significant bit first, as DWG streams are read; BitReader reads them
back (for checking what was written, and tests). Little-endian bytes throughout, as the format
has them. No Qt."""

import struct


class BitWriter:
    def __init__(self):
        self.data = bytearray()
        self.bit = 0                    # (bits used in the last byte: 0 means it is full)

    # ---- raw bits and bytes ----------------------------------------------------------------
    def B(self, v):
        """One bit."""
        if self.bit == 0:
            self.data.append(0)
        if v:
            self.data[-1] |= 0x80 >> self.bit
        self.bit = (self.bit + 1) % 8

    def bits(self, value, n):
        """value's n lowest bits, most significant first."""
        for i in range(n - 1, -1, -1):
            self.B((value >> i) & 1)

    def RC(self, v):
        """A raw char (one byte, on any bit)."""
        self.bits(v & 0xFF, 8)

    def raw(self, bs):
        for b in bs:
            self.RC(b)

    def RS(self, v):
        self.raw(struct.pack("<h" if v < 0 else "<H", v))

    def RL(self, v):
        self.raw(struct.pack("<i" if v < 0 else "<I", v))

    def RD(self, v):
        self.raw(struct.pack("<d", float(v)))

    # ---- compressed forms ------------------------------------------------------------------
    def BB(self, v):
        self.bits(v, 2)

    def BS(self, v):
        """A bitshort: 0 and 256 as their codes, 1-255 as a char, the rest as a short."""
        if v == 0:
            self.BB(2)
        elif v == 256:
            self.BB(3)
        elif 0 < v < 256:
            self.BB(1)
            self.RC(v)
        else:
            self.BB(0)
            self.RS(v)

    def BL(self, v):
        """A bitlong: 0 as its code, 1-255 as a char, the rest as a long."""
        if v == 0:
            self.BB(2)
        elif 0 < v < 256:
            self.BB(1)
            self.RC(v)
        else:
            self.BB(0)
            self.RL(v)

    def BD(self, v):
        """A bitdouble: 0.0 and 1.0 as their codes, the rest as a raw double."""
        v = float(v)
        if v == 0.0 and struct.pack("<d", v) == struct.pack("<d", 0.0):
            self.BB(2)
        elif v == 1.0:
            self.BB(1)
        else:
            self.BB(0)
            self.RD(v)

    def DD(self, v, default):
        """A bitdouble with a default: nothing when equal, else the bytes that differ."""
        new, old = struct.pack("<d", float(v)), struct.pack("<d", float(default))
        if new == old:
            self.BB(0)
        elif new[4:] == old[4:]:
            self.BB(1)
            self.raw(new[:4])
        elif new[6:] == old[6:]:
            self.BB(2)
            self.raw(new[4:6])
            self.raw(new[:4])
        else:
            self.BB(3)
            self.raw(new)

    def BT(self, v):
        """A thickness (R2000): one bit for 0.0, else a bitdouble."""
        if float(v) == 0.0:
            self.B(1)
        else:
            self.B(0)
            self.BD(v)

    def BE(self, x, y, z):
        """An extrusion (R2000): one bit for (0, 0, 1), else three bitdoubles."""
        if (float(x), float(y), float(z)) == (0.0, 0.0, 1.0):
            self.B(1)
        else:
            self.B(0)
            for c in (x, y, z):
                self.BD(c)

    def T(self, text):
        """A text (R2000: its length as a bitshort, then its bytes, in the drawing's code
        page: ANSI_1252; anything it can't hold as ?)."""
        raw = str(text).encode("cp1252", "replace")
        self.BS(len(raw))
        self.raw(raw)

    def H(self, code, handle):
        """A handle reference: its code, how many bytes, then those bytes, most significant
        first."""
        n = 0 if handle == 0 else (handle.bit_length() + 7) // 8
        self.bits(code, 4)
        self.bits(n, 4)
        for i in range(n - 1, -1, -1):
            self.RC((handle >> (8 * i)) & 0xFF)

    def CMC(self, index):
        """A color (R2000: its color index, a bitshort)."""
        self.BS(index)

    def put_RL(self, pos, v):
        """Write the raw long v over the 32 bits at bit pos (a size written before it was
        known: an object's size in bits)."""
        for i, byte in enumerate(struct.pack("<I", v)):
            for k in range(8):
                p = pos + 8 * i + k
                mask = 0x80 >> (p & 7)
                if (byte >> (7 - k)) & 1:
                    self.data[p >> 3] |= mask
                else:
                    self.data[p >> 3] &= ~mask & 0xFF

    # ---- whole bytes -----------------------------------------------------------------------
    def bit_size(self):
        return len(self.data) * 8 - ((8 - self.bit) % 8)

    def bytes(self):
        return bytes(self.data)


def MC(v):
    """A modular char: seven bits a byte, least significant first, the high bit saying another
    byte follows; in the last byte the 0x40 bit marks a negative number."""
    neg, v = v < 0, abs(int(v))
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v == 0 and not (b & 0x40):
            out.append(b | (0x40 if neg else 0))
            return bytes(out)
        if v == 0:
            # (its top bit would read as the sign: one more byte for it)
            out.append(b | 0x80)
            out.append(0x40 if neg else 0)
            return bytes(out)
        out.append(b | 0x80)


def UMC(v):
    """A modular char that is never negative (the object map's offsets and handles)."""
    v = int(v)
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def MS(v):
    """A modular short: fifteen bits a little-endian short, the high bit saying another
    follows (an object's size)."""
    v = int(v)
    out = bytearray()
    while True:
        w = v & 0x7FFF
        v >>= 15
        out += struct.pack("<H", w | (0x8000 if v else 0))
        if not v:
            return bytes(out)


def _crc_table():
    t = []
    for i in range(256):
        c = i
        for _k in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
        t.append(c)
    return t


CRC_TABLE = _crc_table()


def crc8(seed, data):
    """The DWG "8-bit" CRC (two bytes: the CRC-16 of reflected polynomial 0xA001), started
    from seed."""
    dx = seed & 0xFFFF
    for b in data:
        dx = (dx >> 8) ^ CRC_TABLE[(b ^ dx) & 0xFF]
    return dx


class BitReader:
    """Reads what BitWriter writes (for checking a file before it is saved, and tests)."""

    def __init__(self, data, bit=0):
        self.data = bytes(data)
        self.pos = bit

    def B(self):
        byte = self.data[self.pos >> 3]
        v = (byte >> (7 - (self.pos & 7))) & 1
        self.pos += 1
        return v

    def bits(self, n):
        v = 0
        for _i in range(n):
            v = (v << 1) | self.B()
        return v

    def RC(self):
        return self.bits(8)

    def raw(self, n):
        return bytes(self.RC() for _i in range(n))

    def RS(self):
        return struct.unpack("<h", self.raw(2))[0]

    def RL(self):
        return struct.unpack("<i", self.raw(4))[0]

    def RD(self):
        return struct.unpack("<d", self.raw(8))[0]

    def BB(self):
        return self.bits(2)

    def BS(self):
        c = self.BB()
        if c == 0:
            return self.RS()
        if c == 1:
            return self.RC()
        return 0 if c == 2 else 256

    def BL(self):
        c = self.BB()
        if c == 3:
            raise ValueError("a bitlong's code 3 isn't used")
        if c == 0:
            return self.RL()
        return self.RC() if c == 1 else 0

    def BD(self):
        c = self.BB()
        if c == 3:
            raise ValueError("a bitdouble's code 3 isn't used")
        return self.RD() if c == 0 else (1.0 if c == 1 else 0.0)

    def DD(self, default):
        c = self.BB()
        d = bytearray(struct.pack("<d", float(default)))
        if c == 1:
            d[:4] = self.raw(4)
        elif c == 2:
            d[4:6] = self.raw(2)
            d[:4] = self.raw(4)
        elif c == 3:
            d[:] = self.raw(8)
        return struct.unpack("<d", bytes(d))[0]

    def T(self):
        n = self.BS()
        return self.raw(n).decode("cp1252", "replace")

    def H(self):
        code, n = self.bits(4), self.bits(4)
        v = 0
        for _i in range(n):
            v = (v << 8) | self.RC()
        return code, v
