"""Python's garbage collector without long stalls on big drawings (0.26).

Python's cycle collector now and then goes through every object the program holds (a "full
collection"). With big projects open (many sheets of blocks and wires, a long Undo) that is
hundreds of thousands to millions of objects: 60 to 860 ms at a time in the 0.25 self-test,
found nearly always to collect nothing, the window frozen meanwhile (three flaky timing
failures on the builds came from it).

What is done about it: right after each full collection, every object still alive is set
aside (gc.freeze): the collector doesn't go through them again. The next full collection goes
only through what was made since the one before, so a long-lived drawing is gone through once.

Python waits for a full collection until a quarter as many objects as the last one kept have
been made since: after one of a big drawing, that is hundreds of thousands, gone through at
once (80 ms). So soon after (call_soon, the event loop's next turn) a second full collection
follows, of the few objects made in between, and Python counts from that: full collections
then come often and each goes through little (a few ms).

Objects set aside that are no longer used are still freed at once (by their reference count);
only rings of objects that point at each other (cycles) aren't, until sweep() goes through
everything again. That is done when a project is closed (its views, Undo and caches point at
each other: hundreds of MB otherwise kept); working on a drawing leaves no such rings.

Only after a full collection (generation 2): Python 3.12 and 3.13 make those on their own; a
Python whose collector works in increments reports those as younger generations, and nothing
is set aside in the middle of one. No Qt here: MainWindow gives call_soon."""

import gc

_state = {"on": False, "call_soon": None, "due": False, "recounting": False}


def _after_collection(phase, info):
    if phase != "stop" or info.get("generation") != 2:
        return
    gc.freeze()             # (what survived a full collection: not gone through again)
    soon = _state["call_soon"]
    if soon is not None and not _state["due"] and not _state["recounting"]:
        _state["due"] = True
        soon(_recount)


def _recount():
    """The second, small full collection (see above): Python counts from what it kept."""
    _state["due"] = False
    if not _state["on"]:
        return
    _state["recounting"] = True
    try:
        gc.collect()
    finally:
        _state["recounting"] = False


def install(call_soon=None):
    """Set aside what outlives each full collection from now on (once; MainWindow starts it).
    call_soon(f): f run once the work at hand is done (the event loop's next turn)."""
    if call_soon is not None:
        _state["call_soon"] = call_soon
    if not _state["on"]:
        gc.callbacks.append(_after_collection)
        _state["on"] = True


def uninstall():
    """Back to Python's own way, everything given back to the collector (at quitting: the
    objects left are then collected before Qt is torn down)."""
    if _state["on"]:
        gc.callbacks.remove(_after_collection)
        _state["on"] = False
    gc.unfreeze()


def installed():
    return _state["on"]


def _twice():
    _state["recounting"] = True
    try:
        n = gc.collect()            # (the callback sets aside what is left)
        if _state["on"]:
            gc.collect()            # (and Python counts from the few made since: see above)
    finally:
        _state["recounting"] = False
    return n


def settle():
    """A full collection of what was made since the last one (cheap: the rest is set aside),
    that set aside too: after a project is opened, so working on it doesn't go through its
    objects again. The number of objects freed."""
    return _twice()


def sweep():
    """Everything gone through once more, the rings of objects no longer used freed (after a
    project is closed); what is left is set aside again. The number of objects freed."""
    gc.unfreeze()
    return _twice()
