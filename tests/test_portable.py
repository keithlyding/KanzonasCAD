"""Portable mode (paths.py): portable.txt beside the program puts the settings (an INI file),
the library and the recovery copies in a data folder beside it, or where its data= line says
(the PortableApps.com package)."""
import json
import os
import tempfile
import unittest
from unittest import mock

from tests.util import APP  # noqa: F401  (the QApplication)

from kanzonascad import backup, library, paths


class PortableTest(unittest.TestCase):
    def setUp(self):
        self.app_dir = tempfile.mkdtemp(prefix="kzcad-portable-")
        p = mock.patch.object(paths, "app_dir", return_value=self.app_dir)
        p.start()
        self.addCleanup(p.stop)
        # (the tests point these at scratch folders; here the defaults themselves are tested)
        e = mock.patch.dict(os.environ)
        e.start()
        self.addCleanup(e.stop)
        os.environ.pop("KANZONASCAD_LIBRARY", None)
        os.environ.pop("KANZONASCAD_RECOVERY", None)

    def marker(self, text="portable\n"):
        with open(os.path.join(self.app_dir, paths.MARKER), "w", encoding="utf-8") as f:
            f.write(text)

    def test_not_portable_without_the_marker(self):
        self.assertFalse(paths.is_portable())
        self.assertIsNone(paths.portable_data_dir())
        self.assertFalse(paths.platform_updates())
        self.assertFalse(library.default_folder().startswith(self.app_dir))
        self.assertFalse(backup.recovery_folder().startswith(self.app_dir))
        self.assertNotIn(self.app_dir, paths.settings().fileName())

    def test_data_folder_beside_the_program(self):
        self.marker()
        data = os.path.join(self.app_dir, "data")
        self.assertTrue(paths.is_portable())
        self.assertEqual(paths.portable_data_dir(), data)
        self.assertFalse(paths.platform_updates())
        self.assertEqual(library.default_folder(), os.path.join(data, "Library"))
        self.assertEqual(backup.recovery_folder(), os.path.join(data, "recovery"))
        self.assertEqual(paths.data_dir("x"), os.path.join(data, "x"))
        self.assertTrue(os.path.isdir(os.path.join(data, "x")))
        st = paths.settings()
        self.assertEqual(os.path.abspath(st.fileName()),
                         os.path.join(data, "settings.ini"))
        # what the program keeps reads back as it was written (the recent list is JSON text,
        # with commas an INI file could split; window geometry is bytes)
        from PySide6.QtCore import QByteArray, QSettings
        recent = ["C:/a, b/one.kzcad", "D:/two.kzcad"]
        st.setValue("recent", json.dumps(recent))
        st.setValue("geometry", QByteArray(b"\x01\x02,\x00"))
        st.setValue("update_check", "false")
        st.sync()
        again = QSettings(st.fileName(), QSettings.IniFormat)
        self.assertEqual(json.loads(again.value("recent")), recent)
        self.assertEqual(bytes(again.value("geometry")), b"\x01\x02,\x00")
        self.assertEqual(again.value("update_check"), "false")
        # an environment setting (the tests, the self-test) still wins
        os.environ["KANZONASCAD_LIBRARY"] = "/elsewhere"
        self.assertEqual(library.default_folder(), "/elsewhere")

    def test_portableapps_package(self):
        self.marker("KanzonasCAD portable (PortableApps.com Format)\n"
                    "data=..\\..\\Data\nUPDATES = off\nnot a setting\n")
        self.assertEqual(paths.portable_options(),
                         {"data": "..\\..\\Data", "updates": "off"})
        self.assertTrue(paths.platform_updates())
        if os.sep == "\\":
            want = os.path.normpath(os.path.join(self.app_dir, "..", "..", "Data"))
            self.assertEqual(paths.portable_data_dir(), want)

    def test_follow_drive(self):
        self.marker()
        on = {r"F:\Projects\a.kzcad"}
        with mock.patch.object(paths, "app_dir", return_value=r"F:\KanzonasCAD"), \
                mock.patch.object(paths, "is_portable", return_value=True):
            got = paths.follow_drive(r"E:\Projects\a.kzcad", exists=on.__contains__,
                                     splitdrive=_splitdrive)
            self.assertEqual(got, r"F:\Projects\a.kzcad")
            # a file that's there, or not on this drive either, stays as it was
            self.assertEqual(paths.follow_drive(r"F:\Projects\a.kzcad", exists=on.__contains__,
                                                splitdrive=_splitdrive), r"F:\Projects\a.kzcad")
            self.assertEqual(paths.follow_drive(r"E:\gone.kzcad", exists=on.__contains__,
                                                splitdrive=_splitdrive), r"E:\gone.kzcad")
        self.assertEqual(paths.follow_drive(""), "")


def _splitdrive(p):
    return (p[:2], p[2:]) if len(p) > 1 and p[1] == ":" else ("", p)


class PortableWindowTest(unittest.TestCase):
    def test_title_and_update_check_default(self):
        from kanzonascad import main_window
        from tests.util import window
        app_dir = tempfile.mkdtemp(prefix="kzcad-portable-")
        with open(os.path.join(app_dir, paths.MARKER), "w") as f:
            f.write("data=pafdata\nupdates=off\n")
        with mock.patch.object(paths, "app_dir", return_value=app_dir):
            self.assertEqual(main_window.app_title(), "KanzonasCAD (portable)")
            w, v = window()
            try:
                self.assertTrue(w.settings.fileName().startswith(app_dir))
                # the PortableApps.com Platform updates it: no checks of its own to start
                self.assertFalse(w.acts["auto_updates"].isChecked())
                self.assertFalse(w._checker().enabled())
                self.assertIn("(portable)", w.windowTitle())
            finally:
                v.project.saved_at = len(v.project.undo_stack)
                w.close()
        self.assertEqual(main_window.app_title(), "KanzonasCAD")


if __name__ == "__main__":
    unittest.main()
