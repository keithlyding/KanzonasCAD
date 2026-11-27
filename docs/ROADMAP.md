# KanzonasCAD roadmap and decisions

Decisions the owner has made, so every agent and person builds the same thing. Change this
file when a decision changes. Goal: do what AutoCAD Electrical does without its complexity
(its known pain points: editing the title block, moving blocks between drawings, and scaling
nobody understands).

## Done
- 0.1: sheets with zones and title block, AutoCAD-style drawing, layers, DXF/PDF.
- 0.2: symbol, footprint and parts library; Make block, Insert, Explode; Scale Reference and mm
  input; text justification; editable zones; Project vs Sheet properties; Schematic and Panel
  ribbon tabs; ByLayer colors; sheet types; backups, autosave and recovery.
- 0.3: wires that stay attached to pins, cut under placed symbols, junction dots.
- 0.3.1: Library popup, Circle options, Bus. 0.3.2: in-app updates, GitHub releases.
  0.3.3: icons in Windows dark mode.
- 0.4: device tags by page number (CR601), locked tags, Renumber sheet. 0.4.1: Windows
  installer (this user or all users), updates through the next setup.
- 0.5: contacts linked to their coil, cross-references (auto, freeze, update). 0.6: wire
  numbers, distribution blocks, off-sheet connectors. 0.7: three-phase symbols, terminal
  strips, PLC I/O. 0.8: DWG import (ezdwg; ODA File Converter as fallback). 0.9: panel
  sheets with one scale, paper-sized text, {Scale}, dimensions (linear, aligned).
- 0.10: DIN rail and wire duct, panel materials. 0.10.1-0.10.12: icon, wire crossings,
  AutoCAD's object snaps, quick layer tools, one-click Text, Scoot and Align, title block
  position, Trim wire / Delete wire / Clean up wires, double landing, Delete component.
