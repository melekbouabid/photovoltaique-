# scripts/

Utilitaires ponctuels. Chacun se lance depuis la racine du projet.

| Script | Rôle |
|---|---|
| `verify_cities.py` | Compare les coordonnées et altitudes de `configs/cities.yaml` au géocodage d'Open-Meteo (GeoNames) |
| `diagnose_climatology_gap.py` | Montre l'effet de la définition de la normale saisonnière sur l'erreur de la climatologie à Tunis |
| `build_notebook.py` | Construit `notebooks/solarvision_v2.ipynb` |
| `make_archive.py` | Crée l'archive à remettre, sans secret ni cache brut |
