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
5. **Panel sheets and dimensions**:
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
6. **Part assignment**: projects keep their own copies of the parts they use (as they do of
   blocks), so a part leaving the library never breaks a drawing.
   - Symbol, footprint and part stay three separate things; the symbol never knows the brand.
   - Draw with the generic symbol; assign a part now or later. The part picker is filtered to
     parts using the clicked symbol; a project default brand (e.g. Allen-Bradley) sorts first.
   - Bulk assign: select every contactor on the sheet, pick a part once.
   - Placing a device on a panel sheet pulls the footprint from its part. Panel insert can pick
     from the schematic's devices, so tag and cross-reference come along; the schematic side
     flags devices not yet placed on a panel.
7. **Library management**:
   - Right-click a placed symbol with a part -> "Save to library as part" (name defaults to
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
   strip list (done in 0.19.1, CSV). Still to come: Excel export (openpyxl, MIT, imported only
   when exporting) and report sheets drawn in the project.
9. **PDF export opening in KanzonasPDF** when it is installed (export exists).
10. **Check out / check in** sheets: export chosen sheets (with their blocks, parts and
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
14. Later: terminal strips, PLC I/O from a spreadsheet, DWG export, color PDF option,
    in-place text editing, Sheets panel as a popup.

## Decided while the owner was away (Nov 2026; to confirm)
- **Pictures and SVG** (0.20.1): a picture comes in 2" wide on paper (resized with its corner
  grips, keeping its shape); it is drawn under everything and never flipped by Mirror; kept as
  PNG or JPEG as it came (other kinds turned into PNG), up to 15 MB. An SVG too complex to edit:
  over 20,000 straight pieces, 5,000 elements or 5 MB, refused whole (nothing half brought in);
  its colors, fills and fonts are left out, its lines go on the sheet's current layer 0.

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
  down the left and 1-10 along the top to start (both editable).
- Drawing area black by default; PDF always black on white.
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
