# Release notes

Short, plain-language notes for each version. The full details are in
[CHANGELOG.md](CHANGELOG.md).

Every version gets a section `## <version>` (a few lines under **New** and **Fixed**). The
build fails without them.

## 0.2

**New**
- Your own library of schematic symbols, panel footprints and parts, kept in a folder outside
  the program (Documents\KanzonasCAD Library), for every project from now on.
- 27 built-in JIC/NFPA symbols: coils, contacts, pushbuttons, switches, fuses, breakers,
  overloads, lights, motor and more.
- Make block (B) turns a drawing into a symbol (with pins and a tag) or a panel footprint;
  parts link a manufacturer and catalog number to both.
- Scale by Reference brings a manufacturer's drawing to its real size; lengths can be typed in
  millimeters (45mm).
- Text justification like AutoCAD's (top, middle, bottom; left, center, right), and
  double-click a text to change its wording, height, angle or justification.

## 0.1

**New**
- The first version of KanzonasCAD, a free electrical CAD program for Windows and Linux.
- Projects with as many sheets as you need, each with a grid of zones (6-D1) along the top and
  left, and a title block you can redraw yourself (Sheets > Edit title block), with fields
  like {Customer} and {Sheet} OF {Sheets} filled in on every sheet.
- A black drawing area like AutoCAD's; PDFs always print black on white.
- AutoCAD-style drawing: command line (L, PL, C, M, CO, RO, TR...), object snaps, ortho, polar
  tracking at the angles you choose, grid snap, grips, undo and redo.
- Selecting like AutoCAD: the object under the cursor lights up, window and crossing
  selection, and the lasso (hold the button and draw around objects).
- Drag selected objects to move them (hold Ctrl to copy); the cursor shows a move arrow
  when you are over something you can drag.
- Layers, copy and paste, DXF import and export, PDF export.
- The same look as KanzonasPDF: menus, ribbon tabs and light or dark theme.
