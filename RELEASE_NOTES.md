# Release notes

Short, plain-language notes for each version. The full details are in
[CHANGELOG.md](CHANGELOG.md).

Every version gets a section `## <version>` (a few lines under **New** and **Fixed**). The
build fails without them.

## 0.20.1

**New**
- Report sheets (Sheets > Report sheet...): the bill of materials, wire list, terminal strip
  list, pull list or panel materials drawn as a table on sheets of the project, so they print
  with the drawings. Update report sheets draws them again after changes.

## 0.20

**New**
- DXF export keeps symbols and footprints as AutoCAD blocks: each one defined once and placed
  where it is used, with its tag, description, maker, catalog number, location and ratings as
  attributes (the ones shown on the sheet shown in AutoCAD too, the others hidden), so AutoCAD's
  attribute editor and data extraction work on them. The DXF opens again in KanzonasCAD with the
  same symbols, pins and attributes. Edit > Options... turns it off for plain lines and texts.

## 0.19.12

**Fixed**
- A bus no longer runs its wires through a symbol's pins: leaving its pins back through the
  same symbol's other pins, or carried on across another symbol it couldn't land on. That click
  isn't taken, and the command line says which pin is in the way.
- A source or destination arrow's reference with the device on a second line now keeps both
  lines clear of its wire, also where the wire loops round the arrow.

## 0.19.11

**Fixed**
- Wires feeding a column of devices (each drive's S1 drawn on from the corner of the wire
  above) now number each drop as a tap (9005-1, 9005-2...) instead of all sharing the run's
  number. For a drawing made before this version, run Clean up wires on the sheet once.
- Source and destination arrows carried down one ladder, across to the next ladder on the same
  sheet, and on to another sheet now show the right places: the left ladder's foot shows the
  right ladder's head, and so on. A source with nothing after it yet shows "?".
- A wire carried by a source arrow keeps a number of the source's page. A number locked on a
  destination's wire on another page no longer takes the source's wire over (page 2's wire
  taking a page 11 number).

**New**
- A destination arrow paired with List... or Pick on drawing now stays linked to that source
  arrow: it shows that one, and follows it when its wire is renumbered, until you delete that
  source arrow. Double-click a destination arrow to change it (Comes from) or set it back to
  Automatic.

## 0.19.10

**New**
- Contact blocks for pushbuttons, emergency stops and selector switches (Library,
  JIC/Pushbuttons and switches: Pushbutton contact NO/NC, Selector switch contact NO/NC): more
  contacts of one operator on other rungs. Placed straight above or below it, they are joined to
  it by a dashed line drawn by itself, which follows them when they move. Only the operator
  shows the tag; blocks on the line don't repeat it.
- A Save button just left of Undo and Redo, after the menus.
- Bus can start from pins you pick one at a time: type P (Pick pins), click each pin (a safety
  relay's S52, S12, S21 and S22, say, skipping S11), and press Enter. The pins must be on one
  side of one symbol and evenly spaced.
- A wire you draw from or onto another wire (a tap, or carrying it on) now goes on that wire's
  layer, so it has the same voltage, color and gauge, whatever layer is current. A wire that
  joins wires of two different layers stays on the current layer, and the command line warns
  you that it may tie two conductors together.
- Changing a sheet's kind in Sheet properties (to Panel, say) while nothing is drawn on it now
  sets its scale to the project's scale for that kind. A sheet with a drawing keeps its scale.
- The device under a source or destination arrow's reference now skips terminals and shows the
  device past them (PLC1 rather than TB1-12). A terminal with nothing past it still shows.
- The 45-degree lead of a second wire on a pin is now 1/4 inch on paper (it was 1/8). On pins
  closer together it keeps off the next pin's wire, going the other side or getting shorter.

**Fixed**
- Copying, moving or pasting a symbol (a breaker, say) onto a wire now cuts the wire and lands
  it on both of the symbol's terminals, as inserting it there does.
- With the 45-degree lead on, a jumper between two pins one above the other (S11 to S52) now
  goes straight out, straight down and down the lead, instead of running past the lead and back.

## 0.19.5

**Fixed**
- A wire carried over several sheets by source and destination arrows: each arrow now shows
  only the next or previous sheet's arrow, not every arrow of that wire.
- The device under an arrow's reference is now the one device that wire goes straight to on
  the other sheet. When the wire tees off there, or goes on to another arrow, no device shows.

## 0.19.4

**New**
- Set the scale new sheets start at for the whole project: New panel sheets' scale (Panel
  settings) and New sheets' scale for schematic sheets (Schematic settings). Each sheet can
  still have its own scale (Sheet scale, the status bar, Sheet properties); sheets you already
  made keep theirs.

## 0.19.3

**New**
- Source and destination arrows now show, on a second line under their reference
  (4001 / 9-D2), the device the wire goes to at the other arrow (VFD201). Turn it off for the
  whole project (Project properties, Schematic), for one sheet (Sheet properties), or for one
  arrow (double-click it); each of those can override the one before.

## 0.19.2

**New**
- A contact's cross-reference (where its device is, 2-E6) can be moved: select the contact and
  drag the grip under it, inside a big block if you like. It stays there when the block
  moves or turns.

