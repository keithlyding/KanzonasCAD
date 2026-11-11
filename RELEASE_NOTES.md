# Release notes

Short, plain-language notes for each version. The full details are in
[CHANGELOG.md](CHANGELOG.md).

Every version gets a section `## <version>` (a few lines under **New** and **Fixed**). The
build fails without them.

## 0.15.3

**Fixed**
- AutoCAD Electrical drawings no longer show text piled on top of itself: attributes hidden on
  a block in AutoCAD stay hidden (an imported drawing showed hundreds of them over the others),
  attributes moved on a block stay where they were moved to, each keeps its alignment, and a
  device's description lines show one under the other instead of as one long line.

**Security**
- The DWG reader (ezdwg) is updated to 0.19.2. Its changes since 0.19.0 are speed
  improvements, with no security fixes; DWG files open about a fifth faster.

## 0.15.2

**Fixed**
- The lasso no longer turns into a rectangle: once your drag bends away from a straight line it
  stays a lasso until you let go (a thin loop along a slanting row of devices too). A quick,
  nearly straight drag still makes a window.
- The lasso is fast again on big drawings: on an imported AutoCAD panel a mouse move took 3 to
  7 seconds; it now takes a few milliseconds, and selects exactly the same.
- Changing a sheet's scale no longer makes imported text huge: text and dimensions that came
  with a DXF or DWG keep their size in the drawing. Your own notes, tags and dimensions still
  keep their size on paper, multi-line text too. Sheet scale has a new box, "Text and
  dimensions keep their size on paper": untick it to change no text at all (for drawings
  imported before this version).

## 0.15.1

**New**
- Panel footprints come built in: 34 generic devices at typical real sizes, ready to place on
  DIN rail (Library, Generic categories): breakers 1, 2 and 3 pole, fuse holders, a motor
  protector, a rotary disconnect, contactors, an overload relay, plug-in and slim relays, a timer
  relay, 24 VDC power supplies, terminal blocks with end plates and end stops, a PLC processor
  and I/O module, control transformers, and 22 mm door devices. Each one's description gives
  its size; for a part you buy, use its maker's drawing (Make block, or Edit block one of these
  and save it under your own name).
## 0.15

**New**
- Cables between locations (Sheets menu, Output tab): what has to be pulled between panels and
  boxes, and where every wire lands on both sides. Give each sheet its location in Sheet
  properties (MCP, JB-1, FIELD), or a single device its own (double-click it: Location); every
  wire number that lands in two locations is listed, run by run, with the terminal (TB1-12) or
  device pin (CR1:A1) it lands on at each end.
- Type each run's cable and type (W101, 12C #14 TC), choose numbered or color-coded
  conductors, and type any conductor's color. Save the pull list as CSV, or as a PDF with a
  page per run and columns to tick off what's pulled and landed.

## 0.14.1

**Faster**
- Sheets with a lot of text draw and zoom much faster: text is now drawn the way Qt draws it
  fastest (a sheet of 2,000 notes zoomed in 0.6 s instead of 22 s). It looks the same; PDFs
  and printouts still get exact vector letters.

**Fixed**
- AutoCAD Electrical schematic components brought in with a DXF or DWG (TAG1: CR1, M1) are
  now counted in the bill of materials.
- Export to DXF no longer stops with "LAYER 'Defpoints' already exists" after a DXF or DWG
  drawing with dimensions was imported into the project.

## 0.14

**New**
- Bill of materials (Sheets menu, Output tab): every part the project uses, once, with how
  many, by manufacturer and catalog number, with its tags and sheets; a device and its panel
  footprint count once; DIN rail and wire duct as the stock lengths to buy. Save it as CSV for
  a spreadsheet or a purchase order.

## 0.13.5

