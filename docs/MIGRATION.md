# Migration de la v1 vers la v2

La migration est progressive. Le code nouveau naît dans `src/solarvision/` ; les scripts historiques
restent à leur place et continuent de fonctionner. Aucun n'a été déplacé.

## Correspondance des chemins

| Ancien chemin (v1) | Nouveau chemin (v2) | Statut |
|---|---|---|
| `python/collecte_donnees.py` (villes écrites dans le code) | `configs/cities.yaml` + `src/solarvision/data/ingest.py` | Réécrit ; l'ancien script reste utilisable pour les 9 villes |
| `python/collecte_donnees.py` (`agreger_jour`, `corriger_trous_pvgis`) | `src/solarvision/data/process.py` (`aggregate_daily`, `impute_pvgis_gaps`) | Réécrit, même règle, vérifié sur Tunis |
| `data/brut/` | `data/raw/<source>/<ville>/` | Cohabitation : la v2 relit `data/brut/` pour les 9 villes historiques |
| `data/datasets/panel_9_villes_journalier.csv` | `data/processed/panel_journalier_<n>_villes.parquet` | Nouveau panel ; l'ancien fichier est conservé |
| `data/catalogue_datasets.json`, `data/LISEZMOI_donnees.md` | `data/manifest.yaml` | Nouveau manifeste ; les anciens fichiers sont conservés |
| `python/partie_A.py`, `partie_B.py`, `partie_C.py` | `src/solarvision/models/`, `src/solarvision/evaluation/` | Protocole multi-villes réécrit ; l'étude détaillée de Tunis (ACF, STL, VAR, GARCH) reste dans le notebook historique |
| `python/entrainer_modeles_app.py` | `src/solarvision/models/deep.py` | Réécrit (LSTM, GRU, LSTM global) ; l'ancien script sert toujours l'application v1 |
| `resultats/` | `reports/` | Cohabitation : `resultats/` garde l'étude sur 9 villes |
| `figures/` | `reports/figures/` | Cohabitation |
| `app/backend/main.py` (routes `/api/...`) | `src/solarvision/serving/api.py` (routes `/v1/...`) | Nouvelle API sur le port 8001 ; l'API v1 reste servie sur le port 8000 |
| `mini_projet_R.Rmd` | dossier R autonome (copie) | Copié et vérifié hors du projet ; l'original reste à la racine |
| `app/frontend/` (page unique React) | `app/pages/` (neuf pages servies par l'API) | Nouvelle application ; l'ancienne reste en place |
| `python/creer_archive.py` | `scripts/make_archive.py` | Nouveau script (exclut le cache brut de la v2) ; l'ancien reste utilisable |
| `README.md` (v1) | `docs/README_v1.md` | Déplacé ; `README.md` décrit maintenant l'ensemble |
| `rapport/construire_rapport.py` | `python -m solarvision.cli report` (`src/solarvision/reporting/`) | Nouveau rapport dans `reports/rapport/` ; l'ancien script produit toujours le rapport historique |
| `requirements.txt` | `pyproject.toml` | Les deux coexistent |
| `Dockerfile`, `docker-compose.yml` | `infra/Dockerfile`, `infra/docker-compose.yml` | Écrits pour la v2, non construits ; les fichiers d'origine restent à la racine |

## Compatibilité

- Les 9 villes historiques gardent leurs coordonnées exactes : leur cache reste valable.
- La série `pv_crystSi_kwh_kwc` de la v2 est la série `pv_kwh_kwc` de la v1 (écart maximal de 0,00005 kWh/kWc à Tunis, dû à l'arrondi du fichier CSV de la v1).
- Les 13 jours imputés à Tunis sont les mêmes dans les deux versions.

## Différences à connaître

| Point | v1 | v2 |
|---|---|---|
| Villes | 9 | 30 |
| Technologies | Silicium cristallin | Silicium cristallin, CIS, CdTe |
| Format des réponses PVGIS | JSON avec composantes | CSV sans composantes (deux fois moins lourd) |
| Irradiation horizontale | Somme du direct et du diffus | Global horizontal, colonne `ghi_pvgis_kwh_m2` |
| Éclairage naturel (lux) | Calculé | Non repris : il demande les composantes directe et diffuse |
| Configuration | Constantes dans les scripts | Fichiers YAML dans `configs/` |