**Fixed**
- Picking the device a contact belongs to on the drawing (P), or the arrow a destination pairs
  with (Pick on drawing), now uses the pick box, and the device under the cursor lights up as
  you go over it. Before, the cursor was the drawing crosshair and nothing lit up.

## 0.19.1

**New**
- Wire list... and Terminal strip list... (Sheets menu, Output tab: Reports): every wire by
  number with its size and color and what it lands on (CR1:A1 (6-B3), TB1-4 (6-C1)), and every
  terminal with the wires on its left and right. Save as CSV for Excel or a label printer.
- PLC analog input modules with two terminals a channel (IN/RTN: IN-0 on terminal 2 above
  RTN-0 on 1), of 4, 8 or 16 channels.
- A PLC module over two sheets: "points 0-7" on the first (its tag and slot) and "points 8-15
  continued" on the next, which belongs to the module, shows its tag and CONTINUED, and
  follows it when it's retagged.

**Fixed**
- The tag of a symbol turned sideways, dragged onto the symbol's own line, could jump from one
  side to the other when the symbol was moved. It now stays centered on its spot.

## 0.19

**New**
- PLC I/O modules drawn whole (Library, JIC/PLC): a box with the catalog number at the top
  and the terminals down the left, one a rung, each with its number and what it is
  ("0  IN 0"); wires land on them and keep their own numbers. Its slot shows over the catalog
  number. Rockwell POINT I/O as their wiring diagrams give: 1734-IB8, OB8, OB8E, IE8C, OE4C,
  VTM and CTM. For other makes, generic digital and analog input and output modules of 4, 8
  or 16 points (Edit block renames their terminals). They go on the Bill of materials with
  their catalog number.

**Fixed**
- A bus started on a symbol's pins and taken back through that same symbol (from a
  disconnect's L side toward another to its right, say) no longer claims to land with its
  wires cut under the symbol: it says why, and how to start it from the other side.

## 0.18.7

**New**
- Source arrows follow their wire's number: renumber the wire (or the sheet) and the source
  arrow takes the new number; its destination arrows follow their source. A wire carried on
  by arrows is numbered on its source's page.
- The Schematic tab has the layer box and layer list too (its Layers group, with Wire
  layers), as Home and Panel do: pick 24VDC BLU and draw, without going back to Home.
- Footprint labels (tag, part number...) in a color of their own: Panel settings, Footprint
  label color. A tag stays readable on a white footprint on layer 0.
- The Schematic and Panel tabs are laid out alike: drawing first, then Symbols or Footprints
  (the same buttons in the same order), Modify, Dimensions, the tab's own tools, and Parts,
  Layers and Settings at the right end. Stretch is on the Panel tab too.

**Fixed**
- A footprint linked to a device keeps its own manufacturer, catalog number and description
  (typed on it, or set in its block's Properties...) instead of taking the device's; the
  device's fill in only what the footprint doesn't have. Its window shows the footprint's
  greyed where the copy has none, and its label shows the block's description too.
- Double-clicking a sheet in the Sheets list opens its Sheet properties again: the first
  click rebuilt the list under the mouse and the second click was lost.
- Wire numbering's tap bookkeeping no longer depends on which wire it looks at first when two
  wire ends are a hair apart.

## 0.18.5

**New**
- Placing a destination arrow (or an off-sheet connector), pick exactly which one it continues:
  List... on the command line shows them with their wire number and place, waiting ones
  first; Pick on drawing lets you go to that sheet and click it. Typing a name still works.
- Drawing a second wire on a pin asks how it's numbered, as a tap does: Enter as the project
  numbers taps (2001-1), S the same number, N a number of its own. Double-click it to change
  it later.
- Wires side by side that share a gauge label get a thin oval drawn across them with a short
  leader out to the label ("12 AWG"). Gauge labels are now in DXF exports too.
- Turn a layer's gauge label off: click its Gauge shown in Layers... (control power all 16 AWG
  blue, say). Project properties still turns them all off at once.

**Fixed**
- A bus started (or ended) on pins that already have wires leaves each pin on a 45-degree
  lead, as a single wire does, when "A second wire on a pin leaves it on a 45-degree lead" is
  on. Before, a bus came straight off the pins.
- In Edit block, an attribute's alignment (middle center for a rating, say) and angle are kept;
  they went back to baseline.
- Leaving a block's tab, the ribbon goes back to the tab you were on instead of Home.

## 0.18.4

