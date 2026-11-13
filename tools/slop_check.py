"""Look for slop in the code and the text people read (the owner, Nov 2026: "please add a
search for slop in future testing"): what careless or machine-written changes leave behind.
Every build runs it (tests/test_slop.py); by hand: python tools/slop_check.py

Fails on:
- an error swallowed: a bare `except:`, or `except Exception` / `BaseException`, whose block
  neither re-raises, uses the error, tells anyone, nor says on its `except` line why it may
  pass silently (AGENTS.md: "Errors are not swallowed");
- a placeholder left in: TODO, FIXME, XXX, HACK, TBD or lorem ipsum, in the program or what
  people read;
- print() in the program (it talks through the command line, message boxes and the log);
- an import nothing uses (the program and tools);
- a function, class or method of the program nothing calls or names anywhere (Qt's own
  overrides aside);
- a comment, docstring or rules file naming something that doesn't exist (module.name or
  Class.member), as after a rename or a move;
- filler words in the manual, the release notes and the README ("seamless", "robust",
  "leverage", "utilize"...): the project writes plainly;
- a test that checks nothing (no assertion, check or failure path), or asserts a constant;
- commented-out code in the program;
- a block of 8 or more lines repeated in the program (one function, not two copies).

A line may opt out with a comment `slop-ok: <why>` on it (or on its def for a function).
"""

import ast
import io
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "kanzonascad")

# names Qt (or Python) calls on the program's classes itself
CALLED_BY_QT = re.compile(r"(Event|Hint|^paint$|^run$|^accept$|^reject$|^exec$|^done$|"
                          r"^data$|^rowCount$|^columnCount$|^flags$|^setData$|^headerData$|"
                          r"^clone$|^pixmap$|^eventFilter$|^__\w+__$)")
FILLER = re.compile(r"\b(seamless(ly)?|robust(ly|ness)?|leverag(e|es|ed|ing)|utiliz(e|es|ed|ing|"
                    r"ation)|delve|effortless(ly)?|empower(s|ed|ing)?|"
                    r"streamlin(e|ed|es|ing)|rest assured|it's worth noting|elevate(s|d)? your|"
                    r"game[- ]chang|state[- ]of[- ]the[- ]art|best[- ]in[- ]class|supercharg|"
                    r"harness(es|ing)? the|revolutioni[sz])", re.I)
PLACEHOLDER = re.compile(r"\b(TODO|FIXME|XXX|HACK|TBD)\b|[Ll]orem ipsum")      # (capitals: a
                                                                            # variable "todo" is fine)
# short names the code uses for the program's modules (import ... as)
ALIASES = {"M": "model", "G": "geometry", "C": "commands", "F": "scalefit", "OS": "osnap",
           "BC": "battery_checks"}


def _py(folder):
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".py"))


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def _ok(line):
    return "slop-ok:" in line


class Report:
    def __init__(self):
        self.found = []

    def add(self, kind, path, line, what):
        self.found.append((kind, _rel(path), line, what))


def swallowed(rep, files):
    broad = ("Exception", "BaseException")
    for p in files:
        src = _read(p)
        lines = src.splitlines()
        for n in ast.walk(ast.parse(src)):
            if not isinstance(n, ast.ExceptHandler):
                continue
            t = n.type
            if t is not None and not (isinstance(t, ast.Name) and t.id in broad):
                continue
            body = ast.dump(ast.Module(body=n.body, type_ignores=[]))
            reraises = any(isinstance(b, ast.Raise) for b in ast.walk(
                ast.Module(body=n.body, type_ignores=[])))
            uses = n.name is not None and re.search(r"Name\(id='%s'" % n.name, body)
            tells = re.search(r"attr='(write|warning|critical|information|message|messaged|"
                              r"showMessage|add_history|say|append)'", body)
            line = lines[n.lineno - 1]
            if not (reraises or uses or tells or "#" in line or _ok(line)):
                rep.add("swallowed error", p, n.lineno,
                        "broad except that passes silently, with no reason on its line")