**New**
- Use as title block (Sheets menu): select a title block that came with a DXF or DWG drawing and
  make it the project's title block, on every sheet. Its attribute fields become fields
  (AutoCAD Electrical's drawing number, sheet, revisions...), with their values.

## 0.13.4

**New**
- Multiline text (MT): a note of several lines as one object, wrapped to the width of a box
  you draw, typed in a box; double-click to edit it. Multiline text in DXF and DWG drawings
  comes in as one, and goes out as one.

## 0.13.3

**New**
- Hatch (H): click inside a closed shape to fill it solid, with 45-degree lines, a crosshatch
  or level lines; shapes inside it stay open. Hatches in DXF and DWG drawings come in as
  hatches and are written out as hatches.
- Parts from other programs' drawings keep their colors, as they showed there.
- Leader arrowheads are filled.

## 0.13.2

**New**
- Dimensions in DXF and DWG drawings come in as dimensions: linear and aligned ones measure,
  stretch with their grips and follow the sheet's scale, keeping any text they were given.

## 0.13.1

**New**
- Leader (LE): an arrow pointing at a part, with a note (one or several lines) or a balloon
  with an item number that counts up by itself. One tool for AutoCAD's leaders and
  multileaders; double-click one to change it. Leaders and multileaders in DXF drawings come
  in as leaders.

## 0.13

**New**
- Blocks in DXF and DWG drawings stay blocks: each terminal, module or drive comes in as one
  object you can click, move, copy and label, with its attributes. AutoCAD Electrical's
  P_TAG1, DESC1-3, MFG and CAT become the part's tag, description, manufacturer and catalog
  number. Explode still takes one apart, and Edit block saves one to your library.
- Opening a drawing made of blocks is lighter: a panel drawing that came in as 100,000 loose
  lines now comes in as a few hundred parts.

## 0.12.11

**Fixed**
- DWG files come in right: blocks keep their size and place (a scaled border no longer swallows
  the drawing), block attributes and dimensions with their values come through, and layers
  keep their names and colors. Before, many drawings made of blocks lost most of their
  content or had it in the wrong place and at the wrong size.
- Opening big DXF and DWG drawings made of blocks is much faster.

## 0.12.10

**New**
- Drag a DXF or DWG from Explorer onto the drawing to import it right there (it comes in
  selected, ready to move). Drop it anywhere else in the window to open it as its own
  project; dropping a KanzonasCAD project opens it.

## 0.12.9

**New**
- The drawn date fills itself in: a new project starts with today's date ({Drawn date}).
- A print stamp: {Print date} shows when a PDF or DXF was made, so a paper copy shows how old
  it is. The built-in title blocks show DRAWN, REV DATE and PRINTED (a project made before
  this keeps its title block: Project properties can swap in the new one).

**Fixed**
- KanzonasCAD could crash some time after the Sheet scale window had been opened and closed.

## 0.12.8

**New**
- Revisions: New revision... (Sheets menu and Sheets tab) adds the next revision (0, 1, 2...)
  dated today; Revisions... shows and edits the whole history. The title block's revision and
  date now follow it on their own, sheet by sheet, and new fields ({Rev 1}, {Rev 1 date}...)
  fill a revision table.

**Fixed**
- Clicking OK in Project properties without changing anything marked the project as changed.

## 0.12.7

**New**
- Footprint label: select footprints and choose what they show written on them: their tag,
  part number, description or block name, or nothing (Modify > Footprint label, the Panel
  tab, or right-click). Each footprint keeps its own choice, and one Undo takes it back.

## 0.12.6

**New**
- Footprints snap onto DIN rail: while you place, move, copy or drag one, it locks onto the
  rail's centerline as soon as it comes over a rail, and slides along it. Bring it close to a
  part already on the rail and it butts right up against it.
- Each footprint can say where its rail clip is (for parts whose clip isn't halfway up): in
  Edit block, move the pink DIN RAIL marker to the middle of the clip.

## 0.12.5

**New**
- Duplicate a symbol or footprint to make one that is almost the same: Duplicate... in the
  Library (or Library > Duplicate block...) asks for a new name, copies everything but the
  catalog number, and opens the copy in Edit block right away.
- Save block as... in a block's tab saves it under a new name and leaves the original as it
  was.

**Fixed**
- Imported DXF and DWG drawings that came in with only a few lines: flat 3D polylines,
  hatches (their outlines), solids, multileaders, arrays of blocks (MINSERT) and objects from
  AutoCAD Electrical or Mechanical were left out; now they come in.
- Arcs, circles and text inside mirrored blocks landed mirrored in the wrong place.
- A drawing kept in its layout (paper space) instead of model space came in all but empty;
  it is now read from its layout.
- Anything still left out is named in a message after the import.

## 0.12.4

**New**
- Delete several layers at once: in Layers..., select them (Ctrl+click or Shift+click, or
  Select unused for the empty ones) and click Delete. Empty layers go right away; for layers
  that still hold objects, it asks whether to delete them too or keep them. One Undo brings
  everything back.
- The Panel tab has the layers too: the current layer, the list of layers to show, hide,
  lock or unlock, Layers..., Color, Hide layer and Show all.

**Fixed**
- A layer used only by the title block could be deleted as if it were empty.
- Black objects (or a black layer) no longer disappear on the black drawing: they are drawn
  white there, and still print black.
- DIN rail and wire duct always go straight (a snap a little off the line made them slant),
  and stretching an end keeps them straight. To center things on a rail, snap to a mounting
  slot's center, the middle of an edge, or anywhere along its centerline.

## 0.12.3

**New**
- The ribbon shows each group's name under its buttons (Rail and duct, Dimensions, Blocks...),
  so things are easier to find. View > Ribbon group names turns them off.
- Typing PANDUIT starts Wire duct.
- Hold Shift with a window or lasso to take everything it catches out of the selection (as
  Shift+click does for one object).
- Blocks can carry a catalog (part) number too: Make block and Block properties ask for it,
  placing the block fills it in, and the Library's search finds it.

**Fixed**
- Imported DXF and DWG drawings lost their dimension values and all their multi-line text
  (MTEXT): they come through now, each where it belongs.

## 0.12.2

**Fixed**
- Measuring: the second point of a dimension snaps again with Ortho on (Ortho no longer bends
  the points a dimension measures), and the corners, ends and middles of footprints and other
  placed blocks snap too, as in AutoCAD. Wires still go to a symbol's pins first.

## 0.12.1

**Fixed**
- A quick drag to select (press, move fast, let go) selected nothing. It now selects as a
  window from where you pressed to where you let go: left to right what is wholly inside,
  right to left what it crosses too. Drawing a loop around objects is still a lasso.
- With Ortho on, object snaps no longer grab points far from the crosshair: they are looked
  for where the crosshair is, on the Ortho line, not where the mouse really is.

## 0.12

**New**
- Symbols and footprints can say who makes them: **Manufacturer**, **Family** and **Series**
  (all optional). Each field explains itself, offers what your library already holds, and a
  "?" button opens a short section of the manual about what they mean.
- The Library popup searches them too, and two lists above the symbols show one
  manufacturer's or one family's blocks. Placing a block fills in its manufacturer.
- **Properties...** changes a library block's name, category, description, manufacturer,
  family, series and pin names. Renaming it keeps your parts linked to it.
- **Edit block...** opens a library block's drawing in a tab of its own, with its pins and tag
  shown as texts you can move, rename, copy or erase. Change it with any command, then
  **Save block**.
- After a block is changed, KanzonasCAD asks whether to update its copies in your project:
  one step (Undo takes it back), and the wires stay on the pins.
- **Align objects** on the Panel tab lines up footprints, DIN rail and duct: left, center,
  right, top, middle or bottom, to one of them you pick.
- Ctrl+arrow keys move the selected objects one snap step (1/8 inch to start);
  Ctrl+Shift+arrow keys move them a tenth of that. Wires on a moved symbol come along.

**Fixed**
- Footprints made from a manufacturer's drawing (thousands of lines and arcs) no longer make
  the program freeze: moving one, hovering over one and snapping near one are quick again.
- Opening a DXF or DWG drawing (with a double-click, or Open...) showed it in a random place,
  sometimes off the page. The drawing is now put on the sheet and shown: moved to the middle
  when it was drawn somewhere else, and, when it is bigger than the sheet, the sheet gets a
  scale it fits at (the drawing stays its real size). Importing into a sheet keeps its
  coordinates, as before.
- Import DXF or DWG remembers the folder you last imported from.
- The list of running object snaps (the arrow next to OSNAP in the status bar) stays open
  while you tick and untick snaps, so you can set several in a row. Click outside it or press
  Esc when done.
- Make block on a panel sheet starts on Panel footprint (on Schematic symbol on other
  sheets).

## 0.11.9

**Fixed**
- Moving the mouse while drawing, with object snaps on, no longer lags behind on a busy sheet
  (it was worst zoomed out, and still noticeable zoomed in). The crosshair and snap markers
  now follow the mouse without the whole drawing being drawn again on every move.

## 0.11.8

**New**
- A violet icon, so KanzonasCAD is easy to tell apart from KanzonasPDF on the taskbar, the
  desktop and the Start menu (both were red). The logo in Help > About is violet to match.
  Your projects, library and settings are not affected.

## 0.11.7

**New**
- Rotate a sheet: Rotate sheet clockwise (Ctrl+Shift+Plus) and Rotate sheet counterclockwise
  (Ctrl+Shift+Minus), in the Sheets menu. The border, zones and title block turn with the
  sheet, and your drawing stays upright: a tall, narrow cabinet on a tall sheet.
- The Sheet scale window says when turning the sheet would print the drawing bigger ("1:4
  instead of 1:8") and turns it in one click.

## 0.11.6

**New**
- Setting a panel sheet's scale is easier. Sheet scale... shows the sheet with your drawing on
  it at the scale you pick, says what the scale means ("1 inch on paper = 4 inches of panel"),
  and turns red when the drawing is too big, naming a scale that fits.
- Fit picks the biggest scale at which everything fits, clear of the title block. Before
  anything is drawn, give the cabinet's width, height and depth: Fit leaves room for its front
  and its side.
- Click Scale in the status bar for Fit and the common scales in one click. It warns
  ("doesn't fit") when the drawing runs past the border, and Export to PDF asks first.

## 0.11.5

**New**
- A portable version for Windows (the portable zip on the Releases page): unzip it anywhere, a USB
  stick say, and run it. Your settings, library and recovery copies stay in a data folder
  beside it, and nothing is left on the computer. Update now keeps that folder.
- Linux: KanzonasCAD-x86_64.AppImage, one file that runs on Ubuntu 22.04, Debian 12, Fedora 36
  and newer. Make it executable and run it; Update now replaces it with the new version.
- A KanzonasCAD Portable package for the PortableApps.com Platform is on its way.

## 0.11.4

**Fixed**
- Opening a damaged DXF file could garble long multi-line text; DXF files saved in the Korean
  Johab code page couldn't be read. (The DXF library, ezdxf, updated to 1.4.5.)

## 0.11.3

**New**
- A refreshed logo, matching KanzonasPDF's letter for letter. Help > About KanzonasCAD now shows it.

## 0.11.2

**Fixed**
- Moving two symbols with a wire between them could crash KanzonasCAD and lose the move (when
  they moved exactly the wire's length). The wire now moves along with them.

## 0.11.1

**Fixed**
- Drawing on big sheets is much faster: on a sheet with 12,000 wires, adding a wire (with its
  number, dots and crossings) takes about a twentieth of a second instead of more than half a
  second.
- Wire numbers no longer sit on top of a crossing's loop or gap.
- On/off menu items (Help > Check for updates automatically, View > Grid display, Snap to
  grid...) show a check box, so you can see whether they're on.

## 0.11

**New**
- Project templates: set a project up once (settings, wire colors, title block and its fields,
  even sheets) and File > Save as template.... New projects start from it, or pick one with
  New project from template....
- Edit > Options...: the theme, library folder, template for new projects, how many backups to
  keep, how often to autosave, and the drafting settings, in one place.

## 0.10.12

**New**
- Delete component: deletes a symbol and joins its wire back up, so deleting a contact
  leaves the rung whole. The Delete key still just erases.

## 0.10.11

**New**
- Two wires on one terminal: a second wire on a pin leaves it on a short angled lead, then runs
  straight beside the first. A third goes on the other side.

**Fixed**
- Three or more wires on a pin no longer get a junction dot.

## 0.10.10

**New**
- Trim wire: click a piece of wire and it goes, up to the nearest wire or pin. No cutting
  edges to pick.
- Delete wire: deletes only the wires among the selected objects, or the wires you click.
- Clean up wires: joins wires that meet end to end, removes wires drawn twice or of no
  length, and tells you how many wire ends connect to nothing.
- Wires are cleaned up as you draw: a wire carried on from another's end joins it, and one
  drawn over another isn't added twice (Project properties, Schematic, to turn it off).

## 0.10.9

**New**
- Title block position (Project properties, General): in the lower right corner, as a
  right-hand strip, or along the bottom. With a strip the zones stop at the title block, so
  grid references never point into it.
- A ready-made title block for each position, with the same fields (Undo puts yours back).

## 0.10.8

**New**
- The last AutoCAD snaps: Extension, Parallel and Apparent intersection, with AutoCAD's
  tracking (hover over a line or its end first).
- Turn each snap on or off from the status bar: the arrow on OSNAP lists them all.

## 0.10.7

**New**
- Scoot: slide devices along their wire, as in AutoCAD Electrical. The wires follow, and the
  device never leaves its wire.
- Align devices: line devices up on their own wires (the same column on rungs), as AutoCAD
  Electrical's Align.

## 0.10.6

**Fixed**
- Text could come in huge: a second click set its height, and every new text kept it. Now you
  click once and type. Type H, R or J before clicking for the height, rotation or
  justification. A height left huge goes back to 1/8 inch.
- Saving several times within a second could keep the wrong backups (and delete the newest
  ones). Backups are now kept in the order they were saved.

## 0.10.5

**New**
- Undo and Redo arrows right after the menus.
- Layers, quickly: a layer list with a light bulb and a lock for each layer; Hide layer, Show
  only this layer, Show all layers, Lock layer and Unlock all layers.

**Fixed**
- The Sheets menu listed dimension, DIN rail, wire duct and wire crossing commands that belong in Draw.

## 0.10.4

**New**
- Object snaps as in AutoCAD: Node, Perpendicular, Tangent, Nearest and Geometric center join
  Endpoint, Midpoint, Center, Quadrant, Intersection and Insertion. Choose the ones that run
  all the time in Drafting settings.
- A snap for one point: type PER, TAN, NEA... at a point prompt, or Shift + right-click.

## 0.10.3

**New**
- Wire crossings: choose how wires that cross are drawn, plain, with a gap or with a loop
  (Project properties, Schematic). They're found by themselves.
- Wire crossing (WX) adds one by hand where one wasn't found, or hides one (N).

## 0.10.2

**New**
- A bigger CAD on the icon (and on the installer's blue one).

## 0.10.1

**New**
- KanzonasCAD has its own icon: the KanzonasPDF cactus and sunflower with a green CAD tag. It
  shows in the window, the taskbar, the Start menu and on .kzcad files. The installer's icon is
  the same in blue, as KanzonasPDF's is.

## 0.10

**New**
- DIN rail (TS35 x 7.5, TS35 x 15, TS15) and wire duct (2 x 3, 50 x 75 mm... any size) at
  real size: click both ends or type the length, and stretch them with their grips.
- Panel materials: how much rail and duct the project takes, how many stock lengths that is,
  and the cut lengths. Save it as CSV.

## 0.9

**New**
- Panel sheets have a scale (1:4, 3" = 1'-0"...): draw the panel at real size and it prints at
  that scale, with the border, title block and text at their normal size. Sheet scale... on
  the Panel tab, or click Scale in the status bar.
- Dimensions: Linear dimension (DLI) and Aligned dimension (DAL) measure the real distance.
- {Scale} for the title block. Footprints can't be scaled by accident on a panel sheet.

## 0.8

**New**
- Open and import AutoCAD DWG drawings directly (AutoCAD 2018 format and older, which is what
  every current AutoCAD saves), with nothing to install. File > Open... or Import DXF or DWG
  into this sheet....
- If a DWG can't be read and the free ODA File Converter is installed, KanzonasCAD uses it by
  itself.

## 0.7

**New**
- Three-phase symbols: 3-pole breaker, disconnect and fuses, contactor power contacts, overload
  heaters, a 3-phase motor and a VFD. Their poles line up with a 3-wire bus.
- Terminal strips: terminals belong to a strip, show its tag and number themselves 1, 2, 3.
- PLC I/O: input and output points belong to a PLC card, list under it and show their address.
- A power supply (AC in, DC out).

## 0.6

**New**
- Wire numbers: every wire gets its number by itself (6001, 6002 on page 6), one per connected
  wire, and keeps it. Double-click a wire to type your own; Renumber sheet puts them in order.
- Distribution blocks: the wires coming out take the incoming number with A, B, C added.
- Off-sheet connectors: a wire continuing on another sheet keeps its number, and each end
  shows where the other one is.

**Fixed**
- Trimming a wire turned the pieces into plain lines.

## 0.5

**New**
- Contacts belong to their coil: place a contact and press Enter to take the nearest coil, or
  type a tag. The contact shows the coil's tag and follows it when it changes.
- Cross-references: under each coil, a list of its contacts and where they are (NO 6-D3);
  under each contact, where its coil is (6-D1). They update by themselves.
- Freeze cross-references on an issued sheet, or turn automatic updates off for the project
  and use Update cross-references. The status bar tells you when they're out of date.

## 0.4.1

**New**
- A Windows installer: download `KanzonasCAD-v0.4.1-setup.exe` and run it. Install it for
  yourself (no administrator rights needed) or for everyone on the PC. You get a Start menu
  entry, and .kzcad projects open with a double-click.
- An installed KanzonasCAD updates itself with Update now. A copy installed for everyone asks
  for administrator rights first.

## 0.4

**New**
- Devices tag themselves by page: CR601, CR602, M601 on page 6. Copies get their own tag, and
  tags follow when a sheet's page number changes.
- Type a tag yourself and it stays (locked). Renumber sheet puts the rest in order, across then
  down or down then across.

**Fixed**
- Mirror, keeping the originals, could replace an original instead of adding the copy.

## 0.3.3

**Fixed**
- The tool icons vanished when Windows was in dark mode. Light, Dark and Same as system now
  mean exactly that, and the icons always stand out from what's behind them.

## 0.3.2

**New**
- KanzonasCAD now updates itself: it checks for new versions once a day, shows what changed,
  and Update now installs it (Help > Check for updates...).
- Each new version is published on the Releases page with a Windows download.

## 0.3.1

**New**
- The Library opens as a popup (Insert symbol, Insert footprint) instead of taking room at
  the side of the drawing, as AutoCAD Electrical's icon menu does.
- Circle has AutoCAD's other ways: center and diameter, 2-point, 3-point, tangent to two
  objects with a radius; the ribbon button shows the one used last.
- Bus: several wires side by side, as many turns as you need, all turning together.
- Lines on screen are drawn crisp, as in AutoCAD.

## 0.3

**New**
- Wires (W): click to click, straight across and up or down; a wire ends by itself on a pin
  or another wire, with a dot where wires join.
- Moving a symbol drags its wires along; dropping a symbol onto a wire wires it in.

**Fixed**
- Starting another command no longer throws away a wire or polyline being drawn.

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
- Sheets start with rows A to H; the zones along the top and down the left are editable
  (how many, and where they start), and references follow them.
- Project properties (General, Schematic, Panel) and Sheet properties, as in AutoCAD
  Electrical: sheets follow the project's size and zones unless they have their own, and can
  have their own revision.
- Automatic backups: each Save keeps the version before it (the last 10), and unsaved work
  is autosaved every 5 minutes and offered back if KanzonasCAD didn't close normally.
- Sheets have a type (Schematic, Panel, Report, Other) that brings up the matching ribbon tab.
- Schematic and Panel ribbon tabs; objects take their layer's color unless you give them
  their own (Color...); wire, symbol, footprint and dimension colors in Project properties.
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
