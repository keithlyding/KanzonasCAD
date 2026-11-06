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
<b>Home</b>, <b>Schematic</b>, <b>Panel</b>, <b>Sheets</b>, <b>Output</b> and <b>View</b>; each
group of buttons has its name under it (Rail and duct, Dimensions, Blocks...). Double-click a
tab name (or <b>Collapse ribbon</b>, Ctrl+F1) to fold it away; click a tab to open it again.
<b>Ribbon group names</b> (View) turns the names off, for a more compact ribbon, and on
again.</li>
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
<li><b>General</b>: the title block fields (customer, project, drawing number, drawn by, drawn
date (today's when the project is made), checked by, date, revision, and any field of your own
the title block uses), the <b>grid reference
format</b> (<code>{{sheet}}-{{row}}{{col}}</code> gives 6-D1) and the height of new text.</li>
<li><b>Schematic</b> (also <b>Schematic settings...</b>): the sheet size and zones every sheet
uses unless it has its own (8 rows, A to H, and 10 columns to start), the device tag height
(changing it resizes every tag), and the wire and symbol colors.</li>
<li><b>Panel</b> (also <b>Panel settings...</b>): the footprint and dimension colors.</li>
</ul></li>
<li><b>Edit title block</b>: see below.</li>
<li><b>Layers...</b>: add, rename, recolor, switch off, lock and delete layers, and choose the
current layer. To clean up (after importing a DXF, say), select several layers (Ctrl+click,
Shift+click) or click <b>Select unused</b> (the empty ones), then <b>Delete</b>: empty layers
go at once; if some hold objects (on any sheet or in the title block), it lists them and asks
whether to delete them too, with everything on them, or keep them. Layer 0 always stays, and
one Undo brings it all back. The Layer box on the Home tab (and on the Panel tab) picks the current layer; with objects selected, picking
a layer moves them to it.</li>
</ul>

<h2>Colors and layers</h2>
<p>As in AutoCAD, every object takes its <b>layer's color</b> (ByLayer) unless you give it its
own: select it and use <b>Color...</b> (Modify menu, or the Schematic and Panel tabs) to pick a
color, or to set it back to ByLayer. A symbol or footprint's lines follow the color of the
layer it sits on, or its own color if you gave it one. Wires go on layer WIRES, symbols on
SYMBOLS, footprints on PANEL and dimensions on DIMENSIONS: the Schematic and Panel tabs of
Project properties set those colors, which recolors everything on them. On the black drawing,
black (or nearly black) objects are drawn white, and on a white one, white objects are drawn
black, so nothing disappears (as AutoCAD's color 7); their color stays as you set it, and they
print in it.</p>
<p><b>Layers</b>, as in AutoCAD: a hidden layer isn't drawn, printed or picked; a locked one
is drawn but its objects can't be selected or changed. <b>Layers...</b> lists them all (On,
Locked, color, current layer). Quicker, on the Home tab's Layers group (the Panel tab has the layer box, the layer list,
Layers..., Color, Hide layer and Show all too) and the Modify menu:</p>
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
<b>Edit title block</b> (Sheets menu and Sheets tab) shows it by itself: draw, move, trim,
erase and type text there with the usual commands, or <b>Import DXF or DWG into this sheet...</b>
to bring in your company's title block and move it into the lower right corner. Click
<b>Edit title block</b> again (or click a sheet in the Sheets panel) to go back.</p>
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
<p><b>Title block position</b> (Project properties, General) says where the title block sits:</p>
<ul>
<li><b>Lower right corner</b> (to start): the zones run the full width and height of the
sheet, and the title block sits over the lower right corner.</li>
<li><b>Right-hand strip</b>: the title block takes the whole right-hand column of the sheet.
The zones stop at it (a line divides them from the strip) and are spread over the room left,
so grid references (6-D1) never point into the title block.</li>
<li><b>Bottom strip</b>: the same along the bottom of the sheet.</li>
</ul>
<p>The strip's width (or height) is that of the title block you drew. Tick <b>Replace the
title block with one made for this position</b> to swap in a ready-made one, with the same
fields, that fills the strip (or the corner); Undo puts your old one back. On a panel sheet
with a scale the strip stays its size on paper.</p>

