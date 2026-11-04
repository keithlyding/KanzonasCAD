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
<li><b>Sheet properties...</b> (or double-click the sheet in the Sheets panel): what belongs to
one sheet: its title, its <b>type</b> (Schematic, Panel, Report or Other: every tool works on
every sheet; the type brings up the matching ribbon tab and shows in the Sheets panel), page
number and, if it differs from the project's, its own revision.
Its size and zones are the project's unless you tick "This sheet has its own size and zones";
then set how many columns run along the top and the first one's number (11 makes a sheet
continue 11 to 20), and how many rows run down the left and the first one's letter. Grid
references follow the zones as they are set: change them and every reference updates.</li>
<li><b>Project properties...</b> (or double-click the title block): what belongs to the whole
project, in three tabs:
<ul>
<li><b>General</b>: the title block fields (customer, project, drawing number, drawn by, checked
by, date, revision, and any field of your own the title block uses), the <b>grid reference
format</b> (<code>{{sheet}}-{{row}}{{col}}</code> gives 6-D1) and the height of new text.</li>
<li><b>Schematic</b> (also <b>Schematic settings...</b>): the sheet size and zones every sheet
uses unless it has its own (8 rows, A to H, and 10 columns to start), the device tag height
(changing it resizes every tag), and the wire and symbol colors.</li>
<li><b>Panel</b> (also <b>Panel settings...</b>): the footprint and dimension colors.</li>
</ul></li>
<li><b>Edit title block</b>: see below.</li>
<li><b>Layers...</b>: add, rename, recolor, switch off and lock layers, and choose the current
layer. The Layer box on the Home tab picks the current layer; with objects selected, picking
a layer moves them to it.</li>
</ul>

<h2>Colors and layers</h2>
<p>As in AutoCAD, every object takes its <b>layer's color</b> (ByLayer) unless you give it its
own: select it and use <b>Color...</b> (Modify menu, or the Schematic and Panel tabs) to pick a
color, or to set it back to ByLayer. A symbol or footprint's lines follow the color of the
layer it sits on, or its own color if you gave it one. Wires go on layer WIRES, symbols on
SYMBOLS, footprints on PANEL and dimensions on DIMENSIONS: the Schematic and Panel tabs of
Project properties set those colors, which recolors everything on them.</p>
<p>The ribbon's <b>Schematic</b> and <b>Panel</b> tabs gather the tools for each kind of work.
Both are always there: any sheet can hold a schematic, a panel layout, or both.</p>

<h2>The title block</h2>
<p>The title block is a small drawing of its own, the same on every sheet of the project.
<b>Edit title block</b> (Sheets menu and Sheets tab) shows it by itself: draw, move, trim,
erase and type text there with the usual commands, or <b>Import DXF or DWG into this sheet...</b>
to bring in your company's title block and move it into the lower right corner. Click
<b>Edit title block</b> again (or click a sheet in the Sheets panel) to go back.</p>
<p>A text that contains a field name in braces shows that field's value on every sheet:</p>
<ul>
<li><code>{{Customer}}</code>, <code>{{Project}}</code>, <code>{{Drawing number}}</code>,
<code>{{Drawn by}}</code>, <code>{{Checked by}}</code>, <code>{{Date}}</code>,
<code>{{Revision}}</code> - from Project properties.</li>
<li><code>{{Sheet}}</code> (the page number), <code>{{Sheets}}</code> (how many sheets) and
<code>{{Sheet title}}</code> and <code>{{Scale}}</code> (1:4, 3" = 1'-0"...) - from each
sheet. <code>{{Sheet}} OF {{Sheets}}</code> gives
"6 OF 12".</li>
<li>Any other name, like <code>{{Job number}}</code>, becomes a field of your own: it appears
in Project properties to fill in.</li>
</ul>
<p>A name in braces that isn't a field shows as typed, so a typo is easy to spot. Undo works
on title block changes like on any other.</p>

