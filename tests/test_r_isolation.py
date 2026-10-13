"""Le dossier R autonome ne doit avoir aucun lien de code avec le reste du projet, dans les deux sens.

Deux contrôles :
1. aucun fichier du dossier R ne contient de chemin qui en sort (« .. », chemin absolu, dossier du projet) ;
2. aucun fichier de code ou de configuration du projet ne nomme le dossier R.

Les documents rédigés (Markdown) du projet principal peuvent décrire le dossier : ce n'est pas une dépendance.
Ce fichier de test est la seule exception du second contrôle, puisqu'il doit bien désigner le dossier.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R_DIR_NAME = "r_" + "standalone"                      # nom assemblé : ce fichier ne doit pas se signaler lui-même
R_DIR = ROOT / R_DIR_NAME

TEXT_SUFFIXES = {".r", ".rmd", ".qmd", ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ""}
CODE_SUFFIXES = {".py", ".r", ".rmd", ".qmd", ".toml", ".yaml", ".yml", ".json", ".cfg", ".ini", ".sh", ".ps1",
                 ".bat", ".ipynb", ".ts", ".tsx", ".js", ".dockerignore", ".gitignore", ""}
SKIPPED_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "data", "figures", "resultats",
                "mlruns", "dist", ".ruff_cache", "outputs", "reports", "models", R_DIR_NAME, "solarvision.egg-info"}

# Motifs interdits dans le dossier R : remontée de dossier, chemin absolu, dossiers du projet principal.
OUTGOING = [
    # « .. » en début de segment de chemin seulement : des points de suspension suivis de \n ne comptent pas.
    (re.compile(r"(?<![.\w])\.\.[/\\]"), "remontée de dossier (..)"),
    (re.compile(r"(?<![A-Za-z])[A-Za-z]:[/\\]"), "chemin absolu Windows"),
    (re.compile(r"[\"'](/home/|/Users/|~/)"), "chemin absolu Unix"),
    (re.compile(r"\bsetwd\(\s*[\"']"), "setwd() vers un chemin écrit en dur"),
    (re.compile(r"data/datasets|data/brut|\bpython/|\bresultats/|src/solarvision|mini_projet_python|collecte_donnees"),
     "référence à un fichier du projet principal"),
]


def _text_files(folder: Path, suffixes: set[str], skipped: set[str]):
    for path in folder.rglob("*"):
        parts = path.relative_to(folder).parts
        parent_dirs = parts[:-1]
        generated_metadata = any(part.endswith(".egg-info") for part in parent_dirs)
        if path.is_file() and path.suffix.lower() in suffixes and not (set(parent_dirs) & skipped) and not generated_metadata:
            yield path


def test_r_folder_exists_with_expected_layout():
    for name in ("README.md", "INVENTAIRE.md", "DESCRIPTION", "run_all.R", ".here", "R", "notebooks", "data"):
        assert (R_DIR / name).exists(), f"élément manquant dans le dossier R : {name}"
    assert sorted(p.name for p in (R_DIR / "R").glob("*.R")), "aucun script R"


def test_r_folder_has_no_outgoing_path():
    problems = []
    for path in _text_files(R_DIR, TEXT_SUFFIXES, {"outputs", "data"}):
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            problems += [f"{path.relative_to(ROOT)}:{n} : {label}" for pattern, label in OUTGOING if pattern.search(line)]
    assert not problems, "\n".join(problems)


def test_r_scripts_read_and_write_inside_the_folder_only():
    # Toute lecture ou écriture doit passer par here::here(), ancré sur le fichier .here du dossier.
    io_call = re.compile(r"\b(read\.csv|read\.table|readRDS|write\.csv|saveRDS|source|pdf|png)\(\s*[\"']")
    problems = []
    for path in [*(R_DIR / "R").glob("*.R"), *(R_DIR / "notebooks").glob("*.Rmd")]:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if io_call.search(line):
                problems.append(f"{path.relative_to(ROOT)}:{n} : lecture ou écriture sans here::here()")
    assert not problems, "\n".join(problems)


def test_project_code_does_not_reference_r_folder():
    this_file = Path(__file__).resolve()
    problems = []
    for path in _text_files(ROOT, CODE_SUFFIXES, SKIPPED_DIRS):
        if path.resolve() == this_file or path.suffix.lower() == ".md" or path.stat().st_size > 5_000_000:
            continue
        if R_DIR_NAME in path.read_text(encoding="utf-8", errors="replace"):
            problems.append(str(path.relative_to(ROOT)))
    assert not problems, f"fichiers du projet qui nomment le dossier R : {problems}"
