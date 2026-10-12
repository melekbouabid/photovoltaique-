# Fiche de données — Open-Meteo

| Élément | Détail |
|---|---|
| Producteur | Open-Meteo, à partir de la réanalyse ERA5 (Copernicus, ECMWF) |
| Accès | API publique `archive-api.open-meteo.com/v1/archive` |
| Licence | CC BY 4.0 |
| Période | 2005 à 2023 |
| Pas | Journalier (jour local de la ville) |
| Emplacement | `data/raw/open_meteo/<ville>/` ; pour les 9 villes historiques, `data/brut/open_meteo/` |

## Contenu

Dix variables par jour : nébulosité moyenne, durée d'ensoleillement, durée du jour, précipitations, humidité relative,
point de rosée, pression au niveau de la mer, rafale maximale, évapotranspiration de référence, rayonnement global.

## Usage dans le projet

- **Variables ex post** : la météo du jour visé, pour mesurer ce qu'apporterait une prévision météo parfaite.
- **Variables ex ante** : la météo de la veille, connue au moment de prévoir.
- **Contrôle** : le rayonnement ERA5 confirme celui de NASA POWER quand un jour PVGIS paraît faux.

## Limites

- **Réanalyse, pas observation.** ERA5 reconstruit la météo à partir d'un modèle ; la nébulosité d'une maille de
  plusieurs dizaines de kilomètres situe mal certains nuages.
- **Quota.** Une requête de 19 ans pèse lourd dans le quota gratuit : environ dix villes par heure. La collecte attend
  entre deux villes, s'arrête proprement quand le quota est atteint et note l'heure de reprise.
- **Jour local.** Le jour d'Open-Meteo est le jour local, celui de PVGIS le jour UTC : l'écart est d'une à deux heures
  de nuit à ces longitudes.