**Fixed**
- Taps you had set one by one (a number of their own, or the wire's number) kept that choice
  when you changed "Wires tapped off a wire are numbered" for the project. Project properties
  now has "Apply to taps set one by one too" under it (ticked when you change the setting):
  every tap then follows the project, in one step.

## 0.18.3

**New**
- Wires tapped off a wire (the drops off a bus) are numbered from it: off bus wire 2007, the
  drops are 2007-1, 2007-2, 2007-3 in the sheet's numbering order, and a tap off a tap is
  2007-1a. A drop where the bus wire ends and another carries on straight counts too.
  Project properties, Schematic, "Wires tapped off a wire are numbered" chooses this,
  the same number as the wire, or a number of their own. New projects start with -1, -2;
  projects from before keep their numbers until you change it.
- Drawing a tap asks as before: Enter numbers it as the project says, S keeps the wire's
  number (a ladder branch, say), N gives it a number of its own. Double-click a tap to change
  it later.
- Turn the border and zones, and the title block, off and on: for every sheet in Project
  properties (General, "Show on sheets"), or for one sheet in its Sheet properties (as the
  project, shown, or off). What's off isn't drawn, printed or exported.
- Dimensions in fractions: Project properties, Panel, "Dimension units" (decimal, or to the
  nearest 1/8, 1/16, 1/32 or 1/64: 1-9/16"). Dimension units (Modify menu, DU) changes the
  dimensions you select: D decimal, F fractional, or type 1/32.
- Wire gauge labels sit in line with the wire number ("2018  12 AWG") where the wire has room,
  are smaller and show the gauge only ("12 AWG"), once for wires side by
  side (a starter's conductors to its drive, a bus), beside the outside wire. Wire color label
  (Modify menu, WCL) adds the color on the wires you pick ("12 AWG BRN"). Project properties,
  Schematic: "Gauge label height", and "Gauge and color shown" to put it on every wire.
- A source arrow placed on a numbered wire takes the wire's number as its name: nothing to
  type. A destination arrow's wire takes the source's number and its layer too.
- Duplicate sheet (Sheets menu and tab): a copy of the sheet shown, everything on it, on a
  page of its own, its devices and wires numbered for that page.
- Each source or destination arrow shows only its other half's place: a destination its
  source, not every arrow of that name.

**Fixed**
- A gauge label no longer sits on another wire's number: it moves along its wire to a clear
  spot.
- Pasting into another project brings the layers that project doesn't have with their colors
  and settings; a layer it already has keeps its own.
- A wire end moved by Stretch or a grip that stops less than 0.01" from a pin or another wire
  is put on it, instead of being left a hair short and not connected.
- A wire crossing's loop (or gap) is drawn in the colors of its own wires, stripes too, and
  exported on the jumping wire's layer. Before, it kept the default wire layer's color after
  the wires were moved to another layer.
- The text of a source or destination arrow turns with the arrow: on a wire running up and
  down it reads up, in line with the wire past the arrow's tip, instead of lying level.
- Tracking (Extension) now picks up a midpoint, a center or a quadrant you hover, as AutoCAD
  does: hover the middle of a box's edge, move straight down, and text or a part centers under
  it. Before, only ends, intersections, pins and insertion points were picked up, and Parallel
  took the point.

## 0.18.2

**New**
- Add wire layers... (Format menu, Schematic tab): layers for 480 V (BLK, RED, ORG, BRN, YEL, a
  WHT neutral and a GRN ground, 12 AWG), 120 V (RED, BLK, a WHT neutral, 14 AWG), 24 VDC (BLU,
  and a blue common with white stripes, 16 AWG) and Ethernet (green), with their colors, sizes
  and wire colors. Pick one as the current layer and draw.
- Wire size (Modify menu, Schematic tab: Edit wires): give wires a gauge of their own (10, 1/0,
  250 kcmil), or L for their layer's again. Their label shows it.
- A wire color of two names, BLU/WHT for one, draws the wires striped, on the screen and
  printed.

**Fixed**
- Editing a wire duct's size (or maker) in its Properties window took its light hatch (the
  mask, Panel settings) off it. It stays now.
- A Move or Copy typed (@0,-0.5, say) with the object snaps on could go a different distance
  than typed, for the whole selection, when a footprint in it came over a DIN rail: the rail
  magnet pulled it. Typed points and distances now go exactly as typed; the magnet works for
  the mouse only.
- With every object snap on (Extension among them), moving the mouse over big footprints (a
  maker's drive drawings) lagged, in Move most of all. It's about five times quicker.
- With everything selected on a heavy sheet (a panel of maker drive footprints), every mouse
  move lagged. It's quick now, and Select all itself takes about half the time it did.
- Printing a heavy sheet (a panel with maker footprints, wire duct, rails and dimensions)
  could leave whole groups of objects off the paper on Windows, though the screen and a PDF
  were right. They print now.
- A kcmil size showed "250 kcmil AWG"; it now shows "250 kcmil".
- Wires of different layers or sizes meeting end to end are no longer made one wire (one would
  lose its layer or size).
- Scoot with everything attached could pull a wire off another device's pins, when a wire of
  the branch ran on through them. It now refuses that move and says why.
- A rectangle's (or dashed box's) size typed after its first corner, 72,72 say, now goes the
  way the mouse is from that corner. It always went up and to the right. A sign typed (-72 or
  +72) still says which way.
- Clicking off the running snaps menu (the arrow by OSNAP), or off a right-click menu on the
  drawing, only closes it: it no longer also clicks on the drawing (on Windows it put the
  point there).
- A dimension's second point (or any point after the first) snaps Nearest under the mouse:
  a Perpendicular point anywhere in the snap box went first. Perpendicular and Tangent now win
  only when they are close to the mouse.
- Dragging a run of a wire by its middle grip onto the wire's own run beside it could fold the
  wire back over itself (a hidden corner). It's now refused, saying why.
- A bus ended on a symbol's pins could go on instead of landing, when another symbol shared the
  first pin of that side. It now lands, as its preview showed.
- Center snap found an arc's center when zoomed in, on arcs less than half a circle (a
  breaker's, for one); zoomed in, it didn't.
- Scoot could leave a moved device's pin with no wire, when a wire leaving the branch ran
  through that pin to a far end that stays. It's now refused, saying why.

## 0.18.1

**New**
- A footprint can show **several things at once**: Footprint label's Show tag, Show part
  number, Show description and Show block name each turn a line on or off (a tick shows
  what's on). Double-click a footprint for everything it can show.
- **Each line has a grip**: drag it to put that line anywhere on or beside the part. It moves
  and turns with the part.
- Footprint labels are **smaller**: 0.08" on paper to start. Panel settings has **Footprint
  label height** to change it for the whole project. Projects made earlier take 0.08" when
  opened.
- **Wire numbers keep out of the way**: a number moves along its wire, or to its other side,
  to a spot clear of other wires, symbols, texts and numbers. With no room anywhere beside the
  wire, it goes off to the side with a short line back to the wire.
- **Duplicates are marked**: a device tag or wire number used twice anywhere in the project
  gets a red frame on the drawing until you fix it (it doesn't print), and the command line
  says which when one appears. Wires joined by connectors or arrows, and a number kept with
  "just the same number", aren't duplicates.
- A footprint linked to a schematic device has the **device's ratings** (horsepower, volts,
  amps...). Its window lists them; change one there or on the symbol and both have it. Tick
  one to show it on the footprint (5HP, 480V).

## 0.18

**New**
- **Source/destination arrows** (Schematic tab, Cross-references; Draw menu): click the open
  end of a wire where it leaves, then the open end where it arrives, on this sheet or another.
  A Source arrow and a Destination arrow go there; the wires become one wire with the source's
  number, and each arrow shows that number and where the other is (2046 / 7-A2).
- **Update numbers and cross-references...** (Schematic tab, Numbering; Sheets menu): device
  tags, wire numbers and cross-references, together or apart, on this sheet, the sheets you
  tick or the whole project. Renumber them in order, or keep them and only fix what's missing
  or on the wrong page. One Undo takes it back.
- The Library can show only **three-phase** symbols, or only single-phase and control ones
  (the third list above the symbols). Block **Properties...** has Phases to correct the guess.
- **Lock numbers...** (Schematic tab, Numbering; Sheets menu): lock or unlock wire numbers and
  device tags as they are, for the selected ones, this sheet, the sheets you tick or the whole
  project. Locked ones stay when you renumber.
- **Stretch** (S; Modify menu, Home and Schematic tabs): drag a window over the ends of a bus's
  wires and move them all at once; the wires stay square. Or Shift+click several grips (they
  turn red) and drag one: they all move together.
- Numbering can **follow your bus**: **Numbering source** (Schematic tab, Numbering): click
  the disconnect the wires start from, and Renumber numbers each branch in the order it leaves
  the bus, however the bus winds round the sheet, with the branch's wires numbered together.
- Whether wire numbers follow the tags' order is a project setting (Project properties,
  Schematic) and a sheet setting (Sheet properties) that can override it.
- **Wire duct** is drawn from a corner: click one corner and the other end of that edge; the
  duct goes on the side the cursor is (F for the other side). It now shows its finger slots
  and mounting holes, and Panel settings can add a light hatch to every duct.
- A connector's cross-reference text is always outside it, on the side away from its wire,
  however the connector is turned, and moves over or under it when the wire comes back round
  past that side.
- Cross-reference text is on a layer of its own, **XREFS**, in cyan, and a little smaller.
  Projects made earlier get the layer and the new size when opened.
- The ribbon fits the window: when a tab is too wide, its groups shrink from the right (big
  buttons become small ones, then icons with their names as tooltips) and grow back when you
  widen the window.
- A block's tools (Save block, Save block as, Block properties, Duplicate block, Add pin, Pins)
  are on a new **Block** tab that shows up while you edit a block, instead of on the Schematic
  and Panel tabs. **Edit block** stays there to open one; View > **Block tab** keeps the tab
  shown all the time.

**Fixed**
- Renumbering a sheet could give a device the same tag as a device on another sheet. Update
  numbers' "Keep the numbers" now also fixes a tag two devices share.
- Scooting a device whose pin sits on the corner of a wire (not cut there) could slide the pin
  off the wire. It now refuses that move.
- The Schematic tab ran off the screen.
- Trim on a small circle, clicked right where something crosses it (or in its middle), left
  the circle whole. It now cuts it there.
- Dragging a wire's end straight past its last corner, back along the wire, left a hidden
  corner where the wire ran back over itself. The wire now runs straight to where you drop it.
- **Intersection** didn't snap where a line (or a dimension's point, or a Copy or Move point)
  crosses the edge of wire duct or DIN rail, or where duct and rail cross. It does now.
- Carrying a bus on from its open ends with a symbol in the way could route one wire onto the
  bus's own other ends (a stray dot and tangled wires). The bus now leaves its ends straight
  on, and a way round whose wires would touch isn't used.
- Moving or stretching something so a wire's end went back along its own last leg left a
  hidden corner where the wire ran back over itself. The wire now runs straight. Clean up
  wires could also join two wires into one that ran back over itself; it no longer does.
- Typing a wire number that two other wires already had (one kept with "just the same
  number") and answering Source or Destination could say there was no open end when one of
  them had one. The arrow now goes on the one with an open end.
- Dragging a run of wire by its middle grip could leave a symbol's pin with no wire, when a
  wire tapping that run passed through the pin. Such a drag is now refused, with the reason.
- Scooting a breaker with everything attached, or stretching a wire's end onto its other end,
  could squeeze a wire down to nothing and leave it broken. That wire is now removed.
- Copying or moving a footprint to a point you snapped to near DIN rail pulled it onto the
  rail, away from the point you picked it up by. A snapped point now wins.
- Placing a footprint with the same name as a symbol already in the project gave the
  footprint the symbol's drawing. The footprint now keeps its own (as "name (footprint)"), and
  updating one from the library no longer changes the other.

## 0.17.5

**New**
- Motors, drives, starters, breakers, disconnects, fuses, overloads, the control transformer
  and the power supply have fields for their ratings: horsepower, volts, amps (full-load amps
  for a motor), VA and primary/secondary volts, as applies. Type a number (5) and it shows with
  its unit (5HP), each on its own line under the symbol. The bill of materials lists them.
- Double-click a symbol: each attribute in **Shown on the drawing** has an **Angle**, to turn
  its text (the tag too). Hide or show any of them there, or for many symbols at once with
  Modify > Show or hide attributes...
- Projects started earlier get the new fields with **Update blocks from library...**.
- The **Wire number** window has **Lock this number**, as tags have: it ticks itself when you
  type a number; untick it to let numbering change the number later.
- Typing a wire number another wire already has asks whether it's a cross-reference:
  **Source** or **Destination** puts a **Source arrow** and a **Destination arrow** (new in the
  Library, JIC/Wiring) on the open ends of the two wires, so they become one wire and each
  shows where the other is. Or keep just the same number. A source arrow sits on the end of
  its wire pointing away from the line, a destination arrow's tip touches the line pointing
  into it, and past each the wire's number and the other's place (2046 / 7-A2).

**Fixed**
- Moving, scooting or turning a symbol with two pins of the same name (a drive with two GND
  pins) left the wire on one of them behind. Both now come along.
- A three-pole fuse block listed its Rating three times under Shown on the drawing.
- Edit block lost the stacking and angle of a symbol's attribute texts when saving.
- Junction dots show only where a wire taps off another. A wire drawn out and then clicked
  straight back over itself made a hidden corner that showed a dot: Wire and Bus no longer take
  that click, and **Clean up wires** straightens such wires in drawings you already have.
- A bus clicked onto a 3-pole device whose pins line up with another device's (stacked half an
  inch apart) could land one pin over, on the other device. It lands on the pins you click.
- A bus fanned onto a device's pins could leave a wire jogging over and straight back along
  itself.
- Scoot with everything attached could leave a pin off its wire: a pin on a wire's corner, or
  a device whose pin sits on the middle of a wire that moves along. That device now comes
  along, or Scoot refuses the move.

## 0.17.4

**New**
- The **Variable frequency drive** has a ground on each side: PE1 on the line side and PE2 on
  the load side.
- **Linear dimension** and **Aligned dimension** follow Ortho and Polar (an object snap at the
  mouse still comes first), and the dimension tools are on the Home and Schematic tabs too.
- **Extension** snap: where the dotted tracking line crosses a line, a wire or a circle, that
  crossing snaps.
- **Scoot** moves a device with everything attached to it: scoot a motor and its drive and
  contactor come along with the wires between; its drops slide along the bus (or stretch, when
  you scoot toward or away from the bus). Type O to slide only the selected device along its
  own wire, as before.

**Fixed**
- Scoot no longer leaves a wire behind that runs straight through a device's pins across the
  way it moves: it says so and moves nothing.

## 0.17.3

Not released on its own: its changes came out in 0.17.4.

## 0.17.2

**New**
- Drawing a wire off the middle of another asks: Enter keeps that wire's number, N gives the
  new wire a number of its own. Double-click it to change your mind later.
- A wire longer than 6 inches shows its number near both ends (Project properties,
  Schematic, to change the length or turn it off).
- **Wire number label** (Modify menu, Schematic tab): click a wire wherever you want its
  number shown again. It always shows the wire's current number, and moves, copies and is
  saved with the wire.

## 0.17.1

**New**
- Inserting a symbol: **F** flips it horizontally and **V** vertically, as you see it,
  however it's turned.
- A placed symbol's grip is its first pin, where a wire joins it, not its middle.
- Apparent intersection works with circles and arcs: where a line extended would meet one,
  and, with Ortho on, where your Ortho line meets a circle or a line extended.

**Fixed**
- Placing a contact no longer links it to a device unless you choose one: the nearest device
  is offered as a button, and Enter places it on its own.
- The Starter 3-pole is a device with its own tag, not a contact of a coil.
- A bus ended on or near a device lands on its nearest pins, as many as it has wires, on a
  side facing it, jogging in when the pins are closer together or farther apart than its
  wires. Before, it ended where you clicked without connecting.
- A wire clicked on a symbol's drawing goes to its nearest pin.
- Wire crossings are drawn as a loop in new projects (they were drawn plain, so they didn't
  show). Change it in Project properties, Schematic.

## 0.17

**New**
- **Import PDF into this sheet...** (File menu, Output tab): brings in the lines and text of a
  page of a PDF, one a CAD program made or printed, so there's less to draw. Lines, circles and
  arcs come in as lines, circles and arcs, and real text as text you can edit, turned as it
  was. Choose the page and the size (the sheet's scale to start, so it looks as it did
  printed). You can also drag a PDF onto the drawing.
- Text that the PDF draws as letter shapes (many CAD programs print it that way) can't come in
  as text, and a scanned page has no lines in it at all: bringing in pictures and scans comes
  next.

**Fixed**
- A bus started on the pins of a symbol turned at a slant laid its other wires on no pins; it
  now starts there as an ordinary bus.

**Also new since 0.16.6** (0.16.7 wasn't released on its own)
- Wires go around the symbols in their way instead of through them, and arrive at a pin
  straight out of its side. Project properties, Schematic: "Wires go around the symbols in
  their way" turns it off.
- A bus goes around symbols too, all its wires.
- How far wires keep from symbols is a setting (Project properties, Schematic): 1/8 inch to
  start, or 1/4 inch, or what you like.
- Drag a run of wire sideways by the grip in its middle (or with Scoot): the wires on it
  follow and stay connected.

## 0.16.8

**New**
- In a block's tab (Edit block...), **Add pin** adds pins by clicking: click where the pin
  goes, then type its name or press Enter for the next number.
- **Pins...** lists a block's pins with their names and places: rename one, type where it
  goes, drag them into another order, delete one, or find it on the drawing. Undo takes it
  all back in one step.

**Fixed**
- Edit text: "Keep the text where it is on the drawing" no longer starts ticked.
- A bus whose first wire passed just beside a symbol could run its other wires straight
  through it; now it goes around.
- A wire drawn back along another wire from its end was joined to it as one wire doubling
  back over itself; they now stay two wires.
- Wire numbers on extremely long wires no longer slow the drawing down.

## 0.16.7

**New**
- Wires go around the symbols in their way instead of through them, and arrive at a pin
  straight out of its side (a wire from above to a terminal on a drive's bottom edge goes
  down beside the drive and comes up into it). Nothing in the way, a wire is as before.
  Project properties, Schematic: "Wires go around the symbols in their way" turns it off.
- A bus goes around symbols too, all its wires.
- How far wires keep from symbols is a setting (Project properties, Schematic): 1/8 inch to
  start, or 1/4 inch, or what you like.
- Drag a run of wire sideways by the grip in its middle (or with Scoot): the wires on it
  follow and stay connected.

## 0.16.6

**New**
- Symbols can show their pin names (terminal numbers) on the drawing: tick "Show the pin
  names on the drawing" in Make block or Block properties (ticked to start for symbols you
  make). Hide them on one copy like any attribute.
- **Drive control terminals** symbol: a drive's control terminals (S1, S2, S+, 01-08, 11-19,
  R1-R6, C1, C2) with what each one is; it takes its drive's tag.
