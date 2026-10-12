# Suivi d'avancement — SolarVision v2

Dernière mise à jour : 11 octobre 2026 en fin d'après-midi, après les phases 0 à 10.
Rendu : 12 octobre 2026 à 23h55.

## État des phases

| Phase | Contenu | État |
|---|---|---|
| 0 | Prise en main, sauvegarde, audit | Faite (version allégée : sans `uv` ni Python 3.12) |
| 1 | Architecture et dossier R isolé | Faite |
| 2 | Données 30 villes | Faite : 30 villes sur 30 |
| 3 | Panel, découpages, anti-fuite | Faite |
| 4a | Modèles classiques et tests de Diebold-Mariano | Faite |
| 4b | Réseaux récurrents | Faite (sans le modèle hybride) |
| 5 | Technologies photovoltaïques | Faite |
| 6 | Économie | Faite ; hypothèses à vérifier |
| 7 | MLOps | Partielle : DVC, Docker et intégration continue écrits, non exécutés |
| 8 | Application multi-pages | Faite |
| 9 | Notebook, rapport, section LLM, guide de soutenance | Faite ; la section LLM attend le travail du groupe |
| 10 | Audit final | Fait : `reports/conformite_v2.md` |

## À faire par le groupe avant le rendu

| Tâche | Où |
|---|---|
| Renseigner les noms du groupe | `report.authors` dans `configs/params.yaml` |
| Rédiger l'interprétation experte, **avant** d'envoyer les prompts | `docs/llm/interpretation_experte.md` |
| Envoyer les trois prompts à un LLM et coller les réponses | `docs/llm/prompt_*.md`, puis `docs/llm/reponse_1.md` à `reponse_3.md` |
| Remplir le tableau de comparaison | `docs/llm/comparaison_humain_llm.md` |
| Régénérer le rapport | `python -m solarvision.cli report` |
| Confronter l'audit au PDF du cahier des charges, absent du dossier | `reports/conformite_v2.md` |
| Vérifier les hypothèses économiques, ou garder l'avertissement | `configs/economics.yaml` |
| Recréer l'archive | `python scripts/make_archive.py` |
| Lire le guide de soutenance | `docs/DEFENSE_GUIDE.md` |

Le rapport historique (9 villes) a encore deux champs vides : les noms du groupe (`rapport/rapport_corps.md`, ligne 4) et le
paragraphe sur les outils d'IA utilisés (ligne 260).

## Résultats

Tous ces chiffres se relisent dans `reports/`.

| Question | Réponse |
|---|---|
| Données | 30 villes, 6 939 jours chacune, panel de 208 170 lignes ; 11 à 15 jours imputés par ville ; 30 villes au statut « ok » |
| Meilleur modèle ex ante en moyenne | LSTM global : RMSE de 1,1674 contre 1,1934 pour la climatologie |
| Gain sur la climatologie, par ville | de 0,9 % à 4,6 %, médiane 2,3 % |
| À J+1 | AR(1), XGBoost, LSTM, GRU et LSTM global battent significativement la climatologie dans 28 à 30 villes sur 30 ; la persistance et Prophet, dans aucune |
| À J+7 | Dans 0 à 2 villes sur 30 |
| Avec la météo observée (ex post) | RMSE de 0,63 à 0,71 : la limite est l'information sur la météo, pas le modèle |
| Technologie recommandée | CIS dans 9 villes françaises sur 10, CdTe dans 9 villes tunisiennes et 8 espagnoles sur 10 ; 5 villes ex æquo |
| Économie | Le silicium cristallin a la meilleure valeur actuelle nette médiane partout, mais l'écart n'est concluant que dans 1 ville sur 30 |
| Modèle en production | LSTM global 1.0.0 ; le modèle AR(1) a été refusé par la règle de promotion |

## Détail par phase

### Phase 0 — prise en main

- `CLAUDE.md` et `MASTER_PROMPT.md` créés ; sauvegarde `../SAUVEGARDE_backup-original_2026-10-11.zip` ; audit dans `docs/AUDIT_V1.md`.
- Introuvables : le PDF du cahier des charges, `rapport_detaille_SolarVision.md`, `_import_pc1/`.

### Phase 1 — architecture et R isolé

