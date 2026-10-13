"""Crée l'archive à remettre : code, rapports, notebooks et données légères, sans secret ni fichier régénérable.

Exclus :
- `.env` (clé d'API) et tout fichier qui contiendrait cette clé ;
- les environnements et caches (`.venv`, `node_modules`, `.git`, `__pycache__`) ;
- le cache brut (`data/raw`, `data/brut`) et les tables intermédiaires : `data/manifest.yaml` dit comment les reconstruire ;
- les sorties volumineuses ou propres à la machine (prévisions date par date, suivi MLflow, mode rapide).
La série horaire PVGIS de Tunis est gardée : le notebook historique la relit.

Usage : python scripts/make_archive.py [--exclude MOTIF ...]
        exemple : python scripts/make_archive.py --exclude CLAUDE.md --exclude MASTER_PROMPT.md
Sortie : <dossier du projet>_v2.zip, à côté du dossier du projet (l'archive de la première étude n'est pas écrasée).
"""
from __future__ import annotations

import argparse
import fnmatch
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".git", ".ipynb_checkpoints", ".ruff_cache",
                 "mlruns", "mlartifacts", "registry_fast", "outputs"}
EXCLUDED_PREFIXES = ["data/raw", "data/brut", "data/interim", "data/fast", "reports/fast", "reports/forecasts",
                     "reports/forecasts_deep", "reports/monitoring/requests.jsonl", "app/frontend/dist"]
EXCLUDED_NAMES = {".env", "mlflow.db"}
EXCLUDED_SUFFIXES = {".part", ".log", ".zip", ".egg-info"}
# Le panel existe sous deux noms (nombre de villes dans le nom, et alias lu par le code) : un seul suffit.
EXCLUDED_PATTERNS = ["data/processed/panel_journalier_*_villes.parquet"]
KEPT_ANYWAY = {"data/brut/pvgis/tunis_horaire.parquet"}


def included(path: Path, extra: list[str]) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel in KEPT_ANYWAY:
        return True
    if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES or set(path.relative_to(ROOT).parts) & EXCLUDED_DIRS:
        return False
    if any(part.endswith(".egg-info") for part in path.relative_to(ROOT).parts):
        return False
    if any(rel == p or rel.startswith(p + "/") for p in EXCLUDED_PREFIXES):
        return False
    return not any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern) for pattern in [*EXCLUDED_PATTERNS, *extra])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exclude", action="append", default=[], help="motif de fichier à exclure en plus (répétable)")
    args = parser.parse_args()
    files = sorted(f for f in ROOT.rglob("*") if f.is_file() and included(f, args.exclude))
    # Garde-fou : la clé ne doit se trouver dans aucun fichier de l'archive, quel que soit son nom.
    env = ROOT / ".env"
    keys = [line.split("=", 1)[1].strip() for line in env.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")] if env.exists() else []
    keys = [k for k in keys if len(k) >= 12]
    leaks = [f for f in files if f.stat().st_size < 5_000_000 and any(k.encode() in f.read_bytes() for k in keys)]
    if leaks:
        raise SystemExit(f"Clé présente dans {[str(f.relative_to(ROOT)) for f in leaks]} : archive non créée.")
    out = ROOT.parent / f"{ROOT.name}_v2.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for f in files:
            archive.write(f, Path(ROOT.name) / f.relative_to(ROOT))
    total = sum(f.stat().st_size for f in files) / 1e6
    print(f"{len(files)} fichiers, {total:.0f} Mo -> {out} ({out.stat().st_size / 1e6:.1f} Mo)")
    by_folder: dict[str, float] = {}
    for f in files:
        top = f.relative_to(ROOT).parts[0]
        by_folder[top] = by_folder.get(top, 0) + f.stat().st_size
    for folder, size in sorted(by_folder.items(), key=lambda x: -x[1])[:10]:
        print(f"  {folder:<26} {size / 1e6:7.1f} Mo")


if __name__ == "__main__":
    main()