- **Number texts** (Modify menu, Home tab): number the selected texts 1, 2, 3 / A, B, C /
  S1, S2, S3 / A1, B2, C3 ..., top to bottom or left to right, replacing the text or added
  before or after it.
- The user manual (F1) has its chapters on the left and a search box: type to find, with
  Next and Previous.

## 0.16.5

**New**
- **Array** (Modify menu, Home tab): copies of the selected objects in rows and columns, or
  round a center.
- **Offset** (Modify menu, Home tab): a copy of a line, rectangle, polyline, circle or arc a
  set distance away, smaller or bigger, on the side you click (T: through a point).
- Rectangles and polylines have a grip in the middle of each side: drag it to make it longer
  or shorter.
- Rectangle: D asks the length and the width.
- Trim lights up only the piece a click would cut away, not the whole object.

**Fixed**
- A rectangle's size typed after its first corner (0.19,0.15) is now its size, as in AutoCAD.
  It used to be taken as a point on the sheet, giving a much bigger rectangle. Type #x,y for
  a point.
- Mirror shows the mirrored objects while it asks whether to erase the originals.

## 0.16.4

**New**
- **Dashed box** (Draw menu, Schematic tab): drag two corners and write any note inside it.
  It can belong to nothing, or to a device: pick one from the list, type its tag, or choose
  Pick on drawing... and click the device on any sheet. A box that belongs to a device shows
  its tag and where it is, follows it when it is renumbered, and is listed under it. Drag its
  corners, note and tag by their grips; double-click it to change it.
