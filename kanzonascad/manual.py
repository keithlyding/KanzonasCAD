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
<b>Home</b>, <b>Schematic</b>, <b>Panel</b>, <b>Sheets</b>, <b>Output</b> and <b>View</b>, and
<b>Block</b> while you edit a block; each
group of buttons has its name under it (Rail and duct, Dimensions, Numbering...). Move, Copy,
Rotate, Mirror, Stretch and Erase are on the Schematic and Panel tabs too (Modify), not only Home.
The Schematic and Panel tabs are laid out alike: what you draw first (Wire and Bus; DIN rail and
Wire duct), then placing parts (Symbols; Footprints: the same buttons in the same order), Modify,
Dimensions, the tab's own groups, and Parts, Layers and Settings at the right end. Double-click a
tab name (or <b>Collapse ribbon</b>, Ctrl+F1) to fold it away; click a tab to open it again.
<b>Ribbon group names</b> (View) turns the names off, for a more compact ribbon, and on
again. When the window is too narrow for a tab, its groups shrink from the right: big
buttons become small ones with their names beside them, then icons alone (the name shows
when you hold the mouse over one); widen the window and they grow back. Only a tab that
still doesn't fit as icons scrolls sideways (the mouse wheel over it).</li>
<li><b>The Block tab</b> holds a block's own tools: <b>Save block</b>, <b>Save block as...</b>,
<b>Block properties...</b> (in a block's tab, that block's: nothing to select), <b>Duplicate
block...</b>, <b>Add pin</b>, <b>Pins...</b>, <b>Add attribute</b>, <b>Linear dimension</b> and
<b>Aligned dimension</b> (Measure: to measure the block as you draw it; a dimension drawn in
a block's tab isn't saved into the block, so its copies don't carry it; one the block already
had stays), <b>Edit block...</b> and <b>Update blocks from library...</b>. It shows up and opens by itself
in a block's tab (Edit block..., on the Schematic tab's Symbols group and the Panel tab's
Footprints group, opens one), and goes away when you leave it. To have it all the time, turn
on <b>Block tab</b> (View menu, and the View tab's Ribbon group). The same commands are always
in the Library menu.</li>
<li><b>Project tabs</b>: each open project has its own tab. Drag a tab away from the tabs and
let go to give it a window of its own (see <b>Windows and two screens</b>).</li>
<li><b>Sheets panel</b> on the left: the project's sheets with their page numbers. Click one to
show it, double-click to open its properties, right-click for more (<b>Open in a new window</b>,
<b>Print...</b>). Ctrl+click and Shift+click select several sheets without changing the one
shown, for printing them.</li>
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
<li><b>Ctrl+Tab</b> shows the next sheet in page order and <b>Ctrl+Shift+Tab</b> the one
before; past the last sheet it goes round to the first (on sheet 13 of 15: 14, 15, then 1), and
back from the first to the last. Hold Ctrl and keep tapping Tab to go on.</li>
<li><b>Ctrl+`</b> (the key above Tab) goes back to the sheet you were last on, as Studio 5000
does: hold Ctrl and keep tapping ` to go on through the sheets you were on before it, most
recent first, then the ones you haven't opened yet in page order (Ctrl+Shift+` steps back). A
list of the sheets shows meanwhile, the one picked lit; let Ctrl go to open it, or press Esc
(Ctrl still held) to stay where you are.</li>
<li><b>Duplicate sheet</b> (Sheets menu and tab) adds a copy of the sheet shown just after it,
with everything on it, titled with the next number no sheet has ("Motors" becomes "Motors-2",
then "Motors-3"; "480 Distribution - 1" becomes "480 Distribution - 2"), on a page of its own (the next free number when the
original's was typed). Its devices get tags of its page (CR201 becomes CR301), its wires new
numbers, and its off-sheet connectors and arrows no name (so it isn't joined to the original's
wires: name them for the copy). One step, so Undo takes it back.</li>
<li><b>Delete sheet</b> removes the sheet shown (Undo brings it back).</li>
<li><b>Move sheet up</b> and <b>Move sheet down</b> change the order (and so the automatic
page numbers).</li>
<li><b>Sheet properties...</b> (or double-click the sheet in the Sheets panel): what belongs to
one sheet: its title, its <b>type</b> (Schematic, Panel, Report or Other: every tool works on
every sheet; the type brings up the matching ribbon tab and shows in the Sheets panel), its
<b>location</b> (the panel or box what it shows is in: MCP, JB-1, FIELD; see Cables between
panels), page number and, if it differs from the project's, its own revision, and its
default <b>wire layer</b> (the layer new wires on it go on: as the project, or one of its own;
see Colors and layers), its <b>References</b> (as the project, Grid or Ladder: see Ladders), and
how its <b>Tap numbers end in</b> (as the project, -1, a or -a: see Wire numbers).
Its size and zones are the project's unless you tick "This sheet has its own size and zones";
then set how many columns run along the top and the first one's number (11 makes a sheet
continue 11 to 20), and how many rows run down the left and the first one's letter. Grid
references follow the zones as they are set: change them and every reference updates.</li>
<li><b>Project properties...</b> (or double-click the title block): what belongs to the whole
project, in four tabs:
<ul>
<li><b>General</b>: the title block fields (customer, project, drawing number, drawn by, drawn
date (today's when the project is made), checked by, date, revision, and any field of your own
the title block uses), the <b>grid reference
format</b> (<code>{{sheet}}-{{row}}{{col}}</code> gives 6-D1), <b>References</b> (Grid, or
Ladder: places given by rung; see Ladders), <b>Rung numbers</b> and the <b>Rung spacing</b> of
new ladders, and the height of new text.</li>
<li><b>Schematic</b> (also <b>Schematic settings...</b>): the sheet size and zones every sheet
uses unless it has its own (8 rows, A to H, and 10 columns to start), the device tag height
(changing it resizes every tag), and the symbol color.</li>
<li><b>Panel</b> (also <b>Panel settings...</b>): the footprint and dimension colors.</li>
<li><b>Wire layers</b>: <b>New wires go on</b>, the wire layer new wires go on on every sheet
that hasn't one of its own (WIRES to start), and the project's wire layers in a list, as in
Layers...: <b>New</b> makes a wire layer of any name (CONTROL, say), <b>Add preset...</b> adds
the 480 V, 120 V, 24 VDC and Ethernet ones, and Rename, Color..., Delete, the gauge (AWG), wire
color and Gauge shown work as in Layers.... Changes in the list are made at once (Undo takes
them back), even if you then click Cancel.</li>
</ul></li>
<li><b>Edit title block</b>: see below.</li>
<li><b>Layers...</b>: add, rename, recolor, switch off, lock and delete layers, and choose the
current layer. To clean up (after importing a DXF, say), select several layers (Ctrl+click,
Shift+click) or click <b>Select unused</b> (the empty ones), then <b>Delete</b>: empty layers
go at once; if some hold objects (on any sheet or in the title block), it lists them and asks
whether to delete them too, with everything on them, or keep them. Layer 0 always stays, and
one Undo brings it all back. The Layer box on the Home and Panel tabs picks the current layer;
with objects selected, picking a layer moves them to it. The Schematic tab's box is the
<b>wire layer</b> box (below).</li>
</ul>

<h2>Colors and layers</h2>
<p>As in AutoCAD, every object takes its <b>layer's color</b> (ByLayer) unless you give it its
own: select it and use <b>Color...</b> (Modify menu, or the Schematic and Panel tabs) to pick a
color, or to set it back to ByLayer. A symbol or footprint's lines follow the color of the
layer it sits on, or its own color if you gave it one.</p>
<p><b>Wire layers</b> are WIRES, a layer named WIRE..., one with a gauge or wire color, one Add
wire layers made, and one made in Project properties, Wire layers. Each sheet has a <b>default
wire layer</b>, saved with the project: its own (Sheet properties: <b>Wire layer</b>) or, set
to <b>As the project</b>, the project's (Project properties, Wire layers: <b>New wires go
on</b>, WIRES to start). The Schematic tab's layer box is the <b>wire layer</b> box: it lists
the wire layers only and shows the one wires go on. Pick another and the wires you draw on that
sheet go on it, while lines and text stay on the current layer; picking a wire layer in the
Home tab's layer box, or making one current in Layers..., picks it too. Pick a layer that isn't
a wire layer (0, to draw lines) and wires go back on the sheet's default. Each sheet keeps its
own pick while the project is open (another sheet shows its own); a pick isn't saved, so on
opening the project each sheet starts at its default, and changing a default (Sheet properties,
or Project properties) drops the picks it covers so it is used at once. With wires selected,
picking in the wire layer box moves them to it (other objects stay where they are). A wire (or a bus wire, with the Bus layers left at Wires)
that starts or ends on another wire, a tap off it or carrying it on, takes that wire's layer
instead: it is the same conductor, so the same voltage, color and gauge (a size typed on the
new wire is still its own), and the rubber band shows it in that color as you draw. A wire
joining wires of two different layers stays on the wire layer picked (or the default), and the command line warns
that two conductors may be tied together. A wire on its own that starts on a symbol's pin (or, failing that, ends
on one) takes <b>the layer the pin gives</b>, whatever layer is picked: a PLC module's input or
output point, or its V, 24VDC BLU; its common (C, COM, RTN), 24VDC BLU-WHT; a motor's or
drive's power terminal (L1-L3, T1-T3, U, V, W), 480V BLK, and its ground (PE), 480V GRN; a
control transformer's H terminals 480V BLK, X1 120V RED and X2 120V WHT; a power supply's L
120V RED, N 120V WHT, + 24VDC BLU and - 24VDC BLU-WHT. A pin given a wire layer of its own
(<b>Pins...</b>, in a block's tab) gives that one. Only a layer the project has is used (<b>Add
wire layers...</b> brings in all of these), and the command line says which layer and pin. Project
properties, Schematic: <b>A wire takes its layer from the pin it starts on</b> (on to start) turns
it off. Symbols go on
SYMBOLS, footprints on PANEL and dimensions on DIMENSIONS: the Schematic and Panel tabs of
Project properties set those colors, which recolors everything on them. On the black drawing,
black (or nearly black) objects are drawn white, and on a white one, white objects are drawn
black, so nothing disappears (as AutoCAD's color 7); their color stays as you set it, and they
print in it.</p>
<p><b>Wire gauge and color</b>: in <b>Layers...</b>, double-click a wire layer's <b>AWG</b> or
<b>Wire color</b> to give its wires a gauge (14, 10, 2/0...) and insulation color (BLK, BRN,
GRN/YEL...), picked from the usual ones or typed. Each run of joined wires on that layer then
shows its gauge, <b>10 AWG</b>: in line with its number, just after it (<b>2018&nbsp;&nbsp;12
AWG</b>), when the wire's straight piece has room and nothing is in the way, else on the other
side of the wire from its number (under it, or right of it on an upright wire), slid along the
wire off any other wire's number or label; smaller (Project properties, Schematic: <b>Gauge label
height</b>, 0.06" to start); <b>Show a wire layer's gauge beside its wires</b> there turns it
off for the whole project, and a layer's <b>Gauge shown</b> in <b>Layers...</b> (click it: Yes
or No) for that layer's wires only: control power all of one gauge and color (24VDC BLU,
BLU-WHT), say, where the label would only crowd a breaker. A wire given a gauge of its own still
shows it. The label shows the wire's insulation color too (<b>10 AWG BRN</b>) on every wire
when <b>...and its color</b> under that setting is ticked (off to start). <b>Wire color
label</b> (WIRECOLOR, WCL; Modify menu, Schematic tab: Edit wires) turns the color the other way
on the wires you select or click: on where the project leaves it off, off where it shows it;
again, and it goes back. A wire keeps that choice whatever the project setting says. Wires
side by side of one gauge (within 3/4" of each other on paper, running along each other: a
starter's conductors to its drive, a bus) show it <b>once</b>: a thin oval drawn across them
where they run side by side, with a leader out at 45 degrees to the label, level; where there
is no clear spot for that, beside the outside one (the rightmost of upright wires, the lowest
of those across). The colors shown of them are listed once each in order across them (<b>12
AWG BRN, ORG, YEL</b>). <b>Gauge and color shown</b>, On
every wire, puts it back on each. The layers a bus adds (WIRE BROWN,
WIRE ORANGE...) come with their color's name; give them a gauge once and every wire on them
shows it. A wire color of two names, <b>BLU/WHT</b> say, draws the layer's wires striped: the
layer's color with stripes of the second (a 24 VDC common), on the screen and printed (not when
printing in black only).</p>
<p><b>Add wire layers...</b> (Format menu, Schematic tab: Layers; also the <b>Wire layers...</b>
button in Layers...) adds a layer for each wire of the systems you tick, with its color, gauge
and wire color, ready to draw on (pick one in the Schematic tab's wire layer box, then draw
wires):</p>
<ul>
<li><b>480 V</b>, 12 AWG: 480V BLK, 480V RED, 480V ORG, 480V BRN, 480V YEL, 480V WHT (neutral)
and 480V GRN (ground).</li>
<li><b>120 V</b>, 14 AWG: 120V RED, 120V BLK and 120V WHT (neutral).</li>
<li><b>24 VDC</b>, 16 AWG: 24VDC BLU, and 24VDC BLU-WHT for the common, blue with white
stripes.</li>
<li><b>Ethernet</b>: ETHERNET, green, a cable with no gauge.</li>
</ul>
<p>A layer the project has already keeps its own color, gauge and wire color. Change any of
them in Layers... as usual.</p>
<p><b>Wire size</b> (WIRESIZE, WSZ; Modify menu, Schematic tab: Edit wires): give the selected
wires, or wires you click one by one (Enter when done), a gauge of their own in place of their
layer's: type it (<b>10</b>, <b>1/0</b>, <b>250 kcmil</b>), or <b>L</b> to go back to the
layer's. The gauge label beside them shows it (<b>10 AWG BLK</b>). A wire keeps its size when
it is moved, copied, cut or saved; two wires meeting end to end are made one only when they
are on one layer with one size.</p>
<p><b>Layers</b>, as in AutoCAD: pick one in the layer box with objects selected and they go on
it (the box shows their layer, empty when they are on several); with nothing selected it
becomes the current layer. A hidden layer isn't drawn, printed or picked; a locked one
is drawn but its objects can't be selected or changed. <b>Layers...</b> lists them all (On,
Locked, color, current layer). Quicker, on the Home tab's Layers group (the Panel tab has the
layer box, the layer list, Layers..., Color, Hide layer and Show all too; the Schematic tab the
same with the wire layer box in place of the layer box) and the Modify menu:</p>
<ul>
<li>The <b>layer list</b> button next to the current layer: every layer with its light bulb
(click to hide or show it) and lock (click to lock or unlock it).</li>
<li><b>Hide layer</b> (LAYOFF): click an object, or select objects first: their layer hides.</li>
<li><b>Show only this layer</b> (LAYISO): every other layer hides.</li>
<li><b>Show all layers</b> (LAYON) and <b>Unlock all layers</b> (LAYULK).</li>
<li><b>Lock layer</b> (LAYLCK): click an object, or select objects first: their layer locks.</li>
</ul>
<p>Each of these is one step for Undo.</p>
<p>The ribbon's <b>Schematic</b> and <b>Panel</b> tabs gather the tools for each kind of work.
Both are always there: any sheet can hold a schematic, a panel layout, or both.</p>

