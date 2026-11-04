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
- Multi-sheet projects with a sheet list and sheet types (schematic, panel, report, other):
  done since 0.1/0.2.

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
   - Later: "Update from library" lists a project's blocks that are older than the library's
     and updates only the ones chosen.
8. **Reports**: bill of materials (DIN rail and wire duct by length and stock pieces), wire list, terminal strip list (Report sheets; CSV and Excel
   via openpyxl, MIT, imported only when exporting).
9. **PDF export opening in KanzonasPDF** when it is installed (export exists).
10. **Check out / check in** sheets: export chosen sheets (with their blocks, parts and
   settings) for someone else, lock them while out, check them back in matched by sheet id
   with a summary of changes; references and numbers recalculate.
11. Later: terminal strips, PLC I/O from a spreadsheet, DWG export, color PDF option,
    in-place text editing, Sheets panel as a popup.

## Standing decisions
- One `.kzcad` file per project (all sheets inside). It is plain JSON, readable by anyone: the
  working file, shared with other KanzonasCAD users as it is. DXF and PDF are for people
  without KanzonasCAD.
- Exported DXFs carry KanzonasCAD's data too (owner's choice, Nov 2026): devices, tags and
  hidden ids, block roles, the sheet's page number and zones, stored as XDATA/dictionaries
  under KanzonasCAD's own application name. Other programs ignore it; importing such a DXF
  back restores devices instead of plain lines, and data a program left stale (a symbol moved
  or erased in AutoCAD) is checked against the geometry and dropped, never trusted blindly.
  Documented openly (docs/DXF_DATA.md) so any program can read it.
- US practice: JIC/NFPA symbols, horizontal rungs, grid-style references (`6-D1`), zones A-H
  down the left and 1-10 along the top to start (both editable).
- Drawing area black by default; PDF always black on white.
- Revisions: one project revision, each sheet may override it.
- The library lives outside the program (Documents\KanzonasCAD Library); projects keep their
  own copies of the blocks (and, from part assignment on, parts) they use.
- The title block is the project's own drawing with fields (Project properties is its form;
  Sheets > Edit title block redraws it); new fields like `{Scale}` are added as features need.
- Full GitHub releases for each new version on main; the app updates itself.
- Builds as in KanzonasPDF (owner, Nov 2026): every push builds; a finished piece of work is
  pushed, its pull request opened and merged once the `build` and `linux` checks are green
  (a rule on `main` enforces it), which publishes the release: build and publish in one go.