- When placing a contact, **P** lets you pick its coil or device on the drawing, on any sheet.

**Fixed**
- A bus landing on a symbol right after turning close to the pins it started from could land
  with its wires running backward and crossing each other. It now takes a better route, or
  says to click a point farther out first.

## 0.16.3

**New**
- Drawing a wire or bus, pins and wire ends always pull the point onto them, even with Object
  snap (F3) off, and a symbol's middle is never a target, so wires land exactly on pins.
- A wire end that stops just short of a pin or another wire without joining it gets a red
  ring, and the command line says how far and from what.
- A bus that can't land wire for wire on a symbol says why (pin count, spacing, poles the
  other way, or that side facing away) and keeps drawing.

**Fixed**
- A bus ended on a 3-pole symbol below or above where it started now lands wire for wire,
  taking an extra corner when it needs one. Before, it ended there with only its first wire
  on a pin and the others beside the symbol.
- A bus ended on a 3-pole symbol turned the other way no longer claims to land with only its
  first wire connected.

## 0.16.2

**New**
- Two new three-phase symbols in the Library: **Fused disconnect 3-pole** (the disconnect and
  its fuses in one, the fuse rating shown in each fuse) and **Starter 3-pole** (the
  contactor's power contacts and the overload heaters in one). The starter belongs to its
  Contactor coil like any contact: it shows the coil's tag and is listed under it. Both line
  up pole for pole and tag for tag with the other three-pole symbols.
- Overload heaters are drawn as two hooks (the usual US heater symbol) instead of a hump up
  and a hump down. A drawing you already have keeps the old look until you use
  Library > Update blocks from library...
- Move a symbol's tag: select the symbol and drag the grip on its tag (or on its rating)
  wherever you want it. It stays there on that copy and follows the symbol when you move it.

- Edit > Options..., General: **Open the files that were open when KanzonasCAD last closed**.
  Turn it on and KanzonasCAD starts with the projects you had open.

**Fixed**
- Updating with two or more KanzonasCAD windows running closes all of them (each asks to save
  its changes first), not just the one you updated from.
- A symbol turned sideways shows its tag beside it, clear of its poles, instead of on top of
  the outer pole.
- A 3-pole symbol turned either way now lands every pole on the bus you click it onto (turned
  one way, only L1 used to land); it flips itself to fit, and the preview shows it.

## 0.16.1

**Fixed**
- The mouse disappeared over the page while drawing a bus, and the bus showed no preview.
  It is back, with the bus drawn under it as you go.

## 0.16

**New**
- Print (File > Print..., Ctrl+P): print this sheet, all sheets, or the ones you tick, on any
  printer or into a PDF file. Select several sheets in the Sheets panel with Ctrl+click or
  Shift+click and Print starts with those. Print the whole sheet, its extents (everything
  drawn), what the window shows, or a window you pick on the drawing; fit to paper or actual
  size; automatic, portrait or landscape. A preview beside the settings shows each page as it
  will print, and changes as you change them.
- Inserting a symbol holds it by its first pin (L1, 1, A1...): click the pin or wire it joins
  and it lands there. A 3-pole fuse clicked on a disconnect's T1 now joins all three poles.
  Type B while placing it to hold it by another pin, or by its middle as before.
- The tags of the built-in symbols line up: every three-pole device's tag sits at the same
  height, and every one-line symbol's at another, so a disconnect, fuses and contactor in a
  row have their tags in a row. Library > Update blocks from library... gives a drawing you
  already have the new heights (it asks first; Undo takes it back).
- Ratings: fuses, breakers, disconnects, overloads, motors, the transformer, the VFD and the
  power supply have a Rating (30A, 5HP...): double-click the symbol to type it; it shows under
  the symbol and goes on the bill of materials.
- Bus: start it on a symbol's pin (a disconnect's L1, L2 or L3) and it takes that symbol's
  poles and spacing by itself, each wire from its own pin; it no longer asks how many and how
  far apart first. S runs it straight instead of turning; L puts its wires on layers: brown,
  orange, yellow (480 V), black, red, blue, all black, or one by one.