def placeholders(rep, files):
    for p in files:
        for i, line in enumerate(_read(p).splitlines(), 1):
            if PLACEHOLDER.search(line) and not _ok(line) and "PLACEHOLDER" not in line:
                rep.add("placeholder", p, i, line.strip()[:90])


def prints(rep, files):
    for p in files:
        for n in ast.walk(ast.parse(_read(p))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print":
                line = _read(p).splitlines()[n.lineno - 1]
                if not _ok(line):
                    rep.add("print", p, n.lineno, line.strip()[:90])


def unused_imports(rep, files):
    for p in files:
        if p.endswith("__init__.py"):
            continue
        src = _read(p)
        lines = src.splitlines()
        tree = ast.parse(src)
        names = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    names[(a.asname or a.name).split(".")[0]] = n.lineno
            elif isinstance(n, ast.ImportFrom):
                for a in n.names:
                    names[a.asname or a.name] = n.lineno
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        # (a name in __all__ or a string, as a re-export or getattr, counts as used)
        strings = " ".join(n.value for n in ast.walk(tree)
                           if isinstance(n, ast.Constant) and isinstance(n.value, str))
        for k, ln in names.items():
            line = lines[ln - 1]
            if k in used or "noqa" in line or _ok(line) or re.search(r"\b%s\b" % k, strings):
                continue
            rep.add("unused import", p, ln, k)


def dead_code(rep, pkg_files, everything):
    import collections
    words = collections.Counter(re.findall(r"[A-Za-z_][A-Za-z0-9_]*",
                                           "\n".join(_read(p) for p in everything)))

    def count(name):
        return words[name]
    for p in pkg_files:
        src = _read(p)
        lines = src.splitlines()
        tree = ast.parse(src)
        for n in tree.body:
            todo = []
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                todo.append((n, n.name))
            if isinstance(n, ast.ClassDef):
                todo += [(m, n.name + "." + m.name) for m in n.body
                         if isinstance(m, ast.FunctionDef)]
            for d, label in todo:
                name = d.name
                if CALLED_BY_QT.search(name) or _ok(lines[d.lineno - 1]):
                    continue
                if count(name) <= 1:
                    rep.add("dead code", p, d.lineno, label + " is never used")


def stale_references(rep, pkg_files, doc_files):
    mods = {os.path.basename(p)[:-3]: p for p in pkg_files}
    defined, members, bases = {}, {}, {}
    for m, p in mods.items():
        tree = ast.parse(_read(p))
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                names.add(n.name)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                names.add(n.id)
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    names.add((a.asname or a.name).split(".")[0])
            if isinstance(n, ast.ClassDef):
                mem = set()
                for b in ast.walk(n):
                    if isinstance(b, ast.FunctionDef):
                        mem.add(b.name)
                    elif isinstance(b, ast.Attribute) and isinstance(b.ctx, ast.Store):
                        mem.add(b.attr)
                    elif isinstance(b, ast.Name) and isinstance(b.ctx, ast.Store):
                        mem.add(b.id)
                members.setdefault(n.name, set()).update(mem)
                bases[n.name] = [getattr(b, "id", getattr(b, "attr", "")) for b in n.bases]
        defined[m] = names

    def all_members(c, seen=()):
        out = set(members.get(c, ()))
        for b in bases.get(c, ()):
            if b not in seen:
                out |= all_members(b, seen + (c,))
        return out
    pat = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")

    def texts(p):
        src = _read(p)
        if not p.endswith(".py"):
            for i, line in enumerate(src.splitlines(), 1):
                yield i, line
            return
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                yield tok.start[0], tok.string
            elif tok.type == tokenize.STRING and \
                    tok.string.lstrip("rbuRBU").startswith(('"""', "'''")):
                yield tok.start[0], tok.string
    for p in doc_files:
        for ln, t in texts(p):
            if _ok(t):
                continue
            for a, b in pat.findall(t):
                mod = ALIASES.get(a, a)
                if mod in mods and b not in defined[mod] and not b.endswith(("py", "md", "txt")):
                    rep.add("stale reference", p, ln, "%s.%s doesn't exist" % (a, b))
                elif a in members and a[:1].isupper() and not b[:1].isupper() and \
                        b not in all_members(a):
                    rep.add("stale reference", p, ln, "%s.%s doesn't exist" % (a, b))


def filler(rep, files):
    for p in files:
        for i, line in enumerate(_read(p).splitlines(), 1):
            m = FILLER.search(line)
            if m and not _ok(line):
                rep.add("filler word", p, i, "%r in: %s" % (m.group(0), line.strip()[:80]))


def empty_tests(rep, files):
    checks = re.compile(r"assert|Assert|fail|raises|check|BC\.|battery\.|_oracle|mouse_")
    for p in files:
        tree = ast.parse(_read(p))
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test"):
                if not checks.search(ast.dump(n)):
                    rep.add("test checks nothing", p, n.lineno, n.name)
            if isinstance(n, ast.Assert) and isinstance(n.test, ast.Constant) and n.test.value:
                rep.add("test checks nothing", p, n.lineno, "assert of a constant")
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and \
                    n.func.attr in ("assertTrue", "assertIsNotNone") and n.args and \
                    isinstance(n.args[0], ast.Constant) and n.args[0].value:
                rep.add("test checks nothing", p, n.lineno, n.func.attr + " of a constant")


def commented_code(rep, files):
    code = re.compile(r"^(def |class |import |from \w+ import |return\b|if .*:$|for .*:$|"
                      r"while .*:$|self\.\w+\s*=|\w+\s*=\s*\S|\w+\(.*\)$)")
    for p in files:
        for i, line in enumerate(_read(p).splitlines(), 1):
            s = line.strip()
            if not s.startswith("#") or s.startswith(("# (", "#!")) or _ok(s):
                continue
            body = s.lstrip("#").strip()
            if code.match(body):
                try:
                    ast.parse(body + (" pass" if body.endswith(":") else ""))
                except SyntaxError:
                    continue
                rep.add("commented-out code", p, i, body[:90])


def repeated_blocks(rep, files, n=8, size=240):
    seen = {}
    for p in files:
        norm = []
        for i, line in enumerate(_read(p).splitlines(), 1):
            s = line.split("#")[0].strip()
            if len(s) > 3 and not s.startswith(('"""', "'''")):
                norm.append((i, re.sub(r"\s+", " ", s)))
        last = None
        for k in range(len(norm) - n + 1):
            block = "\n".join(t for _i, t in norm[k:k + n])
            if len(block) < size:
                continue
            first = seen.get(block)
            if first is None:
                seen[block] = (p, norm[k][0])
            elif last is None or norm[k][0] > last + n:
                rep.add("repeated block", p, norm[k][0],
                        "%d lines also at %s:%d" % (n, _rel(first[0]), first[1]))
                last = norm[k][0]


def run():
    pkg = _py(PKG)
    tools = _py(os.path.join(ROOT, "tools"))
    tests = _py(os.path.join(ROOT, "tests"))
    people = [os.path.join(PKG, "manual.py"), os.path.join(ROOT, "RELEASE_NOTES.md"),
              os.path.join(ROOT, "README.md")]
    rules = [os.path.join(ROOT, "AGENTS.md"), os.path.join(ROOT, "docs", "ROADMAP.md")]
    rep = Report()
    swallowed(rep, pkg + tools)
    placeholders(rep, pkg + [p for p in people if os.path.exists(p)])
    prints(rep, pkg)
    unused_imports(rep, pkg + tools)
    dead_code(rep, pkg, pkg + tools + tests + [os.path.join(ROOT, "run.py")])
    stale_references(rep, pkg, pkg + tests + [p for p in rules if os.path.exists(p)])
    filler(rep, [p for p in people if os.path.exists(p)])
    empty_tests(rep, tests)
    commented_code(rep, pkg + tools)
    repeated_blocks(rep, pkg)
    return rep.found


def main():
    found = run()
    for kind, path, line, what in found:
        print("%s:%d: %s: %s" % (path, line, kind, what))
    print("%d piece(s) of slop" % len(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
