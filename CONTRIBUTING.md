# Contributing to KanzonasCAD

Thanks for your interest. KanzonasCAD is a free, open-source electrical CAD program for Windows
and Linux, maintained by one person in their spare time, so reviews may take a while.

## Reporting bugs and ideas

Open an issue with the **Bug report** or **Feature request** form. For anything that could let
a file run code or expose data, follow [SECURITY.md](SECURITY.md) instead of opening a public
issue. **Never attach a client's real drawing**: make a sample that shows the problem.

## Code changes

1. Talk first: for anything bigger than a small fix, open an issue describing what you'd like
   to change, so time isn't spent on something that won't be merged.
2. Work on a branch and open a pull request into `main`.
3. Follow the rules in [AGENTS.md](AGENTS.md) (CLAUDE.md points there). In short, every
   user-facing change updates in the same pull request:
   - the user manual in `kanzonascad/manual.py` (Help > User manual);
   - the version in `kanzonascad/__init__.py`;
   - a row in `CHANGELOG.md` and a section in `RELEASE_NOTES.md`.
4. Keep it fast: never walk every object on a mouse move or paint, and import heavy libraries
   (ezdxf, openpyxl...) inside the function that needs them. The self-test's speed budgets
   enforce this.
5. Keep the model free of Qt (`model.py`, `geometry.py`, `trim.py`, `sheetframe.py`), and send
   every change through one undoable edit (`with project.edit(...)`).
6. Use American spelling in all text the user sees. Units are inches.

## Running and testing

```
pip install -r requirements.txt -c constraints.txt
python -m kanzonascad                       # run the app
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -p "test_*.py" -t .
QT_QPA_PLATFORM=offscreen python -m kanzonascad --selftest selftest.log   # must exit 0
```

On Windows, leave out `QT_QPA_PLATFORM=offscreen`. Every push builds the Windows and Linux apps
and runs the tests and the self-test inside them (GitHub Actions); a pull request needs both
builds green. Merging a new version into `main` publishes it as a release automatically.

## License

KanzonasCAD is licensed under the MIT License (see [LICENSE](LICENSE)). Its dependencies must
stay compatible with that: no GPL or AGPL libraries. By contributing, you agree that your
contribution is licensed under the same terms. Code taken from elsewhere keeps its notice and
is listed in [NOTICE.md](NOTICE.md).

## Conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
