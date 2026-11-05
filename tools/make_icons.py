"""Make KanzonasCAD's icon files from the owner's two source pictures.

    python tools/make_icons.py

- assets/kanzonascad-icon-source.png (1024 x 1024): the app icon. From it:
  assets/kanzonascad.png (256 x 256: the Linux AppImage, the PortableApps.com icons),
  kanzonascad/resources/icon.png (the same, shown in the window) and assets/kanzonascad.ico
  (the program's .exe).
- assets/kanzonascad-setup-source.png (1024 x 1024): the installer's icon (a blue tile, so the
  setup can't be mistaken for the program). From it: assets/kanzonascad-setup.ico.

Then run tools/make_paf_icon.py (assets/portableapps-appicon.ico, from assets/kanzonascad.png).

Every size is the source reduced with Lanczos, the way the files were made before this script
(checked pixel for pixel on the 0.11.6 files).
"""
import os
import shutil

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICO_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128),
             (256, 256)]


def path(*parts):
    return os.path.join(ROOT, *parts)


app = Image.open(path("assets", "kanzonascad-icon-source.png")).convert("RGBA")
app.resize((256, 256), Image.LANCZOS).save(path("assets", "kanzonascad.png"))
shutil.copyfile(path("assets", "kanzonascad.png"), path("kanzonascad", "resources", "icon.png"))
app.save(path("assets", "kanzonascad.ico"), format="ICO", sizes=ICO_SIZES)

setup = Image.open(path("assets", "kanzonascad-setup-source.png")).convert("RGBA")
setup.save(path("assets", "kanzonascad-setup.ico"), format="ICO", sizes=ICO_SIZES)

for f in ("assets/kanzonascad.png", "kanzonascad/resources/icon.png", "assets/kanzonascad.ico",
          "assets/kanzonascad-setup.ico"):
    print("wrote", f)
print("now run tools/make_paf_icon.py")
