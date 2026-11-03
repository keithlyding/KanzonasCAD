"""The user manual (Help > User manual, F1). Name menu commands exactly as the menus show
them: the self-test check "user manual covers every command" fails the build when a menu
command is missing here."""

from . import __version__

_HTML = """
<h1>KanzonasCAD user manual</h1>
<p>Version {version}. KanzonasCAD is a free electrical CAD program for Windows and Linux.
It works like AutoCAD (a command line, object snaps, grips, window selection) but keeps
the list of commands short. Drawings are in <b>inches</b> on ANSI sheets.</p>

<p><i>This is the first version: drawing, sheets with a grid of zones and a title block,
layers, and DXF/PDF in and out. Electrical symbols, wires, wire numbers, cross-references
and reports come next.</i></p>

<h2>The window</h2>
<ul>
<li><b>Menus and ribbon</b> along the top, as in KanzonasPDF. The ribbon's tabs are
<b>Home</b>, <b>Sheets</b>, <b>Output</b> and <b>View</b>. Double-click a tab name (or
<b>Collapse ribbon</b>, Ctrl+F1) to fold it away; click a tab to open it again.
<b>Ribbon group names</b> shows the group names under the buttons.</li>
<li><b>Project tabs</b>: each open project has its own tab.</li>
<li><b>Sheets panel</b> on the left: the project's sheets with their page numbers. Click one to
show it, double-click to open its properties, right-click for more.</li>
<li><b>Command line</b> along the bottom (Ctrl+9 shows or hides it).</li>
<li><b>Status bar</b>: the cursor's X and Y in inches and its <b>zone</b> (for example
6-D1: sheet 6, row D, column 1), and the GRID, SNAP, ORTHO and OSNAP switches.</li>
</ul>

<h2>Projects and sheets</h2>
<p>A project (a <code>.kzcad</code> file) holds all its sheets. Each sheet is drawn on an
ANSI sheet (A, B, C or D) with a border, a <b>grid of zones</b> (columns 1, 2, 3 ... along
the top, rows A, B, C ... down the left side; nothing on the right or bottom, so the drawing
gets that room) and a <b>title block</b> in the lower right corner.</p>
<p>The <b>page number</b> of a sheet is its position in the project unless you type one in
<b>Sheet properties...</b>. It is the first part of every grid reference (6-D1) and, later,
of every wire number (6001, 6002 ...).</p>
<ul>
<li><b>New sheet</b> adds a sheet after the one shown, the same size and zones.</li>
<li><b>Delete sheet</b> removes the sheet shown (Undo brings it back).</li>
<li><b>Move sheet up</b> and <b>Move sheet down</b> change the order (and so the automatic
page numbers).</li>
<li><b>Sheet properties...</b>: title, page number, size, number of zone columns and rows.</li>
<li><b>Project properties...</b> (or double-click the title block): the title block fields
(customer, project, drawing number, drawn by, checked by, date, revision, and any field of
your own the title block uses) and the <b>grid reference format</b>
(<code>{{sheet}}-{{row}}{{col}}</code> gives 6-D1).</li>
<li><b>Edit title block</b>: see below.</li>
<li><b>Layers...</b>: add, rename, recolor, switch off and lock layers, and choose the current
layer. The Layer box on the Home tab picks the current layer; with objects selected, picking
a layer moves them to it.</li>
</ul>

<h2>The title block</h2>
<p>The title block is a small drawing of its own, the same on every sheet of the project.
<b>Edit title block</b> (Sheets menu and Sheets tab) shows it by itself: draw, move, trim,
erase and type text there with the usual commands, or <b>Import DXF into this sheet...</b>
to bring in your company's title block and move it into the lower right corner. Click
<b>Edit title block</b> again (or click a sheet in the Sheets panel) to go back.</p>
<p>A text that contains a field name in braces shows that field's value on every sheet:</p>
<ul>
<li><code>{{Customer}}</code>, <code>{{Project}}</code>, <code>{{Drawing number}}</code>,
<code>{{Drawn by}}</code>, <code>{{Checked by}}</code>, <code>{{Date}}</code>,
<code>{{Revision}}</code> - from Project properties.</li>
<li><code>{{Sheet}}</code> (the page number), <code>{{Sheets}}</code> (how many sheets) and
<code>{{Sheet title}}</code> - from each sheet. <code>{{Sheet}} OF {{Sheets}}</code> gives
"6 OF 12".</li>
<li>Any other name, like <code>{{Job number}}</code>, becomes a field of your own: it appears
in Project properties to fill in.</li>
</ul>
<p>A name in braces that isn't a field shows as typed, so a typo is easy to spot. Undo works
on title block changes like on any other.</p>

<h2>Drawing</h2>
<p>Start a command from the ribbon, the <b>Draw</b> and <b>Modify</b> menus, or by typing its
name or alias on the command line and pressing <b>Enter</b> or <b>Space</b>. Enter on an
empty command line repeats the last command. <b>Esc</b> cancels.</p>
<table border="1" cellpadding="3" cellspacing="0">
<tr><th>Menu command</th><th>Typed</th><th>What it does</th></tr>
<tr><td>Line</td><td>LINE, L</td><td>Lines point to point. Close (C) and Undo (U)
options.</td></tr>
<tr><td>Polyline</td><td>PLINE, PL</td><td>One connected object through all its points.</td></tr>
<tr><td>Rectangle</td><td>RECTANG, REC</td><td>Two corners (or the first corner, then
@width,height).</td></tr>
<tr><td>Circle</td><td>CIRCLE, C</td><td>Center, then radius (a point or a number); D for a
diameter.</td></tr>
<tr><td>Arc (3 points)</td><td>ARC, A</td><td>Start, a point on the arc, end.</td></tr>
<tr><td>Text</td><td>TEXT, T, DT</td><td>Start point, height, angle, then type each line and
press Enter; Enter on an empty line ends. Double-click a text to change it.</td></tr>
<tr><td>Move</td><td>MOVE, M</td><td>Select, base point, second point.</td></tr>
<tr><td>Copy objects</td><td>COPY, CO, CP</td><td>Select, base point, then as many copies as
you place (Enter ends).</td></tr>
<tr><td>Rotate</td><td>ROTATE, RO</td><td>Select, base point, angle (a point or degrees).</td></tr>
<tr><td>Scale</td><td>SCALE, SC</td><td>Select, base point, factor.</td></tr>
<tr><td>Mirror</td><td>MIRROR, MI</td><td>Select, two points of the mirror line, keep or erase
the originals. Text stays readable.</td></tr>
<tr><td>Erase</td><td>ERASE, E, or Delete</td><td>Removes the selected objects.</td></tr>
<tr><td>Trim</td><td>TRIM, TR</td><td>Click the part of an object to cut away: it is trimmed
back to the nearest crossing objects on either side (every object is a cutting edge, as in
AutoCAD's quick mode). An object nothing crosses is erased. U undoes the last trim.</td></tr>
<tr><td>Zoom</td><td>ZOOM, Z</td><td>Extents (E), Sheet (S), In (I), Out (O).</td></tr>
</table>
<p>Typed <b>Undo</b> (U) and <b>Redo</b> work on the command line too.</p>

<h3>Typing points</h3>
<ul>
<li><code>3,4</code> - the point x=3, y=4 (inches from the sheet's lower left corner).</li>
<li><code>@1,0</code> - 1 inch right of the last point.</li>
<li><code>@2&lt;45</code> - 2 inches from the last point at 45 degrees.</li>
<li><code>1.5</code> - 1.5 inches from the last point toward the cursor (direct distance;
with ORTHO on, straight across or up and down).</li>
</ul>

<h3>Drafting aids</h3>
<ul>
<li><b>Object snap</b> (F3, OSNAP): points snap to ends, midpoints, centers, quadrants,
intersections and text insertion points near the cursor; a yellow marker shows which.</li>
<li><b>Grid display</b> (F7, GRID): dots across the drawing area.</li>
<li><b>Ortho mode</b> (F8, ORTHO): lines straight across or up and down.</li>
<li><b>Polar tracking</b> (F10, POLAR): near one of the set angles (from the last point), the
cursor locks onto that direction: a green dashed line and a tip show the distance and angle
(<i>Polar: 2.5 &lt; 45&deg;</i>). Typing a number then goes that far along it. The angles are
every 45 degrees to start; <b>Drafting settings...</b> chooses the step (90, 45, 30, 22.5, 18,
15, 10, 5 or your own) and extra angles of your own (for example 60, 120). Ortho and Polar
tracking can't be on together: turning one on turns the other off.</li>
<li><b>Snap to grid</b> (F9, SNAP): points snap to the snap spacing (1/8 inch to start); along a
polar direction, the distance snaps to it.</li>
<li><b>Drafting settings...</b>: snap spacing, grid spacing, text height and the polar tracking
angles (all kept for next time).</li>
</ul>

<h2>Selecting and grips</h2>
<ul>
<li>The object under the cursor <b>lights up</b> (a bright line with a blue glow): that is what a
click selects.</li>
<li>Click an object to add it to the selection; <b>Shift</b>+click removes it.</li>
<li><b>Window</b>: click in an empty spot, move, and click again. <b>Left to right</b> (blue)
selects what is wholly inside; <b>right to left</b> (green, dashed) also selects what it
crosses.</li>
<li><b>Lasso</b>: press in an empty spot, hold the button and draw around the objects, then let
go. Dragged first to the <b>right</b> it is a window lasso (blue: what is wholly inside); to
the <b>left</b>, a crossing lasso (green: what it touches too).</li>
<li>While a window or lasso is open, the objects it would select light up.</li>
<li><b>Select all</b> (Ctrl+A); Esc clears the selection.</li>
<li>Selected objects show blue <b>grips</b>. Click a grip, then click where it goes, to stretch
that end, corner, radius or text position.</li>
<li>Select first, then start Move, Copy objects, Rotate... (or start the command and then
select, pressing Enter when done).</li>
<li>Right-click: Enter while a command runs; otherwise a menu with Repeat, the clipboard and
the modify commands.</li>
</ul>

<h2>Viewing</h2>
<ul>
<li>Mouse wheel zooms at the cursor; hold the <b>middle button</b> to pan; double-click the
middle button for <b>Zoom extents</b>.</li>
<li><b>Zoom extents</b> (Ctrl+Shift+E), <b>Zoom to sheet</b> (Ctrl+0), <b>Zoom in</b> (Ctrl+=),
<b>Zoom out</b> (Ctrl+-).</li>
<li><b>Black drawing background</b> (on to start, as in AutoCAD): the sheet is drawn black with
white lines. Turn it off for a white sheet. <b>Export to PDF...</b> always prints black on
white either way.</li>
<li><b>Theme</b>: Light, Dark or Same as system: the menus, ribbon and panels.</li>
<li><b>Command line</b> and <b>Sheets panel</b> show or hide those panels.</li>
</ul>

<h2>Edit menu</h2>
<ul>
<li><b>Undo</b> (Ctrl+Z) and <b>Redo</b> (Ctrl+Y or Ctrl+Shift+Z): every change, including
sheet and layer changes, can be undone.</li>
<li><b>Cut</b> (Ctrl+X), <b>Copy</b> (Ctrl+C) and <b>Paste</b> (Ctrl+V): paste asks for an
insertion point (the copied objects' lower left corner lands there). Works between projects,
and after KanzonasCAD is closed and started again.</li>
<li><b>Delete</b> erases the selection.</li>
</ul>

<h2>Files</h2>
<ul>
<li><b>New project</b> (Ctrl+N), <b>Open...</b> (Ctrl+O, a project or a DXF drawing),
<b>Open recent</b>, <b>Save</b> (Ctrl+S), <b>Save as...</b> (Ctrl+Shift+S),
<b>Close project</b> (Ctrl+W), <b>Exit</b> (Ctrl+Q).</li>
<li><b>Import DXF into this sheet...</b>: lines, polylines, circles, arcs, text, ellipses and
splines (as polylines), blocks and dimensions (exploded). Drawings in millimeters are
converted to inches. AutoCAD DWG files: save them as DXF first (in AutoCAD, or with the free
ODA File Converter).</li>
<li><b>Export this sheet to DXF...</b> and <b>Export all sheets to DXF...</b>: AutoCAD 2013 DXF
in inches, one file per sheet, border and title block on layer BORDER.</li>
<li><b>Export to PDF...</b>: every sheet at its real size, vector lines, everything printed
black on white (layer colors are for the screen).</li>
</ul>

<h2>Keyboard shortcuts</h2>
<table border="1" cellpadding="3" cellspacing="0">
<tr><td>F1</td><td>User manual</td></tr>
<tr><td>F3</td><td>Object snap on/off</td></tr>
<tr><td>F7</td><td>Grid display on/off</td></tr>
<tr><td>F8</td><td>Ortho mode on/off</td></tr>
<tr><td>F9</td><td>Snap to grid on/off</td></tr>
<tr><td>F10</td><td>Polar tracking on/off</td></tr>
<tr><td>Ctrl+9</td><td>Command line on/off</td></tr>
<tr><td>Ctrl+F1</td><td>Collapse ribbon</td></tr>
<tr><td>Enter / Space</td><td>Finish a step; repeat the last command</td></tr>
<tr><td>Esc</td><td>Cancel the command; clear the selection</td></tr>
<tr><td>Delete</td><td>Erase the selection</td></tr>
<tr><td>Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S</td><td>New / Open / Save / Save as</td></tr>
<tr><td>Ctrl+W / Ctrl+Q</td><td>Close project / Exit</td></tr>
<tr><td>Ctrl+Z / Ctrl+Y</td><td>Undo / Redo</td></tr>
<tr><td>Ctrl+X / Ctrl+C / Ctrl+V / Ctrl+A</td><td>Cut / Copy / Paste / Select all</td></tr>
<tr><td>Ctrl+Shift+E / Ctrl+0 / Ctrl+= / Ctrl+-</td><td>Zoom extents / sheet / in / out</td></tr>
</table>

<h2>Help</h2>
<p><b>User manual</b> (F1) opens this page. <b>About KanzonasCAD</b> shows the version.</p>
"""


def html():
    return _HTML.format(version=__version__)


def plain_text():
    import re
    return re.sub(r"<[^>]+>", " ", html()).replace("&lt;", "<").replace("&gt;", ">")
