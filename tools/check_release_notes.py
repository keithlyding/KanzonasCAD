"""Fail when RELEASE_NOTES.md has no section for the current version."""
import re
import sys

sys.path.insert(0, ".")
from kanzonascad import __version__  # noqa: E402

text = open("RELEASE_NOTES.md", encoding="utf-8").read()
if not re.search(r"^## %s\s*$" % re.escape(__version__), text, re.M):
    print("RELEASE_NOTES.md has no '## %s' section" % __version__)
    sys.exit(1)
print("Release notes for %s found" % __version__)
