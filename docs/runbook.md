# Que faire quand…

Procédures pour les situations rencontrées en exploitant le pipeline. Les commandes se lancent depuis la racine du projet.

## Une source de données refuse de répondre (quota)

**Signe.** La collecte s'arrête sur un message « quota dépassé, reprise possible à … UTC », et `data/failures.json` liste les villes concernées.

| Étape | Commande |
|---|---|
| Voir ce qui manque | `python -m solarvision.cli status` |
| Attendre l'heure indiquée dans `data/failures.json`, puis reprendre | `python -m solarvision.cli ingest --retry-failed` |
| Continuer sans attendre, avec les villes déjà complètes | `python -m solarvision.cli features --allow-partial` |

Open-Meteo accepte une dizaine de villes par heure. Une ville incomplète reste listée comme manquante ; elle n'est jamais simulée.

## Une ville échoue aux contrôles de qualité

**Signe.** Statut `failed` dans `data/quality/summary.csv`, ou erreur de schéma pendant le traitement.

1. Lire les raisons dans `data/quality/<ville>.json`.
2. Si le nombre de jours imputés sort de la plage attendue, vérifier les coordonnées de la ville : `python scripts/verify_cities.py`.
3. Reconstruire la table depuis le cache, sans réseau : `python -m solarvision.cli ingest --reprocess --cities <ville>`.

## Un fichier du cache est corrompu

**Signe.** Erreur de lecture d'un fichier de `data/raw/`.

1. Supprimer le fichier fautif (un fichier `.part` peut être supprimé sans risque).
2. Relancer `python -m solarvision.cli ingest --cities <ville>` : seul ce fichier est retéléchargé.

## Le modèle en production est refusé au chargement

**Signe.** `/health` renvoie `sha256_verifie: false`, et `/v1/predict` répond « le fichier du modèle ne correspond plus à son empreinte ».

Le fichier du modèle a été modifié après son enregistrement. Ne pas le réparer à la main.

| Solution | Commande |
|---|---|
| Revenir à la version précédente | `python -m solarvision.cli rollback` |
| Réenregistrer un modèle sain | `python -m solarvision.cli deep --force`, puis `python -m solarvision.cli register` |

## Une promotion est refusée

**Signe.** `register` affiche « promotion refusée » avec la raison.

Ce n'est pas une panne : la règle a joué son rôle. Trois raisons possibles.

| Raison | Que faire |
|---|---|
| Ne bat pas la climatologie | Ne pas promouvoir. Le modèle n'apporte rien. |
| Ne bat pas la version en production | Garder la version en place. |
| Dates de test ou villes différentes | Les deux modèles ne sont pas comparables. Réévaluer les deux sur le même périmètre, ou repartir d'un registre vide si le périmètre de l'étude a changé. |

## Le suivi signale une dérive

**Signe.** Des variables « en alerte » dans `reports/monitoring/summary.json` ou dans la page Architecture.

1. Lire `reports/monitoring/drift.csv` : quelle variable, dans quelle ville, avec quel écart moyen.
2. Regarder `reports/monitoring/rolling_error.csv` : l'erreur du modèle s'est-elle dégradée par rapport à la climatologie ?
3. Si l'erreur n'a pas bougé, la dérive n'affecte pas le modèle : la noter et continuer à surveiller.
4. Si l'erreur s'est dégradée, réentraîner (`train`, `deep`, `evaluate`, `register`). Le réentraînement n'est jamais automatique.

## Les chiffres du rapport semblent faux

Le rapport ne contient aucun chiffre saisi à la main. Pour retrouver l'origine d'une valeur :

| Valeur | Fichier |
|---|---|
| Erreurs des modèles | `reports/metrics_tidy.csv` |
| Tests de Diebold-Mariano | `reports/dm_tests.csv` |
| Résultats par ville | `reports/synthese_ville.csv` |
| Technologies | `reports/tech_indicators.csv`, `reports/tech_recommendation.csv` |
| Économie | `reports/economics_by_city.csv` |
| Statistiques d'exploration | `reports/exploration_stats.csv` |

Recalculer un tableau sans réentraîner : `python -m solarvision.cli evaluate`. Régénérer le rapport : `python -m solarvision.cli report`.
