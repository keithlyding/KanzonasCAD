"""The DWG bit codes KanzonasCAD writes (dwgbits.py), checked against the worked examples of the
Open Design Specification for .dwg files (section 2): each value below is one of its examples."""
import unittest

from kanzonascad import dwgbits as D


def stream(bits):
    """A string of 0s and 1s as bytes (padded with 0s)."""
    bits = bits + "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


class BitCodesTest(unittest.TestCase):
    def test_bitshort_example(self):
        # (5 bitshorts: 257, 0, 256, 15, 0)
        r = D.BitReader(stream("0000000001000000011011010000111110"))
        self.assertEqual([r.BS() for _i in range(5)], [257, 0, 256, 15, 0])
        w = D.BitWriter()
        for v in (257, 0, 256, 15, 0):
            w.BS(v)
        self.assertEqual(w.bytes(), stream("0000000001000000011011010000111110"))

    def test_bitlong_example(self):
        bits = "000000000100000001000000000000000010010000111110"
        r = D.BitReader(stream(bits))
        self.assertEqual([r.BL() for _i in range(4)], [257, 0, 15, 0])
        w = D.BitWriter()
        for v in (257, 0, 15, 0):
            w.BL(v)
        self.assertEqual(w.bytes(), stream(bits))

    def test_negative_shorts_use_the_short_form(self):
        w = D.BitWriter()
        w.BS(-1)
        self.assertEqual(w.bytes(), stream("00" + "1" * 16))

    def test_modular_char_examples(self):
        self.assertEqual(D.MC(4610), bytes([0b10000010, 0b00100100]))
        self.assertEqual(D.MC(112823273), bytes([0b11101001, 0b10010111, 0b11100110,
                                                 0b00110101]))
        self.assertEqual(D.MC(-1413), bytes([0b10000101, 0b01001011]))

    def test_modular_short_example(self):
        self.assertEqual(D.MS(4650033), bytes([0b00110001, 0b11110100, 0b10001101, 0]))

    def test_handle_example(self):
        # (a layer of handle 5E7, code 5: 0101.0010.00000101.11100111)
        w = D.BitWriter()
        w.H(5, 0x5E7)
        self.assertEqual(w.bytes(), bytes([0b01010010, 0b00000101, 0b11100111]))
        self.assertEqual(D.BitReader(w.bytes()).H(), (5, 0x5E7))

    def test_crc_table(self):
        # (the first and last rows of the specification's table)
        self.assertEqual(D.CRC_TABLE[:8], [0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0,
                                           0x0280, 0xC241])
        self.assertEqual(D.CRC_TABLE[-8:], [0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1,
                                            0x8081, 0x4040])

    def test_crc_check_value(self):
        # (the checksum is CRC-16/ARC: its standard check value over "123456789" is 0xBB3D,
        # and a run is the same in pieces, seeded with the last)
        self.assertEqual(D.crc8(0, b"123456789"), 0xBB3D)
        self.assertEqual(D.crc8(D.crc8(0, b"1234"), b"56789"), 0xBB3D)

    def test_unsigned_modular_char_and_sizes(self):
        self.assertEqual(D.UMC(4610), bytes([0b10000010, 0b00100100]))
        self.assertEqual(D.UMC(64), bytes([0x40]))          # (no sign bit: one byte)
        self.assertEqual(D.MC(64), bytes([0xC0, 0x00]))     # (with one: two)
        w = D.BitWriter()
        w.B(1)
        w.CMC(256)
        self.assertEqual(w.bit_size(), 3)
        self.assertEqual(D.BitReader(w.bytes(), 1).BS(), 256)

    def test_raw_long_written_over_a_placeholder(self):
        w = D.BitWriter()
        w.BB(1)
        pos = w.bit_size()
        w.RL(0)
        w.B(1)
        w.put_RL(pos, 0x12345678)
        r = D.BitReader(w.bytes())
        self.assertEqual((r.BB(), r.RL(), r.B()), (1, 0x12345678, 1))
        w.put_RL(pos, 0)
        r = D.BitReader(w.bytes())
        self.assertEqual((r.BB(), r.RL(), r.B()), (1, 0, 1))

    def test_round_trip(self):
        w = D.BitWriter()
        w.B(1)
        w.BD(0.0)
        w.BD(1.0)
        w.BD(-2.5)
        w.DD(3.0, 3.0)
        w.DD(3.25, 3.0)
        w.T("MOTOR 1")
        w.BS(300)
        r = D.BitReader(w.bytes())
        self.assertEqual((r.B(), r.BD(), r.BD(), r.BD(), r.DD(3.0), r.DD(3.0), r.T(), r.BS()),
                         (1, 0.0, 1.0, -2.5, 3.0, 3.25, "MOTOR 1", 300))


if __name__ == "__main__":
    unittest.main()
