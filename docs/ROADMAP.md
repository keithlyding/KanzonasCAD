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
- Multi-sheet projects with a sheet list and sheet types (schematic, panel, report, other):
  done since 0.1/0.2.

## Next, in build order (each its own pull request with tests)
1. **Device tags by page number**: prefix + page + 2-digit count (`CR601`, `M601`; page 12:
   `CR1201`), per prefix and page. New devices get the lowest free number; a tag typed by hand
   is locked; Renumber sheet re-sequences the unlocked ones (across then down, or down then
   across, per sheet). A device's page part follows its sheet's page number. Every device also
   gets a hidden id that survives renaming. Contacts (child symbols) take their parent's tag
   (picking the parent comes with cross-references).
2. **DWG import** built in, with **ezdwg** (MIT, reads R13-2018, i.e. every current AutoCAD
   file): opening or importing a `.dwg` works like DXF, nothing to install. The ODA File
   Converter, when installed, is only a fallback for a file ezdwg can't read. DXF stays the
   export format. Fixes go in our import code first, upstream to ezdwg second; fork only if
   urgent (its core is Rust).
3. **Panel sheets and dimensions**:
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
4. **Part assignment**: projects keep their own copies of the parts they use (as they do of
   blocks), so a part leaving the library never breaks a drawing.
   - Symbol, footprint and part stay three separate things; the symbol never knows the brand.
   - Draw with the generic symbol; assign a part now or later. The part picker is filtered to
     parts using the clicked symbol; a project default brand (e.g. Allen-Bradley) sorts first.
   - Bulk assign: select every contactor on the sheet, pick a part once.
   - Placing a device on a panel sheet pulls the footprint from its part. Panel insert can pick
     from the schematic's devices, so tag and cross-reference come along; the schematic side
     flags devices not yet placed on a panel.
5. **Library management**:
   - Right-click a placed symbol with a part -> "Save to library as part" (name defaults to
     the catalog number): writes symbol + footprint + part into the library.
   - Library browser: right-click Edit or Delete. Single delete asks once. Bulk delete asks
     once with the count ("Delete 14 parts?"); if some are used in the open project, ask
     separately ("2 of these are in your project. Delete those too?": No deletes only the
     unused ones). Deleting from the library never breaks placed symbols.
6. **Cross-references and wire numbers**:
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
   - **Wire numbers**: page number + 3 digits (`6001`); one number per connected group of
     wires, changing only through a device or terminal; after a distribution block the
     branches get A-Z suffixes (`6001A`...`AA`); a wire continuing to another sheet keeps the
     number of the sheet it starts on; sequence across-then-down or down-then-across per
     sheet; numbers stay stable once given; deleted numbers are reused; locking and Renumber
     sheet.
7. **Reports**: bill of materials, wire list, terminal strip list (Report sheets; CSV and Excel
   via openpyxl, MIT, imported only when exporting).
8. **PDF export opening in KanzonasPDF** when it is installed (export exists).
9. **Check out / check in** sheets: export chosen sheets (with their blocks, parts and
   settings) for someone else, lock them while out, check them back in matched by sheet id
   with a summary of changes; references and numbers recalculate.
10. Later: terminal strips, PLC I/O from a spreadsheet, DWG export, color PDF option,
    in-place text editing, Sheets panel as a popup.

## Standing decisions
- One `.kzcad` file per project (all sheets inside).
- US practice: JIC/NFPA symbols, horizontal rungs, grid-style references (`6-D1`), zones A-H
  down the left and 1-10 along the top to start (both editable).
- Drawing area black by default; PDF always black on white.
- Revisions: one project revision, each sheet may override it.
- The library lives outside the program (Documents\KanzonasCAD Library); projects keep their
  own copies of the blocks (and, from item 4, parts) they use.
- The title block is the project's own drawing with fields (Project properties is its form;
  Sheets > Edit title block redraws it); new fields like `{Scale}` are added as features need.
- Full GitHub releases for each new version on main; the app updates itself.
- Builds: push with `[skip ci]` until the owner says "build"; merge to `main` only through a
  pull request once the `build` and `linux` checks are green (a rule on `main` enforces it).
