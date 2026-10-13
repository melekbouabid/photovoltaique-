# Données du dossier R autonome

Copies des trois seuls jeux de données lus par le code R. Elles ne sont jamais modifiées.

| Fichier | Contenu | Taille | SHA256 |
|---|---|---|---|
| `tn_photovoltaique_journalier.csv` | Production journalière d'1 kWc et variables météo, 3 villes de Tunisie (Tunis est utilisée) | 6.2 Mo | `825ae90712ff85b0a705197882b202afad56d0dfbca4244aa2beea0e14c47f1d` |
| `fr_solaire_national_rte_journalier.csv` | Production solaire nationale mesurée en France (RTE éCO2mix), pour la cointégration | 1.6 Mo | `012cb9a3084f919742650068a56695a281bca7f24cf16449187e6c86b72f3fab` |
| `es_fotovoltaica_ree_journalier.csv` | Production photovoltaïque nationale mesurée en Espagne (REE), pour la cointégration | 1.2 Mo | `e93c2a927efe7fa8afa77df044d15cc669a9a247de8afd65d75f22f8b30dd994` |

## Sources

- **PVGIS 5.3**, Commission européenne (JRC) : production simulée d'1 kWc, rayonnement PVGIS-SARAH3, météo ERA5. Réutilisation autorisée avec mention de la source.
- **Open-Meteo** (réanalyse ERA5, CC BY 4.0) : nébulosité, pluie, humidité.
- **NASA POWER** (MERRA-2, CERES) : aérosols, indice de clarté.
- **RTE éCO2mix** via ODRÉ (Licence Ouverte v2.0) : production solaire nationale française.
- **Red Eléctrica** (REData, « Fuente: Red Eléctrica ») : production photovoltaïque espagnole.

Période : 2005-2023 pour PVGIS, 2012-2026 pour RTE, 2014-2026 pour REE.
La colonne `jour_impute_pvgis` signale les 13 jours de Tunis dont le rayonnement PVGIS, manquant, a été corrigé.
