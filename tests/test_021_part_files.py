"""One file a part (the owner's two library folders, Nov 2026: a shared library in a synced
folder, where two people adding parts at once must not make the sync app leave a conflict
copy): each part in the library's parts folder by its id; a library's old parts.json still read
and moved to files of their own at the first save or delete; a copy a sync app left, or a file
it can't read, reported and not listed."""
import json
import os
import tempfile
import unittest

from kanzonascad.library import Library, Part


class PartFilesTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(tempfile.mkdtemp())

    def test_one_file_a_part(self):
        a = Part(manufacturer="AB", catalog="100-C09", symbol="Contactor coil")
        b = Part(manufacturer="Siemens", catalog="3RT2015", symbol="Contactor coil")
        self.lib.save_part(b)
        self.lib.save_part(a)
        files = sorted(os.listdir(os.path.join(self.lib.folder, "parts")))
        self.assertEqual(files, sorted([a.id + ".json", b.id + ".json"]))
        self.assertEqual([p.catalog for p in self.lib.parts()], ["100-C09", "3RT2015"])
        self.lib.delete_part(a.id)
        self.assertEqual([p.catalog for p in self.lib.parts()], ["3RT2015"])
        self.assertFalse(os.path.exists(os.path.join(self.lib.folder, "parts.json")))

    def test_old_parts_json_read_and_moved(self):
        old = [Part(manufacturer="AB", catalog="700-HC", symbol="Relay coil"),
               Part(manufacturer="ABB", catalog="AF09", symbol="Contactor coil")]
        with open(os.path.join(self.lib.folder, "parts.json"), "w", encoding="utf-8") as f:
            json.dump({"format": "kanzonascad-parts", "version": 1,
                       "parts": [p.to_dict() for p in old]}, f)
        self.assertEqual([p.catalog for p in self.lib.parts()], ["700-HC", "AF09"])
        self.lib.save_part(Part(manufacturer="X", catalog="NEW", symbol="Relay coil"))
        self.assertFalse(os.path.exists(os.path.join(self.lib.folder, "parts.json")))
        self.assertEqual([p.catalog for p in self.lib.parts()], ["700-HC", "AF09", "NEW"])

    def test_conflict_copies_and_bad_files_reported(self):
        a = Part(manufacturer="AB", catalog="100-C09", symbol="Contactor coil")
        self.lib.save_part(a)
        d = os.path.join(self.lib.folder, "parts")
        with open(os.path.join(d, a.id + ".json"), encoding="utf-8") as f:
            text = f.read()
        with open(os.path.join(d, a.id + " (Keith's PC).json"), "w", encoding="utf-8") as f:
            f.write(text)
        with open(os.path.join(d, "broken.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual([p.catalog for p in self.lib.parts()], ["100-C09"])
        self.assertEqual(len(self.lib.part_problems), 2)
        self.assertTrue(any("sync app" in t for t in self.lib.part_problems))
        self.assertTrue(any(t.startswith("broken.json") for t in self.lib.part_problems))


if __name__ == "__main__":
    unittest.main()