- Squelette, `pyproject.toml`, `configs/`, `docs/architecture.md`, `docs/MIGRATION.md`, ADR 0001.
- Dépôt Git créé ; l'état d'origine est sur la branche `backup-original`.
- Dossier R autonome : exécuté seul hors du projet, 8 scripts réussis, 9 tableaux identiques à ceux de l'étude d'origine.

### Phase 2 — données

- Coordonnées des 30 villes vérifiées contre GeoNames (écart maximal de 2 km).
- Collecte : PVGIS et NASA POWER sans incident. Open-Meteo a atteint son quota horaire après 11 villes ; la collecte s'est arrêtée
  proprement et a repris à l'heure suivante. Aucune ville n'a été simulée.
- Tunis : 13 dates imputées identiques à celles de la v1 ; série de référence identique à l'arrondi près.
- Deux défauts trouvés et corrigés en cours de route : le journal des échecs et le manifeste étaient écrasés par une exécution partielle.

### Phase 3 — panel

- 61 colonnes, rôle de chaque colonne déclaré ; découpage 6 245 / 694.
- Test anti-fuite : le futur est falsifié, les variables ex ante ne bougent pas.

### Phase 4 — modèles

- L'écart signalé dans le plan est expliqué : une climatologie non lissée donne 1,1324 à Tunis, la climatologie lissée sur 31 jours
  donne 1,1002, valeur de l'étude historique.
- Diebold-Mariano identique à `forecast::dm.test` de R.
- Sensibilité aux jours imputés : écart de RMSE de 0,002 kWh/kWc au plus.
- Le scénario ex post exclut le rayonnement : avec lui, le modèle recevait l'entrée même de la simulation.

### Phases 5 et 6 — technologies et économie

- Score à cinq critères, incertitude par rééchantillonnage d'années, sensibilité aux poids, front de Pareto, mention ex æquo.
- Arbre de décision jugé ville par ville : 83 % de bonnes réponses contre 60 % pour la règle de la classe majoritaire.
- Orientations : une toiture est-ouest produit 13 à 19 % de moins que le plein sud.
- Économie : toutes les hypothèses sont marquées `TODO_VERIFY`.

### Phases 7 et 8 — MLOps et application

- Registre sur fichiers, règle de promotion, retour arrière, contrôle SHA256, fiches de modèles, suivi MLflow, dérive.
- API `/v1` et neuf pages : `python -m solarvision.cli serve`, puis http://127.0.0.1:8001.

### Phases 9 et 10 — livrables et audit

- Rapport généré : 24 pages hors sommaire et annexes, un chapitre par page.
- Notebook de la v2 exécuté sans erreur ; guide de soutenance ; gabarits de la section LLM.
- Clone propre : parcours rapide réussi de bout en bout (cache brut des 3 villes copié, le quota étant épuisé).
- 72 tests réussis.

## Bloquants et écarts

| Point | Effet |
|---|---|
| PDF du cahier des charges absent | L'audit s'appuie sur la table de correspondance de la v1 et sur le plan |
| Python 3.12 et `uv` non installés | Calculs faits avec Python 3.14 ; pas de fichier de verrouillage |
| DVC, Docker (v2), intégration continue | Fichiers écrits, jamais exécutés |
| Evidently absent | Dérive calculée avec scipy |
| Quota d'Open-Meteo | Une dizaine de villes par heure ; relancer la collecte complète prend environ 3 heures |

## Décisions prises, à confirmer

1. Le dossier de configuration s'appelle `configs/` (voir `docs/adr/0001-environnement-et-configuration.md`).
2. Un dépôt Git a été créé pour suivre les étapes.
3. Les phases ont été enchaînées sans attendre de « continue », à la demande.
4. L'archive de la v2 porte un nouveau nom : celle de la première étude n'est pas écrasée.

## Commandes utiles

Depuis la racine du projet. Détail dans `RUN_ME.md`.

| But | Commande |
|---|---|
| Tests | `python -m pytest` |
| Parcours rapide | `python -m solarvision.cli pipeline --fast` |
| Application | `python -m solarvision.cli serve` |
| Rapport | `python -m solarvision.cli report` |
| Archive | `python scripts/make_archive.py` |
| État du cache | `python -m solarvision.cli status` |