<h2>Symbols, footprints and parts (the library)</h2>
<p>Your <b>library</b> is a folder of its own (<code>Documents\\KanzonasCAD Library</code> to
start, or <code>data\\Library</code> beside the program in the portable version; <b>Library
folder...</b> picks another, a OneDrive folder say). It is kept apart from
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
by), then fill in the name, kind (schematic symbol or panel footprint: it starts on panel
footprint on a panel sheet, on schematic symbol otherwise), category and description, and,
if you like, its manufacturer, family, series and catalog number (see below). For a symbol also: its part in cross-references (a device on its own, a coil or
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
manufacturer's blocks, or one family's; the manufacturer list also filters the Parts tab. A
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
(renaming pins; Edit block adds or removes them). Its kind can't change. Renaming it saves it
under the new name, removes your file under the old one and points your parts at the new
name.</li>
<li><b>Edit block...</b> (a button in the Library popup, its right-click menu, or the Library
menu and the Schematic and Panel tabs, for a block selected in the drawing): the library's
copy of the block opens in a tab of its own, <b>Block: name</b>, as AutoCAD's Block Editor
does. Change it with every normal command (Move, Copy, Trim, Text, grips, Undo...). The cross
is the <b>base point</b> (on the locked layer BLOCK BASE POINT); each green text on layer BLOCK
PINS is a <b>pin</b>: its insertion point, marked with a small ring, is where wires attach, and
its text is the pin's name (edit the text to rename it, move it with its grip, copy it to add
a pin, erase it to remove one); the blue text on BLOCK TAG is where the tag goes, and texts on
BLOCK ATTRIBUTES are where a terminal's number or a PLC address shows. A footprint has a pink
<b>DIN RAIL</b> text on layer BLOCK DIN RAIL: its insertion point (a ring, with a dashed line
across the part where the rail's centerline runs) is the middle of the part's rail clip. Move
it to where the rail's center crosses the part (its height on the part is what counts on a
rail across; snap to the clip's drawing if it has one) and the part sits right on the rail
when placed; left where it opened, it stays the middle of the drawing (also when the drawing
changes); erased, it goes back to that. The blue <b>LABEL</b> text on layer BLOCK TAG is
where its <b>Footprint label</b> goes, the same way: left where it opened, the middle of the
drawing; moved, that spot. <b>Save block</b>
(Library menu, the ribbon, or Save, Ctrl+S, in that tab) puts it back in your library: the
pins keep their order, new ones come after. Closing the tab with changes not saved asks
first. <b>Save block as...</b> (Library menu and the ribbon, in that tab) saves it under a new
name instead, with its catalog number left blank: the block it was opened from stays as it
was in your library, and the tab goes on editing the new one.</li>
<li><b>Duplicate...</b> (a button in the Library popup, its right-click menu, or
<b>Duplicate block...</b> in the Library menu and the Schematic and Panel tabs, for a block
selected in the drawing): to make a block that is almost like one you have (a footprint of
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
name) and stretch to where the pins moved; a wire on a pin that is gone stays where it was,
and the command line says how many. No keeps the old drawing. Other projects keep their own
copies of the block as they were.</p>


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
<p><b>Wire</b> (W; Draw menu and the Schematic tab) draws a wire on layer WIRES (move wires
to another layer afterward like any object: select them and pick the layer in the Layer box;
they stay wires). Click where it
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
<li><b>Crossings</b>: wires that pass through each other don't connect. Project properties,
Schematic, <b>Wire crossings</b> says how that is drawn: <b>Plain</b> (they just cross: no
dot means not connected, to start), <b>Gap</b> (one wire is broken briefly) or <b>Loop</b> (one
wire hops over the other); <b>Which wire jumps</b>: the up-and-down one (to start) or the
across one. Crossings are found by themselves and follow the wires as they move; they print
and export to DXF (the jumping wire cut, the loop as a half circle).</li>
<li><b>Wire crossing</b> (WX; Draw menu, Schematic tab) places one by hand: click a wire where
it should jump, on a crossing or anywhere else on it (over a symbol's line, say). Type
<b>G</b>, <b>L</b> or <b>N</b> first for a gap, a loop or <b>none</b> (none hides a crossing
found by itself). A mark placed by hand lights up as a small circle when the cursor is over
it; select and Erase it to take it away.</li>
<li><b>Two wires on one terminal</b> (double landing): start a wire on a pin that already has
one, or end it there, and the new wire leaves the pin on a short 45-degree lead (1/8 inch on
paper) and then runs straight beside the first, as drawn by hand. It goes to the side the
cursor is on; a third wire takes the other side. The lead keeps its angle when the symbol
moves. Several wires on a pin get no dot: the pin is the connection.</li>
<li><b>Moving a symbol drags its wires</b>: the wire ends on its pins come along (Move, Rotate,
Mirror, Scale, dragging it or its grip), staying straight across and up or down (a jog is added
where needed). Select the wires too and they move with it instead.</li>
<li><b>Placing a symbol on a wire</b> cuts the wire between the symbol's pins, as AutoCAD
Electrical does: drop a contact onto a rung and it is wired in.</li>
<li><b>Scoot</b> (SCOOT, AESCOOT; Modify menu, Schematic tab), as AutoCAD Electrical's:
select devices (a contact, a pushbutton, a terminal...), a base point, then where to. They
slide only along their own wire, across a rung or up and down a vertical wire, however you
move the mouse; the wires on their pins stretch on one side and shorten on the other, staying
straight. They stop short of a wire's far end or corner.</li>
<li><b>Align devices</b> (AEALIGN; Modify menu, Schematic tab), as AutoCAD Electrical's
Align: click the device to line up with, then the devices to line up, and press Enter. Each
slides along its own wire (as Scoot) into line: the same column on rungs across, the same row
on wires up and down. One that would leave its wire stops where its wire ends (the command
line says so).</li>
<li>Wires are ordinary objects otherwise: grips stretch their corners, Trim and Erase work on
them (trimmed pieces stay wires), and they print and export (DXF) as polylines.</li>
</ul>

<h3>Editing wires</h3>
<p>The Schematic tab's <b>Edit wires</b> group (also on the Modify menu):</p>
<ul>
<li><b>Trim wire</b> (TRIMWIRE, AETRIM, TW), as AutoCAD Electrical's: click a piece of wire
and it goes, up to the nearest wire or pin on either side (to the wire's end when there is
none): no cutting edges to pick, and only wires are trimmed, even where a symbol's line is
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
wires meeting end to end with nothing else there (no pin, no third wire) become one. The
command line then says what it did and how many wire ends connect to nothing, which is
usually a wire stopping short of where it should go.</li>
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
on page 6. The number shows above the wire (beside it when it runs up and down), on its
longest straight piece, in the middle of the longest stretch clear of crossings and
junctions.</p>
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
<tr><td>Text</td><td>TEXT, T, DT</td><td>Click where the text goes, then type each line and
press Enter; Enter on an empty line ends. One click only: unlike AutoCAD's TEXT, a second click
doesn't set the height. Before the click, type <b>H</b> for the height (inches on paper: 1/8
to start), <b>R</b> for the rotation (degrees), or <b>J</b> (Justify) for where the point sits
on the text, as in AutoCAD: TL, TC, TR (top), ML, MC, MR (middle), BL, BC, BR (bottom), or L,
C, R (on the baseline). All three are kept for the next texts.
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
<tr><td>Wire duct</td><td>DUCT, WIREWAY, WD, PANDUIT</td><td>Real-size wire duct, the same way. Before
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
<li><b>Object snap</b> (F3, OSNAP), as AutoCAD's: near the cursor, points snap onto objects;
a yellow marker in AutoCAD's shape and the snap's name show which. The snaps:
<b>Endpoint</b> (END), <b>Midpoint</b> (MID), <b>Center</b> (CEN), <b>Geometric center</b>
(GCE: the middle of a closed polyline), <b>Node</b> (NOD: symbol pins, dimension points),
<b>Quadrant</b> (QUA), <b>Intersection</b> (INT), <b>Insertion</b> (INS: blocks and text),
<b>Perpendicular</b> (PER: square to a line, or on a circle in line with its center, from the
last point), <b>Tangent</b> (TAN: touching a circle or arc, from the last point) and
<b>Nearest</b> (NEA: the closest point on any object). And three that follow what the cursor
has hovered over, as AutoCAD's tracking (a small green cross marks what was picked up):
<b>Extension</b> (EXT: hover over a line's end, then move along the line past it: a dotted line
follows it out), <b>Parallel</b> (PAR: hover over a line, then move roughly its way from the
last point: the new line runs parallel to it) and <b>Apparent intersection</b> (APP: hover
over two lines, then near where they would meet if they were longer).</li>
<li><b>Blocks snap too</b>: the ends, middles, centers and quadrants of a placed symbol's or
footprint's own drawing (a footprint's corners, for a dimension), as in AutoCAD. A pin, or an
ordinary object's point of the same kind, comes first, so a wire still lands on a pin.</li>
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
it. (A dimension's two measured points aren't bent by Ortho.)</li>
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
space</b>), red when it is too big (it names a scale that fits). Pick 1:2, 1:4, 1:5... or an
architectural one (3" = 1'-0"...), or type one (1:6).</li>
<li><b>Fit</b> picks the biggest scale at which the drawing fits inside the border and clear
of the title block. With nothing drawn yet, give the <b>Cabinet size</b> (width, height and,
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
says so ("Turned tall it prints bigger: 1:5 instead of 1:8") with a <b>Turn it</b> button; Fit
never turns a sheet by itself. PDF pages print the sheet as turned.</li>
<li>Click <b>Scale 1:4</b> in the status bar for a short list: <b>Fit</b> (with the scale it
would pick), the common scales, and <b>More...</b> (the Sheet scale window). A sheet's scale
is also in Sheet properties.</li>
<li>When the drawing runs past the border or over the title block at the sheet's scale, the
status bar says <b>doesn't fit</b> (in amber), and Export to PDF asks before printing it cut
off.</li>
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
<li><b>Align objects</b> (ALIGNOBJ, ALO; Modify menu, Panel tab) lines up footprints, DIN rail,
duct or anything else: select them, choose <b>Left</b>, <b>Center</b>, <b>Right</b>,
<b>Top</b>, <b>Middle</b> or <b>Bottom</b> (L, C, R, T, M, B), then click the one to line
them up with, or press Enter to line them up with the selection's own outer edge (or its
middle). Each moves only straight across (Left, Center, Right) or straight up and down (Top,
Middle, Bottom), by its outline; one Undo puts them back.</li>
<li><b>DIN rail</b> and <b>Wire duct</b> (Draw menu, Panel tab) are drawn at real size from
one end to the other: the rail's outline, lips and mounting slots, the duct's walls and finger
slots. They always go straight across or straight up and down (a snap off that line only sets
the length), and their end grips stretch them along their own line. Stretch one
with its end grips (or double-click it and type its length), move it with its middle grip. A duct's depth isn't drawn (it's a view from the front) but is part of its
size. Double-click a piece for its profile or size, length, manufacturer, catalog number and
the length it is bought in (the project's to start: Project properties, Panel; 1 m rail and 6
ft duct).</li>
<li><b>Footprint label</b> (Modify menu, the Panel tab's Footprints group, or a right-click
with footprints selected): the selected footprints show, written across them, their
<b>Show tag</b> (M1, CR3), <b>Show part number</b> (its catalog number; the block's own when
the copy has none), <b>Show description</b> or <b>Show block name</b>, or <b>No label</b>
(as they start). Select one or many, pick one: one step, Undo takes it back. Each footprint
keeps its own choice, so some can show part numbers and others tags. The label is centered on
the part (or at its block's label spot, set in Edit block), turned up the page or reading from
the right as the part is turned, and paper-sized like the tags (Project properties: tag
height). An empty tag or description shows "?". It prints and goes into PDF and DXF exports.
Changing the tag, part number or description (double-click the footprint) changes the
label.</li>
<li><b>Footprints snap onto DIN rail.</b> While you place a footprint (Insert), move it,
copy it or drag it, once its <b>DIN rail point</b> (the middle of its rail clip) comes over a
rail it locks onto the rail's centerline and slides along the rail with the mouse, whatever
its base point is; a short yellow line and "On DIN rail" show it. Brought within about ten
pixels of the end of a footprint already on that rail, it butts against it ("On DIN rail,
against the next one"), as devices sit side by side on a real rail; a copy butts against the
one it was copied from. It works on rails across and up and down, and on footprints turned
either way. Take it off the rail by moving it away; with the object snaps off (F3) it isn't
held at all. Moving a rail together with what is on it moves them all as they are. A
footprint's DIN rail point is the middle of its drawing unless its block says otherwise:
parts whose clip isn't halfway up (many breakers, contactors, power supplies) get theirs in
<b>Edit block...</b> (see <b>Changing a library block</b>). The rail's own snaps still work
for anything else: a mounting slot's center (Center, for an end stop or a screw), the middle
of a long edge (Midpoint), its centerline (Nearest, Perpendicular), and Align objects.</li>
<li><b>Panel materials...</b> (Panel tab) lists the project's rail and duct per size and part:
the pieces and their cut lengths, the total length, and how many stock lengths that takes
(the cuts packed into stock lengths, longest first; saw cuts take no width). <b>Save as
CSV...</b> writes it for a spreadsheet or a purchase order. The bill of materials (later)
takes it in.</li>
<li><b>Linear dimension</b> (DLI) and <b>Aligned dimension</b> (DAL), Draw menu and the Panel
tab, measure the true distance, so they're right at any scale; they show inches with two
decimals (12.50"). The two points they measure go where you pick them (the snap): Ortho and
Polar don't bend them, only the dimension line's place. Their grips move the measured points
and the line; they go on layer DIMENSIONS (its color: Project properties, Panel). Dimension
text height: Project properties.</li>
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
<li><b>Lasso</b>: press in an empty spot, hold the button and draw around the objects, then let
go. Dragged first to the <b>right</b> it is a window lasso (blue: what is wholly inside); to
the <b>left</b>, a crossing lasso (green: what it touches too). A quick drag that draws no
loop (from one corner toward the other) is a window from where you pressed to where you let
go, left to right or right to left as above.</li>
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
sheet and layer changes, can be undone. Their arrows also sit right after the menus (File,
Edit, View...), always a click away.</li>
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
<li><b>Blocks stay blocks.</b> Opening or importing a DXF or DWG keeps each named block as a
block of the project: every copy (a terminal, an I/O module, a drive, the border) is one
object you click, move, copy, label (Footprint label) and list, placed where the other program
put it, at its scale and turned or mirrored as it was. Their attributes come with them, as
the copy's own: AutoCAD Electrical's <b>P_TAG1</b> or <b>TAG1</b> becomes its tag,
<b>DESC1</b> to <b>DESC3</b> its description, <b>MFG</b> its manufacturer, <b>CAT</b> its
catalog number; any other (RATING1, TERM...) keeps its name (double-click the copy to see
them all). A block's visible fields show their values as they do in AutoCAD. A block with
AutoCAD Electrical's TAG1 comes in as a schematic symbol, any other as a panel footprint
(with no pins: wires don't attach to imported symbols). <b>Explode</b> takes a copy apart into
its lines and texts; <b>Edit block...</b> opens its drawing, and <b>Save block</b> puts it in
your library to use again. A block of the same name already in the project and different is
not replaced: the imported one is named "name (2)". Blocks scaled differently across and up
and down, arrays (MINSERT) and anonymous ones (a dimension's drawing) still come in as their
lines and texts.</li>
<li><b>Drag and drop</b>: drag a DXF or DWG from Explorer (or a file manager) and drop it on
the drawing: it is imported into the sheet shown, at real size, with its middle where you let
go, and selected (to move it right away); one Undo takes it out. Several dropped at once go
side by side. Drop it anywhere else in the window (the tab bar, the ribbon, the command line,
or a window with no project open) and it opens as a project of its own, as Open... does. A
dropped <b>.kzcad</b> project opens. (Import DXF or DWG into this sheet... keeps the drawing's
own coordinates instead.)</li>
<li><b>AutoCAD DWG files</b> (AutoCAD R13 to 2018 format, which covers every AutoCAD version
since 2018 too) open and import directly, with nothing to install. KanzonasCAD reads them
object by object (with ezdwg, free and open source, decoding the file): every block keeps its
base point and each copy its own place, scale and rotation, block attributes show their
values (invisible ones stay hidden), dimensions come with their lines, arrows and values, and
layers keep their names and colors. Tables, multileaders and arc dimensions in a DWG can't be read yet
(ezdwg doesn't decode them; the same drawing saved as DXF brings them in), nor 3D solids and
regions; the message after opening names what was left out. If this reader fails on a
file, KanzonasCAD tries the older way (ezdwg's own conversion to DXF, which loses blocks'
scale and attributes; the command line says so), then the free <b>ODA File Converter</b> when
it is installed; otherwise it tells you why, and saving the drawing as DXF in the program that
made it always works.</li>
<li><b>Export this sheet to DXF...</b> and <b>Export all sheets to DXF...</b>: AutoCAD 2013 DXF
in inches, one file per sheet, border and title block on layer BORDER.</li>
<li><b>Backups</b>: each Save first keeps the version before it in a folder beside the project,
"<i>name</i> backups", stamped with the date and time (the newest 10 are kept, or as many as
Edit &gt; Options..., Files, says; none turns backups off). <b>Open backups
folder</b> opens it; to go back to one, open it like any project and Save as.</li>
<li><b>Autosave</b>: every 5 minutes (Options, Files, changes it or turns it off), projects with unsaved changes are copied to a recovery
folder (never over your own file; in the portable version, <code>data\\recovery</code> beside
the program). If KanzonasCAD doesn't close normally (a crash, a power
cut), it offers to recover them the next time it starts.</li>
<li><b>Export to PDF...</b>: every sheet at its real size, vector lines, everything printed
black on white (layer colors are for the screen).</li>
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
<li><b>General</b>: the theme (Light, Dark, Same as system), the black drawing area, and
checking for updates automatically.</li>
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
<tr><td>Enter / Space</td><td>Finish a step; repeat the last command</td></tr>
<tr><td>Esc</td><td>Cancel the command; clear the selection</td></tr>
<tr><td>Delete</td><td>Erase the selection</td></tr>
<tr><td>Ctrl+arrows / Ctrl+Shift+arrows</td><td>Move the selection one snap step / a tenth of one</td></tr>
<tr><td>Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S</td><td>New / Open / Save / Save as</td></tr>
<tr><td>Ctrl+W / Ctrl+Q</td><td>Close project / Exit</td></tr>
<tr><td>Ctrl+Z / Ctrl+Y</td><td>Undo / Redo</td></tr>
<tr><td>Ctrl+X / Ctrl+C / Ctrl+V / Ctrl+A</td><td>Cut / Copy / Paste / Select all</td></tr>
<tr><td>Ctrl+Shift+E / Ctrl+0 / Ctrl+= / Ctrl+-</td><td>Zoom extents / sheet / in / out</td></tr>
<tr><td>Ctrl+Shift+Plus / Ctrl+Shift+Minus</td><td>Rotate sheet clockwise / counterclockwise</td></tr>
</table>

<h2>Help</h2>
<p><b>User manual</b> (F1) opens this page. <b>About KanzonasCAD</b> shows the logo, the version and where the source code is.</p>

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
    return _HTML.format(version=__version__)


def plain_text():
    import re
    return re.sub(r"<[^>]+>", " ", html()).replace("&lt;", "<").replace("&gt;", ">")
