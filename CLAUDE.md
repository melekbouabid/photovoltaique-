# SolarVision — règles permanentes

## Projet
Prévision de la production PV journalière (1 kWc, kWh/kWc/jour) à J+1…J+7 sur 30 villes (France, Tunisie, Espagne), comparaison de technologies PV (crystSi, CIS, CdTe), bénéfices économiques et architecture MLOps.
Mini-projet noté sur 20 (TEK-UP, Séries Temporelles). Cahier des charges : Mini_Projet_Series_Temporelles_2026.pdf. Rendu : 12/10/2026 23h55. L'étudiant doit pouvoir expliquer et défendre tout le code.

## Règles scientifiques (non négociables)
- Split chronologique 90/10 (indice de coupure int(n*0.9)), jamais aléatoire, pas de k-fold classique.
- Toujours séparer ex_ante (info disponible à la date d'émission) et ex_post (météo future observée). Ne jamais présenter l'ex_post comme performance opérationnelle.
- Aucun chiffre inventé ni saisi à la main dans le rapport : tout vient de fichiers générés par le code.
- Tout test statistique : hypothèses, taille de famille de tests, correction (Holm), direction du test et fonction de perte écrites explicitement.
- Diebold-Mariano à horizon h : variance de long terme avec h-1 retards + correction de Harvey-Leybourne-Newbold. Famille de Holm = modèles vs climatologie, par (ville, technologie, horizon).
- Les jours imputés (jour_impute_pvgis) restent visibles ; faire une analyse de sensibilité avec/sans.
- Toute valeur économique (tarif, coût, taux) est un paramètre de config marqué TODO_VERIFY avec sa source, jamais une constante cachée. Résultats économiques toujours avec intervalles.
- Si une étape échoue ou si un quota bloque : le dire, ne pas simuler de données.

## Règles d'ingénierie
- Python 3.12 via uv, lockfile versionné. Windows (PowerShell) possible : pas de dépendance à `make` seul ; fournir `python -m solarvision.cli <commande>` (Makefile = simple raccourci).
- Seed fixée (config/params.yaml). Aucun chemin absolu. Pas de .venv/data/ dans Git.
- Un commit par étape, tests verts avant de continuer. Ne jamais casser les scripts historiques : migrer progressivement, garder des wrappers de compatibilité.
- Code commenté : une ligne par bloc qui explique le POURQUOI.
- Documentation en français, noms de code en anglais.
- À la fin de chaque phase : mettre à jour docs/PROGRESS.md (fait / reste / bloquants / commandes) et résumer en 10 lignes max.
- Ne jamais écrire à la place de l'étudiant son interprétation experte de la section LLM (voir Phase 9) : préparer le gabarit seulement.

## Acquis validés à ne pas régresser
- 30 villes × 6939 jours (2005-01-01 → 2023-12-31) = 208170 lignes dans le panel complet.
- Split Tunis : 6245 jours d'entraînement (jusqu'au 2022-02-05), 694 jours de test (à partir du 2022-02-06).
- Imputation NASA POWER : 13 dates PVGIS problématiques à Tunis (voir MASTER_PROMPT §Acquis).
- Environnement : Python 3.12 ; torch, statsmodels, arch, pmdarima, prophet, xgboost, fastapi, pyarrow installables.