- Distribute objects (Modify menu, Panel tab): spread three or more selected objects out
  evenly, horizontally or vertically.
- Copy (with Move, Rotate, Mirror and Erase) is on the Schematic and Panel tabs.
- A second wire on a pin runs straight onto it: the little 45-degree bend is gone (Schematic
  settings can turn it back on).
- Trim wire on a wire with a bend trims only up to the bend, not the whole wire.
- Lining up with another wire's end: with Extension on, hover over the end, then draw; the
  point straight across or up and down from it snaps, with a dotted line.
- After placing a symbol, Enter places the same symbol again.
- Bus: start it on the open ends of a bus to carry it on (each wire joins its own); end it
  on three phase wires running across (or start it on them) and each wire lands on (or leaves
  from) its own phase: a vertical 3-phase drop onto horizontal L1, L2, L3. Clicking any pin of
  the next symbol lands the bus wire for wire.
- Wire gauge and color: Layers has AWG and Wire color columns; wires on such a layer show
  "10 AWG BRN" under their wire number.
- Fuse ratings show inside the fuse's box (on each pole of a 3-pole fuse block).
- Footprints are labeled as you place them: placing one asks which schematic device it is
  (Enter takes the next one without a footprint), and it shows that device's tag, which
  follows the schematic when it is renumbered. New footprints show their tag to start.
