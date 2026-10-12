# Journal des changements — version 2

Date : 11 octobre 2026. La version 1 (étude sur 9 villes) est conservée telle quelle ; son état d'origine est sur la
branche Git `backup-original` et dans l'archive de sauvegarde placée à côté du projet.

## Ajouté

### Données

- 30 villes décrites dans `configs/cities.yaml` (10 par pays), coordonnées vérifiées contre une référence indépendante.
- Trois technologies photovoltaïques par ville : silicium cristallin, CIS, CdTe.
- Collecte avec cache par ville et par source, écriture atomique, reprise, journal des échecs, gestion des quotas.
- Imputation des trous de PVGIS appliquée aux trois technologies ; contrats de données Pandera ; manifeste des données.

### Modélisation

- Panel de modélisation avec variables ex ante et ex post séparées, et rôle déclaré de chaque colonne.
- Protocole commun : chaque origine du test est évaluée, réajustement tous les 30 jours.
- Modèles : persistance, climatologie, AR(1) à termes de Fourier, XGBoost direct, Prophet, LSTM, GRU, LSTM global.
- Intervalles conformes pour le LSTM global.
- Test de Diebold-Mariano avec correction HLN, vérifié contre R ; correction de Holm par famille ; bootstrap par blocs.
- Analyse de sensibilité aux jours imputés ; diagnostic de l'écart de la climatologie à Tunis.

### Technologies et économie

- Score de fiabilité à cinq critères calculés, avec incertitude, sensibilité aux poids, front de Pareto et mention ex æquo.
- Arbre de décision validé ville par ville.
- Valeur actuelle nette, temps de retour, taux de rentabilité interne, coût de l'énergie, CO2 évité, par simulation de Monte-Carlo.
- Valeur de la prévision.

### Architecture

- Paquet `solarvision`, une commande par étape, configuration dans `configs/`.
- Registre de modèles avec règle de promotion, retour arrière et contrôle d'intégrité ; fiches de modèles générées.
- Suivi d'expériences MLflow ; suivi de la dérive et de l'erreur glissante.
- API `/v1` et application de neuf pages.
- Rapport généré à partir des artefacts ; notebook de la v2 ; gabarits de la section sur l'IA générative.
- Dossier R autonome, vérifié hors du projet.
- Tests : données, anti-fuite temporelle, statistiques, économie, registre, API, non-régression des métriques.

## Changé

- `README.md` décrit l'ensemble du dépôt ; l'ancien contenu est dans `docs/README_v1.md`.
- `.gitignore` et `.dockerignore` excluent le cache brut et les artefacts de la v2.

## Inchangé

- Les scripts, notebooks, résultats, rapport et application de la v1. Aucun n'a été déplacé ni modifié.

## Écarts par rapport au plan

| Prévu | Réalisé |
|---|---|
| Python 3.12 installé par `uv`, fichier de verrouillage | Calculs faits avec Python 3.14, sans `uv` ; pas de fichier de verrouillage |
| Pipeline exécuté par DVC | `dvc.yaml` écrit, non exécuté (DVC absent) ; enchaînement testé par la commande `pipeline` |
| Suivi par Evidently | Mêmes statistiques (PSI, Kolmogorov-Smirnov) calculées avec scipy |
| Image Docker et intégration continue | Fichiers écrits, non exécutés |
| Réseaux réajustés comme les autres modèles | Réseaux entraînés une fois sur l'apprentissage |
| Analyse de trois orientations | Non faite pour les nouvelles villes |
| Modèle hybride ARIMA + LSTM, N-BEATS ou TFT, vrai ex ante météo, corrélation dynamique | Non faits en v2 (l'hybride et la corrélation dynamique existent dans la v1) |
| Éclairage naturel (lux) | Non repris en v2 : il demande les composantes directe et diffuse du rayonnement |
