"""Crée l'archive à remettre (code, rapport, notebooks, données), sans secret ni fichier régénérable.

Exclus : .env (clé de l'API Groq), .venv et node_modules (pip install / npm install les recréent), les
réponses brutes des API (data/brut, recréées par la collecte) sauf la série horaire PVGIS de Tunis que le
notebook relit pour montrer les jours corrigés.

Usage : python python/creer_archive.py
Sortie : solarvision_series_temporelles.zip, à côté du dossier du projet.
"""
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE.parent / f"{RACINE.name}.zip"
DOSSIERS_EXCLUS = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".git", ".ipynb_checkpoints"}
FICHIERS_EXCLUS = {".env"}
GARDES_DANS_BRUT = {"pvgis/tunis_horaire.parquet"}


def a_inclure(f: Path) -> bool:
    rel = f.relative_to(RACINE)
    if rel.name in FICHIERS_EXCLUS or any(p in DOSSIERS_EXCLUS for p in rel.parts):
        return False
    if rel.parts[:2] == ("data", "brut"):
        return "/".join(rel.parts[2:]) in GARDES_DANS_BRUT
    return True


fichiers = sorted(f for f in RACINE.rglob("*") if f.is_file() and a_inclure(f))
# Garde-fou : la clé ne doit se trouver dans aucun fichier de l'archive, quel que soit son nom.
cle = next((l.split("=", 1)[1].strip() for l in (RACINE / ".env").read_text(encoding="utf-8").splitlines()
            if l.startswith("GROQ_API_KEY=")), "") if (RACINE / ".env").exists() else ""
if cle:
    fuites = [f for f in fichiers if f.stat().st_size < 5_000_000 and cle.encode() in f.read_bytes()]
    if fuites:
        raise SystemExit(f"Clé Groq présente dans {[str(f.relative_to(RACINE)) for f in fuites]} : archive non créée.")

with zipfile.ZipFile(SORTIE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in fichiers:
        z.write(f, Path(RACINE.name) / f.relative_to(RACINE))

brut = sum(f.stat().st_size for f in fichiers) / 1e6
print(f"{len(fichiers)} fichiers, {brut:.0f} Mo -> {SORTIE} ({SORTIE.stat().st_size / 1e6:.1f} Mo)")
par_dossier = {}
for f in fichiers:
    cle_d = f.relative_to(RACINE).parts[0]
    par_dossier[cle_d] = par_dossier.get(cle_d, 0) + f.stat().st_size
for d, t in sorted(par_dossier.items(), key=lambda x: -x[1])[:8]:
    print(f"  {d:<28} {t / 1e6:6.1f} Mo")