- Delete dot (Modify menu, Schematic tab): click a junction dot to remove it (the wires still
  connect); click again to bring it back. Why a dot sometimes appears when a wire is added at
  the end of another: that point was already a bend, or two wires met there, so three wires
  now meet (the manual explains it under Wires).
- Sheets in their own windows: Window > Open this sheet in a new window (Ctrl+Shift+N) opens
  the sheet you are on in a window you can put on another screen (it fills your second screen
  if you have one). Both windows work on the same project: one Undo, one Save. You can also
  drag a project tab out of the tabs to give it its own window.

**Fixed**
- The layer box: picking a layer for selected objects moved them but the box went back to
  the current layer, as if nothing happened; it now shows their layer. And wires drawn with
  a wire layer current (WIRE BROWN, or one with a gauge) go on it instead of always WIRES.
- Esc deselects (or cancels the command) wherever the keyboard is: after clicking a ribbon
  button, in the layer box or the Sheets list. Ribbon buttons no longer take the keyboard from
  the drawing.
- Block properties: a block made as a panel footprint (Make block makes one on a panel sheet)
  had its tag prefix, part in cross-references and the rest greyed out, with no way to change
  it. Its Kind can now be changed to schematic symbol (and back), and the window says why
  those rows are greyed.

## 0.15.14