<h2>Symbols, footprints and parts (the library)</h2>
<p>Your <b>library</b> is a folder of its own (<code>Documents\\KanzonasCAD Library</code> to
start; <b>Library folder...</b> picks another, a OneDrive folder say). It is kept apart from
the program and from projects, so it lasts through updates and serves every project. Each
project also keeps its own copy of the blocks it uses, so it opens the same anywhere, whatever
happens to the library later.</p>
<ul>
<li><b>Schematic symbols</b>: blocks with <b>pins</b> (where wires attach) and a <b>tag</b>.
A starter set of JIC/NFPA symbols is built in (relay, contactor and timer coils, NO/NC and
timed contacts, pushbuttons, E-stop, selector, limit/pressure/temperature/float switches,
fuse, breaker, disconnect, overload heater and contact, pilot light, motor, solenoid, control
transformer, terminal strip and terminal, ground, distribution block, off-sheet connector;
three-phase: 3-pole breaker, disconnect and fuses, contactor power contacts, overload heaters,
motor, variable frequency drive; power supply; PLC I/O card with input and output points).
A symbol of yours with the same name replaces a built-in one.</li>
<li><b>Panel footprints</b>: the outline of a real part, at real size, for panel layouts.</li>
<li><b>Parts</b>: a manufacturer and catalog number linked to a schematic symbol and a panel
footprint. Placing a part fills in its manufacturer, catalog number and description.</li>
</ul>
<p>The <b>Library</b> opens as a popup window, as AutoCAD Electrical's icon menu does, so the
drawing keeps the whole width: <b>Insert symbol...</b> (Schematic tab) opens it on its Symbols,
<b>Insert footprint...</b> (Panel tab) on its Footprints, and <b>Library...</b> (Library menu)
as you left it; its Parts tab lists your parts. Type in its search box to find one.
Double-click a symbol or footprint (or select it and click <b>Insert</b>): the popup gets out
of the way and you click where it goes; type R to turn it 90 degrees or F to flip it first.
The popup opens again where you last put it. In the Parts tab, Insert asks whether to place
the part's symbol or its footprint.</p>
<h3>Making your own</h3>
<ol>
<li>Draw it, or open the manufacturer's DXF and copy the view you want into your drawing
(Copy, then Paste).</li>
<li>A footprint must be real size: <b>Scale</b>, pick a base point, type R (Reference), pick
the two ends of a dimension you know (the part's width say) and type its real length
(<code>45mm</code> or <code>1.77</code>).</li>
<li>Select it and use <b>Make block</b> (B). Pick the <b>base point</b> (the point it is placed
by), then fill in the name, kind (schematic symbol or panel footprint), category and
description. For a symbol also: its part in cross-references (a device on its own, a coil or
operator with contacts elsewhere, or a contact), the contact type, the tag prefix (CR, M, PB...),
what wire numbers do through it (nothing; a distribution block; an off-sheet connector: see
Wire numbers) and the pin names.</li>
<li>For a symbol, click each <b>pin</b> in order and press Enter, then click where the
<b>tag</b> goes (Enter puts it above).</li>
</ol>
<p>It is saved to your library and, unless you untick it, the selected objects become the
block. <b>New part...</b> then links a manufacturer and catalog number to the symbol and the
footprint.</p>
<p>Double-click a placed symbol or footprint to change its tag, description, manufacturer and
catalog number, or pick one of the library's parts for it. <b>Explode</b> (X) turns placed
blocks back into plain lines and texts. Delete in the Library panel removes your own symbols,
footprints and parts (the built-in symbols stay).</p>


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
down, or down then across. Locked tags stay and their numbers are skipped.</li>
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
to. <b>Enter</b> takes the one offered (the nearest coil with the contact's prefix: CR for a
relay contact; on this sheet first); type a tag (<code>M601</code>) to take that device, or
<b>L</b> for a list of them. A tag no device has yet is kept, and the contact links itself
to the device that gets that tag. With no device in the project at all, it's placed unlinked
(its reference shows <b>?</b>).</li>
<li><b>Changing it later</b>: double-click the contact. "Belongs to" lists the project's
devices; pick one or type a tag. Deleting a coil leaves its contacts unlinked (showing
<b>?</b>) until a device takes that tag again.</li>
<li><b>Cross-references</b> are worked out from the drawing, never typed: under a coil or
operator, one line per contact, <b>NO 6-D3</b> or <b>NC 7-B2</b> (in sheet order, then zone
order); under each contact, where its device is (<b>6-D1</b>). They use the project's grid
reference format and each sheet's zones, and go into PDF and DXF exports as text.</li>
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
<p><b>Wire</b> (W; Draw menu and the Schematic tab) draws a wire on layer WIRES. Click where it
starts (a symbol's pin, another wire, or anywhere), then where it goes: it runs straight across
and up or down, with one corner per click; the corner follows the cursor, and F flips it the
other way. The wire <b>ends by itself</b> when you click a pin or another wire; Enter ends it
anywhere; so does Esc or starting another command (what is drawn is kept). U takes back
the last click.</p>
<p><b>Bus</b> (BU; Draw menu and the Schematic tab) draws several wires side by side, three
phases say. Type how many wires (3 to start) and how far apart (1/2 inch to start; 12mm works
too), pressing Enter to keep what it offers; then click the path as for a wire. Every click
turns it 90 degrees, as many times as you need, and all the wires turn together, keeping their
spacing. The first wire runs where you click, the others to the right of the direction you
draw (F puts them on the other side). Enter or Esc ends it; each wire of the bus is an ordinary
wire, connecting wherever its ends land.</p>
<ul>
<li><b>Connections</b> are worked out from where wire ends are, never stored: a wire end on a
pin, on another wire's end, or on the middle of another wire connects there. A wire ending on
the middle of another (a T), or three or more wire ends at one point, get a <b>dot</b>.</li>
<li><b>Moving a symbol drags its wires</b>: the wire ends on its pins come along (Move, Rotate,
Mirror, Scale, dragging it or its grip), staying straight across and up or down (a jog is added
where needed). Select the wires too and they move with it instead.</li>
<li><b>Placing a symbol on a wire</b> cuts the wire between the symbol's pins, as AutoCAD
Electrical does: drop a contact onto a rung and it is wired in.</li>
<li>Wires are ordinary objects otherwise: grips stretch their corners, Trim and Erase work on
them (trimmed pieces stay wires), and they print and export (DXF) as polylines.</li>
</ul>

<h3>Three-phase power, terminals and PLC I/O</h3>
<ul>
<li><b>Three-pole symbols</b> (breaker, disconnect, fuses, contactor power contacts, overload
heaters) have their poles 1/2 inch apart, top to bottom L1/T1, L2/T2, L3/T3, the spacing
<b>Bus</b> starts with: draw a 3-wire bus, then drop the breaker on it, and each pole cuts
its wire. The motor and the drive (VFD: L1-L3 in, T1-T3 out) line up the same way.</li>
<li><b>Contactor power contacts</b> belong to the contactor's coil like any contact (M601)
and list under it.</li>
<li><b>Terminals</b> belong to a <b>Terminal strip</b> (place the strip first, anywhere: it
takes a tag, TB601). Placing a terminal asks which strip, as a contact asks for its coil; it
shows the strip's tag and numbers itself on the strip: 1, 2, 3... (the lowest free number;
a copy takes the next one). Double-click a terminal to type its number instead. The strip
lists where its terminals are.</li>
<li><b>PLC input</b> and <b>PLC output</b> points belong to a <b>PLC I/O card</b> the same
way, and list under it; double-click a point to type its <b>address</b> (I:0/3, %I0.3...),
shown under it.</li>
</ul>

<h2>Wire numbers</h2>
<p>Every wire gets its number by itself: the page number and three digits, <b>6001</b>, 6002...
on page 6. The number shows above the wire (beside it when it runs up and down).</p>
<ul>
<li><b>One number per connected wire</b>: wires joined end to end or in a T share it. A
symbol's pins don't join wires, so the number changes through a device or a terminal.</li>
<li>Numbers are given in the sheet's <b>numbering order</b> (Sheet properties: across then down,
or down then across) and then <b>kept</b>: drawing more doesn't renumber what's there. A new
wire takes the lowest free number of its page, so a deleted number comes back.</li>
<li>When two wires are joined, the lower number stays; when one is cut in two (a symbol placed
on it, Trim), the part later in order takes a new number.</li>
<li><b>Double-click a wire</b> to type its number (for it and every wire joined to it). A typed
number is locked: numbering leaves it alone. Clear it to let numbering give one back.</li>
<li>When a sheet's page number changes, its unlocked wire numbers follow (6001 becomes 7001),
as device tags do.</li>
<li><b>Renumber sheet</b> also numbers the sheet's unlocked wires again, 001, 002... in
order.</li>
<li><b>Distribution block</b> (Library, JIC/Wiring): the wires on its outputs take the number
of the wire on its input with A, B, C... added (6001A, 6001B; after Z come AA, AB...).</li>
<li><b>Off-sheet connector</b> (Library, JIC/Wiring): place one where a wire leaves the sheet
and one where it comes back on another sheet, with the same name. Placing one asks its name:
Enter takes the one offered (a connector still waiting for its other end, else the next free
letter). The wire keeps the number of the sheet it starts on, and under each connector its
other end's place shows (<b>7-A2</b>).</li>
<li>Project properties, Schematic: <b>Number wires</b> (on to start) and the height of wire
numbers and cross-references.</li>
<li>Wire numbers go into PDF and DXF exports as text.</li>
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
@width,height).</td></tr>
<tr><td>Circle: Center, radius</td><td>CIRCLE, C</td><td>Center, then radius (a point or a
number); D switches to a diameter. At the first prompt, 3P, 2P or TTR switch to those ways.</td></tr>
<tr><td>Circle: Center, diameter</td><td></td><td>Center, then diameter.</td></tr>
<tr><td>Circle: 2-Point</td><td>C, then 2P</td><td>The two ends of a diameter.</td></tr>
<tr><td>Circle: 3-Point</td><td>C, then 3P</td><td>Three points on the circle.</td></tr>
<tr><td>Circle: Tan, tan, radius</td><td>C, then TTR</td><td>Pick two lines, polylines, circles or
arcs near where the circle should touch them, then type its radius (Enter: the last one): of
the circles that fit, you get the one touching nearest your picks.</td></tr>
<tr><td>Arc (3 points)</td><td>ARC, A</td><td>Start, a point on the arc, end.</td></tr>
<tr><td>Text</td><td>TEXT, T, DT</td><td>Start point, height, angle, then type each line and
press Enter; Enter on an empty line ends. Before the start point, J (Justify) chooses where the
point sits on the text, as in AutoCAD: TL, TC, TR (top), ML, MC, MR (middle), BL, BC, BR
(bottom), or L, C, R (on the baseline); it is kept for the next texts.
<b>Double-click a text</b> to change its wording, height, angle and justification afterward
(with "Keep the text where it is" ticked, a new justification moves only its insertion point,
which is where it snaps and turns around).</td></tr>
<tr><td>Move</td><td>MOVE, M</td><td>Select, base point, second point.</td></tr>
<tr><td>Copy objects</td><td>COPY, CO, CP</td><td>Select, base point, then as many copies as
you place (Enter ends).</td></tr>
<tr><td>Rotate</td><td>ROTATE, RO</td><td>Select, base point, angle (a point or degrees).</td></tr>
<tr><td>Scale</td><td>SCALE, SC</td><td>Select, base point, factor. Or <b>Reference</b> (R): pick
two points of a length as drawn (or type it), then type the length it should be: this brings a
manufacturer's drawing to its real size. Lengths can be typed in millimeters:
<code>45mm</code>. On a panel sheet, footprints are left out (they're real size).</td></tr>
<tr><td>Mirror</td><td>MIRROR, MI</td><td>Select, two points of the mirror line, keep or erase
the originals. Text stays readable.</td></tr>
<tr><td>Erase</td><td>ERASE, E, or Delete</td><td>Removes the selected objects.</td></tr>
<tr><td>Trim</td><td>TRIM, TR</td><td>Click the part of an object to cut away: it is trimmed
back to the nearest crossing objects on either side (every object is a cutting edge, as in
AutoCAD's quick mode). An object nothing crosses is erased. U undoes the last trim.</td></tr>
<tr><td>Zoom</td><td>ZOOM, Z</td><td>Extents (E), Sheet (S), In (I), Out (O).</td></tr>
<tr><td>Linear dimension</td><td>DIMLINEAR, DLI, DIM</td><td>Pick the two points to measure,
then where the dimension line goes: across or up and down, whichever way you pull it.</td></tr>
<tr><td>Aligned dimension</td><td>DIMALIGNED, DAL</td><td>The same, measured along the line
between the two points (slanted too).</td></tr>
<tr><td>DIN rail</td><td>DINRAIL, RAIL, DR</td><td>Real-size DIN rail from its start to its end
(or type the length toward the cursor). Before the first click: <b>7.5</b> (TS35 x 7.5 mm, to
start), <b>15</b> (TS35 x 15 mm) or <b>MINI</b> (TS15).</td></tr>
<tr><td>Wire duct</td><td>DUCT, WIREWAY, WD</td><td>Real-size wire duct, the same way. Before
the first click, type its size, width x depth: <code>2x3</code> (inches) or
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
<li><b>Drafting settings...</b>: snap spacing, grid spacing, the polar tracking
angles and the crosshair (all kept for next time).</li>
<li><b>Crosshair</b>: short, as in AutoCAD (each line 5% of the view to start). In Drafting
settings, <b>Crosshair size</b> makes it longer or shorter (1 to 100%), and <b>Full-screen
crosshair</b> runs its lines across the whole view.</li>
</ul>

<h2>Panel sheets and dimensions</h2>
<p>A panel layout is drawn at <b>real size</b>: a 3 inch contactor is 3 inches in the drawing,
on every sheet, forever. Each sheet has <b>one scale</b> that only sets how big it prints:
<b>Sheet scale...</b> (Panel tab), Sheet properties, or click <b>Scale 1:4</b> in the status
bar. Pick 1:2, 1:4, 1:5... or an architectural one (3" = 1'-0"...), or type one (1:6).</p>
<ul>
<li>The border, zones and title block are drawn around the real-size drawing, enlarged by the
scale, so the sheet prints at its paper size (PDF) with the drawing at that scale. DXF
exports hold the real-size drawing with the border enlarged around it, as AutoCAD drawings
in model space do.</li>
<li>Text, tags, cross-references, wire numbers and dimension text are <b>paper-sized</b>: new
text at 1/8 inch prints 1/8 inch high whatever the scale. Changing a sheet's scale changes
their heights with it (in one undoable step).</li>
<li>Footprints aren't scaled by hand on a panel sheet (Scale leaves them out and says so):
bring a manufacturer's drawing to real size with Scale, Reference before it becomes a
footprint.</li>
<li><b>{{Scale}}</b> in the title block shows the sheet's scale (Edit title block to add it).</li>
<li><b>DIN rail</b> and <b>Wire duct</b> (Draw menu, Panel tab) are drawn at real size from
one end to the other: the rail's outline, lips and mounting slots, the duct's walls and finger
slots. Stretch one with its end grips (or double-click it and type its length), move it with
its middle grip. A duct's depth isn't drawn (it's a view from the front) but is part of its
size. Double-click a piece for its profile or size, length, manufacturer, catalog number and
the length it is bought in (the project's to start: Project properties, Panel; 1 m rail and 6
ft duct).</li>
<li><b>Panel materials...</b> (Panel tab) lists the project's rail and duct per size and part:
the pieces and their cut lengths, the total length, and how many stock lengths that takes
(the cuts packed into stock lengths, longest first; saw cuts take no width). <b>Save as
CSV...</b> writes it for a spreadsheet or a purchase order. The bill of materials (later)
takes it in.</li>
<li><b>Linear dimension</b> (DLI) and <b>Aligned dimension</b> (DAL), Draw menu and the Panel
tab, measure the true distance, so they're right at any scale; they show inches with two
decimals (12.50"). Their grips move the measured points and the line; they go on layer
DIMENSIONS (its color: Project properties, Panel). Dimension text height: Project
properties.</li>
</ul>

<h2>Selecting and grips</h2>
<ul>
<li>The object under the cursor <b>lights up</b> (a bright line with a blue glow) and the
cursor's square fills in: that is what a click selects.</li>
<li>Over an object that is <b>already selected</b>, a four-way arrow shows beside the square:
press there and <b>drag</b> to move the selection, and let go where it goes (on the snap grid,
and straight with Ortho). Hold <b>Ctrl</b> when you let go to leave the originals and drop a
<b>copy</b> (a + shows). Undo puts it back. For exact distances use Move or Copy objects.</li>
<li>Over a <b>grip</b> of a selected object, the square jumps onto the grip and the arrow shows:
a click there starts stretching it.</li>
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
<li><b>Theme</b>: Light, Dark or Same as system: the menus, ribbon and panels. Light stays
light and Dark stays dark whatever Windows is set to; Same as system follows Windows, also when
it switches while KanzonasCAD is open.</li>
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
<li><b>New project</b> (Ctrl+N), <b>Open...</b> (Ctrl+O, a project, or a DXF or DWG drawing),
<b>Open recent</b>, <b>Save</b> (Ctrl+S), <b>Save as...</b> (Ctrl+Shift+S),
<b>Close project</b> (Ctrl+W), <b>Exit</b> (Ctrl+Q).</li>
<li><b>Import DXF or DWG into this sheet...</b>: lines, polylines, circles, arcs, text,
ellipses and splines (as polylines), blocks and dimensions (exploded). Drawings in
millimeters are converted to inches.</li>
<li><b>AutoCAD DWG files</b> (AutoCAD R13 to 2018 format, which covers every AutoCAD version
since 2018 too) open and import directly, with nothing to install: KanzonasCAD reads them with
its own DWG reader (ezdwg, free and open source). If it can't read one and the free
<b>ODA File Converter</b> is installed, KanzonasCAD tries that by itself (the command line says
so); otherwise it tells you why, and saving the drawing as DXF in the program that made it
always works.</li>
<li><b>Export this sheet to DXF...</b> and <b>Export all sheets to DXF...</b>: AutoCAD 2013 DXF
in inches, one file per sheet, border and title block on layer BORDER.</li>
<li><b>Backups</b>: each Save first keeps the version before it in a folder beside the project,
"<i>name</i> backups", stamped with the date and time (the newest 10 are kept). <b>Open backups
folder</b> opens it; to go back to one, open it like any project and Save as.</li>
<li><b>Autosave</b>: every 5 minutes, projects with unsaved changes are copied to a recovery
folder (never over your own file). If KanzonasCAD doesn't close normally (a crash, a power
cut), it offers to recover them the next time it starts.</li>
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

<h2>Installing</h2>
<p>On Windows, <b>KanzonasCAD-v&lt;version&gt;-setup.exe</b> from the Releases page installs
KanzonasCAD for you (no administrator rights needed) or, if you pick it on the first page,
for everyone on the PC (Windows asks for administrator rights), with a Start menu entry, an optional
desktop shortcut, and <b>.kzcad</b> projects opening in KanzonasCAD with a double-click (DXF
drawings get KanzonasCAD under <i>Open with</i>). It uninstalls from Windows Settings &gt;
Apps; your projects and library are kept. The zip of the same version runs without
installing.</p>

<h2>Updates</h2>
<p>KanzonasCAD asks GitHub for new versions by itself, at most once a day (also while it stays
open), quietly: nothing shows unless there is one. Then a box tells you what changed in every
version since yours, with three buttons: <b>Update now</b>, <b>Skip this version</b> (you're
not told about it again; a newer one still shows) and <b>Later</b>.</p>
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
<li>Either way you're asked to save any changes first, and your projects and library are never
touched.</li>
</ul>
<p><b>Check for updates...</b> (Help menu) checks now. <b>Check for updates automatically</b>
turns the daily check on or off.</p>
"""


def html():
    return _HTML.format(version=__version__)


def plain_text():
    import re
    return re.sub(r"<[^>]+>", " ", html()).replace("&lt;", "<").replace("&gt;", ">")
