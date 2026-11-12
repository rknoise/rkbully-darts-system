"""Kódtérkép generátor: docs/KODTERKEP.md – minden modul feladata, osztályai, függvényei az AST-ből (a kóddal mindig egyezik).

Futtatás:  python tools/make_codemap.py        (a kód módosítása után érdemes újragenerálni)"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "KODTERKEP.md"


def first_line(doc):
    if not doc:
        return ""
    return " ".join(doc.strip().splitlines()[0].split()).rstrip()


def describe(path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    mod_doc = ast.get_docstring(tree) or ""
    imports = sorted({(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 0}
                     | {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
    local = sorted(i for i in imports if (ROOT / f"{i}.py").exists() and i != path.stem)
    lines = ["", f"### `{path.relative_to(ROOT).as_posix()}`  ({len(src.splitlines())} sor)", ""]
    if mod_doc:
        lines += [mod_doc.strip(), ""]
    if local:
        lines += ["Saját modulokat használ: " + ", ".join(f"`{m}`" for m in local), ""]
    items = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            items.append(f"- **class `{node.name}`**" + (f" ({bases})" if bases else "") + (f" – {first_line(ast.get_docstring(node))}"
                                                                                           if ast.get_docstring(node) else ""))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith("__"):
                    d = first_line(ast.get_docstring(sub))
                    if d or not sub.name.startswith("_"):
                        items.append(f"  - `{sub.name}({', '.join(a.arg for a in sub.args.args if a.arg != 'self')})`" + (f" – {d}" if d else ""))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            d = first_line(ast.get_docstring(node))
            items.append(f"- `{node.name}({', '.join(a.arg for a in node.args.args)})`" + (f" – {d}" if d else ""))
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in node.targets):
            val = ast.unparse(node.value)
            items.append(f"- konstans `{', '.join(t.id for t in node.targets)}` = `{val[:70]}{'…' if len(val) > 70 else ''}`")
    return lines + items


def build():
    parts = ["# RKBully Darts System – kódtérkép", "",
             "*Ezt a fájlt a `tools/make_codemap.py` generálja a forráskódból (AST) – ne kézzel szerkeszd; a kód módosítása után futtasd újra.*",
             "A magyarázó szöveg (architektúra, adatformátumok, hogyan módosíts) a `FEJLESZTOI_ADATLAP.md`-ben van.", "",
             "## Program modulok (gyökérmappa)"]
    for p in sorted(ROOT.glob("*.py")):
        parts += describe(p)
    parts += ["", "## Eszközök (`tools/`)"]
    for p in sorted((ROOT / "tools").glob("*.py")):
        parts += describe(p)
    parts += ["", "## Tesztek (`tests/`)", "", "| fájl | sor | teszt | mit ellenőriz |", "|---|---|---|---|"]
    for p in sorted((ROOT / "tests").glob("*.py")):
        if p.name == "__init__.py":
            continue
        src = p.read_text(encoding="utf-8")
        n = len(re.findall(r"^\s+def test_", src, re.M))
        doc = first_line(ast.get_docstring(ast.parse(src))) or ""
        parts.append(f"| `{p.name}` | {len(src.splitlines())} | {n} | {doc} |")
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return OUT


if __name__ == "__main__":
    out = build()
    print(out, out.stat().st_size, "bájt")