**Fixed**
- Fit, turning a sheet and opening a DXF or DWG move the drawing by whole inches (or 1/2",
  1/4", 1/8" when the room is tight), so it stays on the snap grid. They could move it by odd
  amounts, and a wire drawn on the grid afterwards stopped a few thousandths of an inch short
  of an old one without joining it.
- Security: the library that reads DWG files is updated (ezdwg 0.20.0). It checks malformed
  files more strictly and reads some AutoCAD 2004 files it could lose parts of. DWG files
  also open faster. (Version 0.15.13 had this but was never released.)

## 0.15.13

**Fixed**
- Security: the library that reads DWG files is updated (ezdwg 0.20.0). It checks malformed
  files more strictly and reads some AutoCAD 2004 files it could lose parts of. DWG files
  also open faster.

## 0.15.12

**Fixed**
- The geometric center snap (GCE) lands exactly on the center of small closed shapes far from
  the origin, as in imported drawings (it could be a hair off).
- Zoom extents shows a drawing of any size (it stopped short of showing one over about
  600,000 inches).

## 0.15.11

**Fixed**
- Fewer empty edges while panning and zooming out: while the view stays still, the drawing
  around it is made ready, so it shows right away when you pan or zoom out, and the sharp
  picture comes back sooner after you stop.

## 0.15.10

**Fixed**
- You can start a selection window by pressing in the empty space inside a hatch, as in
  AutoCAD. A patterned hatch is selected by clicking its lines or outline; a solid fill is
  still selected anywhere on it.
- Panning and zooming are smooth: the picture moves and scales with the mouse right away,
  however busy the drawing, and is drawn again sharp a moment after you stop.

## 0.15.9

**New**
- More standard scales: 1:3, 1:6, 1:9 and 1:12, in the Scale list on the status bar, the Sheet
  scale window and Sheet properties. Fit tries them too, so a drawing that fits at 1:3 gets 1:3
  instead of 1:4.
- A wire duct's width and depth can be changed: double-click a duct for separate Width and
  Depth fields and a list of standard sizes. With several ducts selected, they can all take
  the new size at once. The depth goes on the materials list and the bill of materials.
- The Wire duct command shows the standard sizes as buttons to click before you draw.

## 0.15.8

**Fixed**
- Fit no longer leaves the drawing running past the border or over the title block when it
  holds notes, dimensions or tags: they keep their size on paper, so they take more room at
  a smaller scale, and Fit now measures the drawing as it will be at the scale it picks. The
  Sheet scale window's preview measures it the same way.
- Export to DXF works on a drawing that has its own layer named Border (it used to stop with
  "LAYER 'BORDER' already exists").

## 0.15.7

**Fixed**
- Fit picks the biggest scale the drawing really fits at: it no longer chooses a smaller scale
  (1:5) when the drawing fits at a bigger one (1:4) inside the border and clear of the title
  block. Fit and the status bar's "doesn't fit" now agree.
- Open recent no longer lists the same file twice (once with \ and once with / in its
  name, after a Save as), and opening a project that's already open from there goes to its
  tab instead of opening it again.
- Zooming out on a sheet with a scale (1:24, 1:48...) now goes far enough to see the whole
  sheet and drawing. It used to stop too close, and right after Zoom extents a step out
  zoomed in instead.

## 0.15.6

**Fixed**
- A selection window or lasso around a big drawing (an imported DWG or DXF, a panel at real
  size) now selects everything in it. It used to catch only what was in its lower left 32
  inches, so it sometimes selected everything and sometimes only some things. Objects bigger
  than 32 inches (an imported frame, a large outline) can now be picked and snapped to
  anywhere along them, not only near one corner.
- Junction dots no longer stay behind after moving a long wire on a big drawing.

## 0.15.5

**New**
- Object snaps now reach the sheet's border and title block: snap to their corners, line ends,
  middles and intersections to line a drawing up with them. They still can't be selected on a
  sheet (use Edit title block to change the title block).

## 0.15.4

**New**
- Update now shows a progress bar while it downloads (how many MB of how many, and the
  percent), with a Cancel button to stop it. You'll see it from the next update after this
  one: the version you update from does the downloading.

## 0.15.3

**New**
- Show or hide attributes: double-click a symbol or block and choose which of its attributes
  show on the drawing (Shown on the drawing), or select many and use Show or hide
  attributes... (Modify menu, Schematic and Panel tabs) to do it on all of them at once. Hidden
  ones keep their values, and reports still use them.

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