<h2>The title block</h2>
<p>The title block is a small drawing of its own, the same on every sheet of the project.
<b>Edit title block</b> (Sheets menu and Sheets tab) opens it in a tab of its own, as Edit
block opens a block, with the <b>Title block</b> ribbon tab: draw, move, trim, erase and type
text there with the usual commands, or <b>Import DXF or DWG into this sheet...</b> to bring in
your company's title block and move it into the lower right corner. Your drawing stays as it
was in its own tab meanwhile. <b>Save title block</b> (the Title block tab and the Sheets menu,
or Ctrl+S) puts it in the project as one step (Undo in the drawing takes it back), closes the
tab and goes back to the drawing, on the Sheets tab. <b>Close title block</b> (or closing its
tab) leaves the project's title block as it was, asking first if you changed anything: Save,
Discard or Cancel. Edit title block again while its tab is open shows that tab.</p>
<p><b>Title blocks you keep.</b> In the title block's tab, <b>Save as title block...</b> keeps the
title block you drew in your library under a name of your own (your company's, a customer's),
with where it sits on the sheet, for any project; the tab stays open. <b>Title blocks...</b>
(Sheets menu and Sheets tab) puts one in the project: the ready-made ones (<b>Standard, lower
right corner</b>; <b>Standard, right-hand strip</b>; <b>Standard, bottom strip</b>), always there
whatever you save, or one of yours. It goes where it was made for, and Undo puts the old one
back. <b>Delete</b> there takes one of yours out of the library (projects using it keep their
copy). They are kept in the <code>Title blocks</code> folder of your library folder (both library
folders are read, so a shared folder can hold your company's).</p>
<p><b>A logo</b>: in the title block's tab, <b>Picture or SVG</b> (Title block tab) brings in your
logo (PNG, JPEG...); place it and drag a corner to size it. It is kept in the project (and in a
title block you save), and shows on every sheet, printed and in PDFs.</p>
<p>A text that contains a field name in braces shows that field's value on every sheet:</p>
<ul>
<li><code>{{Customer}}</code>, <code>{{Project}}</code>, <code>{{Drawing number}}</code>,
<code>{{Drawn by}}</code>, <code>{{Drawn date}}</code>, <code>{{Checked by}}</code>,
<code>{{Date}}</code>, <code>{{Revision}}</code> - from Project properties.
<code>{{Drawn date}}</code> is set to the day the project is made (or made from a template);
in a project from before it existed, it shows the typed Date. <code>{{Date}}</code> and
<code>{{Revision}}</code> follow the revision history once there is one (see
<b>Revisions</b>): <code>{{Date}}</code> is the revision date.</li>
<li><code>{{Print date}}</code> - when the paper copy was made: the date and time a PDF or
DXF export was written (11/05/2026 3:14 PM); on screen, today's date. The built-in title
blocks show it small, as PRINTED ..., so anyone holding a print can tell how old it is.</li>
<li><code>{{Sheet}}</code> (the page number), <code>{{Sheets}}</code> (how many sheets) and
<code>{{Sheet title}}</code> and <code>{{Scale}}</code> (1:4, 3" = 1'-0"...) - from each
sheet. <code>{{Sheet}} OF {{Sheets}}</code> gives
"6 OF 12".</li>
<li><code>{{Revision date}}</code>, <code>{{Revision description}}</code> and
<code>{{Revision by}}</code> - the latest revision's (see <b>Revisions</b> below); and for a
revision table, <code>{{Rev 1}}</code>, <code>{{Rev 1 date}}</code>,
<code>{{Rev 1 description}}</code> and <code>{{Rev 1 by}}</code> (the latest revision),
<code>{{Rev 2}}</code>... (the one before), empty past the oldest. Draw the table's rows with
those texts in Edit title block, newest on top.</li>
<li>Any other name, like <code>{{Job number}}</code>, becomes a field of your own: it appears
in Project properties to fill in.</li>
</ul>
<h3>Revisions</h3>
<p><b>New revision...</b> (Sheets menu and Sheets tab) adds the next revision to the drawing's
history: numbered 0 for the first, then 1, 2..., dated today (11/05/2026), by the project's
Drawn by, for all sheets; type its description and click OK. <b>Revisions...</b> shows the
whole history, oldest first, to change any cell (number, date, description, by), delete one,
or add one. In <b>Sheets</b>, "All" means the revision covers every sheet; type page numbers
(3, 5) for one that changed only those. Each change is one step that Undo takes back.</p>
<p>Once there is a history, each sheet's <code>{{Revision}}</code> and <code>{{Date}}</code>
show the latest revision that covers that sheet (Project properties shows them, greyed:
they come from the history), so sheet 5 can be at revision 2 while the others are at 1. A
revision typed in a sheet's own Sheet properties still wins on that sheet. With no history,
they show what Project properties says, as before. A new project made from a template starts
with no history.</p>
<p>Dates on the drawing: the <b>drawn date</b> (when it was started), the <b>revision date</b>
(the latest revision's, which an issue is: "Issued for construction" is a revision's
description) and the <b>print date</b>. The built-in title blocks show DRAWN BY, DRAWN (the
drawn date), CHECKED BY and REV DATE, and the print stamp; a project made before 0.12.9 keeps
its title block: tick <b>Replace the title block with one made for this position</b> in
Project properties to get the new one (Undo puts the old one back), or add the fields to it in
Edit title block.</p>
<p>A name in braces that isn't a field shows as typed, so a typo is easy to spot. Undo works
on title block changes like on any other.</p>
<p><b>Use as title block</b> (Sheets menu and tab): to use a title block that came with a
drawing from another program (open or import its DXF or DWG), select it on the sheet (the
block, or its lines and texts) and click Use as title block. It becomes the project's title
block, shown on every sheet in the same place, and leaves the sheet; the old title block goes
(Undo brings it back). A block's attributes become fields: AutoCAD Electrical's (through its
WD_TB attribute, or by name: DWGNO and DWGNAM the drawing number, SHEET and SHEETMAX the sheet
and how many, DWGDESC and TITLE the sheet title, DATE, REV, SCALE, DRAWN, CHECKED, CUSTOMER,
PROJECT), revision rows (REV1, REV1DET, BY1, RD1: <code>{{Rev 1}}</code>, its description, by and
date; KanzonasCAD's Rev 1 is the latest revision), any other its own name, a field of the
project to fill in Project properties. Their values come along into Project properties when the
project's are empty. The sheet must be upright (not turned) to do it.</p>
<p><b>Show on sheets</b> (Project properties, General): untick <b>Border and zones</b> or
<b>Title block</b> to leave them off every sheet: not drawn, printed or exported. A sheet can
say otherwise in its Sheet properties: <b>Border and zones</b> and <b>Title block</b> there are
<b>As the project</b> (to start), <b>Shown</b> or <b>Off</b>, for that sheet alone. Grid
references (6-D1) still follow the zones when the border is off.</p>
<p><b>Title block position</b> (Project properties, General) says where the title block sits:</p>
<ul>
<li><b>Lower right corner</b> (to start): the zones run the full width and height of the
sheet, and the title block sits over the lower right corner. The ready-made one is 5" wide and
1-1/16" tall: SHEET TITLE; CUSTOMER and PROJECT; DRAWN BY, DRAWN, CHECKED BY and REV DATE;
DRAWING NO., REV, SCALE and SHEET. A project made before 0.22.2 keeps its bigger one (6-1/2"
by 1-3/8", no SCALE): choose Lower right corner and tick <b>Replace the title block with one
made for this position</b> to get the new one.</li>
<li><b>Right-hand strip</b>: the title block takes the whole right-hand column of the sheet.
The zones stop at it (a line divides them from the strip) and are spread over the room left,
so grid references (6-D1) never point into the title block.</li>
<li><b>Bottom strip</b>: the same along the bottom of the sheet.</li>
</ul>
<p>The strip's width (or height) is that of the title block you drew. Tick <b>Replace the
title block with one made for this position</b> to swap in a ready-made one, with the same
fields, that fills the strip (or the corner); Undo puts your old one back. The title block you
leave is kept with the project: choose its position again with the box ticked and you get it
back, edits and all, not a ready-made one (going to the strip and back to the corner gives you
your own corner title block). Ticking the box without changing the position gives a fresh
ready-made one. On a panel sheet with a scale the strip stays its size on paper.</p>

<h2>Symbols, footprints and parts (the library)</h2>
<p>Your <b>library</b> is a folder of its own (<code>Documents\\KanzonasCAD Library</code> to
start, or <code>data\\Library</code> beside the program in the portable version; <b>Library
folder...</b> picks another, a OneDrive folder say). <b>Second library folder...</b> (Library
menu) adds a second one, searched with the first: one shared with your team in a synced folder
(OneDrive, SharePoint, Google Drive, Dropbox: their own apps sync it) and one of your own, say,
or any two folders. Everything in the second shows "(second library)" in the Library panel; a
name in both is the first library's. A block or part is always saved back to the library it is
in; new ones go to the first, or to the second with <b>Save new blocks and parts to the second
library</b> ticked (Library menu). A folder you can't write to (a read-only share) is used
read-only: its blocks and parts are there to place, and saving one says why it can't. Cancel in
the second folder's window offers to take it away (its files stay). It is kept apart from
the program and from projects, so it lasts through updates and serves every project. Each
project also keeps its own copy of the blocks it uses, so it opens the same anywhere, whatever
happens to the library later. Each part is a file of its own in the library's <b>parts</b>
folder, so two people adding parts to a library in a synced folder at the same time don't
make the sync app keep a conflict copy; if it keeps one anyway ("... (Keith's PC).json"), the
Library panel names it instead of listing the part twice. A library from before 0.21 keeps
its parts in parts.json until a part is next saved or deleted, when they move to files of
their own.</p>
<ul>
<li><b>Schematic symbols</b>: blocks with <b>pins</b> (where wires attach) and a <b>tag</b>.
A starter set of JIC/NFPA symbols is built in (relay, contactor and timer coils, NO/NC and
timed contacts, pushbuttons, E-stop, selector, limit/pressure/temperature/float switches,
fuse, breaker, disconnect, overload heater and contact, pilot light, motor, solenoid, control
transformer, terminal strip and terminal, ground, distribution block, off-sheet connector;
three-phase: 3-pole breaker, disconnect and fuses, fused disconnect, contactor power contacts,
overload heaters, starter, motor, drive control terminals, variable frequency drive; power supply; PLC I/O card with input and output points).
A symbol of yours with the same name replaces a built-in one.</li>
<li><b>Panel footprints</b>: the outline of a real part, at real size, for panel layouts.
KanzonasCAD comes with generic ones at typical sizes, in the Generic categories: breakers 1, 2
and 3 pole, fuse holders, a motor protector, a surge protector and a rotary disconnect
(Protection); contactors, an overload relay, plug-in relays with their bases, a slim interface
relay and a timer relay (Control); 24 VDC power supplies of 2.5, 5 and 10 A; terminal blocks
(2.5, 4 and 10 mm2, ground and fuse terminals), an end plate and an end stop (Terminals); a PLC
processor and an I/O module (PLC); control transformers of 100, 250 and 500 VA (Transformers,
for the back panel); 22 mm pushbuttons, pilot lights and selector switches and a 40 mm
emergency stop (Door devices). DIN-rail devices are 18 mm a pole and about 90 mm tall; each one's
description gives its size. They are typical, not any maker's: for a part you buy, draw its
own from its maker's drawing (Make block), or Edit block one of these and save it under your
own name. A footprint of yours with the same name replaces a built-in one.</li>
<li><b>Parts</b>: a manufacturer and catalog number linked to a schematic symbol and a panel
footprint. Placing a part fills in its manufacturer, catalog number and description.</li>
<li><b>A symbol and a footprint with the same name</b> stay apart in a project: the one
placed second is kept as "name (footprint)" or "name (symbol)" (its tab in the Library still
shows its own name), so a footprint never takes a symbol's drawing, or the other way round.
Edit block..., Update blocks from library... and saving a changed block find each by its own
name and kind.</li>
</ul>
<p>The <b>Library</b> opens as a popup window, as AutoCAD Electrical's icon menu does, so the
drawing keeps the whole width: <b>Insert symbol...</b> (Schematic tab) opens it on its Symbols,
<b>Insert footprint...</b> (Panel tab) on its Footprints, and <b>Library...</b> (Library menu)
as you left it; its Parts tab lists your parts. Type in its search box to find one.
Double-click a symbol or footprint (or select it and click <b>Insert</b>): the popup gets out
of the way and you click where it goes; type R to turn it 90 degrees, F to flip it
horizontally (left and right swap) or V to flip it vertically (upside down) first, as it is
on the drawing however it is turned.
Once it is placed, <b>Enter</b> (or Space) inserts the same symbol again, with a tag of its
own.
A symbol with pins is held by its <b>first pin</b> (L1 on a 3-pole device, 1 on a contact, A1 on
a coil): the point you click is where that pin goes, so click the pin or wire it is to join (a
3-pole fuse clicked on a disconnect's T1 meets T1, T2 and T3 with its L1, L2 and L3). The
command line says which pin it is held by; type B to hold it by the next pin, and after the
last, by its base point (the middle of the library's symbols). Footprints are placed by their
base point. Once placed, a symbol's grip (the one that moves it) is its first pin too, where
a wire joins it, not its middle. Turned (R) and flipped (F, V) as you like, a symbol with several pins clicked onto
wires or pins flips itself when that lands more of its pins: a 3-pole symbol turned either way
onto a bus running up and down lands every pole on its own wire (the preview shows it as it
will go). The popup opens again where you last put it. The JIC symbols' tags sit at one
height above the wire (all the three-pole devices at one, all the one-line symbols at
another), so the tags of symbols side by side line up; a project started before 0.16 takes
the new heights with <b>Update blocks from library...</b>. A symbol turned sideways shows its
tag beside it, read across, starting at its spot and running away from the symbol (clear of
its poles). Select a symbol to see a grip on its tag (and on a Rating or other attribute it
shows at one spot): drag it anywhere, and it stays there on that copy, following the symbol
when it is moved or turned (Undo puts it back). In the Parts tab, Insert asks whether to place
the part's symbol or its footprint.</p>
<h3>Making your own</h3>
<ol>
<li>Draw it, or open the manufacturer's DXF and copy the view you want into your drawing
(Copy, then Paste).</li>
<li>A footprint must be real size: <b>Scale</b>, pick a base point, type R (Reference), pick
the two ends of a dimension you know (the part's width say) and type its real length
(<code>45mm</code> or <code>1.77</code>).</li>
<li>Select it and use <b>Make block</b> (B). Pick the <b>base point</b> (the point it is placed
by), then fill in the name, kind (schematic symbol or panel footprint: it starts on panel
footprint on a panel sheet, on schematic symbol otherwise), category and description, and,
if you like, its manufacturer, family, series and catalog number (see below). For a symbol also: its part in cross-references (a device on its own, a coil or
operator with contacts elsewhere, or a contact), the contact type, the tag prefix (CR, M, PB...),
what wire numbers do through it (nothing; a distribution block; an off-sheet connector: see
Wire numbers) and the pin names, and whether the <b>pin names show on the drawing</b>
(ticked to start for a symbol you make: its terminal numbers, 13, 14, A1, written just inside
each pin, above the wire or beside it, read across however the symbol is turned; untick it
when your drawing already has them as text). Block properties changes it later (Update
blocks from library brings it to a project), and on one copy it is <b>Pin names</b> in the
attributes window's Shown on the drawing (or Show or hide attributes).</li>
<li>For a symbol, click each <b>pin</b> in order and press Enter, then click where the
<b>tag</b> goes (Enter puts it above).</li>
</ol>
<p>It is saved to your library and, unless you untick it, the selected objects become the
block. <b>New part...</b> then links a manufacturer and catalog number to the symbol and the
footprint.</p>
<p><b>Assign part...</b> (Library menu, the Panel tab's Parts): select the devices
(every contactor on the sheet, say), then pick one of your library's parts for them, from those
made for their symbols, filtered as you type; every selected device using the part's symbol takes
its manufacturer, catalog number and description, in one step, and keeps its tag. Type your
<b>brand</b> there (Allen-Bradley, Siemens...) and its parts are listed first in this project.
The project keeps its own copy of each part it uses, so changing or deleting a part in the
library never changes a drawing. <b>Save to library as part</b> (Library menu) does the other
way round: select one device with a catalog number and it is saved to your library as a part,
with its manufacturer, description, symbol and the footprint linked to it (saving it again
updates that part).</p>
<p>Double-click a placed symbol or footprint to change its tag, description, manufacturer and
catalog number, or pick one of the library's parts for it. Fuses, circuit breakers,
disconnects, overloads, motors, the control transformer, the VFD and the power supply also
have a <b>Rating</b> (30A, 5HP, 500VA...): typed there, it shows <b>in a fuse's box</b> (in
each of a three-pole fuse block's), and under the other symbols (at one height for every
one-line symbol and another for every three-pole one, so a row's ratings line up), and on the bill of materials it is added to the description (two fuses without a catalog
number but with different ratings are different lines). A project started before 0.16 gets the
Rating with <b>Update blocks from library...</b>. They also have a field for each of their
ratings, as applies: a motor <b>Horsepower</b>, <b>Volts</b> and <b>Full-load amps</b>; a drive
and a starter Horsepower, Volts and <b>Amps</b>; breakers and disconnects Amps and Volts; fuses
Volts (their amps are the Rating in the box); overload heaters Amps; the control transformer
<b>VA</b>, <b>Primary volts</b> and <b>Secondary volts</b>; the power supply Volts and Amps. A
plain number gets its unit on the drawing (5 shows as 5HP, 460 as 460V, 7.6 as 7.6A FLA);
anything else (1/2 HP, 480V 3PH) shows as typed. They show under the Rating, each on a line of
its own; an empty or hidden one leaves no gap. The bill of materials adds them to the
description (a 5HP motor and a 10HP one are different lines). A project started before 0.17.5
gets them with <b>Update blocks from library...</b>. Its <b>Shown on the drawing</b>
boxes choose which of its attributes (its tag, a terminal's number, an imported block's
location, rating...) show on this copy; a hidden one keeps its value, and reports still use
it. Beside each is its <b>Angle</b>, the angle its text is drawn at on the drawing (the arrows
turn it 90 degrees at a time): turned, it turns with the symbol when the symbol is turned
afterward, as in AutoCAD; set back to the symbol's own angle, it is drawn as the symbol draws
it again (the tag read across). <b>Show or hide attributes...</b> (Modify menu; Schematic tab: Symbols, Panel tab:
Footprints) does the same for every selected symbol and block at once: each attribute any of
them shows is ticked when shown on all of them, unticked when hidden on all, partly ticked when
it differs (left so); one undoable step. <b>Explode</b> (X) turns placed
blocks back into plain lines and texts. Delete in the Library panel removes your own symbols,
footprints and parts (the built-in symbols and footprints stay).</p>

<a name="manufacturer-family-series"></a>
<h3>Manufacturer, family and series</h3>
<p>Every symbol and footprint can say who makes it, in three optional fields (Make block asks
for them; <b>Block properties...</b> changes them). They are only for finding and grouping
blocks: nothing else depends on them, and you can leave any of them blank.</p>
<ul>
<li><b>Manufacturer</b>: the company whose name is on the part's label: Allen-Bradley
(Rockwell Automation), Siemens, Schneider Electric, Phoenix Contact...</li>
<li><b>Family</b>: the product line within that manufacturer: ControlLogix, CompactLogix or
PowerFlex 525 (Allen-Bradley); SIMATIC S7-1500 (Siemens)...</li>
<li><b>Series</b>: the line or generation within the family, when the maker uses one. For
Rockwell it is the hardware series letter on the label (Series A, B, C...); other makers use
"series" for a sub-line of a family. Leave it blank if you don't need it.</li>
<li><b>Catalog number</b>: the manufacturer's part number for this exact part, as on its label
and in its catalog (1756-A10, 1769-L33ER, 3RT2015-1BB41...). Placing the block fills it in as
the placed copy's catalog number (CAT), as a part does. Give one when the block is one part
(a footprint usually is); leave it empty for a generic symbol many parts use, and link those
parts to it with <b>New part...</b> instead.</li>
</ul>
<p>Makers name things differently, and there is no one right way: pick a way of writing each
name and keep to it (Allen-Bradley or Rockwell Automation, not both), so your blocks group
together. Each field offers what your library already holds (the families of the
manufacturer typed, the series of that family); the list grows from what you type. The
<b>?</b> button beside Manufacturer opens this section.</p>
<p>In the Library popup, the search box also finds a manufacturer, family or series, and the
two lists above the symbols (<b>All manufacturers</b>, <b>All families</b>) show only one
manufacturer's blocks, or one family's; the manufacturer list also filters the Parts tab. The
third list, <b>All phases</b>, shows only the <b>Three-phase</b> blocks or only the
<b>Single-phase and control</b> ones. A block is three-phase when it has pins L1-L3, T1-T3 or
U, V, W, or says 3-pole, 3-phase or 3ph in its name or description (the breakers,
disconnects, fuses, contactor power contacts, overloads and starter of three poles, the
three-phase motor and the drive); <b>Phases</b> in its Properties... (Automatic, Three-phase,
Single-phase or control) sets it when that guess is wrong. A
block's tooltip shows all three. Placing a block whose manufacturer is set fills in the placed
copy's manufacturer (as a part does; a part's own manufacturer wins), and <b>New part...</b>
with a symbol or footprint selected in the Library starts the part with that block and its
manufacturer.</p>

<h3>Changing a library block</h3>
<p>Select a symbol or footprint in the Library popup (or one placed in the drawing) and use:</p>
<ul>
<li><b>Properties...</b> (a button in the Library popup, its right-click menu, or
<b>Block properties...</b> in the Library menu): the details Make block asked for, filled in:
name, category, description, manufacturer, family, series and, for a symbol, its part in
cross-references, contact, tag prefix, wire numbers through it and its pin names in order
(renaming pins; Edit block adds or removes them). Those last are greyed out on a panel
footprint (Make block makes one when you are on a panel sheet): change its <b>Kind</b> to
<b>Schematic symbol</b> to give it a tag prefix and the rest (it gets a tag spot above its
drawing; Edit block... adds its pins); the kind can change either way. Renaming it saves it
under the new name, removes your file under the old one and points your parts at the new
name.</li>
<li><b>Edit block...</b> (a button in the Library popup, its right-click menu, or the Library
menu, the Schematic tab's Symbols group, the Panel tab's Footprints group and the Block tab,
for a block selected in the drawing): the library's
copy of the block opens in a tab of its own, <b>Block: name</b>, as AutoCAD's Block Editor
does. Change it with every normal command (Move, Copy, Trim, Text, grips, Undo...). The cross
is the <b>base point</b> (on the locked layer BLOCK BASE POINT); each green text on layer BLOCK
PINS is a <b>pin</b>: its insertion point, marked with a small ring, is where wires attach, and
its text is the pin's name (edit the text to rename it, move it with its grip, copy it to add
a pin, erase it to remove one). <b>Add pin</b> (ADDPIN, PIN, AP; Library menu and the Block
tab, in that tab) adds pins by clicking: click where the pin goes (the
snaps help: a line's end), then type its name or press Enter for the one offered (one more than
the highest number: 15 after 13 and 14, A3 after A1 and A2); it goes on with the next pin until
Enter or Esc. A name already there is asked again. <b>Pins...</b> (the same places) lists the
pins in their order, with each one's name and place (X and Y in inches from the base point):
double-click a name or a place to change it (a pin put in the wrong spot: type where it goes);
drag a row, or <b>Move up</b> and <b>Move down</b>, to change the order (the order a bus lands
on them wire for wire, and the order Properties... lists them); <b>Delete</b> takes a pin out;
<b>Find</b> selects it on the drawing and puts it in the middle of the view; <b>Wire layer</b>
(double-click it) gives a pin a wire layer of its own: a wire started on that pin goes on that
layer when the project has it (blank: worked out from the block, as Layers describes). OK makes
all of it one step (Undo takes it back); two pins with the same name are refused. A pin's name in a block's tab is a text you can justify like any other
(double-click it: Left, Center, Right, or More... for top, middle or bottom too); the block
keeps it, and a copy showing its pin names shows it so; left as it opened, it follows the
pin's side: the side its lead line comes in from (or the nearest edge of the block), so a pin
on the bottom edge near a corner (PE2 beside T3 on a drive) reads as a bottom pin. The blue text on BLOCK TAG is where the tag goes, and texts on
BLOCK ATTRIBUTES are where a terminal's number, a PLC address or a rating shows; their
alignment and angle (Edit text: middle center, say, so a rating sits in the middle of a fuse
whichever way it is turned) are kept with the block. <b>Add attribute</b> (ADDATTR, ATTDEF,
ATT, AA; Library menu and the Block tab, in that tab) gives the block one more: type its name
(HP, VOLTS, FLA, KW... one word, no spaces; TAG has its own marker), then click where its
value shows, or type <b>S</b> to put it under the block's ratings (RATING, HP, VOLTS...), in
their stack, so it closes up with them when one above it is empty (a rating's text copied
straight down under the stack joins it too); it goes on with the next name until Enter or Esc.
Each copy of the block then has a box for it in <b>Properties...</b>: an empty one shows
nothing. HP, VOLTS, AMPS, FLA, VA, PRI and SEC typed as a plain number show their unit (5 shows
5HP); any other attribute shows as typed. Leaving the block's tab, the ribbon goes
back to the tab it was on. A footprint has a pink
<b>DIN RAIL</b> text on layer BLOCK DIN RAIL: its insertion point (a ring, with a dashed line
across the part where the rail's centerline runs) is the middle of the part's rail clip. Move
it to where the rail's center crosses the part (its height on the part is what counts on a
rail across; snap to the clip's drawing if it has one) and the part sits right on the rail
when placed; left where it opened, it stays the middle of the drawing (also when the drawing
changes); erased, it goes back to that. The blue <b>LABEL</b> text on layer BLOCK TAG is
where its <b>Footprint label</b> goes, the same way: left where it opened, the middle of the
drawing; moved, that spot. <b>Save block</b>
(Library menu, the ribbon's Block tab, or Save, Ctrl+S, in that tab) puts it back in your library: the
pins keep their order (or the one set in Pins...), new ones come after, and the block's tab
closes, back to the drawing it was opened from. Closing the tab with changes not saved asks
first. <b>Save block as...</b> (Library menu and the Block tab, in that tab) saves it under a new
name instead, with its catalog number left blank: the block it was opened from stays as it
was in your library, and the tab closes too.</li>
<li><b>Duplicate...</b> (a button in the Library popup, its right-click menu, or
<b>Duplicate block...</b> in the Library menu and the Block tab, for a block selected in the
drawing): to make a block that is almost like one you have (a footprint of
the next size up, a contactor with another contact arrangement), it asks for a name (offering
"name copy"), saves a copy under it in your library with everything the same but the catalog
number, left blank, and opens the copy in Edit block right away to be changed. Set its
details (catalog number, series...) with Properties....</li>
</ul>
<p>Changing a built-in JIC symbol saves your own copy of the same name, which takes its place
(Delete in the Library brings the built-in one back). After saving, if the project in the
drawing tab (for Edit block, the one it was opened from) has copies of the block, KanzonasCAD
asks <b>Update the copies of ... in ...?</b> Yes changes them in one step (Undo takes it back):
they take the new drawing, a renamed block's copies take its new name, and their tags,
descriptions, manufacturers and catalog numbers stay. Wires stay on the pins (matched by
name; two pins of one name in their order) and stretch to where the pins moved; a wire on a pin that is gone stays where it was,
and the command line says how many. No keeps the old drawing. Other projects keep their own
copies of the block as they were.</p>
<p><b>Update blocks from library...</b> (Library menu) does the same for every block in the
project in the drawing tab that the library has differently: one of yours changed since it
was placed, or a JIC symbol a newer KanzonasCAD draws differently. It lists them and asks
first; Yes updates them all in one step (Undo takes it back), each copy keeping its tag,
attributes and place, its wires on its pins. A project keeps its own copy of every block it
uses, so it opens the same anywhere: this is how it takes a newer one.</p>


<h2>Device tags</h2>
<p>Every device you place gets its tag by itself: the symbol's prefix, the page number and a
two-digit count on that page. On page 6 that's <b>CR601</b>, CR602, <b>M601</b>, PB601...; on
page 12, CR1201. The <code>CR?</code> you may have seen before means a device still waiting
for a number (Renumber sheet gives it one).</p>
<ul>
<li>A new device takes the <b>lowest free</b> number for its prefix on its page, so deleting
CR602 frees 02 for the next relay.</li>
<li><b>Copies</b> (Copy, Paste, Mirror keeping the original, Ctrl+drag) get their own tag;
a device pasted onto another page takes that page's number (CR601 pasted on page 7 becomes
CR701 when that's free).</li>
<li>When a sheet's <b>page number changes</b> (typed in Sheet properties, or by moving sheets
around), its tags follow: CR601 becomes CR701.</li>
<li><b>Typing a tag yourself</b> (double-click the device) locks it: automatic numbering never
changes it. Untick "Lock this tag" there to give it back.</li>
<li><b>Renumber sheet</b> (Schematic tab, Sheets menu) numbers the sheet's unlocked devices
01, 02... per prefix in the sheet's <b>numbering order</b> (Sheet properties): across then
down, or down then across, or <b>along the wires</b>. Locked tags stay and their numbers are
skipped. Only devices hold numbers: a footprint, contact or power section carrying a device's
tag takes the device's new tag, and never makes it skip one.</li>
<li><b>Along the wires</b> follows a bus however it winds round the sheet (right along the top
row, down the side and back left along the next, say). <b>Numbering source</b> (NUMSOURCE;
Schematic tab: Numbering, Sheets menu): click the symbol the wires start from (the disconnect)
and the sheet is numbered along the wires from it, as you would trace them: each branch off the
bus in the order its drop leaves the bus, and everything down that branch (its contactor, drive
and motor) with the same count, M209, VFD209 and MTR209. Wire numbers follow too: a branch's
own wires get their numbers before the next branch's (a drop off the bus is the bus's wire and
has its number). Devices the wires don't reach from the source come after, across then down.
Renumber sheet or Update numbers then numbers it so. A bus wire that doubles back on itself
(Clean up wires straightens it) can upset the order. Whether wire numbers follow the tags'
order or go across and down is a project setting (Project properties, Schematic: <b>Wire
numbers follow the tags' numbering order</b>, on to start) that a sheet can override (Sheet
properties: <b>Wire numbers in</b>: as the project, the tags' order, or across, then
down).</li>
<li><b>Update numbers and cross-references...</b> (Schematic tab: Numbering, Sheets menu) does
it for more at once. Tick what to update: <b>Device tags</b>, <b>Wire numbers</b>,
<b>Cross-references</b> (any of them, or all). Choose how: <b>Renumber in order</b> (01, 02...
for tags and 001, 002... for wires, in each sheet's order; locked ones stay) or <b>Keep the
numbers</b> (only what has no number gets one, and a number that isn't of its sheet's page is
fixed, its count kept when free). And where: <b>This sheet</b>, <b>The whole project</b>, or
<b>These sheets</b> (tick them in the list). One step: Undo takes it all back. Frozen sheets
keep their cross-references.</li>
<li><b>Lock numbers...</b> (Schematic tab: Numbering, Sheets menu) locks wire numbers and/or
device tags as they are, so numbering, Renumber sheet and Update numbers leave them alone:
<b>The selected objects</b> (select the wires and devices first), <b>This sheet</b>, <b>The
whole project</b> or <b>These sheets</b>. <b>Unlock</b> in the same window gives them back to
numbering. It is the same lock as a device's <b>Lock this tag</b> and a wire's <b>Lock this
number</b> (double-click it), which lock one at a time; new wires and devices still get
numbers. (Freeze cross-references, below, is for a sheet's cross-reference text only.)</li>
<li>Contacts take their device's tag (next section); symbols without a tag prefix get no
tag.</li>
<li>Behind each tag, every device also has a hidden identity that survives renaming, so
contacts, cross-references and panel footprints stay linked whatever the tag becomes.</li>
</ul>

<h2>Contacts and cross-references</h2>
<p>A contact (a relay contact, a timed contact, an overload contact...) belongs to a device:
a coil, a pushbutton or switch operator, a timer. It shows that device's tag and follows it:
renumber or retag the coil, or move its sheet, and its contacts change with it.</p>
<ul>
<li><b>Placing a contact</b>: after the click, the command line asks which device it belongs
to. The nearest device with the contact's prefix (CR for a relay contact; on this sheet first)
is offered as a button (or type its tag); type another tag (<code>M601</code>) to take that
device, or <b>L</b> for a list of them, or <b>P</b> to <b>pick it on the drawing</b>: go to any sheet
(the Sheets panel) and click the device (the pick box lights a device as you go over it;
wires and other objects don't light up, as they can't be picked); you come back and the
contact is placed, linked to it (Esc stops). A tag no device has yet is kept, and the contact links itself
to the device that gets that tag. <b>Enter</b> places it on its own, linked to no device
(its reference shows <b>?</b>; double-click it to link it later), and so does a contact with
no device in the project to offer. A Starter 3-pole is a device of its own with its own tag
(M), not a contact of a coil: its auxiliary and overload contacts belong to it.</li>
<li><b>Contact blocks</b> (Library, JIC/Pushbuttons and switches: <b>Pushbutton contact NO</b>,
<b>Pushbutton contact NC</b>, <b>Selector switch contact NO</b>, <b>Selector switch contact
NC</b>): more contacts of one pushbutton, emergency stop or selector switch, on other rungs (an
E-stop's second NC for another circuit, an NO to a PLC input). They belong to it as any contact
does (PB or SS: the nearest pushbutton or switch is offered). Placed in its column on its sheet
(straight above or below it), they are joined to it by a <b>dashed line</b> drawn by itself, from
the operator through the farthest block, as one operator works them all; it follows them when
they move, and a block moved out of the column leaves it. Blocks joined by the line show no
tag and no reference of their own, and aren't listed under the operator (the line shows where
they belong; only the operator shows the tag); one on another sheet, or out of the column, shows
its tag and reference and is listed as usual. A block's tag you hide yourself (double-click it,
Shown on the drawing) stays hidden either way. Relay
contacts are never joined this way.</li>
<li><b>Changing it later</b>: double-click the contact. "Belongs to" lists the project's
devices; pick one or type a tag. Deleting a coil leaves its contacts unlinked (showing
<b>?</b>) until a device takes that tag again.</li>
<li><b>Dashed box</b> (DB; Draw menu and the Schematic tab, Draw): a dashed outline around
anything, with a note in it, that can belong to a device or to nothing. Pick two opposite
corners; its window asks for the <b>Note</b> (several lines, written inside its top left
corner; or none) and what it <b>Belongs to</b>: <b>(nothing: a box with a note)</b>, a device
from the list (every device in the project, by page; type in the box to find one, or type a
tag such as <code>PDB1</code> or <code>M101</code>), or <b>Pick on drawing...</b>: go to any
sheet and click the device, and you come back with the box made. A box that belongs to a
device shows its tag above its top left corner, with where the device is beside it
(<code>M101 2-E3</code>), follows it when it is renumbered or retagged, and is listed under the
device like a contact (its zone). Its grips: the four corners (it stays a rectangle), the note
and the tag (drag them anywhere). Double-click it to change its note or what it belongs to.
Its text and dashes are paper-sized (the tag height in Project properties), it goes on layer
NOTES, and it moves, copies, turns, prints and exports to DXF (as dashes and texts) like any
object.</li>
<li><b>Cross-references</b> are worked out from the drawing, never typed: under a coil or
operator, one line per contact, <b>NO 6-D3</b> or <b>NC 7-B2</b> (in sheet order, then zone
order); under each contact, where its device is (<b>6-D1</b>). They use the project's grid
reference format and each sheet's zones (or, by ladder, the rung: <b>NC 605</b>, <b>603</b>;
see Ladders), and go into PDF and DXF exports as text.</li>
<li><b>Ladders</b> (LADDER, LAD; Draw menu, and the Schematic tab: Draw, the Dashed box button's menu): a ladder's two rails,
its rungs numbered down the left of the left rail. Click the top of the left rail, then the top
of the right rail (or type the width; the rails stay level), then the bottom (or type how many
rungs, or Enter: down to the bottom of the sheet). Before the first click, <b>F</b> gives it a
first number of its own and <b>S</b> the rungs' spacing (1/2 inch to start: Project
properties, General, <b>Rung spacing</b>). Rungs are numbered from the page: page 6 gives 600,
601, 602... (or, with Project properties, General, <b>Rung numbers</b> set to the page, a dash,
the rung: 6-01, 6-02...), and a second ladder on the sheet carries on from the first (left to
right, then top down). Renumbering pages renumbers them. Its rails' ends and every rung's ends
are snap points, for wires. Its grips: the left rail's top (moves it), the right rail's top
(its width) and the left rail's bottom (how many rungs). Double-click it for its first number
(blank: from the page), its rungs and their spacing. It goes on layer LADDER and moves, copies,
prints and exports to DXF (as lines and texts) like any object.
<br>With <b>References</b> set to <b>Ladder</b> (Project properties, General; or one sheet's,
Sheet properties), a device's place is the number of the rung it is on, not its grid zone:
cross-references (<b>NO 603</b> under a coil, <b>603</b> beside a contact), off-sheet arrows,
reports and the status bar read it. A device off every ladder still gives its grid zone.</li>
<li><b>Moving a contact's reference</b>: select the contact; the grip under it is its
reference's. Drag it anywhere, inside a big block (a drive's control terminals) say: it
stays there, moving and turning with the block.</li>
<li>They are on a layer of their own, <b>XREFS</b> (cyan to start; Layers... changes its color or
switches them off, on the screen, in prints and in exports), and a little smaller than wire
numbers: 0.065 inch (Project properties, Schematic). A project made before 0.18 gets the layer
when it is opened, and its cross-references the new size unless it was changed.</li>
<li>Double-click a coil and untick <b>List its contacts under it</b> to hide its list; untick
<b>List this contact under its device</b> on a contact to leave it out of the list.</li>
<li>They follow every change. <b>Update cross-references automatically</b> (Schematic tab,
Sheets menu) turns that off for the project: every sheet then keeps what it shows until
<b>Update cross-references</b>.</li>
<li><b>Freeze cross-references</b> (Schematic tab, Sheets menu) holds the current sheet's
references as they are, for a sheet that has been issued; Update cross-references leaves it
alone until you untick Freeze.</li>
<li>While any sheet shows references that aren't what the drawing says, the status bar says
<b>Cross-references out of date</b>, with the sheets in its tip; click it to update them.</li>
</ul>

<h2>Wires</h2>
<p><b>Wire</b> (W; Draw menu and the Schematic tab) draws a wire on layer WIRES (move wires
to another layer afterward like any object: select them and pick the layer in the Layer box;
they stay wires). Click where it
starts (a symbol's pin, another wire, or anywhere), then where it goes: it runs straight across
and up or down, with one corner per click; the corner follows the cursor, and F flips it the
other way. The wire <b>ends by itself</b> when you click a pin or another wire; Enter ends it
anywhere; so does Esc or starting another command (what is drawn is kept). U takes back
the last click. A wire never runs <b>through a symbol's pin</b> on the way (that would wire
the pin to it): a click whose leg would pass through one isn't taken, the command line says
which pin, and you click on the pin to end there, or elsewhere.</p>
<p>A wire <b>goes around the symbols in its way</b>: when the leg to your click would run
through a symbol's drawing, it goes round it instead (straight across and up or down, the
fewest corners, 1/8 inch clear of it on paper), and it leaves a pin, and arrives at one,
straight out of the side the pin is on: a wire from above to a drive's L3 on its bottom edge
goes down beside the drive and comes up into L3 from below. The preview shows the way it will
go. With nothing in the way a wire is as it always was. A <b>bus</b> goes round them too, all
its wires: as close as the clearance lets it when its other wires are on the outside of the
turns, with room for them when they are on the inside. When there is no way round for a bus
that wide from where you clicked (its other wires already past the symbol), the click isn't
taken and the command line says so: click farther from the symbol, or start again with fewer
wires (N) or closer ones (D). Project properties, Schematic,
<b>Wires go around the symbols in their way</b> turns it off, and <b>...keeping this far from
them</b> sets how far (on paper: 1/8 inch to start, 0.25 for 1/4 inch).</p>
<p><b>Dragging a run of wire</b> (AutoCAD Electrical's Scoot on a wire): select a wire and
drag the grip in the middle of one of its straight runs (or Scoot, click the wire, Enter, then
click the run): a run up and down moves left or right, a run across moves up or down, and its
neighbours stretch, staying square. The wires on it follow: a wire teed onto the run moves its
end with it, a wire carrying the run straight on moves with it, and one joined at a corner
stretches. An end of the run on a pin or another wire stays connected through a short jog. A
run with a symbol's pin on its middle (or at a corner of it) isn't moved: the command line
says so (move the symbol, or Scoot it along the wire).</p>
<p>Drawing a wire or a bus, <b>pins and wire ends always pull the point onto them</b> (the
green snap marker shows it), even with Object snap (F3) off, so a wire lands exactly on the
pin you click near; a symbol's insertion point (its middle, which is not a pin) is never a
target then, nor the lines of a symbol's drawing. If a wire end still stops just short of a
pin or another wire without joining it (within 1/32 inch on paper: typed coordinates, or a
point picked with the snaps off), a <b>red ring</b> marks it and the command line says how far
and from what ("A wire end stops 0.01" short of pin 2 of CR101 without joining it"); the ring
goes with the next change. Move the end onto the pin (its grip, with the snap) to join it.</p>
<p><b>Bus</b> (BU; Draw menu and the Schematic tab) draws several wires side by side, three
phases say. A bus never runs through a symbol's pin on the way (that would wire the pin to it):
a click that would take one of its wires through a pin (leaving its pins back through the same
symbol's other pins, or across another symbol) isn't taken, and the command line says which
pin is in the way; click somewhere else, or U takes the last point back. <b>Start it on a symbol's pin</b> (a disconnect's L1, L2 or L3, a breaker's T1...)
and it takes that side of the symbol: as many wires as it has pins there, as far apart as they
are, the first from its first pin and the others from the others, whichever way you head off
(the first leg leaves the pins square); whichever pin you start on, the next clicks are where
that pin's wire goes. To start from only some of a side's pins (a safety relay's S52, S12,
S21 and S22, not S11 above them), type <b>P</b> (<b>Pick pins</b>) first and click each pin, in
any order: each one picked shows a short stub, a pin clicked again is left out, and Enter goes
on, the bus with a wire from each of them, the first from the first in the symbol's order. They
must be one symbol's pins, in one line and evenly spaced (every other pin is fine; a bus keeps
its wires the same distance apart, so draw an odd one as a wire). Click a pin of a symbol with
as many pins as far apart (any of a fuse
block's L1, L2, L3) and the bus lands wire for wire (T1 on L1, T2 on L2...) and is done,
arriving square onto its pins: when it can't with the corners you have, it takes one more (a
Z: across, up or down, across again), each wire on its own pin and none crossing another.
<b>Click on or near a device</b> (on its drawing, near a pin, or a pin of a side the bus can't
land on as it is) and the bus lands on the device's <b>nearest pins</b>: as many as it has wires,
the ones nearest where you clicked, on a side that faces the bus (a fuse block turned with its L
side away: its T side). The bus comes square at the side, and when the pins are closer
together or farther apart than its wires (a drive's control terminals, 1/4" apart, from a bus
1/2" apart), each wire jogs over onto its own pin near the end, none crossing another, the
wires and the pins in the same order across (a symbol turned round: wire 1 lands on the pin
across from it, not L1). When no way there lands (a side with fewer pins than the bus has
wires, or no way round what's in between, or a bus started on a symbol's pins heading back
through that symbol), it goes on drawing and the command line says why.
<b>Start it on a bus's open end</b> (the free ends of wires side by side, as far apart) and it
carries that bus on: each wire joins its own, keeping its layer. <b>Start it on wires side by
side</b> (on the middle of one of three phases running across the sheet) and it drops one wire
off each, the first off the farthest back, each with a dot where it leaves its own; <b>end it
on them</b> (the last click on one of them, the bus arriving square) and each wire lands on its
own, the first on the first it meets, crossing the others, and the bus is done: a vertical
3-phase bus onto horizontal L1, L2, L3. Started anywhere else, it uses the last bus's count and spacing (the same on paper on a sheet of another scale; 3 wires,
1/2 inch to start): type <b>N</b> (or just the number) for how many, then how far apart (1/2
inch; 12mm works too), or <b>D</b> for the spacing alone. Then click the path as for a wire:
every click turns it 90 degrees, as many times as you need, and all the wires turn together,
keeping their spacing. <b>S</b> runs it <b>straight</b> instead: each click goes straight
across or straight up or down from the last point, with no corner (S again goes back to
corners; the next bus remembers). The other wires go to the right of the direction you draw (F
puts them on the other side). <b>L</b> picks each wire's <b>layer</b>, and so its color:
<b>Brown, orange, yellow (480 V)</b>, <b>Black, red, blue (208/240 V)</b>, <b>All black</b>,
<b>Wires</b> (the WIRES layer), or a layer for each wire; the layers it needs are added to the
project (WIRE BROWN, WIRE ORANGE...; black prints black and shows white on the black drawing
area), and the next bus remembers the choice. Enter or Esc ends it; each wire of the bus is an
ordinary wire, connecting wherever its ends land, whatever its layer.</p>
<ul>
<li><b>Connections</b> are worked out from where wire ends are, never stored: a wire end on a
pin, on another wire's end, or on the middle of another wire connects there; clicked on a
symbol's drawing (not on a pin), it goes to that symbol's nearest pin. A wire ending on
the middle of another (a T), or three or more wire ends at one point, get a <b>dot</b>.</li>
<li><b>Crossings</b>: wires that pass through each other don't connect. Project properties,
Schematic, <b>Wire crossings</b> says how that is drawn: <b>Loop</b> (one wire hops over the
other, to start in a new project), <b>Gap</b> (one wire is broken briefly) or <b>Plain</b>
(they just cross: no dot means not connected; projects started before 0.17.1 keep theirs, plain
unless changed); <b>Which wire jumps</b>: the up-and-down one (to start) or the
across one. Crossings are found by themselves and follow the wires as they move; they print
and export to DXF (the jumping wire cut, the loop as a half circle).</li>
<li><b>Wire crossing</b> (WX; Draw menu, Schematic tab) places one by hand: click a wire where
it should jump, on a crossing or anywhere else on it (over a symbol's line, say). Type
<b>G</b>, <b>L</b> or <b>N</b> first for a gap, a loop or <b>none</b> (none hides a crossing
found by itself). A mark placed by hand lights up as a small circle when the cursor is over
it; select and Erase it to take it away.</li>
<li><b>Two wires on one terminal</b> (double landing): start a wire on a pin that already has
one, or end it there, and the new wire runs straight onto the pin like the first. Schematic
settings, <b>A second wire on a pin leaves it on a 45-degree lead</b>, makes it leave the pin on
a short 45-degree lead (1/4 inch on paper) and then run beside the first, as drawn by hand (to
the side the cursor is on; a third wire takes the other side; the lead keeps its angle when the
symbol moves); it is off to start. A wire coming from farther out arrives along the lead's way;
one coming from beside the pin (a jumper from the pin just above it, S11 to S52) comes straight
out of its own pin, straight down onto the lead's corner and down the lead, never past the
corner and back; leaving such a pin to go back beside it does the same the other way. Drawing a second wire on a pin asks how it is numbered, as
a tap does: <b>Enter</b> as the project numbers taps (with -1, -2: the wire on the pin's
number -1), <b>S</b> the same number, <b>N</b> a number of its own; double-click it to change
it later (Wire number window, <b>Tapped off</b>). A <b>Bus</b> started or ended on pins that already have
wires does the same, each of its wires on its own lead, all bending the way the bus turns.
Several wires on a pin get no dot: the pin is the connection.</li>
<li><b>Junction dots</b>: a dot goes only where a wire taps off another: where <b>three or more
wire ends meet</b>, or where a wire <b>ends on another wire's middle or bend</b> (a T), so that
wires leave the point three or more ways. Two wires meeting end to end get no dot, straight or
turning a corner. A wire carried on from a free end of another
joins it into one wire, with no dot; carried on from a point that is already a bend, or where
two wires already meet end to end, it makes three: a dot (on the screen both look like the end
of one wire). <b>Delete dot</b> (DELDOT, DD; Modify menu, Schematic tab: Edit wires): click a
dot and it goes from the drawing, the print and the PDF; the wires still join there. Click the
same spot again (or Undo) to bring it back; keep clicking, Enter ends. It is kept with the
sheet.</li>
<li><b>Moving a symbol drags its wires</b>: the wire ends on its pins come along (Move, Rotate,
Mirror, Scale, dragging it or its grip), staying straight across and up or down (a jog is added
where needed), on every pin, two pins with the same name too (a drive's two GND). Select the
wires too and they move with it instead.</li>
<li><b>Placing a symbol on a wire</b> cuts the wire between the symbol's pins, as AutoCAD
Electrical does: drop a contact onto a rung and it is wired in. The same goes for a symbol
copied (Copy), moved (Move) or pasted (Ctrl+V) onto a wire: the wire is cut between its pins and
lands on both of them, in the same step (Undo puts the wire back whole).</li>
<li><b>Scoot</b> (SCOOT, AESCOOT; Modify menu, Schematic tab): select devices (a motor, a
drive, a contact...), a base point, then where to. They move <b>with everything attached to
them</b>: the symbols wired to them, and theirs (a motor brings its drive and its contactor;
the drive brings the motor), and the wires between, straight across or up and down, whichever
way the mouse goes more. Where the branch meets a bus (its drops tapping the bus's wires), the
drops slide along the bus when you scoot along it, and stretch or shorten when you scoot
toward or away from it; the bus and the other branches stay. Type <b>O</b> (Only these) to
slide just the selected devices along their own wire, as AutoCAD Electrical's Scoot does,
across a rung or up and down a vertical wire, however you move the mouse: the wires on their
pins stretch on one side and shorten on the other, staying straight, and they stop short of a
wire's far end or corner (<b>A</b> goes back to everything attached). A scoot that would
pull a wire off a pin is refused and says why: a wire running uncut through a pin of what
moves, across the way it goes, or a wire of the branch running on through a pin of a device
that stays (cut it at that pin first with Trim wire, or select that device too).</li>
<li><b>Align devices</b> (AEALIGN; Modify menu, Schematic tab), as AutoCAD Electrical's
Align: click the device to line up with, then the devices to line up, and press Enter. Each
slides along its own wire (as Scoot) into line: the same column on rungs across, the same row
on wires up and down. One that would leave its wire stops where its wire ends (the command
line says so).</li>
<li>Wires are ordinary objects otherwise: grips stretch their corners (an end dropped less than
0.01" from a pin or another wire is put on it), Trim and Erase work on
them (trimmed pieces stay wires), and they print and export (DXF) as polylines.</li>
</ul>

<h3>Editing wires</h3>
<p>The Schematic tab's <b>Edit wires</b> group (also on the Modify menu):</p>
<ul>
<li><b>Trim wire</b> (TRIMWIRE, AETRIM, TW), as AutoCAD Electrical's: click a piece of wire
and it goes, up to the nearest wire, pin or bend on either side (to the wire's end when there
is none): on a wire that turns a corner, only the straight run you clicked goes, up to the
corner. No cutting edges to pick, and only wires are trimmed, even where a symbol's line is
nearer. Keep clicking; U takes back the last one, Enter ends.</li>
<li><b>Delete wire</b> (DELWIRE, DW): with objects selected, only the wires among them go
(window-select a whole area and the symbols stay); with nothing selected, click wires one by
one.</li>
<li><b>Delete component</b> (DELCOMP, AEERASECOMP; Schematic tab, Symbols group, and the
Modify menu): the selected symbols go (anything else selected stays), or click them one by
one, and the wire each one sat on is <b>joined back up</b> through where it was: delete a
contact from a rung and the rung is whole again, with its wire number; a 3-pole breaker
leaves its three wires whole. Wires are joined only where two pins face each other in line,
each with one wire carrying straight on. <b>Erase</b> (the Delete key) still just erases,
leaving the gap.</li>
<li><b>Clean up wires</b> (WIRECLEAN): cleans the selected wires, or every wire on the sheet
when none is selected, in one step (Undo puts it back): wires of no length and extra points
(repeated, or in the middle of a straight run) go, a wire drawn over another goes, and two
wires meeting end to end with nothing else there (no pin, no third wire) become one. A wire
ending on another wire's corner and carrying straight on from it (a column of drives fed one
after another, each drop drawn on from the corner of the one before) cuts that wire at the
corner, so its leg turning off to the device is a tap of the run with a number of its own
(9005-1, 9005-2...); Wire does this as you draw, and Clean up wires does it for a drawing made
before version 0.19.11. The device where the run ends keeps the run's number. The
command line then says what it did and how many wire ends connect to nothing, which is
usually a wire stopping short of where it should go. A wire that runs straight back over
itself at an end (drawn out past where it was needed and clicked back) loses the doubled piece,
so it is one straight wire again. <b>Wire</b> and <b>Bus</b> don't take such a click: the command
line says so, and you click on past it or off to the side, U takes the last point back, or
Enter ends the wire there.</li>
<li><b>Cleanup as you draw</b>: a wire drawn exactly where one already runs isn't added twice,
and a wire drawn on from another wire's free end joins it, so it is one wire. Trim wire and
Delete wire join the wires they leave meeting end to end. Turn it off with <b>Clean up wires
as they're drawn</b> (Project properties, Schematic).</li>
</ul>

<h3>Three-phase power, terminals and PLC I/O</h3>
<ul>
<li><b>Three-pole symbols</b> (breaker, disconnect, fuses, contactor power contacts, overload
heaters) have their poles 1/2 inch apart, top to bottom L1/T1, L2/T2, L3/T3, the spacing
<b>Bus</b> starts with: draw a 3-wire bus, then drop the breaker on it, and each pole cuts
its wire. The motor and the drive (VFD: L1-L3 in, T1-T3 out) line up the same way; the drive has a
ground on each side, PE1 under L1-L3 and PE2 under T1-T3 (3/4 inch below L3 and T3, so a bus
still lands on the three phases).</li>
<li><b>Contactor power contacts</b> belong to the contactor's coil like any contact (M601)
and list under it.</li>
<li>Two devices in one symbol, as they're bought and wired: the <b>Fused disconnect 3-pole</b>
(the disconnect and its fuses: tag DS, the fuse rating in each fuse) and the <b>Starter
3-pole</b> (the contactor's power contacts and its overload heaters: a contact of its
<b>Contactor coil</b>, so it shows the coil's tag, M601, and lists under it; the heaters'
rating under them). Each is 1 inch long, L1-L3 in on the left and T1-T3 out on the right,
and lines up with the other three-pole symbols. The <b>Overload contact NC</b> in the coil's
rung belongs to the same coil.</li>
<li><b>Drive control terminals</b> (JIC/Power): a small AC drive's control terminals in one
column, 1/4 inch apart, wires landing on the left: S1, S2, S+ (safety), 01-08 (stop and
digital inputs), 11-19 (+24V, +10V, analog in and out, opto outputs), R1, R2, R5, R6 (relays)
and C1, C2 (comms), each number in its box and what it is beside it. It is a contact of its
<b>Variable frequency drive</b>: placed, it asks which drive (as a contact asks for its coil),
shows the drive's tag (VFD101) and is listed under it. A drive with other terminals: Edit block
and change the texts and pins, then save it under a name of your own.</li>
<li><b>Terminals</b> belong to a <b>Terminal strip</b> (place the strip first, anywhere: it
takes a tag, TB601). Placing a terminal asks which strip, as a contact asks for its coil; it
shows the strip's tag and numbers itself on the strip: 1, 2, 3... (the lowest free number;
a copy takes the next one). Double-click a terminal to type its number instead. The strip
lists where its terminals are.</li>
<li><b>PLC input</b> and <b>PLC output</b> points belong to a <b>PLC I/O card</b> the same
way, and list under it; double-click a point to type its <b>address</b> (I:0/3, %I0.3...),
shown under it.</li>
<li><b>PLC I/O modules</b>, drawn whole (Library, JIC/PLC): a box with the module's catalog
number at the top and its terminals down one side, one a rung (1/2" apart), each a pin
with its terminal number and what it is (<b>0  IN 0</b>); each point keeps its own wire
number. An input module's terminals are on its left, where its field devices' wires come in;
an output module's (1734-OB8, OB8E, OE4C and the generic output modules: sourcing) on its
right, so it sits on the left of the sheet with its loads to its right. Its tag goes above (PLC prefix: PLC601), and its
<b>SLOT</b> (double-click it, type 3) over the catalog number. Rockwell POINT I/O, as their
wiring diagrams give: <b>1734-IB8</b> (inputs 0-7), <b>1734-OB8</b> and <b>1734-OB8E</b>
(outputs 0-7), <b>1734-IE8C</b> (current inputs 0-7), <b>1734-OE4C</b> (outputs 0-3, C on 4
and 5, V on 6 and 7), and the <b>1734-VTM</b> and <b>1734-CTM</b> that bring V and C to the
IB8 and OB8 (all eight terminals V, or C). For any other make, <b>PLC digital input</b>,
<b>digital output</b>, <b>analog input</b> and <b>analog output module</b> of 4, 8 or 16
points: <b>Edit block...</b> renames their terminals to match the module, and Save block as
keeps it in your library under its own name. Each carries its manufacturer and catalog
number, so the Bill of materials lists it; PLC input and output points can belong to it as to
a PLC I/O card. To put the terminals on the right, Mirror it.</li>
<li><b>Import I/O list...</b> (Sheets menu) brings in an I/O list as its modules: a CSV file or
an Excel workbook (its first sheet) whose first row names the columns, in any order:
<b>Slot</b> (or Rack), <b>Catalog</b> (or Catalog number, Module, Part), <b>Point</b> (or
Channel), <b>Address</b>, <b>Tag</b> and <b>Description</b>. The rows of one slot are one
module, the library's symbol of that catalog number (1734-IB8...) or a generic module by its
name; each goes on a sheet of its own ("Slot 2 - 1734-IB8") after the sheet shown, its slot
shown, its tag of that page, and each point's address, tag and description written beside its
terminal, where the field wire comes in (layer PLC I/O): an input module a third of the way
across with the texts to its left, an output module at the left of the sheet with the texts to
its right. Each point's address is also kept on the module (attributes ADDR0, ADDR1..., not
shown), for <b>Number wires on PLC I/O points by their address</b>. A module the library
hasn't got, or a point a module hasn't got, is left out and named on the command line. One
Undo takes it all back.</li>
<li><b>Two terminals a channel</b>: <b>PLC analog input module, 4, 8 or 16 channels IN/RTN</b>,
each channel's input above its return, numbered as a 1756-IF16 is drawn (IN-0 on terminal 2,
RTN-0 on 1, IN-1 on 4...).</li>
<li><b>A module over two sheets</b> ("SLOT 7 CONTINUED"): place <b>PLC ... module, 16
points, points 0-7</b> (or <b>16 channels IN/RTN, channels 0-7</b>) on the first sheet, with
its tag and slot, and <b>PLC ... module, points 8-15 continued</b> (or <b>channels 8-15
IN/RTN continued</b>) on the next: it asks which module it belongs to (type its tag, L lists
them, P picks it on the drawing), shows that module's tag and CONTINUED at the top, and
follows it when the module is renumbered or retagged.</li>
</ul>

<h2>Wire numbers</h2>
<p>Every wire gets its number by itself: the page number and three digits, <b>6001</b>, 6002...
on page 6. The number shows above the wire (beside it when it runs up and down), on its
longest straight piece, in the middle of the longest stretch clear of crossings and
junctions, <b>where it is out of the way</b>: when another wire, a symbol or its texts, or
another number is there, it moves along the wire, or to the other side of it, to the first
spot where it touches nothing. With no room beside the wire anywhere, it is set off to the
side with a <b>short line</b> back to the wire (drawn, printed and exported with it). A
number you put with Wire number label stays where you put it. A wire longer than 6 inches on paper shows it near <b>both ends</b> instead (Project
properties, Schematic: <b>Number near both ends of wires longer than</b>; Off for one).</p>
<ul>
<li><b>One number per connected wire</b>: wires joined end to end share it. A symbol's pins
don't join wires, so the number changes through a device or a terminal.</li>
<li><b>Taps</b> (a wire whose end is on the middle of another, with a dot: a drop off a bus) are
numbered as Project properties, Schematic, <b>Wires tapped off a wire are numbered</b> says:
<ul>
<li><b>The wire's number with -1, -2, -3</b> (new projects): the drops off bus wire 2007 are
2007-1, 2007-2, 2007-3 in the sheet's numbering order, those off 2008 are 2008-1, 2008-2...,
and a tap off a tap takes a letter, 2007-1a, 2007-1b. The wires past the device a drop lands
on are numbered as usual. Adding or removing a drop renumbers the others on that wire
(unless their numbers are locked). <b>Tap numbers end in</b>, just under it, picks how:
<b>-1, -2, -3</b> (2007-1), <b>a, b, c</b> (2007a) or <b>-a, -b, -c</b> (2007-a). A tap off a
tap takes the other kind, without a dash: 2007-1a, 2007a1, 2007-a1, and one off that the first
kind again (2007-1a1). Letters are lowercase, so a tap is never taken for a distribution
block outlet's 2007A; after z come aa, ab... A sheet can choose otherwise (Sheet properties,
<b>Tap numbers end in</b>), and so can a tap (double-click it: the Wire number window's <b>Tap
number ends in</b>; the choice goes with the whole wire, and copies, cuts and trims keep it).
The tap's own choice comes first, then its sheet's, then the project's. Changing any of them
renumbers the taps it touches (Undo puts them back).</li>
<li><b>The same number as the wire</b> (projects from before 0.18.3 keep this one): a tap is
one wire with the wire it taps.</li>
<li><b>A number of its own</b>: each tap takes the next free number of its page.</li>
</ul>
A drop is a tap too where a bus wire ends at it and another wire carries straight on from there
(the bus going on to another row). A wire that ends on another's bend and carries straight on
along it is the same wire, not a tap: to number a drop drawn as one wire with the run that goes
on, draw the drop as a wire of its own.
Changing it renumbers the taps in one step (Undo puts them back). A number you typed stays.
A tap you set by itself (<b>N</b>, <b>S</b>, or the Wire number window's <b>Tapped off</b>)
keeps its own choice whatever the project says; <b>Apply to taps set one by one too</b> under
the setting (it ticks itself when you change the setting) makes them follow the project
again.</li>
<li><b>Tapping off a wire</b>: draw a wire from (or to) the middle of another and the command line
asks: <b>Enter</b> numbers the tap as the project says, <b>S</b> gives it the same number as that
wire whatever the project says (a branch of a ladder rung, say: a seal-in contact), <b>N</b>
gives it a number of its own (it stays connected, with its dot; only the numbers differ).
Double-click the tap to change it later: <b>Tapped off</b> has the same three choices.</li>
<li><b>Wire number label</b> (WIRELABEL, WL; Modify menu, Schematic tab: Edit wires): click a
wire anywhere along it and its number shows there too, as many places as you like. It always
shows the wire's number as it is now, never a copy typed in, so renumbering changes every one.
It goes with the wire: moved, copied, joined, cut (each piece keeps the labels on it), undone
and saved with it. Type <b>R</b> then click near one to take it off; <b>U</b> undoes the
last.</li>
<li>Numbers are given in the sheet's <b>numbering order</b> (Sheet properties: across then down,
or down then across) and then <b>kept</b>: drawing more doesn't renumber what's there. A new
wire takes the lowest free number of its page, so a deleted number comes back.</li>
<li>When two wires are joined, the lower number stays; when one is cut in two (a symbol placed
on it, Trim), the part later in order takes a new number.</li>
<li><b>Double-click a wire</b> to type its number (for it and every wire joined to it).
<b>Lock this number</b> ticks itself when you type one: numbering leaves a locked number alone.
Untick it to keep the number for now but let numbering change it (Renumber sheet, a new page
number, or a number that isn't of its sheet's page). Clear the number to let numbering give one
back. For a tap, the same window has <b>Tapped off</b>: as the project numbers taps, the same
number as the wire it taps, or a number of its own.</li>
<li>Typing a number another wire already has asks whether this is a <b>cross-reference</b>:
<b>Source</b> (this wire goes on to that one) or <b>Destination</b> (it comes from there) puts a
pair of arrows with a new name on the open end of each wire (the end on nothing): a <b>Source
arrow</b> pointing out where the wire leaves and a <b>Destination arrow</b> pointing in where it
arrives. They are then one wire with that number, and each shows
the other's place under it (7-A2). One step: Undo takes it all back. <b>No: just the same
number</b> gives this wire the number as typed, without connectors, and locks it (numbering
would give an unlocked one a free number again), and that number is then kept on purpose: it
isn't marked as a duplicate. A wire with no open end
(both ends on pins or wires) says so: draw it out to where it leaves the sheet first.</li>
<li><b>Duplicates are marked.</b> A device tag two devices have, or a wire number two wires
that aren't joined have, anywhere in the project, gets a <b>red frame</b> round it on the
drawing, on every sheet it is on, until you fix it (on the screen only: it doesn't print). When
one appears (a tag typed, something pasted, a number locked), the command line says which and
on what sheets. Not duplicates: a contact or footprint showing its device's tag, wires joined
by off-sheet connectors or source and destination arrows (one wire), and a number kept with
"No: just the same number".</li>
<li>When a sheet's page number changes, its unlocked wire numbers follow (6001 becomes 7001),
as device tags do.</li>
<li><b>Renumber sheet</b> also numbers the sheet's unlocked wires again, 001, 002... in
order.</li>
<li><b>Distribution block</b> (Library, JIC/Wiring): the wires on its outputs take the number
of the wire on its input with A, B, C... added (6001A, 6001B; after Z come AA, AB...).</li>
<li><b>Power distribution block</b> (Library, JIC/Wiring: <b>Distribution block 3-pole</b> and
<b>Distribution block outlet 3-pole</b>): the block, tagged PDB101..., takes the three phases
on its L1, L2 and L3, where the feeder ends; type how many outlets it has a phase in its
<b>OUTLETS</b> attribute as on its part (1:18, or 18), shown under it. Each outlet belongs to a
block (placing one asks which, as a contact asks for its coil) and numbers itself on it:
<b>PDB101-1</b>, <b>PDB101-2</b>..., on any sheet, with a cross-reference to where its block
is. The wires on an outlet's T1, T2 and T3 take their phase's number with the outlet's letter:
outlet 1's are 6001A, 6002A, 6003A, outlet 2's 6001B... (each phase keeps its own number).
More outlets than OUTLETS says are marked red and named on the command line. Placed on a bus
whose phases are spaced other than 1/2" (its L1 clicked on the top wire), the block or outlet
is drawn to fit them, as "Distribution block 3-pole (0.75" poles)".</li>
<li><b>Off-sheet connector</b> (Library, JIC/Wiring): place one where a wire leaves the sheet
and one where it comes back on another sheet, with the same name. Placing one asks its name:
Enter takes the one offered (a connector still waiting for its other end, else the next free
letter). The wire keeps the number of the sheet it starts on, and beside each connector its
other end's place shows (<b>7-A2</b>), outside the connector on the side away from its wire,
whichever way the connector is turned. <b>Source arrow</b> and <b>Destination arrow</b>
(Library, JIC/Wiring) are the same, drawn as arrows on the wire's end: a source arrow points
away from the line where the wire leaves, a destination arrow's tip is on the line, pointing
into it, where the wire arrives. Past each arrow's far end (not over the wire), the wire's
number and the other arrow's place (<b>2046 / 7-A2</b>), turned the way the arrow is: on a wire
running up and down it reads up, in line with the wire (as that wire's number reads); across,
it is level. A source arrow placed on the end of a numbered wire is named by the wire's number (2046):
nothing to type (unless another source arrow has that name: then it asks). It keeps following
it: when the wire is renumbered (a number typed, Renumber sheet, Update numbers), the source
arrow takes the new number and its destination arrows follow their source. A wire carried on by
arrows is numbered where its source is (page 6: 6012), whatever sheets its destinations are
on. A number locked on a destination's wire before an arrow joined it to the source (typed
there earlier) doesn't take the source's wire over: the source keeps a number of its own page and
the destination follows; a number typed on either side once they are joined numbers the whole
wire. A name another pair already goes by is left alone, so two pairs never join. A destination arrow
offers the name of a source still waiting for it (or <b>List...</b> on the command line picks the one it continues from a list of them, wire number and place, waiting ones first; <b>Pick on drawing</b> lets you go to its sheet and click it, and comes back; a destination paired either way is <b>linked</b> to that source arrow: it shows that one whatever the order of the others, and follows it when its wire is renumbered, until that source arrow is deleted. Double-click a destination arrow to change it: <b>Comes from</b> lists every source arrow, or <b>Automatic</b> pairs it by order); placed, its wire takes the source's number
and its layer (480V BRN, with its color and gauge). Each arrow shows only its other half's
place: a destination its source, a source its destination. A wire carried on over several
sheets (page 4 to 5 to 6, a destination and a source on page 5) shows only the next or the
previous hop: page 4's source shows page 5, page 6's destination shows page 5's source. A
source carried to two sheets with no hop between them shows both. Hops on one sheet work the
same way: a ladder's rail with a destination at its head and a source at its foot is one run,
in the order the runs start across the sheet, so the left ladder's foot feeds the right ladder's
head and the right ladder's foot goes on to the next sheet. A source with nothing after it yet
shows <b>?</b>. On a second line under it,
the device the wire goes straight to at the other arrow (<b>VFD201</b>), so you see where the
wire goes and to what without turning to that page. Terminals on the way are passed through to
the device past them; a terminal with nothing past it, or a T past it, shows itself
(<b>TB1-12</b>). It
is set at three levels, each overriding the one before: <b>Source and destination arrows show
the device at the other end</b> (Project properties, Schematic; on to start), <b>Arrows show
the far device</b> in Sheet properties (<b>As the project</b>, <b>Shown</b> or <b>Off</b>, for
that sheet), and <b>Show the far device</b> in an arrow's attributes (double-click it:
<b>As the sheet</b>, <b>Shown</b> or <b>Off</b>, for that arrow alone). Nothing shows when that
wire lands on nothing there, tees off to more than one device, or carries on to another
arrow.</li>
<li><b>Source/destination arrows</b> (SIGARROW, SDA; Draw menu, Schematic tab:
Cross-references), as AutoCAD Electrical's signal arrows: click near the open end of the wire
where it leaves (an end on nothing: a Source arrow goes there), then near the open end where it
arrives, on this sheet or another (go to it in the Sheets panel: the command waits), and a
Destination arrow goes there. They get a new name, the two wires become one wire with the
source's number and the destination's wire takes the source wire's layer, and each arrow shows
that number and the other's place. It goes on with the
next pair; Enter or Esc ends it. An end connected to something, or the same wire twice, is
refused with a message.</li>
<li>Project properties, Schematic: <b>Number wires</b> (on to start) and the height of wire
numbers and cross-references.</li>
<li><b>Number wires on PLC I/O points by their address</b> (Project properties, Schematic, or
Schematic settings...; off to start): a wire on a PLC module's input or output point (a
terminal marked <b>IN n</b>, <b>OUT n</b> or <b>IN-n</b>; not V, C, RTN or other power and
common terminals) is numbered by that point's address, as if typed: the whole wire, up to
the devices it lands on. The address is the one <b>Import I/O list...</b> brought in for the
point, as the list writes it (Local:3:O.Data.0); otherwise it is made from the module's
<b>SLOT</b> and the point: <b>O:3/0</b> for output 0 of slot 3, <b>I:2/7</b> for input 7 of
slot 2 (a continued piece uses its module's SLOT). A <b>PLC input</b> or <b>PLC output</b>
point's wire takes the point's <b>address</b> (ADDR). A module with no SLOT and no address
kept leaves its wires numbered as usual, and a locked number (typed by hand) stays. A wire on
two points takes the first of their addresses in order. Two separate wires on one address
(two modules both slot 3) both take it and are marked as duplicates, never joined. Changing
the setting, a SLOT or an address renumbers them with that change; turned off, they take
page numbers again.</li>
<li>Wire numbers go into PDF and DXF exports as text.</li>
</ul>

<h2>Wire list and terminal strip list</h2>
<p><b>Wire list...</b> (Sheets menu, Output tab: Reports) lists every numbered wire in number
order: its size and color (its layer's, or its own), what it lands on, each with where
(<b>CR1:A1 (6-B3), TB1-4 (6-C1)</b>: terminals by strip and number, anything else by tag and
pin), and the sheets it is on. Off-sheet connectors and source and destination arrows carry a
wire on, so they are not landings. <b>Terminal strip list...</b> lists every terminal, strip
by strip in number order, with the wire numbers on its left and right pins and where it is.
<b>Terminal count...</b> (the same places; on the ribbon, the Terminals button's menu) says
how many terminals and jumpers the tapped wires need: every wire number tapped off (6001 with
6001-1, 6001-2... and a tap off a tap, 6001-1a), its taps, and one terminal for the number and
one for each tap, bridged by one jumper fewer than terminals (6001 tapped three times: 4
terminals, 3 jumpers), with the sheets they are on and the totals at the bottom. It counts one
wire on each terminal side, the most you can need: multi-level terminals, or two wires on a
side, need fewer. It counts taps numbered -1, -2..., a, b... or -a, -b... (or with numbers of
their own: Project properties, Schematic, <b>Wires tapped off a wire are numbered</b>); taps
that keep the wire's number aren't told apart, and it says so. All three are worked out from the drawing each time they open; <b>Save as CSV or Excel...</b>
writes them for a label printer (CSV) or as an Excel workbook (pick "Excel workbook" as the
file's type: its header bold and kept in sight, columns wide enough, counts as numbers).</p>
<p><b>Report sheet...</b> (Sheets menu) draws a report on sheets of the project, so it prints
and goes into the PDF with the drawings: pick the bill of materials, wire list, terminal strip
list, pull list or panel materials, and it comes in as a table (lines and texts on layer
REPORT) on report sheets just after the sheet shown, as many as it takes ("Bill of materials (1
of 3)"), in the room the border and title block leave; a cell too long for its column ends in
"…". A report sheet isn't kept up to date as you draw (that would slow every change on a big
project): <b>Update report sheets</b> (Sheets menu) draws every report sheet again from the
drawing as it is, and picking a report that has sheets already draws it again there. One Undo
each.</p>

<h2>Cables between panels</h2>
<p><b>Cables between locations...</b> (Sheets menu, Output tab: Reports) lists what has to be
pulled between panels and boxes, and where every wire lands on both sides: the pull list.</p>
<ul>
<li>Give each sheet its <b>location</b> in Sheet properties: MCP, JB-1, FIELD (any name). A
device that isn't where its sheet is (a pushbutton in the field drawn on the panel's sheet)
gets its own: double-click it, <b>Location</b>. Its own wins; leave it empty for its sheet's.</li>
<li>A wire number that lands on devices in two or more locations is a conductor to pull.
Wires joined by off-sheet connectors are one wire (one number), so a wire that goes from the
MCP's sheet to the junction box's sheet is listed once. A terminal's two sides are two wires:
the field wire lands on one side, the panel wiring on the other.</li>
<li>The conductors are grouped by the locations they run between (<b>MCP &#8596; JB-1</b>), in
wire number order. For each location: the terminal it lands on (<b>TB1-12</b>: the strip's tag
and the terminal's number); where it lands on no terminal there, the devices' pins
(<b>CR1:A1</b>). A terminal not on a strip yet shows TB?.</li>
<li>For each run you can type the <b>cable</b> (W101) and its <b>type</b> (12C #14 TC, or loose
#14 THHN in 1" conduit), and choose how its conductors are marked: <b>Numbered</b> (black,
with the wire number on them: shown as BLK, #6001) or <b>Color coded</b>. Type any conductor's
color or marking in its line (RED, WHT/BLK...); clear it to go back to the default. OK keeps
it with the project in one step (Edit, Undo takes it back); Cancel keeps nothing.</li>
<li><b>Save as CSV or Excel...</b>: a line per conductor (from, to, cable, type, wire, color or
marking, where it lands on each side) for a spreadsheet. <b>Save as PDF...</b>: a page per
run, with empty <b>Pulled</b> and <b>Landed</b> columns to tick off on the job.</li>
<li>Lengths are not part of it: they are worked out on the job. A wire landing in one
location and on a sheet or device with no location isn't listed; the window says how many
there are.</li>
</ul>

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
width,height, toward the mouse; D: length and width, then the side).</td></tr>
<tr><td>Circle: Center, radius</td><td>CIRCLE, C</td><td>Center, then radius (a point or a
number); D switches to a diameter. At the first prompt, 3P, 2P or TTR switch to those ways.</td></tr>
<tr><td>Circle: Center, diameter</td><td></td><td>Center, then diameter.</td></tr>
<tr><td>Circle: 2-Point</td><td>C, then 2P</td><td>The two ends of a diameter.</td></tr>
<tr><td>Circle: 3-Point</td><td>C, then 3P</td><td>Three points on the circle.</td></tr>
<tr><td>Circle: Tan, tan, radius</td><td>C, then TTR</td><td>Pick two lines, polylines, circles or
arcs near where the circle should touch them, then type its radius (Enter: the last one): of
the circles that fit, you get the one touching nearest your picks.</td></tr>
<tr><td>Arc (3 points)</td><td>ARC, A</td><td>Start, a point on the arc, end.</td></tr>
<tr><td>Text</td><td>TEXT, T, DT</td><td>Click where the text goes, then type each line and
press Enter; Enter on an empty line ends. One click only: unlike AutoCAD's TEXT, a second click
doesn't set the height. Before the click, type <b>H</b> for the height (inches on paper: 1/8
to start), <b>R</b> for the rotation (degrees), or <b>J</b> (Justify) for where the point sits
on the text, as in AutoCAD: TL, TC, TR (top), ML, MC, MR (middle), BL, BC, BR (bottom), or L,
C, R (on the baseline). All three are kept for the next texts.
<b>Double-click a text</b> to change its wording where it is: an edit box opens over it,
Enter keeps what you typed (one Undo), Esc leaves it as it was, and clicking elsewhere keeps it
too. Just above the box, <b>Left</b>, <b>Center</b> and <b>Right</b> justify it (kept with
what you typed, the same Undo; a multi-line note keeps its top, middle or bottom), and
<b>More...</b> keeps what you typed and opens its window. Right-click it and pick <b>Text
properties...</b> (or More...) for its wording, height, angle and
justification (a new justification moves the text around its insertion point; tick "Keep the
text where it is", unticked to start, to move only the insertion point instead, which is where
it snaps and turns around).</td></tr>
<tr><td>Multiline text</td><td>MTEXT, MT, NOTE</td><td>One text of several lines (a note): click a
corner of its box, then the opposite corner (its lines wrap at the box's width), or press
Enter after the first corner for no wrapping; type the text in the box that opens (Enter starts
a new line) and click OK. Before the first click, <b>H</b> sets its height (paper inches). It
is one object: it moves and copies whole. <b>Double-click</b> it to change its text where it
is (Enter starts a new line there, <b>Ctrl+Enter</b> keeps it, Esc drops it); right-click
<b>Text properties...</b> changes its text, height, wrap width and the point it hangs from (top
left ... bottom right). A DXF's or DWG's MTEXT
comes in as one, and DXF export writes it as MTEXT.</td></tr>
<tr><td>Move</td><td>MOVE, M</td><td>Select, base point, second point.</td></tr>
<tr><td>Copy objects</td><td>COPY, CO, CP</td><td>Select, base point, then as many copies as
you place (Enter ends).</td></tr>
<tr><td>Rotate</td><td>ROTATE, RO</td><td>Select, base point, angle (a point or degrees).</td></tr>
<tr><td>Scale</td><td>SCALE, SC</td><td>Select, base point, factor. Or <b>Reference</b> (R): pick
two points of a length as drawn (or type it), then type the length it should be: this brings a
manufacturer's drawing to its real size. Lengths can be typed in millimeters:
<code>45mm</code>. On a panel sheet, footprints are left out (they're real size).</td></tr>
<tr><td>Mirror</td><td>MIRROR, MI</td><td>Select, two points of the mirror line, keep or erase
the originals (the mirrored objects show while it asks). Text stays readable.</td></tr>
<tr><td>Stretch</td><td>STRETCH, S</td><td>Drag a crossing window over the ends to move (the
three ends of a bus, say), then a base point and where it goes. Wire ends in the window move
and their wires stay square (a corner slides along, or a jog is added); a line's ends and a
polyline's corners in it move; an object wholly in it, and a symbol, text or circle whose
insertion point or center is in it, moves whole (wires on a symbol's pins follow). A wire
end it leaves less than 0.01" from a pin or another wire is put on it. One step.
</td></tr>
<tr><td>Array</td><td>ARRAY, AR</td><td>Copies of the selected objects in rows and columns
(R, to start: how many rows, how many columns, the distance between rows (up; negative: down)
and between columns (across; negative: left)) or round a center (P: the center, how many in
all, the angle they fill: Enter for 360; each copy turned with it). Copied devices get tags of
their own, as with Copy; one Undo takes the whole array back. The copies stay an array, kept
with the sheet: Edit array changes it later.</td></tr>
<tr><td>Edit array</td><td>ARRAYEDIT, AE</td><td>Select any object of an array made with Array
(Modify menu, Home tab), then type its numbers again, each offered as it is (Enter keeps it):
rows, columns and the distances between them, or how many round its center and the angle they
fill. Copies still the array's move to their new places and keep their tags, new ones get tags
of their own, those past the new count are erased (a wire drawn to one stays where it is,
unconnected). A copy you moved, turned or changed on its own has left the array and stays as
it is. <b>U</b> (Unlink) at the first question ends the array: its copies stay, objects of their
own. One Undo each.</td></tr>
<tr><td>Offset</td><td>OFFSET, O</td><td>A copy of a line, polyline or rectangle, circle or
arc, a set distance away: smaller or bigger, on the side you click. Type the distance (Enter:
the last one), pick the object, click the side; it goes on with the same distance until
Enter. <b>T</b> (Through) instead of a distance: the copy passes through the point you click.
A shape offset inward past its middle is refused (it would turn inside out); wires aren't
offset (draw a bus).</td></tr>
<tr><td>Number texts</td><td>NUMBER, NUM, TCOUNT</td><td>Numbers the selected texts (single-
and multi-line) in order, as AutoCAD's TCOUNT: <b>1, 2, 3</b>; <b>A, B, C</b> (Z, then AA,
AB); <b>a, b, c</b>; or <b>A1, B2, C3</b> (the letter and the number together), from the start
you give (a number, or a letter), by the step (2: 1, 3, 5), with as many digits as you ask
(01, 02), a prefix before each (S: S1, S2, S3; TB1-: TB1-1...) and a suffix after. The
<b>order</b>: top to bottom, then the next column to the right; or left to right, then the
next row down (texts lined up on their insertion points make a column or a row, however long
each is). The number <b>replaces</b> the text, or goes in front of it or after it. The
window shows what it gives and remembers your choices; one Undo puts the texts back.</td></tr>
<tr><td>Erase</td><td>ERASE, E, or Delete</td><td>Removes the selected objects.</td></tr>
<tr><td>Trim</td><td>TRIM, TR</td><td>Click the part of an object to cut away: it is trimmed
back to the nearest crossing objects on either side (every object is a cutting edge, as in
AutoCAD's quick mode). An object nothing crosses is erased. As the cursor goes over an
object, only the piece a click there would cut away lights up. U undoes the last trim.</td></tr>
<tr><td>Zoom</td><td>ZOOM, Z</td><td>Extents (E), Sheet (S), In (I), Out (O).</td></tr>
<tr><td>Linear dimension</td><td>DIMLINEAR, DLI, DIM</td><td>Pick the two points to measure,
then where the dimension line goes: across or up and down, whichever way you pull it.</td></tr>
<tr><td>Aligned dimension</td><td>DIMALIGNED, DAL</td><td>The same, measured along the line
between the two points (slanted too).</td></tr>
<tr><td>Wire color label</td><td>WIRECOLOR, WCL</td><td>The selected (or clicked) wires show
their color in their gauge label, or stop (the other way from how they show it now).</td></tr>
<tr><td>Dimension units</td><td>DIMUNITS, DU</td><td>The selected (or clicked) dimensions:
D decimal, F fractional, or 1/8, 1/16, 1/32, 1/64.</td></tr>
<tr><td>Hatch</td><td>HATCH, H, BHATCH, BH, FILL</td><td>Click inside a closed shape to fill it
(SOLID, ANSI31, ANSI37, LINES pick the pattern; SP the spacing, AN the angle); Enter
ends.</td></tr>
<tr><td>Leader</td><td>LEADER, LE, LEAD, MLEADER, MLD, QLEADER, BALLOON</td><td>Pick the
arrow's point, then where the line bends, Enter; type the note, or B for a balloon (Enter takes
the next item number).</td></tr>
<tr><td>DIN rail</td><td>DINRAIL, RAIL, DR</td><td>Real-size DIN rail from its start to its end
(or type the length toward the cursor). Before the first click: <b>7.5</b> (TS35 x 7.5 mm, to
start), <b>15</b> (TS35 x 15 mm) or <b>MINI</b> (TS15).</td></tr>
<tr><td>Wire duct</td><td>DUCT, WIREWAY, WD, PANDUIT</td><td>Real-size wire duct, from a corner:
click one corner and then the other end of that edge (or type the length); the duct goes on the
side of that edge the cursor is on, F puts it on the other side. Before the first click, click a
standard size on the command line or type one, width x depth: <code>2x3</code> (inches) or
<code>50x75mm</code>.</td></tr>
</table>
<p>Typed <b>Undo</b> (U) and <b>Redo</b> work on the command line too.</p>

<p>On the Home tab, <b>Circle</b> has an arrow beside it listing all its ways; the button then
shows the way you used last, as in AutoCAD. The Draw menu has them under Circle.</p>

<h3>Typing points</h3>
<ul>
<li><code>3,4</code> - the point x=3, y=4 (inches from the sheet's lower left corner).</li>
<li><code>@1,0</code> - 1 inch right of the last point.</li>
<li><code>@2&lt;45</code> - 2 inches from the last point at 45 degrees.</li>
<li><code>#3,4</code> - the point x=3, y=4 wherever a plain x,y means something else (a box's
second corner, below).</li>
<li>A <b>Rectangle</b>'s or <b>Dashed box</b>'s second corner: <code>0.19,0.15</code> is its
<b>size</b> from the first corner, 0.19 across and 0.15 up or down, <b>the way the mouse
is</b> from the first corner (move it left and down, and the box goes left and down), as
AutoCAD's dynamic input takes it. A sign typed says which way whatever the mouse does
(<code>-2,-1</code> left and down, <code>+2,+1</code> right and up); <code>#x,y</code> is a
point. Rectangle's
<b>D</b> (Dimensions) asks the length, then the width, then a click on the side it goes
(Enter: up and right).</li>
<li><code>1.5</code> - 1.5 inches from the last point toward the cursor (direct distance;
with ORTHO on, straight across or up and down).</li>
</ul>

<h3>Drafting aids</h3>
<ul>
<li><b>Object snap</b> (F3, OSNAP), as AutoCAD's: near the cursor, points snap onto objects;
a yellow marker in AutoCAD's shape and the snap's name show which. The snaps:
<b>Endpoint</b> (END), <b>Midpoint</b> (MID), <b>Center</b> (CEN), <b>Geometric center</b>
(GCE: the middle of a closed polyline), <b>Node</b> (NOD: symbol pins, dimension points),
<b>Quadrant</b> (QUA), <b>Intersection</b> (INT: where two lines, arcs or edges cross, a
footprint's lines and the edges of wire duct and DIN rail included), <b>Insertion</b> (INS:
blocks and text),
<b>Perpendicular</b> (PER: square to a line, or on a circle in line with its center, from the
last point), <b>Tangent</b> (TAN: touching a circle or arc, from the last point) and
<b>Nearest</b> (NEA: the closest point on any object). And three that follow what the cursor
has hovered over, as AutoCAD's tracking (a small green cross marks what was picked up):
<b>Extension</b> (EXT: hover over a line's end, then move along the line past it: a dotted line
follows it out; and, as AutoCAD's object snap tracking, hover over a wire's end, a pin, an
intersection, a midpoint, a center or a quadrant and the points straight across and straight
up or down from it snap (to center text under a box, hover the middle of the box's edge, then
move straight down), first where
that line meets the one you are drawing: draw a wire across, hover over another wire's end
above, and the wire stops exactly under it; where such a line, or a line's extension, crosses
a line, a wire or a circle, that crossing snaps too), <b>Parallel</b> (PAR: hover over a line, then move roughly its way from the
last point: the new line runs parallel to it) and <b>Apparent intersection</b> (APP: hover
over two lines, then near where they would meet if they were longer; or a line and a circle or
arc, where the line extended would meet it; with <b>Ortho</b> on, the line straight across or
up and down from the last point counts too: hover over a circle, or a line, and the point
lands exactly where your Ortho line meets it or its extension). When several are in reach,
ends, intersections, insertion points and pins go first, then centers and quadrants, then
midpoints, then tracking, then Nearest; Perpendicular and Tangent go with centers only when
their point is close to the mouse (farther, Nearest under the mouse wins).</li>
<li><b>Blocks snap too</b>: the ends, middles, centers and quadrants of a placed symbol's or
footprint's own drawing (a footprint's corners, for a dimension), as in AutoCAD. A pin, or an
ordinary object's point of the same kind, comes first, so a wire still lands on a pin.</li>
<li><b>The border and title block snap too</b>: the border's corners, the zone strips' lines
and the title block's lines and texts (ends, middles, intersections, nearest...), so a
drawing lines up with them. They still can't be selected or changed on a sheet (Edit title
block to change the title block), and hiding a layer of the title block stops its snaps.</li>
<li><b>Turning snaps on and off</b>: the arrow on the status bar's <b>OSNAP</b> button lists
every snap with a check mark; click one to turn it on or off. The list stays open, so you
can tick several in a row (Select all and Clear all too); click outside it or press Esc when
done (Object snap settings... is there too). <b>Drafting settings...</b> has the same checkboxes. Endpoint,
Midpoint, Center, Node, Quadrant, Intersection and Insertion are on to start; the choice is
kept between sessions; F3 turns them all off and on at once.</li>
<li><b>A snap for one point</b>: at a point prompt, type its short name (PER, TAN, NEA,
END...) and Enter, or <b>Shift + right-click</b> and pick it from the list: the next point
uses that snap only, ticked or not, even with F3 off. NON gives the next point no snap.</li>
<li><b>Grid display</b> (F7, GRID): dots across the drawing area.</li>
<li><b>Ortho mode</b> (F8, ORTHO): lines straight across or up and down. The crosshair stays
on that line, and object snaps are looked for around it (not around where the mouse really
is), so an end or pin on the line snaps and one off to the side doesn't pull the line to
it. A dimension's points follow Ortho too, but an object snap right at the mouse (the
corner you are measuring to) still wins over the Ortho line.</li>
<li><b>Polar tracking</b> (F10, POLAR): near one of the set angles (from the last point), the
cursor locks onto that direction: a green dashed line and a tip show the distance and angle
(<i>Polar: 2.5 &lt; 45&deg;</i>). Typing a number then goes that far along it. The angles are
every 45 degrees to start; <b>Drafting settings...</b> chooses the step (90, 45, 30, 22.5, 18,
15, 10, 5 or your own) and extra angles of your own (for example 60, 120). Ortho and Polar
tracking can't be on together: turning one on turns the other off.</li>
<li><b>Snap to grid</b> (F9, SNAP): points snap to the snap spacing (1/8 inch to start); along a
polar direction, the distance snaps to it.</li>
<li><b>Drafting settings...</b>: snap spacing, grid spacing, the polar tracking
angles and the crosshair (all kept for next time).</li>
<li><b>Crosshair</b>: short, as in AutoCAD (each line 5% of the view to start). In Drafting
settings, <b>Crosshair size</b> makes it longer or shorter (1 to 100%), and <b>Full-screen
crosshair</b> runs its lines across the whole view.</li>
</ul>

<h2>Panel sheets and dimensions</h2>
<p>A panel layout is drawn at <b>real size</b>: a 3 inch contactor is 3 inches in the drawing,
on every sheet, forever. Each sheet has <b>one scale</b> that only sets how big it prints.</p>
<ul>
<li><b>Sheet scale...</b> (Panel tab) shows the sheet at its paper size with your drawing
inside at the scale you pick, says what the scale means in plain words ("1 inch on paper = 4
inches of panel") and how much of the room the drawing takes, in green when it fits, amber
when it fits but not where it is (tick <b>Move the drawing to the middle of the free
space</b>), red when it is too big (it names a scale that fits). Pick 1:1, 1:2, 1:3, 1:4, 1:5,
1:6, 1:8, 1:9, 1:10, 1:12, 1:16 or 1:20, or an architectural one (3" = 1'-0"...), or type one
(1:7).</li>
<li><b>Fit</b> picks the biggest of those scales (the architectural ones on a sheet that has
one) at which the drawing fits inside the border and clear of the title block; past 1:20, the
next whole 1:N that fits (1:23). It uses the same test as the status bar's <b>doesn't fit</b>,
and when it has to move the drawing, centers it with a little space kept around it if there is room for that.
It moves the drawing by whole inches (by 1/2", 1/4" or 1/8" when the room is tight), so a drawing
on the snap grid stays on it and new wires still meet the old ones; turning a sheet and opening a
DXF or DWG move it the same way.
It measures the drawing as it will be at each scale it tries: text, dimensions and tags keep
their size on paper, so they take more of the drawing at a smaller scale. With nothing drawn yet, give the <b>Cabinet size</b> (width, height and,
optionally, depth, in inches): Fit then makes room for the cabinet's front and, with a depth,
its side beside it, so you can draw the outside of the cabinet as well as the backplate. The
size is kept with the sheet, and the next panel sheet offers the one you used last.</li>
<li><b>Rotate sheet clockwise</b> (Ctrl+Shift+Plus) and <b>Rotate sheet counterclockwise</b>
(Ctrl+Shift+Minus), in the Sheets menu and on the Sheets tab, turn a sheet a quarter turn, for
a tall, narrow cabinet on a tall sheet. The border, the zones and the title block turn with it,
as if you turned the paper; the drawing stays upright and stays on the page (one undoable
step). Grid references follow the turned zones. Sheet properties and the Sheet scale window
set it too (<b>Rotation</b>: upright, turned clockwise, upside down, turned counterclockwise).
When a quarter turn would print the drawing (or the cabinet) bigger, the Sheet scale window
says so ("Turned tall it prints bigger: 1:4 instead of 1:5") with a <b>Turn it</b> button; Fit
never turns a sheet by itself. PDF pages print the sheet as turned.</li>
<li>Click <b>Scale 1:4</b> in the status bar for a short list: <b>Fit</b> (with the scale it
would pick), the common scales, and <b>More...</b> (the Sheet scale window). A sheet's scale
is also in Sheet properties.</li>
<li><b>The scale new sheets start at</b> is a project setting, one for each kind of sheet:
<b>New panel sheets' scale</b> (Project properties, Panel tab; Panel settings...) for panel
sheets, and <b>New sheets' scale</b> (Project properties, Schematic tab; Schematic settings...)
for schematic, report and other sheets. Both start at 1:1. A new sheet takes the one for its
kind (New sheet makes one of the kind of the sheet shown); after that its scale is its own:
Sheet scale..., the status bar or Sheet properties change it for that sheet alone. Changing the
project's setting changes no sheet already made. Changing a sheet's kind in Sheet properties
while nothing is drawn on it changes its scale to the project's for that kind (shown in the
Scale box before you press OK, so you can pick another); a sheet with a drawing on it keeps its
scale.</li>
<li>When the drawing runs past the border or over the title block at the sheet's scale, the
status bar says <b>doesn't fit</b> (in amber), and Export to PDF and Print ask before printing
it cut off, naming what doesn't fit (see Printing).</li>
<li>The border, zones and title block are drawn around the real-size drawing, enlarged by the
scale, so the sheet prints at its paper size (PDF) with the drawing at that scale. DXF
exports hold the real-size drawing with the border enlarged around it, as AutoCAD drawings
in model space do.</li>
<li>Text, multi-line text, tags, cross-references, wire numbers, leaders and dimension text
you make in KanzonasCAD are <b>paper-sized</b>: new text at 1/8 inch prints 1/8 inch high
whatever the scale. Changing a sheet's scale changes their heights with it (in one undoable
step). Text, dimensions and leaders that came with a DXF or DWG are <b>drawing-sized</b>: the
program that drew them sized them for the drawing, so they keep their size in it when the
scale changes. In Sheet scale..., untick <b>Text and dimensions keep their size on paper</b>
to change no text at all (for a drawing imported before version 0.15.2, whose text isn't
marked as drawing-sized).</li>
<li>Footprints aren't scaled by hand on a panel sheet (Scale leaves them out and says so):
bring a manufacturer's drawing to real size with Scale, Reference before it becomes a
footprint.</li>
<li><b>{{Scale}}</b> in the title block shows the sheet's scale (the ready-made title blocks
have a SCALE cell; Edit title block adds it to one of your own).</li>
<li><b>Align objects</b> (ALIGNOBJ, ALO; Modify menu; Panel tab: Arrange; Schematic tab:
Modify) lines up footprints, DIN rail, duct, symbols or anything else: select them, choose <b>Left</b>, <b>Center</b>, <b>Right</b>,
<b>Top</b>, <b>Middle</b> or <b>Bottom</b> (L, C, R, T, M, B), then click the one to line
them up with, or press Enter to line them up with the selection's own outer edge (or its
middle). Each moves only straight across (Left, Center, Right) or straight up and down (Top,
Middle, Bottom), by its outline, and wires on a moved symbol's pins follow, square; one Undo
puts them back.</li>
<li><b>Distribute objects</b> (DISTRIBUTE, DIST; Modify menu; Panel tab: Arrange; Schematic
tab: Modify) spreads three or more selected objects out evenly: <b>Horizontally</b> or <b>Vertically</b> (H, V). The two
outermost stay where they are and the others move straight across (or straight up and down)
so the gaps between them are equal. With Snap on, each move is rounded to the snap spacing, so
symbols' pins stay on the grid and wires still meet them (the gaps can then differ by up to
one snap step); wires on a moved symbol's pins follow. One Undo puts them back.</li>
<li><b>DIN rail</b> and <b>Wire duct</b> (Draw menu, Panel tab) are drawn at real size from
one end to the other (a rail along its middle, a duct along one edge, from a corner): the rail's outline, lips and mounting slots; the duct's outline, its finger slots
along both edges (one every half inch) and its mounting holes along the middle (every 3
inches). <b>Wire duct drawn with a light hatch</b> (Panel settings) adds light diagonal lines
across every duct, as a mask; new ducts take it too. They always go straight across or straight up and down (a snap off that line only sets
the length), and their end grips stretch them along their own line. Stretch one
with its end grips (or double-click it and type its length), move it with its middle grip. A duct's depth isn't drawn (it's a view from the front) but is part of its
size: it goes on the materials list and the bill of materials. Double-click a piece for its
properties: a rail's profile; a duct's <b>Width</b> and <b>Depth</b> (or a <b>Standard size</b>
that fills both); its length, manufacturer, catalog number and the length it is bought in
(the project's to start: Project properties, Panel; 1 m rail and 6 ft duct). With other rails
(or ducts) selected too, <b>Also the other selected...</b> gives them all the same size and part
in one step, each keeping its own length.</li>
<li><b>Footprint label</b> (Modify menu, the Panel tab's Footprints group, or a right-click
with footprints selected): what the selected footprints show written on them. <b>Show tag</b>
(M1, CR3), <b>Show part number</b> (its catalog number; the block's own when the copy has
none), <b>Show description</b> and <b>Show block name</b> each turn that line on, and picked
again, off: a footprint can show several at once, one under the other (a tick shows what
every selected footprint shows). <b>No label</b> takes them all off. A footprint you place
shows its tag to start (one with no tag, its part number or block name): Project properties,
Panel, <b>New footprints show</b> picks another. Select one or many, pick one: one step, Undo
takes it back. Double-click a footprint for the rest: <b>Shown on it</b> lists everything it
can show, its device's ratings too (see below). The lines are centered on the part (or at its
block's label spot, set in Edit block), turned up the page or reading from the right as the
part is turned. Each shown line has a grip: select the footprint and drag a line's grip to put
that line anywhere; it then stays there on the part, moving and turning with it. They are
<b>0.08"</b> tall on paper to start: Panel settings, <b>Footprint label height</b>, sets it
(and <b>Footprint label color</b>, <b>In a color of their own</b>, draws them in a color of
their own on every footprint, so a tag stays readable on a white footprint on layer 0;
unticked, they take the footprint's color)
for every footprint in the project (projects made before 0.18.1 take 0.08" when opened; their
labels were the tag height). An empty tag or description shows "?"; an empty rating shows no
line. It prints and goes into PDF and DXF exports. Changing the tag, part number or
description (double-click the footprint) changes the label.</li>
<li><b>Which device a footprint is</b>: placing a footprint (Insert footprint, or a part's
footprint) asks which schematic device it is, as a contact asks which coil: <b>Enter</b> takes
the one offered (the next device with no footprint yet, in page order; one with the
footprint's catalog number first), a typed tag takes that device, <b>L</b> lists them, <b>N</b>
leaves it a footprint of its own. It then carries the device's tag (and its manufacturer,
catalog number and description where neither it nor its footprint block has one: a
footprint's own, typed on it or set in its block's <b>Properties...</b> in the library, come
first; its window shows the block's greyed where the copy has none), shows it, and follows it: renumber the
schematic and the panel's labels change with it. It has the device's ratings too
(horsepower, volts, amps, full-load amps, VA, primary and secondary volts, rating): its
window (double-click it) lists them under <b>From its device</b>, and they are the same on
both: change one there or on the symbol and the other has it (one step for Undo). Tick them
under <b>Shown on it</b> to write them on the footprint (5HP, 480V). On the bill of materials the device and its
footprint are one part. Typing another tag on a footprint (double-click it) makes it that
device's footprint, or, if no device has that tag, a footprint of its own showing it.</li>
<li><b>Footprints snap onto DIN rail.</b> While you place a footprint (Insert), move it,
copy it or drag it, once its <b>DIN rail point</b> (the middle of its rail clip) comes over a
rail it locks onto the rail's centerline and slides along the rail with the mouse, whatever
its base point is; a short yellow line and "On DIN rail" show it. Brought within about ten
pixels of the end of a footprint already on that rail, it butts against it ("On DIN rail,
against the next one"), as devices sit side by side on a real rail; a copy butts against the
one it was copied from. It works on rails across and up and down, and on footprints turned
either way. Take it off the rail by moving it away; with the object snaps off (F3) it isn't
held at all. A point or distance you type (<code>@0,-0.5</code>, a length) is never pulled:
the whole selection goes exactly as typed. A point you snap to wins: with the cursor on an object snap (an intersection on
a duct's or rail's edge, an end), the part goes exactly where you snapped, held by the point
you picked it up by, and isn't pulled onto the rail. Moving a rail together with what is on it moves them all as they are. A
footprint's DIN rail point is the middle of its drawing unless its block says otherwise:
parts whose clip isn't halfway up (many breakers, contactors, power supplies) get theirs in
<b>Edit block...</b> (see <b>Changing a library block</b>). The rail's own snaps still work
for anything else: a mounting slot's center (Center, for an end stop or a screw), the middle
of a long edge (Midpoint), its centerline (Nearest, Perpendicular), and Align objects.</li>
<li><b>Bill of materials...</b> (Sheets menu, Output tab: Reports) lists every part the project
uses, once, with how many: one line per manufacturer and catalog number, with the
description, the tags (CR1, CR2...) and the sheets they are on. A device and its panel
footprint share a tag, so they are one part (the manufacturer, catalog number and description
come from whichever has them); a contact belongs to its device and has no line of its own;
symbols without a tag (an off-sheet connector) are not parts. An AutoCAD Electrical schematic
component brought in with a DXF or DWG (its TAG1: CR1, M1) is a part; its contacts (TAG2) are
not. Parts without a catalog number
are listed by their block's name (a drawing brought in from AutoCAD: its terminals, modules
and drives, counted), or left out with the box unticked. DIN rail and wire duct come last, as
the stock lengths to buy (Panel materials has their cuts). The lines are numbered: a
leader's balloon (Leader, B) can show a part's item number on the panel. <b>Save as
CSV or Excel...</b> writes it for a spreadsheet or a purchase order. Give parts their manufacturer and
catalog number by double-clicking them, or through a part from the library.</li>
<li><b>Panel materials...</b> (Panel tab: Reports) lists the project's rail and duct per size and part:
the pieces and their cut lengths, the total length, and how many stock lengths that takes
(the cuts packed into stock lengths, longest first; saw cuts take no width). <b>Save as
CSV or Excel...</b> writes it for a spreadsheet or a purchase order. The bill of materials takes it
in.</li>
<li><b>Linear dimension</b> (DLI) and <b>Aligned dimension</b> (DAL), Draw menu and the Home,
Schematic and Panel tabs (Dimensions), measure the true distance, so they're right at any scale; they show inches with two
decimals (12.50") or, as Project properties, Panel, <b>Dimension units</b> says, fractional
to the nearest 1/8, 1/16, 1/32 or 1/64 (1-9/16", 3/4"). Changing it there changes the
dimensions already drawn too, unless you untick <b>Change the dimensions already drawn
too</b>. The second point follows Ortho and Polar from the first, as any point
does, except that an object snap at the mouse is taken first (so a corner off the Ortho line
still snaps). Their grips move the measured points
and the line; they go on layer DIMENSIONS (its color: Project properties, Panel). Dimension
text height: Project properties.</li>
<li><b>Dimension units</b> (DIMUNITS, DU; Modify menu, and Dimensions on the Home, Schematic and
Panel tabs): the selected dimensions, or dimensions you click (Enter when done), read
<b>D</b> decimal or <b>F</b> fractional (to the project's precision, 1/16 unless it says
another), or type the precision: 1/8, 1/16, 1/32, 1/64. Each dimension keeps its own.</li>
<li><b>Hatch</b> (H; Draw menu, Home tab) fills an area: click inside a closed shape (a closed
polyline, a rectangle, a circle) and it is filled, the smallest shape around the click; closed
shapes inside it stay open (islands: a cutout's holes, a label). The buttons, or typing their
names, choose the pattern: <b>Solid</b>, <b>45 lines</b> (ANSI31), <b>Crosshatch</b>
(ANSI37) or <b>Level lines</b>; <b>Spacing</b> (SP) the space between the lines, in real
inches, and <b>Angle</b> (AN) their angle. Click more areas, Enter to finish; the pattern is
remembered. A hatch is its own object, not tied to the shapes it was made in: it moves,
copies, rotates and scales with them when selected with them. Click a solid fill anywhere on it
to select it, and a patterned hatch on its lines or its outline: a press in the gaps between its
lines starts a selection window there, as in AutoCAD. On screen a fill is under the lines; printed black and white (PDF), fills print light gray
so the lines and texts on them stay readable. DXF and DWG hatches come in as hatches (their
pattern: ANSI31 and ANSI37 by name, any other as its lines), and go out as HATCH
entities.</li>
<li><b>Leader</b> (LE; Draw menu and the Home, Schematic and Panel tabs, Dimensions) points at a part with an arrow
and says something about it: AutoCAD's leader and multileader in one. Pick the arrow's point
(on the part), then one or more points where the line goes, and press Enter. Then type the
<b>note</b> and press Enter (or Enter alone for no text), or type <b>B</b> for a
<b>balloon</b>: a circle with an item number, as a bill of materials numbers parts; Enter takes
the next number (one more than the highest balloon in the project), or type your own. The note
or balloon sits at the end of a short level landing, on the side the last line points to.
Double-click a leader to change its note (several lines), switch between note and balloon, or
change its text height; its grips move the arrow and each bend. Its text is paper-sized, like a
dimension's (Project properties, dimension text height), and it goes on layer DIMENSIONS.
Leaders and multileaders in a DXF or DWG come in as leaders (a multileader's note or balloon
number with it; a DWG's multileaders aren't readable yet).</li>
</ul>

<h2>Selecting and grips</h2>
<ul>
<li>The object under the cursor <b>lights up</b> (a bright line with a blue glow) and the
cursor's square fills in: that is what a click selects.</li>
<li>Over an object that is <b>already selected</b>, a four-way arrow shows beside the square:
press there and <b>drag</b> to move the selection, and let go where it goes (on the snap grid,
and straight with Ortho). Hold <b>Ctrl</b> when you let go to leave the originals and drop a
<b>copy</b> (a + shows). Undo puts it back. For exact distances use Move or Copy objects.</li>
<li><b>Ctrl+arrow keys</b> move the selection one snap step (Drafting settings, 1/8 inch to
start) left, right, up or down; <b>Ctrl+Shift+arrow</b> a tenth of a step, for fine placement.
Each press is one Undo; wires on a moved symbol's pins come along, and objects on locked
layers stay.</li>
<li>Over a <b>grip</b> of a selected object, the square jumps onto the grip and the arrow shows:
a click there starts stretching it.</li>
<li>Click an object to add it to the selection; <b>Shift</b>+click removes it. Hold
<b>Shift</b> for a window or lasso too, and what it catches is removed from the selection
instead of added (as in AutoCAD).</li>
<li><b>Window</b>: click in an empty spot, move, and click again. <b>Left to right</b> (blue)
selects what is wholly inside; <b>right to left</b> (green, dashed) also selects what it
crosses.</li>
<li><b>Lasso</b>: press, hold the button and draw around the objects, then let go: in an empty
spot or on an object not selected (it is picked when pressed, and let go of again once you
drag on), however fast the mouse goes; let go with no move between, away from where you
pressed, and it is the window between the two. Dragged first to the <b>right</b> it is a window lasso (blue: what is wholly inside); to
the <b>left</b>, a crossing lasso (green: what it touches too). A quick drag nearly straight
from one corner toward the other is a window from where you pressed to where you let go, left
to right or right to left as above; once the drag has bent away from that straight line, it
is a lasso until you let go, whatever its shape (a thin loop along a slanting row of devices
too).</li>
<li>While a window or lasso is open, the objects it would select light up.</li>
<li><b>Select all</b> (Ctrl+A); Esc clears the selection.</li>
<li>Selected objects show blue <b>grips</b>. Click a grip, then click where it goes, to stretch
that end, corner, radius or text position (a symbol: its insertion point, its tag, an
attribute shown). A polyline or rectangle also has a grip in the <b>middle of each side</b>:
drag it and that side moves straight out or in (a rectangle stays a rectangle, longer or
shorter); a wire has its corners only. <b>Shift+click</b> grips to pick several (on any of
the selected objects: the ends of a bus's wires, say): they turn red; click one of them and
then where it goes, and all of them move the same way, in one step. Shift+click a picked grip
again to put it back; Esc drops them all.</li>
<li>Select first, then start Move, Copy objects, Rotate... (or start the command and then
select, pressing Enter when done).</li>
<li>Right-click: Enter while a command runs; otherwise a menu with Repeat, the clipboard and
the modify commands.</li>
</ul>

<h2>Viewing</h2>
<ul>
<li>Mouse wheel zooms at the cursor; hold the <b>middle button</b> to pan; double-click the
middle button for <b>Zoom extents</b>. While you pan or zoom, the picture on screen moves and
scales with the mouse (instantly, however busy the drawing), and the drawing is drawn again
sharp a moment after you stop. While the view stays still, the drawing around it (half the
window more on every side) is made ready too, so panning and zooming out show it right away.</li>
<li>The mouse wheel never changes a number box (the boxes with up and down arrows) or a closed
drop-down list, in any window or on the ribbon: it scrolls the window or list they're in, so
scrolling down a window can't change a setting by accident. Type the value, use the arrow
keys, or click the arrows; open a list to pick from it (the wheel scrolls an open list).</li>
<li><b>Zoom extents</b> (Ctrl+Shift+E), <b>Zoom to sheet</b> (Ctrl+0), <b>Zoom in</b> (Ctrl+=),
<b>Zoom out</b> (Ctrl+-). Zooming out goes until the whole sheet and everything drawn take
about a quarter of the window, on a sheet with a scale too (at 1:24 the sheet is 24 times its
paper size).</li>
<li><b>Black drawing background</b> (on to start, as in AutoCAD): the sheet is drawn black with
white lines. Turn it off for a white sheet. <b>Export to PDF...</b> prints black on white
either way, unless <b>Export to PDF in the layers' colors</b> is ticked.</li>
<li><b>Export to PDF in the layers' colors</b> (off to start): Export to PDF... draws each layer
in its color on white paper (a white or black layer in black), as Print does with "the layers'
colors".</li>
<li><b>Theme</b>: Light, Dark or Same as system: the menus, ribbon and panels. Light stays
light and Dark stays dark whatever Windows is set to; Same as system follows Windows, also when
it switches while KanzonasCAD is open.</li>
<li><b>Command line</b> and <b>Sheets panel</b> show or hide those panels.</li>
</ul>

<h2>Edit menu</h2>
<ul>
<li><b>Undo</b> (Ctrl+Z) and <b>Redo</b> (Ctrl+Y or Ctrl+Shift+Z): every change, including
sheet and layer changes, can be undone. Their arrows also sit at the left end of the ribbon's
row of tabs (Home, Schematic...), always a click away, after <b>Open</b>, <b>Save</b> and
<b>Print</b>, as in KanzonasPDF.</li>
<li><b>Cut</b> (Ctrl+X), <b>Copy</b> (Ctrl+C) and <b>Paste</b> (Ctrl+V): paste asks for an
insertion point (the copied objects' lower left corner lands there). Works between projects,
and after KanzonasCAD is closed and started again. Their layers come with them: a layer the
project you paste into doesn't have is added as it was (its color, line type, wire size and
color); a layer it already has keeps its own.</li>
<li><b>Delete</b> erases the selection.</li>
</ul>

<h2>Files</h2>
<ul>
<li><b>New project</b> (Ctrl+N), <b>Open...</b> (Ctrl+O, a project, or a DXF or DWG drawing),
<b>Open recent</b>, <b>Save</b> (Ctrl+S), <b>Save as...</b> (Ctrl+Shift+S),
<b>Close project</b> (Ctrl+W), <b>Exit</b> (Ctrl+Q). Save is grayed out while the project has
no unsaved changes (the tab's name shows a * when it has some); Save as... always works. In a
block's tab, Save saves the block.</li>
<li><b>Opening a DXF or DWG</b> (Open..., or a double-click on it) makes a new project of it
and puts the drawing on the page, wherever the other program drew it: left where it is when
it already lies on the sheet (a DXF exported from KanzonasCAD, or one drawn on a sheet of
this size), moved to the middle of the sheet when it fits, and, when it is bigger than the
sheet, the sheet gets the biggest scale it fits at (as <b>Fit</b> does; the drawing and its
text stay their real size). The command line says what was done; Sheet scale... changes the
scale.</li>
<li><b>Import DXF or DWG into this sheet...</b> keeps the drawing's own coordinates. It reads
lines, polylines (2D and 3D, flattened onto the page; polyface and mesh polylines as their
edges), circles, arcs, text and multi-line text (MTEXT), ellipses and splines (as polylines),
blocks and dimensions (exploded, with their values), and the outlines of hatches, solids,
traces and 3D faces (their fills aren't drawn); drawings in millimeters are converted to
inches. Points and objects with no 2D shape (3D solids, regions, images) are left out, and a
message names them. A drawing whose model space is empty or nearly so (fewer than 20
objects) but whose layouts (paper space) hold more is read from its layouts instead, as many
manufacturers' and older drawings keep their geometry there; the command line says so.
Opening a DXF or DWG reads it the same way. It opens in the folder you last imported from
(manufacturers' drawings usually sit together).</li>
<li><b>Import PDF into this sheet...</b> (File menu, Output tab) brings in the lines and text
of a page of a PDF: one a CAD program made or printed, or a schematic or drawing someone sent
you as PDF, so there is less to draw by hand. A window asks which page, and how big:
<b>Drawing inches per page inch</b> starts at the sheet's scale, so the page looks on the sheet
as it did printed (on a panel sheet at 1:4 it starts at 4, which brings a 1:4 panel drawing in
at real size); 1 brings it in at its paper size. The page's lower left corner goes at 0,0 of the
sheet, and what comes in is selected (to move it right away); one Undo takes it out. What comes
in:
<ul>
<li>every line the PDF draws: a straight piece as a line, more as a polyline (closed when the
PDF closes it), curves followed closely; a curve that is a circle comes in as a circle, part of
one as an arc; all on layer <b>PDF LINES</b>;</li>
<li>its text, as texts on layer <b>PDF TEXT</b>: the letters on one line, of one size and turn,
as one text (turned as it was: a wire number up the page stays up the page), its height that
of capital letters;</li>
<li>a filled circle (a junction dot) as a circle. Other filled shapes are left out and counted:
most are letters drawn as shapes, which can't be read back as text, and solid arrowheads. Tick
<b>Bring in filled shapes too</b> to bring them in as closed polylines.</li>
</ul>
What can't come in: <b>text drawn as letter shapes</b> (many CAD programs print their fonts
that way, AutoCAD's SHX fonts among them, and KanzonasCAD's own PDFs do too) comes in as those
shapes (or is left out, when filled), not as text you can edit; and a <b>scanned page</b> or a
picture saved as PDF has no lines or text in it at all, only dots, so nothing comes in (the
command line says so). Lines come in as plain lines, not wires, and symbols as their lines, not
symbols. Drag a PDF from Explorer onto the drawing to bring it in where you let go (the same
window asks for the page and size first). A PDF that asks for a password to open can't be
read.</li>
<li><b>Import picture or SVG into this sheet...</b> (File menu, Output tab), or a picture or
SVG dragged onto the drawing. A <b>picture</b> (PNG, JPEG, BMP or GIF: a company logo, a drawing
to trace over) is kept in the project itself, so the project carries it wherever it goes and the
picture file isn't needed again. It comes in 2" wide on paper, in the middle of the view (or
where it was dropped), selected; drag a corner grip to size it (it keeps its shape, from the
corner across), or move, copy, rotate and scale it like anything else. It is drawn under the
lines, printed and put in PDFs; mirrored, it lands where the mirror puts it but isn't flipped.
To have a logo on every sheet, put it in the title block (Edit title block). Exported to DXF, a
picture goes out as an AutoCAD image with its file beside the DXF (sheet-picture-1.png), as
AutoCAD keeps them; a DXF with its pictures beside it brings them back in. An <b>SVG</b> comes
in as real lines, polylines, circles and texts you can snap to and edit: its shapes, paths
(curves and arcs as short straight pieces) and texts, at the size the SVG says (or 96 to the
inch); colors, fills, gradients and fonts are left out. An SVG too detailed to be worth editing
(more than 20,000 pieces or 5,000 elements, or over 5 MB) isn't brought in, and the message
says why: save it as a PNG to bring it in as a picture.</li>
<li><b>Blocks stay blocks.</b> Opening or importing a DXF or DWG keeps each named block as a
block of the project: every copy (a terminal, an I/O module, a drive, the border) is one
object you click, move, copy, label (Footprint label) and list, placed where the other program
put it, at its scale and turned or mirrored as it was. Their attributes come with them, as
the copy's own: AutoCAD Electrical's <b>P_TAG1</b> or <b>TAG1</b> becomes its tag,
<b>DESC1</b> to <b>DESC3</b> its description, <b>MFG</b> its manufacturer, <b>CAT</b> its
catalog number; any other (RATING1, TERM...) keeps its name (double-click the copy to see
them all; an AutoCAD Electrical block's description lines, DESC1 to DESC3, are fields of their
own there, and its description is them joined). The values show as they do in AutoCAD: each
copy's attributes hidden on it stay hidden (AutoCAD Electrical hides most of them copy by copy:
location, installation, ratings...), those moved on it stay where they were moved to (and go
with the copy when you move or turn it), each keeps its alignment, and the description lines
show one under the other. A block with
AutoCAD Electrical's TAG1 comes in as a schematic symbol, any other as a panel footprint
(with no pins: wires don't attach to imported symbols). Their pieces keep their own colors
(or their layer's), as the other program shows them: a manufacturer's colored parts look as
they did (white or black pieces follow the copy's color). <b>Explode</b> takes a copy apart into
its lines and texts; <b>Edit block...</b> opens its drawing, and <b>Save block</b> puts it in
your library to use again. A block of the same name already in the project and different is
not replaced: the imported one is named "name (2)". Blocks scaled differently across and up
and down, arrays (MINSERT) and anonymous ones (a dimension's drawing) still come in as their
lines and texts.</li>
<li><b>Dimensions stay dimensions.</b> A linear dimension (across or up and down) or an
aligned one in a DXF or DWG comes in as a KanzonasCAD dimension: it measures the true distance,
its grips move its points and line, and it follows Sheet scale. A text it was given (34 mm /
1.34 in) stays, with &lt;&gt; standing for the length. It shows the length in inches with
two decimals (12.50"), its value centered along its line, as KanzonasCAD's own do: a vertical
one reads sideways, and a short one has its value over its arrows, where AutoCAD may have put
it level or beside. Angular, radius, diameter and ordinate dimensions, linear ones turned at
another angle, and those with a scale factor (DIMLFAC) come in as their lines and texts, as
drawn.</li>
<li><b>Drag and drop</b>: drag a DXF or DWG from Explorer (or a file manager) and drop it on
the drawing: it is imported into the sheet shown, at real size, with its middle where you let
go, and selected (to move it right away); one Undo takes it out. Several dropped at once go
side by side. Drop it anywhere else in the window (the tab bar, the ribbon, the command line,
or a window with no project open) and it opens as a project of its own, as Open... does. A
dropped <b>.kzcad</b> project opens; a dropped <b>PDF</b> is brought into the sheet shown (see
Import PDF into this sheet...). (Import DXF or DWG into this sheet... keeps the drawing's own
coordinates instead.)</li>
<li><b>AutoCAD DWG files</b> (AutoCAD R13 to 2018 format, which covers every AutoCAD version
since 2018 too) open and import directly, with nothing to install. KanzonasCAD reads them
object by object (with ezdwg, free and open source, decoding the file): every block keeps its
base point and each copy its own place, scale and rotation, block attributes show their
values (invisible ones stay hidden), dimensions come with their values, and layers keep their
names and colors. Tables, multileaders and arc dimensions in a DWG can't be read yet
(ezdwg doesn't decode them; the same drawing saved as DXF brings them in), nor 3D solids and
regions; the message after opening names what was left out. If this reader fails on a
file, KanzonasCAD tries the older way (ezdwg's own conversion to DXF, which loses blocks'
scale and attributes; the command line says so), then the free <b>ODA File Converter</b> when
it is installed; otherwise it tells you why, and saving the drawing as DXF in the program that
made it always works.</li>
<li><b>Export this sheet to DXF...</b> and <b>Export all sheets to DXF...</b>: AutoCAD 2013 DXF
in inches, one file per sheet, border and title block on layer BORDER. Each symbol and footprint
goes out as an AutoCAD <b>block</b> (defined once, placed wherever it is used, turned, scaled
and flipped as it is), with its tag, description, maker, catalog number, location and ratings
as <b>attributes</b>: those shown on the sheet where KanzonasCAD shows them, the others hidden,
so AutoCAD's attribute editor and data extraction find all of them. Layers keep their names and
colors; wires go out as polylines on their layers. AutoCAD opens the DXF and can save it as a
DWG. A flipped symbol's own texts (the TR of a timer coil, a module's point names) stay
readable in AutoCAD: AutoCAD would draw the texts inside a flipped block backwards, so in a
block placed flipped they go out as locked attributes (KZTEXT1...) placed on each copy as
KanzonasCAD draws them. A DXF exported this way opens again in KanzonasCAD with the same
symbols, pins and attributes. To have everything broken into plain lines and texts instead, as before version
0.20, untick <b>Export DXF with symbols and footprints as blocks</b> in Edit &gt; Options...,
General.</li>
<li><b>Backups</b>: each Save first keeps the version before it in a folder beside the project,
"<i>name</i> backups", stamped with the date and time (the newest 10 are kept, or as many as
Edit &gt; Options..., Files, says; none turns backups off). <b>Open backups
folder</b> opens it; to go back to one, open it like any project and Save as.</li>
<li><b>Autosave</b>: every 5 minutes (Options, Files, changes it or turns it off), projects with unsaved changes are copied to a recovery
folder (never over your own file; in the portable version, <code>data\\recovery</code> beside
the program). If KanzonasCAD doesn't close normally (a crash, a power
cut), it offers to recover them the next time it starts.</li>
<li><b>Export to PDF...</b>: every sheet at its real size, vector lines, everything printed
black on white, or in the layers' colors with Export to PDF in the layers' colors ticked in Edit
&gt; Options..., General.</li>
</ul>

<h2>Printing</h2>
<p><b>Print...</b> (File menu, Ctrl+P, the Output tab, or right-click in the Sheets panel)
opens the Print window. The <b>preview</b> on its right shows the page as it will print (the
dashed line is the edge the printer can print to), and is drawn again as you change anything;
<b>&lt;</b> and <b>&gt;</b> go through the pages. <b>Full preview...</b> shows them all
bigger.</p>
<ul>
<li><b>Printer</b>: the printers your computer has, and <b>PDF file</b> (it asks for the
file's name when you click Print). <b>Paper</b> lists the sizes the printer takes, starting
with its own; <b>Copies</b> how many of each.</li>
<li><b>Orientation</b>: <b>Automatic</b> (to start) turns each sheet a quarter turn when that
prints it bigger (an ANSI B sheet on letter paper prints sideways, its title block at the top
right, as a printer's Landscape does); <b>Portrait</b> and <b>Landscape</b> set the page's way
and never turn the drawing.</li>
<li><b>What to print</b>: <b>Whole sheet</b> (to start: the border, title block and drawing);
<b>Extents</b>, everything drawn, cross-references and wire numbers too, without the empty
paper around it; <b>Display</b>, what the drawing window shows now; <b>Window</b>, two corners
you pick: choosing it hides the Print window, you pick the corners on the drawing (snaps
work; Esc goes back without one), and the Print window comes back. <b>Pick window &lt;</b>
picks again. Display and Window print the sheet shown. To print only part of a sheet (a
few devices, one rung), use Window, as in AutoCAD. A border or title block turned off
(Project or Sheet properties) isn't printed.</li>
<li><b>Sheets</b>: <b>This sheet</b> (the one shown), <b>All sheets</b>, or <b>These
sheets</b>, ticked in the list (<b>Tick all</b>, <b>Tick none</b>). With several sheets
selected in the Sheets panel (Ctrl+click, Shift+click), the window starts with those ticked.
They print in the project's order, one sheet a page; the Print button says how many.</li>
<li><b>Fit to paper</b> (to start): what is printed as big as the paper holds. A panel sheet
prints at its scale, shrunk to the paper. Lines stay as thin on paper whatever the
shrinking.</li>
<li><b>Actual size</b>: as on the sheet's own paper (a 1:4 panel sheet at 1:4), centered on
the page; past the printer's paper is cut off at the page's edges (its middle shows).</li>
<li><b>Black on white</b> (to start), as Export to PDF; untick it to print the layers'
colors.</li>
</ul>
<p>When a scaled sheet's drawing doesn't fit on it (the status bar's <b>doesn't fit</b>),
printing the whole sheet asks first, as Export to PDF does. The question names each sheet that
doesn't fit by its number and title, says whether its drawing runs past the border or over the
title block, and names what does (a symbol by its tag, a text by what it says, up to five a
sheet). <b>Print anyway</b> prints; <b>Go back</b> opens the Print window again as you left it;
<b>Show them</b> goes to the first of those sheets with everything on it in view and what
doesn't fit selected (the command line lists it), so you can move it or use Fit. {{Print
date}} in the title block is when you printed.</p>

<h2>Windows and two screens</h2>
<p>Any sheet can have a window of its own, to put on another screen: the schematic on one
screen and the panel layout on the other, say.</p>
<ul>
<li><b>Open this sheet in a new window</b> (Window menu, Ctrl+Shift+N, the View tab's
<b>New window</b>): a new window on the same project, showing the sheet you are on (right-click
a sheet in the Sheets panel and <b>Open in a new window</b> for another one). With two screens
it opens filling the other one; drag it wherever you like.</li>
<li>Both windows work on <b>the same project</b>: what you draw in one is in the other at once,
<b>Undo</b> and <b>Redo</b> in either take back or redo the last change made in any of them,
and <b>Save</b> saves the project once for both. Each window has its own ribbon, command line,
Sheets panel and selection, and shows the sheet you pick in it.</li>
<li><b>Move this project to a new window</b> (Window menu, the View tab's <b>Move to
window</b>) moves the tab to a window of its own. Dragging a project tab away from the tabs and
letting go does the same, where you let go; let go over another KanzonasCAD window to move the
tab into it.</li>
<li><b>Close this window</b> (Window menu) closes that window; closing a window, or a tab, only
asks to save a project when no other window shows it. Closing the first window (the one
KanzonasCAD started with) closes the others too.</li>
<li>Settings (Black drawing area, the object snaps, Drafting settings) apply in every
window.</li>
</ul>

<h2>Project templates</h2>
<p>A <b>template</b> is an ordinary project that new projects start from: everything in it
comes along, so set it up once. Its settings (Project properties), layers and their colors
(wire colors too), the title block drawing and its field values (Drawn by, say), the zones, and
its <b>sheets with what is drawn on them</b> (a cover sheet, a legend, a ladder ready to wire,
a panel sheet with its scale set). What you leave out of it isn't there: delete a sheet from
the template and new projects don't have it; leave Customer blank and it starts blank.</p>
<ul>
<li><b>Save as template...</b> (File menu) saves the open project as a template, in the
<b>Templates</b> folder of your library (a shared library can share them), then asks whether
every new project should start from it. The project you saved stays as it was.</li>
<li><b>New project</b> (Ctrl+N) starts from that default template; with none chosen, from
KanzonasCAD's own settings.</li>
<li><b>New project from template...</b> (File menu) starts one from any template you pick
(one per customer, say).</li>
<li>A new project from a template is untitled: Save asks where to put it, and the template file
is never changed by it. To change a template, open it like any project, change it and Save.</li>
<li><b>Edit &gt; Options...</b>, Files, shows which template new projects start from;
<b>Built-in</b> goes back to KanzonasCAD's own settings.</li>
</ul>

<h2>Options</h2>
<p><b>Options...</b> (Edit menu) holds what belongs to you and this computer, for every project
(<b>Project properties</b> holds what belongs to one project):</p>
<ul>
<li><b>General</b>: the theme (Light, Dark, Same as system), the black drawing area,
checking for updates automatically, and <b>Open the files that were open when KanzonasCAD
last closed</b> (off to start): on, KanzonasCAD starts with the saved projects that were open
when you last closed it (all its windows' tabs, as tabs of one window; not when another
KanzonasCAD is already running, which has them).</li>
<li><b>Files</b>: the library folder, the template for new projects (Browse..., or Built-in),
how many backups to keep of each project (None turns them off), and how often unsaved work is
autosaved (Off turns it off).</li>
<li><b>Drafting</b>: the same settings as <b>Drafting settings...</b> (View menu): snap and grid
spacing, the crosshair, the running object snaps and polar tracking angles.</li>
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
<tr><td>Enter / Space</td><td>Finish a step; repeat the last command (Insert: the same symbol)</td></tr>
<tr><td>Esc</td><td>Cancel the command; clear the selection (anywhere in the window)</td></tr>
<tr><td>Delete</td><td>Erase the selection</td></tr>
<tr><td>Ctrl+arrows / Ctrl+Shift+arrows</td><td>Move the selection one snap step / a tenth of one</td></tr>
<tr><td>Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S</td><td>New / Open / Save / Save as</td></tr>
<tr><td>Ctrl+W / Ctrl+Q</td><td>Close project / Exit</td></tr>
<tr><td>Ctrl+P</td><td>Print...</td></tr>
<tr><td>Ctrl+Shift+N</td><td>Open this sheet in a new window</td></tr>
<tr><td>Ctrl+Tab / Ctrl+Shift+Tab</td><td>Next / previous sheet in page order (round from
the last to the first)</td></tr>
<tr><td>Ctrl+` / Ctrl+Shift+`</td><td>The sheet you were last on; hold Ctrl and tap ` for the
ones before it (Shift+` back)</td></tr>
<tr><td>Ctrl+Z / Ctrl+Y</td><td>Undo / Redo</td></tr>
<tr><td>Ctrl+X / Ctrl+C / Ctrl+V / Ctrl+A</td><td>Cut / Copy / Paste / Select all</td></tr>
<tr><td>Ctrl+Shift+E / Ctrl+0 / Ctrl+= / Ctrl+-</td><td>Zoom extents / sheet / in / out</td></tr>
<tr><td>Ctrl+Shift+Plus / Ctrl+Shift+Minus</td><td>Rotate sheet clockwise / counterclockwise</td></tr>
</table>

<h2>Help</h2>
<p><b>User manual</b> (F1) opens this page: its <b>chapters</b> on the left (click one to go
there; a chapter's sections under it) and a <b>search</b> box over it. Type in it: the chapters
narrow to those that mention it, with how many times, every match lights up, and
<b>Next</b> and <b>Previous</b> (Enter and Shift+Enter) go from one to the next ("3 of 17").
<b>About KanzonasCAD</b> shows the logo, the version, the license and where the source code is.
KanzonasCAD is free to use, at home or at work, under the PolyForm Shield License 1.0.0
(LICENSE.txt in the program's folder). Versions 0.20 and earlier were released under the MIT
License.</p>

<h2>Installing</h2>
<p>On Windows, <b>KanzonasCAD-v&lt;version&gt;-setup.exe</b> from the Releases page installs
KanzonasCAD for you (no administrator rights needed) or, if you pick it on the first page,
for everyone on the PC (Windows asks for administrator rights), with a Start menu entry, an optional
desktop shortcut, and <b>.kzcad</b> projects opening in KanzonasCAD with a double-click (DXF
drawings get KanzonasCAD under <i>Open with</i>). It uninstalls from Windows Settings &gt;
Apps; your projects and library are kept.</p>
<ul>
<li><b>Without installing</b> (<b>KanzonasCAD-v&lt;version&gt;-windows.zip</b>): unzip it anywhere
and run KanzonasCAD\\KanzonasCAD.exe. It keeps its settings on the computer, like the installed
version.</li>
<li><b>Portable version</b> (<b>KanzonasCAD-v&lt;version&gt;-portable.zip</b>): unzip the
KanzonasCAD folder anywhere (a USB stick, a network drive) and run KanzonasCAD.exe. Because of
the <b>portable.txt</b> file inside, your settings (<code>settings.ini</code>), your library
(<code>Library</code>) and the autosave recovery copies (<code>recovery</code>) are kept in a
<b>data</b> folder next to the program instead of the computer's registry and user folders, so
they travel with the folder and nothing is left on the computer. The window title and Help
&gt; About say <b>(portable)</b>. Keep the whole folder together; delete portable.txt to make it
behave like the installed version. A library folder, template or recent project on the stick
is found again when the stick gets another drive letter on another PC (E: here, F: there).</li>
<li><b>PortableApps.com version</b> (KanzonasCAD Portable, for the PortableApps.com Platform):
the same, with your files in the package's <b>Data</b> folder. The PortableApps.com Platform
updates it, so KanzonasCAD doesn't check for updates by itself unless you tick Help &gt;
<b>Check for updates automatically</b>, and then it only opens the release page.</li>
<li><b>Linux</b>: <b>KanzonasCAD-x86_64.AppImage</b> (64-bit PC; Ubuntu 22.04, Debian 12, Fedora
36 or newer). Make it executable (right-click &gt; Properties &gt; Permissions &gt; Allow
executing file as program, or <code>chmod +x KanzonasCAD-x86_64.AppImage</code>) and
double-click it; no installation or administrator rights are needed. If it doesn't start and
mentions FUSE or libfuse.so.2, install FUSE 2 (Ubuntu 22.04 and Debian 12: <code>sudo apt
install libfuse2</code>; Ubuntu 24.04 and later: <code>sudo apt install libfuse2t64</code>;
Fedora: <code>sudo dnf install fuse-libs</code>) or start it with
<code>--appimage-extract-and-run</code>. Settings are kept in
~/.config/KanzonasCAD/KanzonasCAD.conf, recovery copies in
~/.local/share/KanzonasCAD/KanzonasCAD/recovery, the library in ~/Documents/KanzonasCAD
Library. The
same program is also a folder, <b>KanzonasCAD-v&lt;version&gt;-linux.tar.gz</b>: unpack it and
run KanzonasCAD/KanzonasCAD (it doesn't update itself).</li>
</ul>

<h2>Updates</h2>
<p>KanzonasCAD asks GitHub for new versions by itself, at most once a day (also while it stays
open), quietly: nothing shows unless there is one. Then a box tells you what changed in every
version since yours, with three buttons: <b>Update now</b>, <b>Skip this version</b> (you're
not told about it again; a newer one still shows) and <b>Later</b>. While Update now
downloads, its window shows a progress bar with how much has come (48.3 of 75.2 MB, 64%), and
<b>Cancel</b> stops the download; once it's done (or failed) the button is <b>Close</b>.
When you finish the update, every other KanzonasCAD you have running closes first, as Quit
would (each asks to save its changes); if you cancel in one, it stays open and the update
stops until you close it. With <b>Open the files that were open...</b> on (Options), the new
version opens the files all of them had open.</p>
<ul>
<li>Run from source (the README's way): Update now gets the new version (git pull) and what it
needs, shows what it did, and offers to start the new version.</li>
<li>Installed with the setup (KanzonasCAD-v&lt;version&gt;-setup.exe): Update now downloads
the new setup, uses it only if it matches the release exactly (its sha256), closes
KanzonasCAD and installs the new version over this one, then starts it again. No
administrator rights are needed for a copy installed for you; a copy installed for all users
updates for all users too, and Windows asks for administrator rights first.</li>
<li>The Windows zip (unzipped by hand): Update now downloads the new zip, checks it the same
way, and replaces this copy when KanzonasCAD closes, then starts it again.</li>
<li>The portable version: Update now downloads the new portable zip, checks it the same way,
and replaces the program files in the same folder when KanzonasCAD closes, then starts it
again; the data folder (settings, library, recovery copies) is kept. Or close KanzonasCAD and
unzip the new download over the same folder, replacing the files.</li>
<li>The PortableApps.com version: the PortableApps.com Platform updates it; Update now opens the
release page.</li>
<li>The Linux AppImage: Update now downloads the new KanzonasCAD-x86_64.AppImage, checks it the
same way, puts it in place of the old file (same name and place), closes KanzonasCAD and starts
the new version. If you keep it open, the new version starts the next time you open
KanzonasCAD. If the AppImage is in a folder you can't change, the release page opens instead:
download the new file and replace the old one yourself. The Linux folder (tar.gz) only opens
the release page.</li>
<li>Either way you're asked to save any changes first, and your projects and library are never
touched.</li>
</ul>
<p><b>Check for updates...</b> (Help menu) checks now. <b>Check for updates automatically</b>
turns the daily check on or off.</p>
"""


def html():
    """The manual, every chapter and section heading with an anchor of its own (chapters())."""
    import re
    out, n = [], 0
    last = 0
    text = _HTML.format(version=__version__)
    for m in re.finditer(r"<h([23])>", text):
        out.append(text[last:m.start()])
        n += 1
        out.append('<a name="ch-%d"></a>' % n)
        last = m.start()
    out.append(text[last:])
    return "".join(out)


def chapters():
    """[(level, title, anchor, its text)]: the manual's chapters (2) and their sections (3),
    in order, each with the plain text under it up to the next heading (for Help's search)."""
    import re
    text = html()
    heads = list(re.finditer(r'<a name="(ch-\d+)"></a><h([23])>(.*?)</h[23]>', text, re.S))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = re.sub(r"<[^>]+>", " ", text[m.end():end])
        title = re.sub(r"<[^>]+>", "", m.group(3)).replace("&amp;", "&")
        out.append((int(m.group(2)), title, m.group(1), _unescape(body)))
    return out


def _unescape(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace(
        "&quot;", '"')


def plain_text():
    import re
    return re.sub(r"<[^>]+>", " ", html()).replace("&lt;", "<").replace("&gt;", ">")
