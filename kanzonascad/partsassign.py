"""Parts on devices (the roadmap's item 6 and the owner's "Save to library as part", Nov 2026).

- Assign part: every device selected that uses a part's symbol takes the part (its maker,
  catalog number and description, and the part's id), in one edit; the parts offered are those
  for the selected symbols, the project's brand first (project setting "brand").
- The project keeps its own copy of each part it uses (project setting "parts": {id: part}),
  so a part taken out of the library, or changed there, never changes a drawing.
- Save to library as part: a placed device's maker, catalog number and description, its symbol
  and the footprint linked to it, saved to the library as a part (its symbol and footprint too
  when the library hasn't got them).

No Qt: the windows (main_window) ask and say."""

from . import model as M
from . import tags


def devices(sheet, ids):
    """The selected objects that can take a part: devices (not contacts or footprints)."""
    out = []
    for i in ids:
        e = sheet.entities.get(i)
        if isinstance(e, M.Insert) and tags.is_device(e):
            out.append(e)
    return out


def candidates(library, ents, brand=""):
    """The library's parts for the selected devices' symbols, the brand's first, then by
    maker and catalog number."""
    names = {e.block for e in ents}
    got = [p for p in library.parts() if p.symbol in names]
    b = (brand or "").strip().lower()
    got.sort(key=lambda p: (0 if b and p.manufacturer.strip().lower() == b else 1,
                            p.manufacturer.lower(), p.catalog.lower()))
    return got


def assign(ed, project, sheet, ents, part):
    """The part on every device given that uses its symbol (the others left as they are),
    and a copy of it kept in the project. Returns how many took it."""
    n = 0
    for e in ents:
        if e.block != part.symbol:
            continue
        ed.change(sheet, e.copy(attrs=dict(e.attrs, **part.attrs())))
        n += 1
    if n:
        kept = dict(project.settings.get("parts") or {})
        kept[part.id] = part.to_dict()
        ed.project_settings({"parts": kept})
    return n


def linked_footprint(project, dev):
    """The block name of the footprint linked to a device (its PARENT is the device's DEV),
    or ""."""
    dev_id = dev.attrs.get("DEV")
    if not dev_id:
        return ""
    for s in project.sheets:
        for e in s.inserts():
            if tags.is_footprint(e) and e.attrs.get("PARENT") == dev_id:
                return e.block
    return ""


def part_from(project, dev):
    """A part made from a placed device (Save to library as part), or (None, why)."""
    from .library import Part
    cat = (dev.attrs.get("CAT") or "").strip()
    if not cat:
        return None, "give it a catalog number first (double-click it: Catalog number)"
    return Part(manufacturer=(dev.attrs.get("MFR") or "").strip(), catalog=cat,
                description=(dev.attrs.get("DESC") or "").strip(), symbol=dev.block,
                footprint=linked_footprint(project, dev)), None