- 0.11: project templates; Edit > Options.... 0.11.6: the Sheet scale window (preview, plain
  words, Fit, cabinet size, a warning when the drawing doesn't fit). 0.11.7: rotating sheets
  both ways (Ctrl+Shift+Plus / Minus): border, zones and title block turn with the sheet, the
  drawing stays upright (owner's choice).
- 0.12: blocks' Manufacturer, Family and Series (owner, Nov 2026: "Family is good. Add series
  as well. I also need some sort of help with nomenclature": placeholders, tooltips and a "?"
  opening the manual's section; suggestions grow from what is typed, no built-in list); the
  Library's Manufacturer and Family filters; a library block's Properties...; Edit block...
  (owner's decision: it edits the library's copy, in a tab of its own, as AutoCAD's Block
  Editor) and Save block; then "Update the N copies of ... in ...?" each time (default Yes),
  wires kept on the pins. Other projects keep their own copies.
- Multi-sheet projects with a sheet list and sheet types (schematic, panel, report, other):
  done since 0.1/0.2.

- 0.18: cross-references and numbering (owner, Nov 2026): Source/destination arrows as
  AutoCAD Electrical's (click the source end, then the destination end on any sheet; one wire,
  the source's number; each arrow shows the number and the other's place); Update numbers and
  cross-references (tags, wires, cross-references; renumber or keep, asked each time; this
  sheet, picked sheets or the whole project); the Library's phase filter (worked out from pins
  and name, Properties... overrides).
  Also in 0.18: cross-reference text on layer XREFS, cyan, 0.065" (owner's choice); Lock
  numbers (lock what's there, for a selection, sheets or the project: owner's choice over a
  sheet setting); Stretch, as AutoCAD's, and Shift-picked grips moving together (owner: both).
  The ribbon (owner, Nov 2026: "the schematic ribbon goes off the screen... make it its own
  tab that only shows up when needed (or manually selected)"): a block's tools on a Block tab
  shown in a block's tab (or always, View > Block tab); a tab too wide for the window shows
  its groups smaller from the right, as Office does, rather than scrolling.
- 0.18.1 (owner, Nov 2026): footprint labels: several lines at once, a grip for each, their
  own height (0.08" to start: owner's choice), a linked device's ratings on its footprint,
  edited from either one (owner's choice); duplicate tags and wire numbers marked red on the
  drawing and said on the command line, over the whole project (owner's choices); wire numbers
  out of the way, with a short line back to the wire when there's no room.
- 0.18.2 (owner, Nov 2026: "I'll need a lot of different ones...480, 120, 24vdc, Ethernet and
  others"): Add wire layers, a preset with the owner's colors and sizes (480 V BLK, RED, ORG,
  BRN, YEL, WHT neutral, GRN ground, 12 AWG; 120 V RED, BLK, WHT neutral, 14 AWG; 24 VDC BLU
  and a BLU/WHT striped common, 16 AWG; Ethernet green, no size); a size per wire with the
  layer's as default (Wire size); two-color wire layers drawn striped.
- 0.21.2 (owner, Nov 2026: "every time I reopen the project, the layer I had selected reverts
  to the default wires layer"; "project and per sheet (so both)"): each sheet has a default
  wire layer, its own (Sheet properties: Wire layer, saved) or the project's (Project
  properties, new Wire layers tab, with the wire layers' list); the Schematic tab's layer box
  lists the wire layers only and picks one on top of the default, per sheet, not saved;
  picking a layer that isn't a wire layer (0) goes back to the sheet's default (owner:
  "Picking layer 0 should revert the wires default back to whatever the sheet default is"). Next (owner: "let's get the other 3 in first"): a wire starting
  on a PLC I/O pin or a motor/drive terminal picks its voltage's layer.
- 0.21.2 (owner, Nov 2026: "wire numbers for wires connecting to a PLC input or output (not
  power) should have the option of being numbered according to its I/O point"; asked: its
  address, O:3/0): Project properties, Schematic, Number wires on PLC I/O points by their
  address (off to start); Import I/O list's address wins over the one made from the SLOT.
  Also in 0.21.2: Ctrl+Tab sheet cycling (as Studio 5000), output modules sourcing on the left,
  -2/-3 duplicate sheet titles, Align/Distribute on the Schematic tab, fast window selection.
  Changed in 0.22.2 (owner, Nov 23 2026): Ctrl+Tab / Ctrl+Shift+Tab go next / previous in
  page order, round from the last sheet to the first; the most-recent cycle moved to Ctrl+`.
- 0.18.3 (owner, Nov 2026: "all three wires tapping off the bus are still the same wire number
  ... Those need to change where they tap off"): taps numbered from the wire they tap, -1, -2,
  -3 in the numbering order, a tap off a tap a, b, c (2007-1a); a project setting (that, the
  same number, or a number of its own), on for new projects, projects from before keep "same";
  per tap, S keeps the wire's number, N its own. Tracking picks up midpoints and centers.
  Also: border and title block switches (project and sheet), layers carried by Paste,
  fractional dimensions (Dimension units), gauge labels once per group, gauge only, in line
  with the number (Wire color label per wire), arrows named by their wire and the source's
  layer on the destination, Duplicate sheet.
  Still to come: power distribution block outputs with -1, -2 per phase (they keep letters
  today), AutomationDirect T1/T1E duct sizes (actual sizes from AD's spec sheets, waiting on
  the owner's look at the table).

- 0.22 (owner, Nov 2026: "the ability to not just do grid style cross references but also the
  line by line ones"; "Let's do ladder references as an option"): ladders (Draw > Ladder) and
  References Grid or Ladder for the project and per sheet; rungs numbered from the page (600,
  601... by default; 6-01 as the other style), a second ladder carrying on from the first.
  Not yet (offer): device tags and wire numbers from the rung (CR603, 603-1), as AutoCAD
  Electrical can. X Zones (columns only, IEC) not planned (owner: "Who uses just the x grid?").

- 0.22.1 (owner, Nov 2026: "Yes, on the auto wire layer"): a wire takes its layer from the pin
  it starts on (PLC points 24VDC BLU, commons BLU-WHT, motor/drive power 480V BLK, ground 480V
  GRN, transformer X1/X2 120V RED/WHT, power supply L/N/+/-), and a pin's own wire layer in
  Pins.... Owner's answers the same day: panel wiring as a per-device wiring list ("yes, a per
  device wiring list"); a drawn point-to-point diagram "seems extremely busy" (offered instead:
  each footprint terminal labeled with its wire number and where it goes); symbols "lean heavy
  on the Allen Bradley stuff" and "also put in IEC symbols" (IEC 60617 as a per-project symbol
  set: changes AGENTS.md's US-only line when it lands).
- 0.23.2 (owner, Nov 2026: "Don't toggle with ctrl e. That always opens or brings it to
  forefront. Only clicking the button should toggle it"): the Trace button (Schematic tab, View
  tab's Panels, View, Trace panel) opens and closes the panel and shows checked while it is
  open; clicked while the panel is open but out of sight (a tab behind another panel) it raises
  it. Ctrl+E (a separate, non-checkable action) only opens or raises. Several selected: the
  owner chose "Last one picked" (the view keeps the order picks were made in, view.pick_batches;
  a window or lasso: the device, else wire, nearest the top left of what it added), devices and
  wires before anything else, the header adding "(and N others selected)".
- 0.23.1 (owner, Nov 2026: "Like for pdf, if I click on a cross reference, will it navigate me
  to that location?"; yes, including the source/destination arrows, which he may drop):
  Export to PDF makes each cross-reference a link to the page and spot it names (/FitR, zoomed
  round the object), with pypdf (BSD-3-Clause) added as a dependency; none to a sheet left out.
- 0.22.4 (owner, Nov 23 2026: "I think it should actually have its own tab, kind of like editing
  a block"): the title block edited in a tab of its own, Save title block and Close title
  block on its own ribbon tab.
- 0.22.4 (owner, Nov 23 2026: "In addition to -1, can we add a, b, c, etc for wire taps? Also
  -a, -b, -c, etc. This would be a project wide setting, able to be overridden by sheet and by
  wire"; asked: a tap off a tap alternates, letters lowercase): Tap numbers end in -1, a or -a,
  project, sheet and wire.
- 0.22.2 (owner, Nov 23 2026: "the poor efficiency of releases and builds and merges is getting
  really tedious"; chose one release for the six queued changes and parallel unit tests, not
  batch releases from now on): print fit check, ezdwg 0.21.3 (security, #139), smaller title
  block with SCALE, Terminal count..., justify in-place text, Measure on the Block tab, block
  properties in a block's tab, pin name justification kept, pin names near corners, Ctrl+Tab
  in page order (the last-shown cycle on Ctrl+`). Unit tests in parallel (tools/run_tests.py), and main's build
  skips the tests already passed on the same files (the owner: "Don't re-run the tests on main
  for code the PR build already passed"; tools/already_tested.py), and nightly tests on main at
  midnight EST to make up for it (.github/workflows/nightly.yml; failures in a `nightly` issue).

- 0.23 (owner, Nov 23 2026: "One thing we still need, and it's very important ... is Cross
  reference navigation. AutoCAD Electrical has a surfer version ... Not sure it's super
  intuitive ... I like Allen Bradley's Cross referencing in their Studio 5000 software. I click
  on a tag and then use control E to go to a cross-references tab which shows all the places
  that tag is used and shows whether it's an output or input, and some other metadata"):
  **Trace** (Ctrl+E), a panel docked at the bottom that stays open while you work (the owner's
  choice over a popup); double-click or Enter on a row goes there. Then (owner): it follows
  the selection while open (no Ctrl+E needed); docks left, right or bottom and is put back
  where it was left, open or closed; speed is a hard requirement: one index of the project,
  rebuilt only when the project changed and the panel is open, a click one lookup, nothing
  done while the panel is closed. The name is **Trace** (the owner's final choice, Nov 2026;
  set in one place, where_used.NAME). A hard requirement (the owner: "make sure that the
  loading of the cross-references doesn't prevent any interaction with the sheet itself.
  That's a big pain point on AutoCAD Electrical. If the properties panel is open, I can't do
  anything until all of the properties load"): a click only starts a short timer; the
  look-up runs in slices of a few milliseconds on the event loop (no threads), a newer pick
  dropping an older one; each sheet's index is kept until that sheet changes; rows go in a
  batch at a time. Not in this version (asked to
  leave room for them): back/forward through places gone to, Ctrl+click on a drawing's
  cross-reference text to go there, a search box (a tag or wire number typed).

- 0.24 (owner, Nov 24 2026: "If someone is an AutoCAD user and wants to switch over but
  doesn't want to lose AutoCAD's native blocks and any they've created, can they copy their
  blocks into the KanzonasCAD folder and they'll work?"; asked whether to build a batch import:
  "Yes. Start it please. People can bring in Autocad's blocks on their own if they wanted to,
  but we would advertise that it's for blocks people have created on their own"): **Import
  blocks from folder...** (Library menu; Output tab's Import group; Block tab). A folder of
  DWG/DXF files (subfolders optional) or one drawing; a WBLOCK'd file is one block named after
  the file, a drawing of named blocks gives each (anonymous, xref, layout, "_" arrowhead and
  nested-only blocks left out). A window lists them (picture, kind guessed, pins, file,
  status: new / name already in the library: skip, replace or keep both as "name (2)", skip to
  start / can't be read, with why), category (Imported) and library (first or second,
  writable). Read and written a file or block at a time on the event loop under a progress
  window; Cancel puts the library back as it was. AutoCAD Electrical's wire connection
  attributes X?TERMnn become pins (named by TERMnn's value, else nn), TAG1 the tag spot, an
  H/V + family name (HCR1) the tag prefix (CR). Decided: presented everywhere as importing
  **your own** blocks (the owner's words); nothing refuses Autodesk's. Not done: the cross-
  reference role from AutoCAD Electrical's name convention (its fourth character, parent or
  child, could not be confirmed from Autodesk's own documentation: every import is a device,
  fixed in Properties...); dynamic block parameters; AutoCAD Electrical's wire numbering and
  cross-reference behavior. Terminal strips and what followed moved down one number.
- 0.24.1, released in 0.25 (owner, Nov 24 2026: "I need to be able to edit footprint rating
  font sizes. Both in the footprint block itself and the ability to override individually its
  instances"): a text
  size per footprint label line in the block (Block properties, Label text sizes) and on a copy
  (its attributes window), paper inches; the copy's, then the block's, then the project's
  Footprint label height. Also fixed: a label line's Angle wasn't kept ("I also reoriented the
  label 90 degrees and it reverted back"). Decided ("Option 2, but overridable"): a turned line
  is kept readable (180 drawn as 0, 270 as 90, on its spot), with Keep readable per line on
  the copy to draw it exactly as set; no block-level default for it.
- 0.25 (owner, Nov 24 2026: "Make all this one release please"; the 0.24.1 work above, never
  published on its own, went out in it):
  - **File locking** (the owner: "I was able to open two instances of the same file in two
    different instances of KanzonasCAD. I think we need something to say locked for editing,
    open as read only?"; the design agreed with the owner): a hidden lock note beside a
    project open for editing (`.~lock.<file>#`, one name on both platforms), made atomically;
    a second copy asks: Open read-only (default), Open anyway (warned), Cancel. Decided here:
    a read-only project can be edited in memory, as AutoCAD allows, and only saving over the
    file is refused (Save As makes your own, editable, locked copy); stale notes from this
    computer taken over silently, other computers' asked about; File > Reopen for editing
    reloads the file once the other copy has closed it (cheap: close and open again).
  - **A symbol and a footprint with the same name** (the owner: "both having the same name
    should be ok. Right now, one will supersede the other"): kept apart as since 0.18 under
    one name key ("name (footprint)"), shown everywhere by their own name; decided here over
    keying the project's blocks by (kind, name): no format change, nothing to migrate. Make
    block, Import I/O list and Save to library as part were still going by the plain name.
  - **A block piece's own color** (the owner: "I want to key it at the same layer but just
    change the color of ... a little rectangle in the block. Can you also add color to the
    block editing tab?"): Save block and Make block keep a piece's color and mark the block as
    keeping its pieces' colors; a block with none draws as before. Color on the Block tab.
  - **Properties panel** (the owner: "Can text properties be in the block panel, so I don't have
    to right click it each time?"; asked what it shows, "Everything of the selection"): a
    docked panel as AutoCAD's Properties palette, Ctrl+1 (opens or raises; the View menu's and
    View tab's button toggles, as Trace's), right to start, left, bottom or floating, kept in
    the window state. It follows the selection as Trace does (a timer, never in the click,
    nothing while closed; the owner's rule from Trace: "make sure that the loading ... doesn't
    prevent any interaction with the sheet itself"). General for anything; a kind's own fields
    when everything selected is of that kind; *varies* where several differ, set on all in one
    step. Decided here: edits apply on Enter or when a field loses focus (ticks and lists at
    once), each one undoable step, through the attributes window's and the Wire number
    window's own code (both windows stay). A symbol's text size is shown, not edited (its tag
    is the project's Tag height, set again on every symbol when that changes; its attributes
    are their block's); a wire's number is edited one wire at a time; a multi-line note's
    lines, and the other kinds past General, are left to their own windows for now.
  - **Devices without a footprint** (the owner: "make a check, so any schematic block in the
    drawing that's not assigned to a panel footprint will give me some sort of alert"): an
    orange frame on each (on to start; Project properties, Panel, turns them off), a status
    bar count opening a list (double-click goes there), and a report (sheet, CSV, Excel).
    Decided here: a device counts when it gets a tag of its own (devices and parents; not
    contacts, terminals, outlets or arrows); it is in the field, and left out, when its
    location (its own LOC, else its sheet's, as Cables between locations reads it) is called
    FIELD... or, once a panel sheet names a location, is one no panel sheet names (the
    program had no other way to tell a panel from the field); it has a footprint when one on
    a panel sheet is linked to it (PARENT, as placed for it) or, linked to none, has its tag;
    "No footprint needed" per device for the rest.
  - **Ribbon**: Explode on Home's Modify and on the Block tab (a new Modify group); Block
    properties... beside Edit block on the Schematic and Panel tabs. The owner reversed the 0.18
    decision ("Block properties should generally only be visible when editing/creating a
    block"): the ribbon now shrinks a crowded tab's groups (Ribbon.fit), so the room it took
    is no longer the worry.

- 0.26 (the owner's handwritten list, Nov 25 2026, from AutoCAD Electrical habits):
  - **Footprint tag sizing when showing/hiding**: a footprint with every label line hidden
    kept its label's sizing (tag_h, label_k) up to date no more: Footprint label height
    changed meanwhile left it at the old height, and label_k was dropped and taken afresh
    from the sheet when a line was shown again. Now label_k is kept with the lines hidden and
    the height change reaches every footprint.
  - **Coordinate display for devices** (the owner's choice: X,Y of the insertion point):
    the status bar shows the symbol or footprint under the mouse, "CR101  X 6.250  Y 4.500",
    from the hover the view already finds; the Properties panel's Position X/Y (there since
    0.25) moves it.
  - **Dashed polygon** (DASHPOLY): a dashed box of any shape; decided here: the same object
    as a dashed box (a subclass, kind "dashpoly"), its window, layer and settings, a corner
    grip moving that corner alone.
  - **Bus: swap phases 1 and 3** (W, and a right-click menu in Bus: decided here, Enter first
    so a right-click and a click still ends it): the wires cross over just before the pins
    in square steps, through a lane of their own beside the first, so no crossing is a
    joint. Only where the bus lands on pins.
  - **Join** (J, AutoCAD's JOIN): decided here: wires left out (they join by themselves as
    drawn, Clean up wires for the rest; joining wires changes connections); nothing joins at
    a branch (three ends) or an overlap; an arc only with arcs of its circle (polylines are
    straight); gaps up to 0.03" on paper said.

## Owner's list after 0.21.4 (Nov 2026), in order
1. Ladder references (0.22, above).
2. Auto wire layer (0.22.1, above).
3. Cross-reference navigation, Trace (0.23, above; put ahead of terminal strips by the
   owner, Nov 23 2026: "very important").
4. Terminal strips (0.27; was 0.24 until Import blocks from folder... took 0.24, 0.25
   until the Properties panel and Devices without a footprint took 0.25, then 0.26 until the
   owner's handwritten list and the collector fix took 0.26, one release): strips,
   jumpers, a strip editor, a terminal plan report.
5. Panel wiring (0.28): a per-device wiring list (owner: yes); point-to-point as wire labels on
   the footprints' terminals, not a drawn diagram (see 0.22.1).
6. Saved circuits dropped in whole ("not a bad idea"), and more symbols and footprints (0.29):
   "lean heavy on the Allen Bradley stuff", and IEC symbols too (see 0.22.1). Templates
   library: not now.
   Done in 0.29 (decisions marked "decided here" are open to the owner's change):
   - **Saved circuits** (Library > Save circuit..., Insert circuit...): one file a circuit in
     the library's circuits folder, in either library as blocks and parts are, holding its
     objects around its base point and its own copies of their blocks and layers. Decided
     here: its picture is drawn from the circuit itself when the browser lists it, not kept as
     a picture file beside it (nothing to fall out of step when it is renamed, or synced
     half-way); its base point is clicked as Make block's is (Enter: the lower left corner);
     R and S (a typed scale) as it is placed, no flip (a flipped rung reads backwards). Placed,
     its devices take the sheet's lowest free tags (a locked tag kept), contacts whose device
     came with it link to the new copy, one whose device was left out is placed unlinked with
     its tag cleared (decided here: its old tag would link it to an unrelated device of the
     project), unlocked wire numbers go (the sheet numbers them), connectors and arrows get
     new names, the same within the circuit (decided here: a pair stays a pair; a lone one
     waits for its other end), one undo step. The owner confirmed (Nov 27 2026): a lone contact
     stays unlinked with its tag cleared.
   - **More symbols and footprints, leaning on Allen-Bradley**: symbols drawn here in the
     JIC style (motor protection circuit breaker, electronic overload and its NO contact,
     3-position selector and its contacts, pilot light with its color letter, PLC modules of
     ControlLogix, CompactLogix, Compact 5000 and POINT I/O drawn whole); built-in parts by
     catalog number (100-C, 140M, E300, 700-HA, 800F contact blocks, 1492-J, 1606-XLP,
     PowerFlex 525, the PLC modules, controllers and chassis), read-only as the built-in
     blocks are (a part of yours with the same id takes its place). Catalog numbers only
     where their numbering is sure (E300's depends on three modules: left blank);
     footprints only where none generic is near: PowerFlex 525 frames at Rockwell's
     published nominal sizes, the PLC modules and chassis as "(approximate)"; parts use the
     generic footprints otherwise (the owner confirmed all three, Nov 27 2026: as built).
     PLC modules' pins (the owner, Nov 27 2026: "Both"): named by Rockwell's terminal (screw)
     number as its wiring diagram prints it, the point beside it ("2  IN 0"), commons and
     supplies too, only from Rockwell's own document, its publication named
     (allen_bradley.TERMINALS); a module not confirmed stays by point. Wire numbers by
     address and Import I/O list read the point from the text beside the pin. Still to do:
     the 1756, 1769, 5069 and 1734-IB4/OB4E modules' terminal numbers (Rockwell's literature
     library refused the build machine: all 13 are still by point; the 1734 modules from
     0.19 were numbered from the owner's Rockwell diagrams, terminals 0-7).
   - **IEC 60617 symbols as a project's symbol standard** (Project properties, Schematic:
     JIC/NFPA (US) or IEC 60617; every project from before and a new one JIC): a core set
     of 30 drawn here (coils, contacts and timed ones, pushbuttons, E-stop, selector, fuse,
     breaker, disconnector, thermal overload and its contact, lamp, motors 1~ and 3~,
     solenoid, transformer, 3-pole power devices, terminal, PE). Insert symbol offers the
     project's set in place of the other one's equivalents; the rest (PLC, drives,
     connectors) in both. Decided here: laid out for horizontal rungs as the JIC set; the
     symbols keep the JIC prefixes (CR, M, PB...), which say what kind of device each is to
     the program.
   - **IEC 81346-2 letter codes in an IEC project** (the owner, Nov 27 2026, into 0.29):
     tags made of the device's class letter instead of the US prefix (tags.prefix_for), by
     what it does (IEC 81346-2:2019 Table 1, from public summaries; the standard itself not
     read): K control and timing relays and PLC modules; Q contactors (coil and main
     contacts one device, one tag: 81346-2 puts power switching under Q, signal relays
     under K), breakers, motor protection breakers, disconnects; S pushbuttons, selectors,
     E-stops; F fuses and overload relays; P pilot lights; M motors and solenoids; T
     transformers, power supplies and drives; X terminal strips (X601) and distribution
     blocks. Decided here, open to the owner's change: limit, pressure, temperature and
     float switches B (81346-2: sensing a condition), not S as the owner's list had them;
     power supplies T (converting AC to DC), not G; PLC K, not A; drives T; solenoids M.
     Devices of one letter share its counts on a page; your own prefixes are kept. A tag of
     the other letters (the project's standard changed, No to retagging) is kept and follows
     its page until Renumber sheet; copies take the project's letters. No project from before had IEC
     symbols, so nothing is renumbered on open. The owner confirmed (Nov 27 2026): the
     letters as built (B for sensing switches, T for power supplies and drives, K for PLCs);
     terminal strips by page (X601, its terminals X601-1); switching the standard asks
     "Retag the unlocked devices with the <new> letters?" (Yes retags them all in the same
     Undo step, each keeping its page and count when free, contacts, terminals,
     cross-references and arrows following, locked tags never changed; No keeps them;
     Cancel cancels the whole Project properties change; not asked when there are none:
     tags.retag_letters, through Update numbers' fix_sheet); a device or contact with no tag
     yet shows the project's letter, K?, X?, Q? (BlockDef.tag_letter, set by the project).
     PLC modules' screw numbers: being sourced from Rockwell's documents via mirror sites
     (allen_bradley.TERMINALS still empty). Still to come: vertical (IEC-style,
     top-to-bottom) layouts, and IEC versions of the limit, pressure, temperature and float
     switches, the fused disconnect and starter combinations, drive terminals and the
     distribution blocks.
7. **UDTs** (0.30, the owner, Nov 26 2026; named "UDT" as in PLCs and Ignition, the owner's
   choice): a circuit type built on saved circuits, for example a whole motor circuit
   (disconnect, manual starter, VFD, terminal blocks, motor).
   - **Choices** (the manual starter swappable with fuses), **optional parts** that can be
     added or left out (line and load reactors), and **ratings** for every device.
   - Placed in any direction; its devices, wires and labels become ordinary objects with
     their own tags, wire numbers, cross-references and parts, "as if it was a bunch of
     individual parts like normal" (so reports, terminal strips and the battery see them as
     any other), tied together by a hidden group id.
   - Proposed (to confirm with the owner when it is started):
     - A placed UDT keeps its type and choices: select it, change a choice (fuses for the
       starter, add a load reactor) and it is rebuilt in place, devices that stay keeping
       their tags and wire numbers.
     - A device edited by hand inside one keeps the edit and the rebuild warns; Detach makes
       it plain parts.
     - A change to the type reaches placed ones only through a command (Update from type)
       that shows what will change first, not silently.
   - **Built-in UDTs and your own** (the owner, Nov 26 2026: "If I have two different
     style motor circuits, I would use two different UDTs"): a few UDTs come with the
     program, read-only as the built-in blocks and parts are (editing one saves your own
     copy); you make your own from a saved circuit and keep them in either library folder.
   - **Ratings are worked out automatically and can be overridden** (the owner: "I'm good
     with overridable auto calculations"): from the motor's HP and voltage, the full-load
     current from the NEC motor tables (430.247-430.250), then each device's rating from it
     by a rule the UDT holds (for example a dual-element fuse at a percent of the table
     current, per Table 430.52; the percent is the UDT's, editable, so a shop's own rule or
     a drive maker's fuse table can be used). Any device's rating can be typed over; an
     overridden one is kept through a rebuild and shown as overridden. Built-in tables are
     marked to check against the code edition in force.
   - Two phases: choices, optional parts and rebuild in place first; values and ratings
     second.

## Next, in build order (each its own pull request with tests)
Owner, Nov 2026: "do it all", schematic work first (contacts linked to their coil,
cross-references, wire numbers, off-sheet connectors, more symbols), then the panel.
1. **Contacts linked to their coil, and cross-references** (0.5):
   - A contact (child symbol) belongs to a parent device through the parent's hidden id
     (attribute PARENT = the parent's DEV) and shows the parent's tag, following it when the
     parent is renumbered or retagged. Placing a contact asks for its parent: a list of the
     project's devices with the same prefix (nearest first), or a tag typed; a tag with no
     parent yet leaves the contact unlinked (flagged) until that parent exists.
   - **Schematic <-> panel links go through the device (tag + hidden id), not the part**: three
     contactors may share one catalog number. Links ignore scale and screen position.
   - Under a coil / operator: one line per contact with an NO or NC mark and its location
     (`6-D3`); next to each contact: its coil's location (`6-D1`). Each device's listing can be
     switched off, and each contact line on or off; spare contacts as hollow marks (a setting,
     off by default). Panel sheets too: footprint <-> device locations.
   - **Updated automatically** after every change (computed, never stored as text). Project
     setting "Update cross-references automatically" (on by default); per-sheet **Freeze
     cross-references** for issued sheets; a status bar warning "Cross-references out of date"
     and an **Update cross-references** command whenever anything is off or frozen.
   - Format follows the project's grid reference format and each sheet's zones.
2. **Wire numbers and off-sheet connectors** (0.6):
   - Source/destination arrows for a wire continuing on another sheet, linked in pairs, each
     showing the other's location (`7-A2`); the wire keeps its start sheet's number.
   - Wire numbers: page number + 3 digits (`6001`); one number per connected group of
     wires, changing only through a device or terminal; after a distribution block the
     branches get A-Z suffixes (`6001A`...`AA`); a wire continuing to another sheet keeps the
     number of the sheet it starts on; sequence across-then-down or down-then-across per
     sheet; numbers stay stable once given; deleted numbers are reused; locking and Renumber
     sheet.
3. **More symbols**: 3-phase (3-pole breaker and disconnect, contactor power contacts, 3-pole
   overload, motor starter), VFD, power supply, PLC I/O (input/output points linked to a card
   like contacts to a coil), terminal strips (terminals sharing a strip tag), relay base.
4. **DWG import** built in, with **ezdwg** (MIT, reads R13-2018, i.e. every current AutoCAD
   file): opening or importing a `.dwg` works like DXF, nothing to install. The ODA File
   Converter, when installed, is only a fallback for a file ezdwg can't read. DXF stays the
   export format. Fixes go in our import code first, upstream to ezdwg second; fork only if
   urgent (its core is Rust).
5. **Panel sheets and dimensions** (done by 0.12.6):
   - Panel geometry is always real-world inches, 1:1: a 3" contactor footprint is 3" in the
     data on every sheet, forever.
   - Each panel sheet has ONE visible scale (e.g. 1:4), a lens on the real-size layout. Named
     presets (architectural, engineering, metric: 1/4" = 1'-0", 1:10...), as in KanzonasPDF's
     sheet scales. Shown in the status bar; written into the title block as a field
     (`{Scale}`).
   - Text, tags, dimension numbers and cross-reference text keep a fixed paper height (1/8"
     to start) at any scale; a per-text height override as today.
   - Footprints are never scaled by hand on a panel sheet: Scale refuses them (with a
     message). Scale -> Reference stays the tool for bringing a vendor drawing to real size
     before it becomes a footprint.
   - Never show the word "annotative" or any per-object scale list.
   - Dimensions (linear, aligned, radius...) read the true geometry, so they're right at any
     scale.
   - **DIN rail and wire duct** (owner, Nov 2026), real size on panel sheets, drawn by two
     clicks and stretched by their end grips or a typed length (no fixed blocks):
     - DIN rail profiles: 35 x 7.5 mm (TS35/7.5) and 35 x 15 mm (TS35/15), plus 15 mm mini
       (TS15) and a custom width. Drawn as the rail outline with its slot line.
     - Wire duct (Panduit-style): width and depth from presets (1 x 2, 1 x 3, 1.5 x 3, 2 x 2,
       2 x 3, 2 x 4, 3 x 3, 3 x 4, 4 x 4 in, metric too) or typed. The depth isn't drawn in
       2D but is kept for the bill of materials. Drawn as the duct outline with its fingers
       side shown.
     - Each piece can carry a part (manufacturer, catalog number, stock length: rail 1 m or
       2 m, duct 6 ft to start). The bill of materials lists total length per size and part,
       the number of stock pieces it takes (rounded up) and each cut length.
     - Footprints onto rail (owner, Nov 2026; 0.12.6): placed, moved, copied or dragged, a
       footprint locks onto a rail's centerline by its rail point and slides along; near a
       neighbor on the rail it butts against it. Each footprint block may set its rail point
       (the middle of its clip) in Edit block; else the middle of its drawing.
6. **Part assignment** (wanted: the owner, Nov 2026): projects keep their own copies of the parts they use (as they do of
   blocks), so a part leaving the library never breaks a drawing.
   - Symbol, footprint and part stay three separate things; the symbol never knows the brand.
   - Draw with the generic symbol; assign a part now or later. The part picker is filtered to
     parts using the clicked symbol; a project default brand (e.g. Allen-Bradley) sorts first.
   - Bulk assign: select every contactor on the sheet, pick a part once.
   - Placing a device on a panel sheet pulls the footprint from its part. Panel insert can pick
     from the schematic's devices, so tag and cross-reference come along; the schematic side
     flags devices not yet placed on a panel (done in 0.25: Devices without a footprint).
7. **Library management**:
   - (wanted: the owner, Nov 2026) Right-click a placed symbol with a part -> "Save to library as part" (name defaults to
     the catalog number): writes symbol + footprint + part into the library.
   - Library browser: right-click Edit or Delete. Single delete asks once. Bulk delete asks
     once with the count ("Delete 14 parts?"); if some are used in the open project, ask
     separately ("2 of these are in your project. Delete those too?": No deletes only the
     unused ones). Deleting from the library never breaks placed symbols.
   - **Two library folders** (owner's choice, Nov 2026), each chosen freely: the setup
     suggests the first as a shared one in a cloud-synced folder (OneDrive / SharePoint /
     Teams, Google Drive, Dropbox: synced by their own apps, no sign-in inside KanzonasCAD)
     and the second as a personal one, but either can be anything (two local folders to keep
     two libraries apart is fine). Both are searched together; each item shows which library
     it's from; a name in both shows both; saving asks which one (remembering the last).
   - **One file per part** (not one parts.json), so two people adding parts at once don't
     make a sync conflict copy.
   - A folder KanzonasCAD can't write to (read-only share) is used read-only, and says so.
   - Changes made by others show up without reopening (the folders are watched); conflict
     copies left by a sync app ("parts (Keith's PC).json"...) are pointed out, not listed as
     parts.
   - Next: "Update blocks from library": lists a project's blocks that differ from the
     library's and updates only the ones chosen (0.12 updates the open project's copies right
     after a block is changed; other projects keep theirs until then).
8. **Reports**: cables between locations (done in 0.15: the owner's "what cables need to be
   pulled between panels and where all the wires need to be landed on both sides"; locations
   per sheet or device, runs with landings, cable tag/type/marking and colors editable, CSV and
   PDF; lengths left to the job), bill of materials (done in 0.14: parts by manufacturer and catalog number, a
   device and its footprint once, rail and duct as stock lengths, CSV), wire list and terminal
   strip list (done in 0.19.1, CSV). Excel export (openpyxl, MIT, imported only when
   exporting) and report sheets drawn in the project: done in 0.21.
9. ~~PDF export opening in KanzonasPDF~~: dropped (the owner, Nov 2026: low value; opening a
   .kzcad in KanzonasPDF would be KanzonasPDF's feature, not this one's).
10. **Check out / check in** sheets (can wait: the owner, Nov 2026): export chosen sheets (with their blocks, parts and
   settings) for someone else, lock them while out, check them back in matched by sheet id
   with a summary of changes; references and numbers recalculate.
11. **AutoCAD export with real blocks** (phase 1 done in 0.20: blocks, attributes, read back
    as the same symbols; next, the AutoCAD Electrical attribute names option, then the owner
    trying it in AutoCAD Electrical) (the owner, Nov 2026: "blocks stay as blocks and
    doesn't come in as lines and text"; DXF export today explodes every block reference into
    lines and texts, fileio.export_dxf). The middle ground, the owner's choice:
    - Each symbol and footprint written as a BLOCK definition and placed as an INSERT (its
      position, turn, scale, mirror), its attributes as real ATTDEF/ATTRIB (tag, description,
      part number, maker, ratings; hidden ones hidden), so AutoCAD's attribute editor and data
      extraction work on them. Layers with their names and colors; wires as polylines on
      their layers; dimensions, hatches and multi-line text as their own kinds. DXF (AutoCAD
      opens it and saves it as DWG); writing DWG would need the ODA File Converter.
    - An option, **AutoCAD Electrical attribute names**: TAG1, MFG, CAT, DESC1-3, LOC, INST and
      the terminal attributes, as KanzonasCAD's DWG/DXF import already reads them, so AutoCAD
      Electrical can find tags and parts. Not promised: full AutoCAD Electrical intelligence
      (its WD_M block, wire-number blocks, xdata, the .wdp project) - to be checked against
      the owner's AutoCAD Electrical before going further.
    - Tested by reading the export back (ezdxf: blocks, inserts, attributes match the
      drawing) and by the owner opening it in AutoCAD.
12. PLC I/O (0.19 started it: whole-module boxes, Rockwell POINT I/O 1734-IB8/OB8/OB8E/IE8C/
    OE4C/VTM/CTM and generic 4/8/16-point modules; the owner asked for one box per module, as
    a 1756-IF16 "SLOT 7" with its terminals down one side, one a rung). Still to come: a
    0.19.1 added modules continued on the next sheet (a 16-point module as "points 0-7" and a
    linked "points 8-15 continued" piece) and IN/RTN analog input modules. Still to come: more
    catalogs as the owner sends their wiring diagrams (a 1756-IF16 by its own terminal map once
    its wiring mode is confirmed). Known: a wide bus
    (11 wires off a 16-point module) turned closer than it is wide runs its inner wires back
    over the ones drawn (the battery, seed 2203); a first try at refusing such turns also
    refused Bus's own routes around symbols, so it was taken back out of 0.19.
13. **Platforms** (the owner, Nov 2026: "one thing that this program really has going for it is
    that I don't think there are a lot of cad programs, especially electrical in the Linux
    space. Same with Mac. I think we need to add Mac to the roadmap"):
    - **macOS**: the same program as a `.app` in a `.dmg`, built by a macOS job in the same
      workflow (PySide6 and ezdxf run on macOS; the work is packaging, menus where macOS puts
      them, Cmd for Ctrl, its own settings and data folders through `paths.py`, and the
      self-test run in the build). Update now on macOS: replace the app in place as the
      AppImage does. The owner's decisions (Nov 2026):
      - **Apple Silicon and Intel both** ("3 year old Mac actively in use is probably very
        common. We probably need both"): two downloads, one per kind of Mac, each built and
        self-tested on its own kind of runner, unless every library (PySide6, ezdxf, ezdwg,
        pdfminer.six) has universal2 builds, then one universal app. Check that GitHub still
        offers Intel macOS runners when this starts; if not, the Intel app is built on an
        Apple Silicon runner under Rosetta and tested there.
      - **Unsigned first**: no Apple developer program yet; the download page says how to
        allow it (System Settings, Privacy & Security, Open Anyway). Signing and notarizing
        later, once Mac users show up.
    - **Linux, more at home**: the app offers to add itself to the applications menu and to
      open `.kzcad` files on a double-click (as KanzonasPDF's linux_desktop.py does); listed on
      Flathub and AppImageHub (the AppStream metadata exists already: packaging/linux).
14. Later (all wanted: the owner, Nov 2026): terminal strips, DWG export (written by our own
    code: the owner, "You write it. Don't rely on some third party tool"), Sheets panel as a
    popup. Done in 0.21: PLC I/O from a spreadsheet, the color PDF option, in-place text
    editing.
15. **Editing an array** (done in 0.21; the owner, Nov 2026): the copies stay linked as one
    array until exploded; Edit array changes its spacing, rows and columns, or a polar array's
    count and angle. Copies added take tags of their own, copies kept keep theirs; wires on
    copies taken away stay where they are, unconnected (flagged by the near-miss marker).
    Still to come: a properties box and array grips.

## Decided while the owner was away (Nov 2026; released in 0.21, to confirm)
- **Power distribution block** (0.21): two symbols, the block (L1-L3 in, tag PDB) and its
  outlet (T1-T3 out, PDB101-1...), not one box with outlets drawn on it: an outlet can sit on
  any sheet beside what it feeds, as a contact beside its load. The block is where the feeder
  ends (a bus going on past it isn't cut); outlets letter their wires by their own number
  (outlet 3: C, even when 2 isn't drawn); OUTLETS is typed as on the part (1:18 or 18).

- **Pictures and SVG** (0.21): a picture comes in 2" wide on paper (resized with its corner
  grips, keeping its shape); it is drawn under everything and never flipped by Mirror; kept as
  PNG or JPEG as it came (other kinds turned into PNG), up to 15 MB. An SVG too complex to edit:
  over 20,000 straight pieces, 5,000 elements or 5 MB, refused whole (nothing half brought in);
  its colors, fills and fonts are left out, its lines go on the sheet's current layer 0.

- **Editing an array** (0.21): editing one copy on its own takes it out of the array (rather
  than changing every copy); Edit array asks the numbers again on the command line, as Array
  does (no dialog, no array grips yet); an array whose original objects are erased or moved on
  their own is no longer one. Arrays made before 0.21 can't be edited (they weren't kept).

- **Parts** (0.21): Assign part works on the selection (not "every contactor on the sheet" by
  itself: select them first); the brand is typed in the Assign part window and kept per project;
  a device whose symbol isn't the part's is left alone and counted in the message; Save to
  library as part needs a catalog number, and the same maker and catalog number updates that
  part. Not yet: the footprint from the part on panel insert (devices not yet on a panel are
  flagged since 0.25: Devices without a footprint).

- **Library parts** (0.21): one file a part done first, on its own (the two folders' shared
  library needs it); parts.json moves to the files at the first save or delete, not at start-up
  (opening a library never changes it).
- **Second library folder** (0.21): a name in both libraries shows the first's only (not both,
  as the roadmap said: one name, one block when placing); saving doesn't ask each time which
  library: a checkable "Save new blocks and parts to the second library" (Library menu) says, and
  anything already in a library is saved back there. Not yet: watching the folders for others'
  changes (the Library panel refreshes when it opens).

- **Report sheets** (0.21): drawn as plain lines and texts (not a live table), drawn again by
  Update report sheets rather than at every change (keeps edits fast), placed after the sheet
  shown; a cell too long for its column is cut with an ellipsis.

- **In-place text editing** (0.21): clicking elsewhere keeps what was typed (as AutoCAD);
  an emptied text is left as it was (not erased); the text's window moved to right-click Text
  properties...; leaders and dashed boxes still open their windows.

- **I/O list import** (0.21): one module a sheet (as the owner's one box per module); the
  columns read by name (Slot, Catalog, Point, Address, Tag, Description); a point's text is
  "address  tag  description" beside its terminal (no wire drawn to it, no PLC input symbol);
  a module or point the library hasn't got is left out and named, never guessed.

## Standing decisions
- Bringing in drawings from PDFs and pictures (owner, Nov 2026: "a feature ... that literally
  only does lines and text. That way, I can pull in a picture, PDF, screenshot, whatever of a
  drawing or schematic"; both kinds wanted, no preference which first). Lines and text only:
  no symbols or wires recognized. Step 1, done in 0.17: PDFs that hold lines and text (made or
  printed by a CAD program), with pdfminer.six (MIT; PyMuPDF stays ruled out, AGPL). Step 2,
  next: pictures, screenshots, scans and photos: lines found in the pixels (OpenCV,
  Apache-2.0) and text read (OCR: Tesseract or an ONNX model, Apache-2.0), the scale set by
  two points and their real distance, a photo straightened by its four corners first; its
  results reviewed by the user, as they won't be exact. Heavy libraries imported only when
  used.
- Printing and windows (owner, Nov 2026; 0.16): "I need to be able to print selected or all
  sheets": File > Print... prints this sheet, all sheets or those picked (several selected in
  the Sheets panel start ticked), on a printer or into a PDF file; Fit to paper by default
  (owner's choice), turned to match the paper; Actual size as the option. "I would like to be
  able to pull out a drawing tab to another screen": asked whether a whole project or any sheet,
  the owner chose any sheet in its own window. Windows on one project share it (one Undo, one
  Save); a project tab can also be moved or dragged out to a window of its own.
- Testing (owner, Nov 2026): "Let's do the extended battery on every big update 0.xx.0. And the
  smaller battery can be done on minor updates." Every build runs the short battery (1,000
  steps); a middle-number release (0.16...) also runs the long one (3,000 steps x 3 seeds, job
  battery-long) before it is published. The battery checks what commands must do, not only
  that the model holds together (owner: "I want all of those added to the battery checks":
  varied and far drawings, correctness checks, the mouse and the view, real-style files,
  Windows paths, speed on imported drawings).
- Imports (owner, Nov 2026; 0.12.11-0.13.5): DWG read object by object (dwgread); imported
  blocks stay blocks with their colors and attributes (AutoCAD Electrical's mapped); linear and
  aligned dimensions, leaders, multileaders, hatches and multiline text come in as
  KanzonasCAD's own; Use as title block takes an imported title block. Leaders and
  multileaders are one tool (Leader, with numbered balloons).
- Revisions (owner, Nov 2026; 0.12.8): a revision history per project, numbered 0, 1, 2...,
  each covering all sheets or the ones named; the title block's {Revision} and {Date} follow
  the latest revision of each sheet. Footprints show a label of the user's choice per copy
  (tag, part number, description, block name), set for a selection (0.12.7).
- One `.kzcad` file per project (all sheets inside). It is plain JSON, readable by anyone: the
  working file, shared with other KanzonasCAD users as it is. DXF and PDF are for people
  without KanzonasCAD.
- Exported DXFs carry KanzonasCAD's data too (owner's choice, Nov 2026): devices, tags and
  hidden ids, block roles, the sheet's page number and zones, stored as XDATA/dictionaries
  under KanzonasCAD's own application name. Other programs ignore it; importing such a DXF
  back restores devices instead of plain lines, and data a program left stale (a symbol moved
  or erased in AutoCAD) is checked against the geometry and dropped, never trusted blindly.
  Documented openly (docs/DXF_DATA.md) so any program can read it.
- No AutoCAD Electrical project export for now (owner, Nov 2026: "let's leave acade project
  export off the table for awhile"). It would mean blocks with TAG1/MFG/CAT/DESC1-3 and
  X?TERMnn wire-connection attributes, a .wdp listing the sheets, and DWG files (ezdxf writes
  only DXF). The owner has AutoCAD Electrical to test it with if it comes back.
- US practice: JIC/NFPA symbols, horizontal rungs, grid-style references (`6-D1`), zones A-H
  down the left and 1-10 along the top to start (both editable). IEC 60617 symbols as a
  project's choice since 0.29 (Symbol standard; the owner, 0.22.1: "also put in IEC
  symbols"), JIC to start.
- Drawing area black by default; PDF black on white to start. Export to PDF asks color or
  black and white in its window (Save as type) and keeps the last pick (the owner, 0.26: "the
  Export PDF window gets a Color / Black and white choice that remembers the last pick"; the
  same setting as Options' Export to PDF in the layers' colors).
- Paste (the owner, 0.26): a click places the objects by their lower left corner; Enter
  instead puts them at the exact coordinates they were copied from, on whatever sheet is
  shown (copy from sheet 1, paste on sheet 2 in the same spot; AutoCAD's PASTEORIG).
- A file that can't be written (a PDF open in Adobe, a workbook open in Excel) is always said
  in a message box, never passed over (the owner, 0.26); PDFs are written beside the file and
  put in its place, so an old PDF never passes for the new one.
- Revisions: one project revision, each sheet may override it.
- The library lives outside the program (Documents\KanzonasCAD Library); projects keep their
  own copies of the blocks (and, from part assignment on, parts) they use.
- The title block is the project's own drawing with fields (Project properties is its form;
  Sheets > Edit title block redraws it); new fields like `{Scale}` are added as features need.
- Templates (owner, Nov 2026): a template is an ordinary project, sheets and field values
  included (no "include sheets" switch, no fields cleared): what's in it is what a new project
  gets. Kept in the library's Templates folder; the default is chosen in Edit > Options....
- Options (Edit menu) holds what belongs to the user and computer; Project properties what
  belongs to one project.
- Delete component (not the Delete key) joins the wire back up through a deleted symbol;
  Erase leaves the gap, as in AutoCAD Electrical.
- Logos (owner, Nov 2026): every Kanzonas logo comes from the Kanzonas-Site repository's
  `brand/` folder (its make_logos.py, artwork, fonts and SPEC.md), the single source of truth.
  A logo is changed there, never here, and its files copied in (brand/README.md says where).
- Full GitHub releases for each new version on main; the app updates itself.
- Builds as in KanzonasPDF (owner, Nov 2026): every push builds; a finished piece of work is
  pushed, its pull request opened and merged once the `build` and `linux` checks are green
  (a rule on `main` enforces it), which publishes the release: build and publish in one go.
