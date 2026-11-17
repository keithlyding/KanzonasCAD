"""Numbering texts (no Qt; the owner, 0.16: "automatic numbering. So I would select whatever
text boxes and then choose 1,2,3...; A,B,C...; S1, S2, S3...; A1, B2,C3... etc and it would
change the ones selected either top to bottom, left to right or left to right, top to
bottom"), as AutoCAD Express Tools' TCOUNT.

A number is prefix + the sequence's value + suffix. Sequences:
- "number": 1, 2, 3 (start and step any whole numbers; padded to digits: 01, 02);
- "letter": A, B, C ... Z, AA, AB (start a letter; step whole);
- "lower": a, b, c ...;
- "letter_number": A1, B2, C3 (the letter and the number go up together).
The texts are taken in order: "down" (top to bottom, then the next column to the right) or
"across" (left to right, then the next row down); texts at about the same height (or the same
place across) make one row (or column)."""

SEQUENCES = ("number", "letter", "lower", "letter_number")
ORDERS = ("down", "across")
MODES = ("replace", "before", "after")


def letters(n):
    """1 -> A, 26 -> Z, 27 -> AA (as spreadsheet columns)."""
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def letter_index(s):
    """A -> 1, Z -> 26, AA -> 27; None when it isn't letters."""
    s = (s or "").strip().upper()
    if not s or not s.isalpha() or not s.isascii():
        return None
    n = 0
    for ch in s:
        n = n * 26 + (ord(ch) - 64)
    return n


def value(sequence, i, start="1", step=1, digits=0, letter_start="A"):
    """The i-th (from 0) value of a sequence."""
    if sequence in ("letter", "lower"):
        k = (letter_index(start) or 1) + i * step
        v = letters(max(1, k))
        return v.lower() if sequence == "lower" else v
    num = int(start) + i * step
    txt = str(abs(num)).zfill(max(0, int(digits)))
    txt = ("-" + txt) if num < 0 else txt
    if sequence == "letter_number":
        k = (letter_index(letter_start) or 1) + i * step
        return letters(max(1, k)) + txt
    return txt


def labels(count, sequence="number", start="1", step=1, digits=0, prefix="", suffix="",
           letter_start="A"):
    return [prefix + value(sequence, i, start, step, digits, letter_start) + suffix
            for i in range(count)]


def _middle(e):
    """Where a text is for ordering: its insertion point (texts in a column line up on it,
    however long each is: their middles don't), else the middle of its box."""
    pos = getattr(e, "pos", None)
    if pos is not None:
        return pos
    bb = e.bbox()
    return ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)


def ordered(texts, order="down"):
    """The texts in numbering order. down: columns left to right, each top to bottom;
    across: rows top to bottom, each left to right. Texts whose middles are within half the
    usual text height of each other across (or up and down) are one column (or row), by their
insertion points."""
    texts = list(texts)
    if not texts:
        return []
    hs = sorted(getattr(e, "height", 0.1) or 0.1 for e in texts)
    tol = hs[len(hs) // 2] * 0.5
    mids = {id(e): _middle(e) for e in texts}
    k = 0 if order == "down" else 1             # (what makes a column, or a row)
    keyed = sorted(texts, key=lambda e: (mids[id(e)][k] if k == 0 else -mids[id(e)][k]))
    groups, cur, last = [], [], None
    for e in keyed:
        c = mids[id(e)][k]
        if last is not None and abs(c - last) > tol:
            groups.append(cur)
            cur = []
        cur.append(e)
        last = c
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        if order == "down":
            g.sort(key=lambda e: (-mids[id(e)][1], mids[id(e)][0]))
        else:
            g.sort(key=lambda e: (mids[id(e)][0], -mids[id(e)][1]))
        out += g
    return out


def apply_to(text, label, mode="replace"):
    if mode == "before":
        return label + text
    if mode == "after":
        return text + label
    return label
