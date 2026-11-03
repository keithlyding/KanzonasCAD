# KanzonasCAD roadmap and decisions

Decisions the owner has made, so every agent and person builds the same thing. Change this
file when a decision changes.

## Done
- 0.1: sheets with zones and title block, AutoCAD-style drawing, layers, DXF/PDF.
- 0.2 (branch `claude/symbol-library`): symbol, footprint and parts library; Make block,
  Insert, Explode; Scale Reference and mm input; text justification; editable zones;
  Project vs Sheet properties; Schematic and Panel ribbon tabs; ByLayer colors; sheet types;
  backups, autosave and recovery.

## Next, in order
1. **Wires** that stay attached to pins; breaking a wire where a symbol is placed on it.
2. **Device tags by page number**: prefix + page + 2-digit count (`CR601`, `M601`; page 12:
   `CR1201`). New devices get the next free number; a tag can be locked; Renumber sheet
   re-sequences the unlocked ones. Contacts (child symbols) take their parent's tag.
3. **Cross-references**, AutoCAD Electrical style:
   - Under a coil / operator: one line per contact with an NO or NC mark and its location
     (`6-D3`); next to each contact: its coil's location (`6-D1`).
   - Each device's listing can be switched off, and each contact line in it on or off.
     Spare (unused) contacts shown as hollow marks: a setting, off by default.
   - **Panel sheets too**: a footprint carries its device's tag; the footprint shows where
     the device is on the schematic, and the device where its footprint is on the panel.
   - **Updated automatically** after every change (computed from the drawing, never stored as
     text that can go stale). Project setting "Update cross-references automatically" (on by
     default); per-sheet **Freeze cross-references** for issued sheets; a status bar warning
     "Cross-references out of date" and an **Update cross-references** command whenever
     anything is off or frozen.
   - Format follows the project's grid reference format and each sheet's zones.
4. **Wire numbers**: page number + 3 digits (`6001`); one number per connected group of wires,
   changing only through a device or terminal; after a distribution block the branches get
   A-Z suffixes (`6001A`, `6001B`..., then `AA`); a wire continuing to another sheet keeps the
   number of the sheet it starts on; sequence left-to-right/top-to-bottom or
   top-to-bottom/left-to-right per sheet; numbers stay stable once given; deleted numbers are
   reused for the next wire; locking and Renumber sheet.
5. **Dimensions** (linear, aligned, radius...) and panel sheet **scale** (footprints at real
   size shown at the sheet's scale; dimensions read real lengths; text stays sheet-size: no
   AutoCAD-style annotative objects).
6. **Reports**: BOM, wire list, terminal plan (Report sheets; Excel/PDF).
7. **Check out / check in** sheets: export chosen sheets (with their blocks and settings) for
   someone else, lock them in the project while out, check them back in matched by sheet id
   with a summary of changes; references and numbers recalculate.
8. Later: terminal strips, PLC I/O from a spreadsheet, DWG via the ODA File Converter if
   installed, color PDF option, in-place text editing.

## Standing decisions
- One `.kzcad` file per project (all sheets inside).
- US practice: JIC/NFPA symbols, horizontal rungs, grid-style references (`6-D1`), zones A-H
  down the left and 1-10 along the top to start (both editable).
- Drawing area black by default; PDF always black on white.
- Revisions: one project revision, each sheet may override it.
- The library lives outside the program (Documents\KanzonasCAD Library); projects keep their
  own copies of the blocks they use.
- Builds: push with `[skip ci]` until the owner says "build"; merge to `main` only through a
  pull request once both builds are green.
