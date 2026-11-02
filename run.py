"""Entry point for PyInstaller (the Windows exe and the Linux build)."""
import sys

from kanzonascad.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
