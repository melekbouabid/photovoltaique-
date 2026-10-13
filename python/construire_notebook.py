"""Assemble les trois parties (format « percent ») en un notebook Jupyter unique.

Usage : python python/construire_notebook.py            -> mini_projet_python.ipynb
        python python/construire_notebook.py --script   -> python/_tout.py (mise au point en script)
"""
import pathlib
import sys

import nbformat as nbf

ici = pathlib.Path(__file__).resolve().parent
source = "\n".join((ici / f"partie_{p}.py").read_text(encoding="utf-8").rstrip() + "\n" for p in "ABC")
if "--script" in sys.argv:                      # mode mise au point : un seul script exécutable
    (ici / "_tout.py").write_text(source, encoding="utf-8")
    sys.exit(0)

cellules, courant, genre = [], [], None
for ligne in source.splitlines():
    if ligne.startswith("# %%"):
        if genre is not None:
            cellules.append((genre, courant))
        genre, courant = ("markdown" if "[markdown]" in ligne else "code"), []
    else:
        courant.append(ligne)
cellules.append((genre, courant))

nb = nbf.v4.new_notebook()
for genre, lignes in cellules:
    while lignes and not lignes[-1].strip():
        lignes.pop()
    if genre == "markdown":
        texte = "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in lignes)
        nb.cells.append(nbf.v4.new_markdown_cell(texte))
    else:
        nb.cells.append(nbf.v4.new_code_cell("\n".join(lignes)))
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nbf.write(nb, ici.parent / "mini_projet_python.ipynb")
print(len(nb.cells), "cellules écrites")
