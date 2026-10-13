# Fiche de données — NASA POWER

| Élément | Détail |
|---|---|
| Producteur | NASA Langley Research Center, projet POWER (MERRA-2, CERES) |
| Accès | API publique `power.larc.nasa.gov/api/temporal/daily/point` |
| Licence | Données ouvertes |
| Période | 2005 à 2023 |
| Pas | Journalier (heure solaire locale) |
| Emplacement | `data/raw/nasa_power/<ville>/` ; pour les 9 villes historiques, `data/brut/nasa_power/` |

## Contenu

Neuf variables par jour : rayonnement global horizontal, rayonnement par ciel clair, indice de clarté, rayonnement au
sommet de l'atmosphère, nébulosité, épaisseur optique des aérosols, indice UV, albédo, rayonnement photosynthétique.

## Usage dans le projet

- **Source indépendante de rayonnement.** Elle sert à repérer les jours où PVGIS enregistre un rayonnement nul par erreur,
  puis à les corriger.
- **Aérosols.** L'épaisseur optique décrit les épisodes de poussières sahariennes.

## Limites

- **Maille large** (environ un demi-degré) : la valeur décrit une zone, pas un point.
- **Valeur de remplissage.** Une donnée manquante vaut -999 dans la réponse ; le projet la remplace par une valeur manquante.
- **Pas de quota rencontré** pendant la collecte, mais le service peut être lent.
