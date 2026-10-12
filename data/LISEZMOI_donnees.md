# Jeux de données du projet SolarVision - Séries temporelles

Ce document est produit automatiquement par `python/collecte_donnees.py`.

## Origine : les liens du rapport SolarVision

Le rapport `Rapport_SolarVision_MLOps_complet.pdf` contient 21 liens. Un seul donne accès à des séries temporelles : **PVGIS** (re.jrc.ec.europa.eu/pvg_tools), l'outil de la Commission européenne que le rapport recommande pour remplacer l'hypothèse G = 1 800 kWh/m²/an à Tunis. Les autres liens sont des articles scientifiques (résumés récupérés pour le RAG) et des jeux d'images aériennes (métadonnées seulement). Détail : `sources/liens_rapport_solarvision.json`.

| Catégorie | Nombre de liens | Usage |
|---|---|---|
| série temporelle | 1 | API interrogée : séries horaires 2005-2023 pour 9 villes |
| article | 14 | résumés intégrés au corpus du RAG |
| jeu d'images | 5 | métadonnées archivées |
| documentation | 1 | titre archivé |

## Sources complémentaires

- **PVGIS** : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source)
- **Open-Meteo** : Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0)
- **NASA POWER** : NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov
- **RTE** : RTE éCO2mix via le portail ODRÉ, jeu eco2mix-national-cons-def - https://odre.opendatasoft.com (Licence Ouverte v2.0)
- **REE** : Red Eléctrica (REData API, bilan électrique) - https://apidatos.ree.es (réutilisation avec mention « Fuente: Red Eléctrica »)

## Sites

| Site | Ville | Pays | Latitude | Longitude |
|---|---|---|---|---|
| paris | Paris | France | 48.8566 | 2.3522 |
| lyon | Lyon | France | 45.764 | 4.8357 |
| marseille | Marseille | France | 43.2965 | 5.3698 |
| tunis | Tunis | Tunisie | 36.8065 | 10.1815 |
| sfax | Sfax | Tunisie | 34.7406 | 10.7603 |
| tozeur | Tozeur | Tunisie | 33.9197 | 8.1335 |
| madrid | Madrid | Espagne | 40.4168 | -3.7038 |
| seville | Séville | Espagne | 37.3891 | -5.9845 |
| barcelone | Barcelone | Espagne | 41.3874 | 2.1686 |

## Liste des jeux de données

Exigence : plus de 1 000 lignes et au moins 20 variables explicatives (hors identifiants : date  heure  ville  pays  coordonnées) pour chaque jeu.

| Fichier | Thème | Pays | Lignes | Variables | Période | Conforme |
|---|---|---|---|---|---|---|
| `fr_photovoltaique_journalier.csv` | photovoltaïque | France | 20 817 | 36 | 2005-01-01 au 2023-12-31 | oui |
| `fr_eclairement_journalier.csv` | éclairement | France | 20 817 | 37 | 2005-01-01 au 2023-12-31 | oui |
| `tn_photovoltaique_journalier.csv` | photovoltaïque | Tunisie | 20 817 | 36 | 2005-01-01 au 2023-12-31 | oui |
| `tn_eclairement_journalier.csv` | éclairement | Tunisie | 20 817 | 37 | 2005-01-01 au 2023-12-31 | oui |
| `es_photovoltaique_journalier.csv` | photovoltaïque | Espagne | 20 817 | 36 | 2005-01-01 au 2023-12-31 | oui |
| `es_eclairement_journalier.csv` | éclairement | Espagne | 20 817 | 37 | 2005-01-01 au 2023-12-31 | oui |
| `panel_9_villes_journalier.csv` | photovoltaïque et éclairement | France  Tunisie  Espagne | 62 451 | 57 | 2005-01-01 au 2023-12-31 | oui |
| `mensuel_9_villes.csv` | photovoltaïque et éclairement | France  Tunisie  Espagne | 2 052 | 40 | 2005-01-01 au 2023-12-01 | oui |
| `climatologie_9_villes.csv` | photovoltaïque et éclairement | France  Tunisie  Espagne | 3 294 | 32 | - | oui |
| `horaire_9_villes_2023.csv.gz` | photovoltaïque et éclairement | France  Tunisie  Espagne | 78 840 | 40 | 2023-01-01 au 2023-12-31 | oui |
| `tmy_9_villes.csv` | éclairement | France  Tunisie  Espagne | 78 840 | 28 | 2023-01-01 au 2023-12-31 | oui |
| `pvgis_orientations_9_villes.csv` | photovoltaïque | France  Tunisie  Espagne | 2 916 | 23 | - | oui |
| `fr_solaire_national_rte_journalier.csv` | photovoltaïque (mesuré) | France | 5 357 | 38 | 2012-01-01 au 2026-08-31 | oui |
| `es_fotovoltaica_ree_journalier.csv` | photovoltaïque (mesuré) | Espagne | 4 666 | 36 | 2014-01-01 au 2026-10-10 | oui |

### fr_photovoltaique_journalier.csv

Photovoltaïque - France : production journalière d'1 kWc et 35 variables explicatives, 3 villes.

Lignes : 20 817 ; colonnes : 43 dont 36 variables explicatives ; valeurs manquantes : 0.008 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `pv_kwh_kwc` | kWh/kWc | Énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_pic_w_kwc` | W/kWc | Puissance horaire maximale de la journée | PVGIS |
| `heures_production` | h | Nombre d'heures avec une production non nulle | PVGIS |
| `irr_poa_kwh_m2` | kWh/m² | Irradiation globale reçue sur le plan des modules | PVGIS |
| `irr_poa_direct_kwh_m2` | kWh/m² | Composante directe sur le plan des modules | PVGIS |
| `irr_poa_diffus_kwh_m2` | kWh/m² | Composante diffuse sur le plan des modules | PVGIS |
| `irr_poa_reflechi_kwh_m2` | kWh/m² | Composante réfléchie par le sol sur le plan des modules | PVGIS |
| `fraction_diffuse_poa` | - | Part du diffus dans l'irradiation du plan des modules (indicateur de couverture nuageuse) | PVGIS, calculé |
| `ratio_performance` | - | Énergie produite / irradiation reçue (pertes thermiques et système) | PVGIS, calculé |
| `t2m_moy_c` | °C | Température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `t2m_max_c` | °C | Température maximale | PVGIS (ERA5) |
| `t2m_min_c` | °C | Température minimale | PVGIS (ERA5) |
| `t2m_jour_c` | °C | Température moyenne pendant les heures de jour (influe sur le rendement des modules) | PVGIS (ERA5) |
| `amplitude_thermique_c` | °C | Écart entre maximum et minimum de température (ciel clair = forte amplitude) | PVGIS, calculé |
| `vent_moy_ms` | m/s | Vitesse moyenne du vent à 10 m (refroidit les modules) | PVGIS (ERA5) |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `ensoleillement_h` | h | Durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `rafales_max_kmh` | km/h | Rafale maximale à 10 m | Open-Meteo (ERA5) |
| `aerosols_aod` | - | Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `indice_clarte` | - | Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `ghi_ciel_clair_kwh_m2` | kWh/m² | Irradiation horizontale par ciel clair (sans nuages) | NASA POWER |
| `irr_extraterrestre_kwh_m2` | kWh/m² | Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `duree_jour_astro_h` | h | Durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `hauteur_soleil_midi_deg` | ° | Hauteur du soleil à midi solaire, calculée (connue à l'avance) | calcul astronomique |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `heures_reconstruites` | h | Heures dont le rayonnement a été reconstruit par PVGIS (indicateur de qualité) | PVGIS |
| `jour_impute_pvgis` | 0/1 | 1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées | calculé |
| `pv_veille` | kWh/kWc | Production de la veille (t-1) | calculé |
| `pv_j7` | kWh/kWc | Production à t-7 | calculé |
| `pv_moy7_passe` | kWh/kWc | Moyenne de la production sur les 7 jours précédents | calculé |
| `pv_ecart_type7_passe` | kWh/kWc | Écart-type de la production sur les 7 jours précédents (volatilité récente) | calculé |
| `nebulosite_veille` | % | Nébulosité de la veille | calculé |

### fr_eclairement_journalier.csv

Éclairement et éclairage naturel - France : irradiation horizontale, éclairement lumineux et 36 variables explicatives, 3 villes.

Lignes : 20 817 ; colonnes : 44 dont 37 variables explicatives ; valeurs manquantes : 0.003 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `ghi_kwh_m2` | kWh/m² | Irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `bhi_kwh_m2` | kWh/m² | Irradiation directe horizontale | PVGIS |
| `dhi_kwh_m2` | kWh/m² | Irradiation diffuse horizontale | PVGIS |
| `eclairement_max_klux` | klux | Éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus) | PVGIS, calculé |
| `heures_lumiere_10klux` | h | Heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant) | PVGIS, calculé |
| `dose_lumineuse_klux_h` | klux·h | Exposition lumineuse cumulée de la journée | PVGIS, calculé |
| `besoin_eclairage_h` | h | Heures où la lumière naturelle est insuffisante (24 - heures au-dessus de 10 000 lux) | PVGIS, calculé |
| `ghi_era5_kwh_m2` | kWh/m² | Irradiation globale horizontale selon la réanalyse ERA5 (seconde source) | Open-Meteo (ERA5) |
| `ghi_nasa_kwh_m2` | kWh/m² | Irradiation globale horizontale selon NASA POWER (troisième source) | NASA POWER |
| `ghi_ciel_clair_kwh_m2` | kWh/m² | Irradiation horizontale par ciel clair (sans nuages) | NASA POWER |
| `indice_clarte` | - | Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `rayonnement_toa_kwh_m2` | kWh/m² | Irradiation au sommet de l'atmosphère | NASA POWER |
| `par_kwh_m2` | kWh/m² | Rayonnement photosynthétiquement actif (lumière visible utile aux plantes) | NASA POWER |
| `indice_uv` | - | Indice UV par tout ciel | NASA POWER |
| `albedo` | - | Albédo de surface (part du rayonnement réfléchi par le sol) | NASA POWER |
| `aerosols_aod` | - | Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `nebulosite_nasa_pct` | % | Couverture nuageuse (satellite) | NASA POWER |
| `ensoleillement_h` | h | Durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `duree_jour_h` | h | Durée du jour (lever au coucher du soleil) | Open-Meteo |
| `duree_jour_astro_h` | h | Durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `hauteur_soleil_max_deg` | ° | Hauteur maximale du soleil sur l'horizon (pas horaire) | PVGIS |
| `hauteur_soleil_midi_deg` | ° | Hauteur du soleil à midi solaire, calculée (connue à l'avance) | calcul astronomique |
| `irr_extraterrestre_kwh_m2` | kWh/m² | Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `point_rosee_c` | °C | Point de rosée moyen à 2 m | Open-Meteo (ERA5) |
| `pression_hpa` | hPa | Pression moyenne ramenée au niveau de la mer | Open-Meteo (ERA5) |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `et0_mm` | mm | Évapotranspiration de référence FAO-56 | Open-Meteo (ERA5) |
| `t2m_moy_c` | °C | Température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jour_impute_pvgis` | 0/1 | 1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées | calculé |
| `ghi_veille` | kWh/m² | Irradiation horizontale de la veille | calculé |
| `ghi_moy7_passe` | kWh/m² | Moyenne de l'irradiation horizontale sur les 7 jours précédents | calculé |
| `nebulosite_veille` | % | Nébulosité de la veille | calculé |

### tn_photovoltaique_journalier.csv

Photovoltaïque - Tunisie : production journalière d'1 kWc et 35 variables explicatives, 3 villes.

Lignes : 20 817 ; colonnes : 43 dont 36 variables explicatives ; valeurs manquantes : 0.008 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `pv_kwh_kwc` | kWh/kWc | Énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_pic_w_kwc` | W/kWc | Puissance horaire maximale de la journée | PVGIS |
| `heures_production` | h | Nombre d'heures avec une production non nulle | PVGIS |
| `irr_poa_kwh_m2` | kWh/m² | Irradiation globale reçue sur le plan des modules | PVGIS |
| `irr_poa_direct_kwh_m2` | kWh/m² | Composante directe sur le plan des modules | PVGIS |
| `irr_poa_diffus_kwh_m2` | kWh/m² | Composante diffuse sur le plan des modules | PVGIS |
| `irr_poa_reflechi_kwh_m2` | kWh/m² | Composante réfléchie par le sol sur le plan des modules | PVGIS |
| `fraction_diffuse_poa` | - | Part du diffus dans l'irradiation du plan des modules (indicateur de couverture nuageuse) | PVGIS, calculé |
| `ratio_performance` | - | Énergie produite / irradiation reçue (pertes thermiques et système) | PVGIS, calculé |
| `t2m_moy_c` | °C | Température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `t2m_max_c` | °C | Température maximale | PVGIS (ERA5) |
| `t2m_min_c` | °C | Température minimale | PVGIS (ERA5) |
| `t2m_jour_c` | °C | Température moyenne pendant les heures de jour (influe sur le rendement des modules) | PVGIS (ERA5) |
| `amplitude_thermique_c` | °C | Écart entre maximum et minimum de température (ciel clair = forte amplitude) | PVGIS, calculé |
| `vent_moy_ms` | m/s | Vitesse moyenne du vent à 10 m (refroidit les modules) | PVGIS (ERA5) |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `ensoleillement_h` | h | Durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `rafales_max_kmh` | km/h | Rafale maximale à 10 m | Open-Meteo (ERA5) |
| `aerosols_aod` | - | Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `indice_clarte` | - | Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `ghi_ciel_clair_kwh_m2` | kWh/m² | Irradiation horizontale par ciel clair (sans nuages) | NASA POWER |
| `irr_extraterrestre_kwh_m2` | kWh/m² | Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `duree_jour_astro_h` | h | Durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `hauteur_soleil_midi_deg` | ° | Hauteur du soleil à midi solaire, calculée (connue à l'avance) | calcul astronomique |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `heures_reconstruites` | h | Heures dont le rayonnement a été reconstruit par PVGIS (indicateur de qualité) | PVGIS |
| `jour_impute_pvgis` | 0/1 | 1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées | calculé |
| `pv_veille` | kWh/kWc | Production de la veille (t-1) | calculé |
| `pv_j7` | kWh/kWc | Production à t-7 | calculé |
| `pv_moy7_passe` | kWh/kWc | Moyenne de la production sur les 7 jours précédents | calculé |
| `pv_ecart_type7_passe` | kWh/kWc | Écart-type de la production sur les 7 jours précédents (volatilité récente) | calculé |
| `nebulosite_veille` | % | Nébulosité de la veille | calculé |

### tn_eclairement_journalier.csv

Éclairement et éclairage naturel - Tunisie : irradiation horizontale, éclairement lumineux et 36 variables explicatives, 3 villes.

Lignes : 20 817 ; colonnes : 44 dont 37 variables explicatives ; valeurs manquantes : 0.003 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `ghi_kwh_m2` | kWh/m² | Irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `bhi_kwh_m2` | kWh/m² | Irradiation directe horizontale | PVGIS |
| `dhi_kwh_m2` | kWh/m² | Irradiation diffuse horizontale | PVGIS |
| `eclairement_max_klux` | klux | Éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus) | PVGIS, calculé |
| `heures_lumiere_10klux` | h | Heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant) | PVGIS, calculé |
| `dose_lumineuse_klux_h` | klux·h | Exposition lumineuse cumulée de la journée | PVGIS, calculé |
| `besoin_eclairage_h` | h | Heures où la lumière naturelle est insuffisante (24 - heures au-dessus de 10 000 lux) | PVGIS, calculé |
| `ghi_era5_kwh_m2` | kWh/m² | Irradiation globale horizontale selon la réanalyse ERA5 (seconde source) | Open-Meteo (ERA5) |
| `ghi_nasa_kwh_m2` | kWh/m² | Irradiation globale horizontale selon NASA POWER (troisième source) | NASA POWER |
| `ghi_ciel_clair_kwh_m2` | kWh/m² | Irradiation horizontale par ciel clair (sans nuages) | NASA POWER |
| `indice_clarte` | - | Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `rayonnement_toa_kwh_m2` | kWh/m² | Irradiation au sommet de l'atmosphère | NASA POWER |
| `par_kwh_m2` | kWh/m² | Rayonnement photosynthétiquement actif (lumière visible utile aux plantes) | NASA POWER |
| `indice_uv` | - | Indice UV par tout ciel | NASA POWER |
| `albedo` | - | Albédo de surface (part du rayonnement réfléchi par le sol) | NASA POWER |
| `aerosols_aod` | - | Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `nebulosite_nasa_pct` | % | Couverture nuageuse (satellite) | NASA POWER |
| `ensoleillement_h` | h | Durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `duree_jour_h` | h | Durée du jour (lever au coucher du soleil) | Open-Meteo |
| `duree_jour_astro_h` | h | Durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `hauteur_soleil_max_deg` | ° | Hauteur maximale du soleil sur l'horizon (pas horaire) | PVGIS |
| `hauteur_soleil_midi_deg` | ° | Hauteur du soleil à midi solaire, calculée (connue à l'avance) | calcul astronomique |
| `irr_extraterrestre_kwh_m2` | kWh/m² | Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `point_rosee_c` | °C | Point de rosée moyen à 2 m | Open-Meteo (ERA5) |
| `pression_hpa` | hPa | Pression moyenne ramenée au niveau de la mer | Open-Meteo (ERA5) |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `et0_mm` | mm | Évapotranspiration de référence FAO-56 | Open-Meteo (ERA5) |
| `t2m_moy_c` | °C | Température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jour_impute_pvgis` | 0/1 | 1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées | calculé |
| `ghi_veille` | kWh/m² | Irradiation horizontale de la veille | calculé |
| `ghi_moy7_passe` | kWh/m² | Moyenne de l'irradiation horizontale sur les 7 jours précédents | calculé |
| `nebulosite_veille` | % | Nébulosité de la veille | calculé |

### es_photovoltaique_journalier.csv

Photovoltaïque - Espagne : production journalière d'1 kWc et 35 variables explicatives, 3 villes.

Lignes : 20 817 ; colonnes : 43 dont 36 variables explicatives ; valeurs manquantes : 0.008 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `pv_kwh_kwc` | kWh/kWc | Énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_pic_w_kwc` | W/kWc | Puissance horaire maximale de la journée | PVGIS |
| `heures_production` | h | Nombre d'heures avec une production non nulle | PVGIS |
| `irr_poa_kwh_m2` | kWh/m² | Irradiation globale reçue sur le plan des modules | PVGIS |
| `irr_poa_direct_kwh_m2` | kWh/m² | Composante directe sur le plan des modules | PVGIS |
| `irr_poa_diffus_kwh_m2` | kWh/m² | Composante diffuse sur le plan des modules | PVGIS |
| `irr_poa_reflechi_kwh_m2` | kWh/m² | Composante réfléchie par le sol sur le plan des modules | PVGIS |
| `fraction_diffuse_poa` | - | Part du diffus dans l'irradiation du plan des modules (indicateur de couverture nuageuse) | PVGIS, calculé |
| `ratio_performance` | - | Énergie produite / irradiation reçue (pertes thermiques et système) | PVGIS, calculé |
| `t2m_moy_c` | °C | Température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `t2m_max_c` | °C | Température maximale | PVGIS (ERA5) |
| `t2m_min_c` | °C | Température minimale | PVGIS (ERA5) |
| `t2m_jour_c` | °C | Température moyenne pendant les heures de jour (influe sur le rendement des modules) | PVGIS (ERA5) |
| `amplitude_thermique_c` | °C | Écart entre maximum et minimum de température (ciel clair = forte amplitude) | PVGIS, calculé |
| `vent_moy_ms` | m/s | Vitesse moyenne du vent à 10 m (refroidit les modules) | PVGIS (ERA5) |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `ensoleillement_h` | h | Durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `rafales_max_kmh` | km/h | Rafale maximale à 10 m | Open-Meteo (ERA5) |
| `aerosols_aod` | - | Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `indice_clarte` | - | Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `ghi_ciel_clair_kwh_m2` | kWh/m² | Irradiation horizontale par ciel clair (sans nuages) | NASA POWER |
| `irr_extraterrestre_kwh_m2` | kWh/m² | Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `duree_jour_astro_h` | h | Durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `hauteur_soleil_midi_deg` | ° | Hauteur du soleil à midi solaire, calculée (connue à l'avance) | calcul astronomique |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `heures_reconstruites` | h | Heures dont le rayonnement a été reconstruit par PVGIS (indicateur de qualité) | PVGIS |
| `jour_impute_pvgis` | 0/1 | 1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées | calculé |
| `pv_veille` | kWh/kWc | Production de la veille (t-1) | calculé |
| `pv_j7` | kWh/kWc | Production à t-7 | calculé |
| `pv_moy7_passe` | kWh/kWc | Moyenne de la production sur les 7 jours précédents | calculé |
| `pv_ecart_type7_passe` | kWh/kWc | Écart-type de la production sur les 7 jours précédents (volatilité récente) | calculé |
| `nebulosite_veille` | % | Nébulosité de la veille | calculé |

### es_eclairement_journalier.csv

Éclairement et éclairage naturel - Espagne : irradiation horizontale, éclairement lumineux et 36 variables explicatives, 3 villes.

Lignes : 20 817 ; colonnes : 44 dont 37 variables explicatives ; valeurs manquantes : 0.003 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `ghi_kwh_m2` | kWh/m² | Irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `bhi_kwh_m2` | kWh/m² | Irradiation directe horizontale | PVGIS |
| `dhi_kwh_m2` | kWh/m² | Irradiation diffuse horizontale | PVGIS |
| `eclairement_max_klux` | klux | Éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus) | PVGIS, calculé |
| `heures_lumiere_10klux` | h | Heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant) | PVGIS, calculé |
| `dose_lumineuse_klux_h` | klux·h | Exposition lumineuse cumulée de la journée | PVGIS, calculé |
| `besoin_eclairage_h` | h | Heures où la lumière naturelle est insuffisante (24 - heures au-dessus de 10 000 lux) | PVGIS, calculé |
| `ghi_era5_kwh_m2` | kWh/m² | Irradiation globale horizontale selon la réanalyse ERA5 (seconde source) | Open-Meteo (ERA5) |
| `ghi_nasa_kwh_m2` | kWh/m² | Irradiation globale horizontale selon NASA POWER (troisième source) | NASA POWER |
| `ghi_ciel_clair_kwh_m2` | kWh/m² | Irradiation horizontale par ciel clair (sans nuages) | NASA POWER |
| `indice_clarte` | - | Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `rayonnement_toa_kwh_m2` | kWh/m² | Irradiation au sommet de l'atmosphère | NASA POWER |
| `par_kwh_m2` | kWh/m² | Rayonnement photosynthétiquement actif (lumière visible utile aux plantes) | NASA POWER |
| `indice_uv` | - | Indice UV par tout ciel | NASA POWER |
| `albedo` | - | Albédo de surface (part du rayonnement réfléchi par le sol) | NASA POWER |
| `aerosols_aod` | - | Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `nebulosite_nasa_pct` | % | Couverture nuageuse (satellite) | NASA POWER |
| `ensoleillement_h` | h | Durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `duree_jour_h` | h | Durée du jour (lever au coucher du soleil) | Open-Meteo |
| `duree_jour_astro_h` | h | Durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `hauteur_soleil_max_deg` | ° | Hauteur maximale du soleil sur l'horizon (pas horaire) | PVGIS |
| `hauteur_soleil_midi_deg` | ° | Hauteur du soleil à midi solaire, calculée (connue à l'avance) | calcul astronomique |
| `irr_extraterrestre_kwh_m2` | kWh/m² | Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `point_rosee_c` | °C | Point de rosée moyen à 2 m | Open-Meteo (ERA5) |
| `pression_hpa` | hPa | Pression moyenne ramenée au niveau de la mer | Open-Meteo (ERA5) |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `et0_mm` | mm | Évapotranspiration de référence FAO-56 | Open-Meteo (ERA5) |
| `t2m_moy_c` | °C | Température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jour_impute_pvgis` | 0/1 | 1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées | calculé |
| `ghi_veille` | kWh/m² | Irradiation horizontale de la veille | calculé |
| `ghi_moy7_passe` | kWh/m² | Moyenne de l'irradiation horizontale sur les 7 jours précédents | calculé |
| `nebulosite_veille` | % | Nébulosité de la veille | calculé |

### panel_9_villes_journalier.csv

Panel complet : 9 villes x 6 939 jours, toutes les variables (table de modélisation).

Lignes : 62 451 ; colonnes : 65 dont 57 variables explicatives ; valeurs manquantes : 0.007 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `pv_kwh_kwc` | kWh/kWc | Énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_pic_w_kwc` | W/kWc | Puissance horaire maximale de la journée | PVGIS |
| `heures_production` | h | Nombre d'heures avec une production non nulle | PVGIS |
| `irr_poa_kwh_m2` | kWh/m² | Irradiation globale reçue sur le plan des modules | PVGIS |
| `irr_poa_direct_kwh_m2` | kWh/m² | Composante directe sur le plan des modules | PVGIS |
| `irr_poa_diffus_kwh_m2` | kWh/m² | Composante diffuse sur le plan des modules | PVGIS |
| `irr_poa_reflechi_kwh_m2` | kWh/m² | Composante réfléchie par le sol sur le plan des modules | PVGIS |
| `ghi_kwh_m2` | kWh/m² | Irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `bhi_kwh_m2` | kWh/m² | Irradiation directe horizontale | PVGIS |
| `dhi_kwh_m2` | kWh/m² | Irradiation diffuse horizontale | PVGIS |
| `eclairement_max_klux` | klux | Éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus) | PVGIS, calculé |
| `heures_lumiere_10klux` | h | Heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant) | PVGIS, calculé |
| `dose_lumineuse_klux_h` | klux·h | Exposition lumineuse cumulée de la journée | PVGIS, calculé |
| `hauteur_soleil_max_deg` | ° | Hauteur maximale du soleil sur l'horizon (pas horaire) | PVGIS |
| `t2m_moy_c` | °C | Température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `t2m_max_c` | °C | Température maximale | PVGIS (ERA5) |
| `t2m_min_c` | °C | Température minimale | PVGIS (ERA5) |
| `t2m_jour_c` | °C | Température moyenne pendant les heures de jour (influe sur le rendement des modules) | PVGIS (ERA5) |
| `vent_moy_ms` | m/s | Vitesse moyenne du vent à 10 m (refroidit les modules) | PVGIS (ERA5) |
| `heures_reconstruites` | h | Heures dont le rayonnement a été reconstruit par PVGIS (indicateur de qualité) | PVGIS |
| `fraction_diffuse_poa` | - | Part du diffus dans l'irradiation du plan des modules (indicateur de couverture nuageuse) | PVGIS, calculé |
| `ratio_performance` | - | Énergie produite / irradiation reçue (pertes thermiques et système) | PVGIS, calculé |
| `amplitude_thermique_c` | °C | Écart entre maximum et minimum de température (ciel clair = forte amplitude) | PVGIS, calculé |
| `besoin_eclairage_h` | h | Heures où la lumière naturelle est insuffisante (24 - heures au-dessus de 10 000 lux) | PVGIS, calculé |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `ensoleillement_h` | h | Durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `duree_jour_h` | h | Durée du jour (lever au coucher du soleil) | Open-Meteo |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `point_rosee_c` | °C | Point de rosée moyen à 2 m | Open-Meteo (ERA5) |
| `pression_hpa` | hPa | Pression moyenne ramenée au niveau de la mer | Open-Meteo (ERA5) |
| `rafales_max_kmh` | km/h | Rafale maximale à 10 m | Open-Meteo (ERA5) |
| `et0_mm` | mm | Évapotranspiration de référence FAO-56 | Open-Meteo (ERA5) |
| `ghi_era5_kwh_m2` | kWh/m² | Irradiation globale horizontale selon la réanalyse ERA5 (seconde source) | Open-Meteo (ERA5) |
| `ghi_nasa_kwh_m2` | kWh/m² | Irradiation globale horizontale selon NASA POWER (troisième source) | NASA POWER |
| `ghi_ciel_clair_kwh_m2` | kWh/m² | Irradiation horizontale par ciel clair (sans nuages) | NASA POWER |
| `indice_clarte` | - | Indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `rayonnement_toa_kwh_m2` | kWh/m² | Irradiation au sommet de l'atmosphère | NASA POWER |
| `nebulosite_nasa_pct` | % | Couverture nuageuse (satellite) | NASA POWER |
| `aerosols_aod` | - | Épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `indice_uv` | - | Indice UV par tout ciel | NASA POWER |
| `albedo` | - | Albédo de surface (part du rayonnement réfléchi par le sol) | NASA POWER |
| `par_kwh_m2` | kWh/m² | Rayonnement photosynthétiquement actif (lumière visible utile aux plantes) | NASA POWER |
| `irr_extraterrestre_kwh_m2` | kWh/m² | Irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `duree_jour_astro_h` | h | Durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `hauteur_soleil_midi_deg` | ° | Hauteur du soleil à midi solaire, calculée (connue à l'avance) | calcul astronomique |
| `jour_annee` | - | Rang du jour dans l'année | calendrier |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jour_impute_pvgis` | 0/1 | 1 si le rayonnement PVGIS manque ce jour-là (trou de la base SARAH3) : valeurs PVGIS imputées | calculé |
| `pv_veille` | kWh/kWc | Production de la veille (t-1) | calculé |
| `pv_j7` | kWh/kWc | Production à t-7 | calculé |
| `pv_moy7_passe` | kWh/kWc | Moyenne de la production sur les 7 jours précédents | calculé |
| `pv_ecart_type7_passe` | kWh/kWc | Écart-type de la production sur les 7 jours précédents (volatilité récente) | calculé |
| `ghi_veille` | kWh/m² | Irradiation horizontale de la veille | calculé |
| `ghi_moy7_passe` | kWh/m² | Moyenne de l'irradiation horizontale sur les 7 jours précédents | calculé |
| `nebulosite_veille` | % | Nébulosité de la veille | calculé |

### mensuel_9_villes.csv

Mensuel : totaux, moyennes, extrêmes et nombre de jours de pluie, de ciel couvert ou de poussières par ville (2005-2023).

Lignes : 2 052 ; colonnes : 47 dont 40 variables explicatives ; valeurs manquantes : 0.0 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `pv_kwh_kwc_somme` | kWh/kWc | Somme mensuelle de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `irr_poa_kwh_m2_somme` | kWh/m² | Somme mensuelle de : irradiation globale reçue sur le plan des modules | PVGIS |
| `irr_poa_direct_kwh_m2_somme` | kWh/m² | Somme mensuelle de : composante directe sur le plan des modules | PVGIS |
| `irr_poa_diffus_kwh_m2_somme` | kWh/m² | Somme mensuelle de : composante diffuse sur le plan des modules | PVGIS |
| `ghi_kwh_m2_somme` | kWh/m² | Somme mensuelle de : irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `bhi_kwh_m2_somme` | kWh/m² | Somme mensuelle de : irradiation directe horizontale | PVGIS |
| `dhi_kwh_m2_somme` | kWh/m² | Somme mensuelle de : irradiation diffuse horizontale | PVGIS |
| `ensoleillement_h_somme` | h | Somme mensuelle de : durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `precipitation_mm_somme` | mm | Somme mensuelle de : cumul de précipitations | Open-Meteo (ERA5) |
| `dose_lumineuse_klux_h_somme` | klux·h | Somme mensuelle de : exposition lumineuse cumulée de la journée | PVGIS, calculé |
| `heures_lumiere_10klux_somme` | h | Somme mensuelle de : heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant) | PVGIS, calculé |
| `besoin_eclairage_h_somme` | h | Somme mensuelle de : heures où la lumière naturelle est insuffisante (24 - heures au-dessus de 10 000 lux) | PVGIS, calculé |
| `irr_extraterrestre_kwh_m2_somme` | kWh/m² | Somme mensuelle de : irradiation extraterrestre sur plan horizontal, calculée (connue à l'avance) | calcul astronomique |
| `et0_mm_somme` | mm | Somme mensuelle de : évapotranspiration de référence FAO-56 | Open-Meteo (ERA5) |
| `heures_production_somme` | h | Somme mensuelle de : nombre d'heures avec une production non nulle | PVGIS |
| `t2m_moy_c_moy` | °C | Moyenne mensuelle de : température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `t2m_max_c_moy` | °C | Moyenne mensuelle de : température maximale | PVGIS (ERA5) |
| `t2m_min_c_moy` | °C | Moyenne mensuelle de : température minimale | PVGIS (ERA5) |
| `nebulosite_pct_moy` | % | Moyenne mensuelle de : couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `humidite_pct_moy` | % | Moyenne mensuelle de : humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `pression_hpa_moy` | hPa | Moyenne mensuelle de : pression moyenne ramenée au niveau de la mer | Open-Meteo (ERA5) |
| `vent_moy_ms_moy` | m/s | Moyenne mensuelle de : vitesse moyenne du vent à 10 m (refroidit les modules) | PVGIS (ERA5) |
| `aerosols_aod_moy` | - | Moyenne mensuelle de : épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `indice_clarte_moy` | - | Moyenne mensuelle de : indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `fraction_diffuse_poa_moy` | - | Moyenne mensuelle de : part du diffus dans l'irradiation du plan des modules (indicateur de couverture nuageuse) | PVGIS, calculé |
| `ratio_performance_moy` | - | Moyenne mensuelle de : énergie produite / irradiation reçue (pertes thermiques et système) | PVGIS, calculé |
| `duree_jour_astro_h_moy` | h | Moyenne mensuelle de : durée astronomique du jour, calculée (connue à l'avance) | calcul astronomique |
| `eclairement_max_klux_moy` | klux | Moyenne mensuelle de : éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus) | PVGIS, calculé |
| `pv_kwh_kwc_min` | kWh/kWc | Minimum mensuel de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_kwh_kwc_max` | kWh/kWc | Maximum mensuel de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_kwh_kwc_et` | kWh/kWc | Écart-type mensuel de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `aerosols_aod_max` | - | Maximum mensuel de : épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `rafales_max_kmh_max` | km/h | Maximum mensuel de : rafale maximale à 10 m | Open-Meteo (ERA5) |
| `jours_pluie` | jours | Jours du mois avec au moins 1 mm de pluie | Open-Meteo, calculé |
| `jours_couverts` | jours | Jours du mois avec une nébulosité d'au moins 80 % | Open-Meteo, calculé |
| `jours_clairs` | jours | Jours du mois avec un indice de clarté d'au moins 0,65 | NASA POWER, calculé |
| `jours_poussiere` | jours | Jours du mois avec une épaisseur optique des aérosols d'au moins 0,8 | NASA POWER, calculé |
| `jours_imputes` | jours | Jours du mois dont le rayonnement PVGIS a été imputé | calculé |
| `annee` | - | Année | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |

### climatologie_9_villes.csv

Normales par jour de l'année (2005-2020) : moyennes, écarts-types, centiles et probabilités de pluie ou de ciel couvert.

Lignes : 3 294 ; colonnes : 39 dont 32 variables explicatives ; valeurs manquantes : 0.0 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0) ; NASA Langley Research Center, projet POWER (MERRA-2, CERES) - https://power.larc.nasa.gov

| Variable | Unité | Description | Source |
|---|---|---|---|
| `jour_annee` | - | Rang du jour dans l'année | calendrier |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `pv_kwh_kwc_moyenne` | kWh/kWc | Moyenne (jour de l'année, 2005-2020) de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_kwh_kwc_ecart_type` | kWh/kWc | Écart-type (jour de l'année, 2005-2020) de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `ghi_kwh_m2_moyenne` | kWh/m² | Moyenne (jour de l'année, 2005-2020) de : irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `ghi_kwh_m2_ecart_type` | kWh/m² | Écart-type (jour de l'année, 2005-2020) de : irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `irr_poa_kwh_m2_moyenne` | kWh/m² | Moyenne (jour de l'année, 2005-2020) de : irradiation globale reçue sur le plan des modules | PVGIS |
| `irr_poa_kwh_m2_ecart_type` | kWh/m² | Écart-type (jour de l'année, 2005-2020) de : irradiation globale reçue sur le plan des modules | PVGIS |
| `nebulosite_pct_moyenne` | % | Moyenne (jour de l'année, 2005-2020) de : couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `nebulosite_pct_ecart_type` | % | Écart-type (jour de l'année, 2005-2020) de : couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `t2m_moy_c_moyenne` | °C | Moyenne (jour de l'année, 2005-2020) de : température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `t2m_moy_c_ecart_type` | °C | Écart-type (jour de l'année, 2005-2020) de : température moyenne de l'air à 2 m | PVGIS (ERA5) |
| `heures_lumiere_10klux_moyenne` | h | Moyenne (jour de l'année, 2005-2020) de : heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant) | PVGIS, calculé |
| `heures_lumiere_10klux_ecart_type` | h | Écart-type (jour de l'année, 2005-2020) de : heures où l'éclairement lumineux horizontal dépasse 10 000 lux (éclairage naturel suffisant) | PVGIS, calculé |
| `ensoleillement_h_moyenne` | h | Moyenne (jour de l'année, 2005-2020) de : durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `ensoleillement_h_ecart_type` | h | Écart-type (jour de l'année, 2005-2020) de : durée d'ensoleillement (rayonnement direct > 120 W/m²) | Open-Meteo (ERA5) |
| `precipitation_mm_moyenne` | mm | Moyenne (jour de l'année, 2005-2020) de : cumul de précipitations | Open-Meteo (ERA5) |
| `precipitation_mm_ecart_type` | mm | Écart-type (jour de l'année, 2005-2020) de : cumul de précipitations | Open-Meteo (ERA5) |
| `aerosols_aod_moyenne` | - | Moyenne (jour de l'année, 2005-2020) de : épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `aerosols_aod_ecart_type` | - | Écart-type (jour de l'année, 2005-2020) de : épaisseur optique des aérosols à 550 nm (poussières sahariennes, pollution) | NASA POWER (MERRA-2) |
| `indice_clarte_moyenne` | - | Moyenne (jour de l'année, 2005-2020) de : indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `indice_clarte_ecart_type` | - | Écart-type (jour de l'année, 2005-2020) de : indice de clarté (irradiation au sol / irradiation au sommet de l'atmosphère) | NASA POWER |
| `eclairement_max_klux_moyenne` | klux | Moyenne (jour de l'année, 2005-2020) de : éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus) | PVGIS, calculé |
| `eclairement_max_klux_ecart_type` | klux | Écart-type (jour de l'année, 2005-2020) de : éclairement lumineux horizontal maximal de la journée (100 lm/W direct, 125 lm/W diffus) | PVGIS, calculé |
| `duree_jour_h_moyenne` | h | Moyenne (jour de l'année, 2005-2020) de : durée du jour (lever au coucher du soleil) | Open-Meteo |
| `duree_jour_h_ecart_type` | h | Écart-type (jour de l'année, 2005-2020) de : durée du jour (lever au coucher du soleil) | Open-Meteo |
| `pv_kwh_kwc_p10` | kWh/kWc | 10e centile (jour de l'année) de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_kwh_kwc_p50` | kWh/kWc | Médiane (jour de l'année) de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `pv_kwh_kwc_p90` | kWh/kWc | 90e centile (jour de l'année) de : énergie produite dans la journée par 1 kWc (pente optimale, plein sud, pertes 14 %) - CIBLE photovoltaïque | PVGIS |
| `ghi_kwh_m2_p10` | kWh/m² | 10e centile (jour de l'année) de : irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `ghi_kwh_m2_p90` | kWh/m² | 90e centile (jour de l'année) de : irradiation globale horizontale (éclairement énergétique cumulé) - CIBLE éclairement | PVGIS |
| `proba_pluie` | - | Probabilité d'au moins 1 mm de pluie ce jour de l'année (2005-2020) | Open-Meteo, calculé |
| `proba_ciel_couvert` | - | Probabilité d'une nébulosité d'au moins 80 % ce jour de l'année (2005-2020) | Open-Meteo, calculé |
| `n_annees` | - | Nombre d'années ayant servi au calcul | calculé |

### horaire_9_villes_2023.csv.gz

Horaire 2023 : puissance PV, éclairement (plan incliné, horizontal, lux), nuages par étage et météo ERA5, grandeurs dérivées.

Lignes : 78 840 ; colonnes : 48 dont 40 variables explicatives ; valeurs manquantes : 4.512 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source) ; Open-Meteo Historical Weather API (réanalyse ERA5 de Copernicus/ECMWF) - https://open-meteo.com (CC BY 4.0)

| Variable | Unité | Description | Source |
|---|---|---|---|
| `heure_utc` | - | heure_utc | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `p_w_kwc` | W/kWc | Puissance photovoltaïque d'1 kWc pendant l'heure | PVGIS |
| `gb_poa_w_m2` | W/m² | Éclairement direct sur le plan des modules | PVGIS |
| `gd_poa_w_m2` | W/m² | Éclairement diffus sur le plan des modules | PVGIS |
| `gr_poa_w_m2` | W/m² | Éclairement réfléchi sur le plan des modules | PVGIS |
| `gb_h_w_m2` | W/m² | Éclairement direct horizontal | PVGIS |
| `gd_h_w_m2` | W/m² | Éclairement diffus horizontal | PVGIS |
| `hauteur_soleil_deg` | ° | Hauteur du soleil sur l'horizon | PVGIS ou calcul astronomique |
| `t2m_c` | °C | Température de l'air à 2 m | PVGIS (ERA5) |
| `vent_ms` | m/s | Vitesse du vent à 10 m | PVGIS (ERA5) |
| `reconstruit` | 0/1 | 1 si le rayonnement de l'heure a été reconstruit par PVGIS | PVGIS |
| `ghi_w_m2` | W/m² | Éclairement global horizontal | PVGIS |
| `poa_w_m2` | W/m² | Éclairement global sur le plan des modules | PVGIS, calculé |
| `fraction_diffuse_h` | - | Part du diffus dans l'éclairement horizontal | PVGIS, calculé |
| `g0_horizontal_w_m2` | W/m² | Éclairement extraterrestre sur plan horizontal (calcul astronomique) | calculé |
| `indice_clarte_h` | - | Indice de clarté horaire (éclairement au sol / extraterrestre) | calculé |
| `masse_air` | - | Masse d'air traversée par le rayonnement (1 / sin de la hauteur du soleil) | calculé |
| `eclairement_lux` | lux | Éclairement lumineux horizontal (100 lm/W direct, 125 lm/W diffus) | calculé |
| `eclairement_direct_lux` | lux | Part directe de l'éclairement lumineux horizontal | calculé |
| `eclairement_diffus_lux` | lux | Part diffuse de l'éclairement lumineux horizontal | calculé |
| `lumiere_suffisante` | 0/1 | 1 si l'éclairement lumineux dépasse 10 000 lux (éclairage naturel suffisant) | calculé |
| `t_module_c` | °C | Température estimée des modules (modèle NOCT : T air + éclairement / 800 x 25 °C) | calculé |
| `ratio_performance_h` | - | Puissance produite / éclairement reçu pendant l'heure | calculé |
| `heure_solaire` | h | Heure solaire locale (heure UTC + longitude / 15) | calculé |
| `h_sin` | - | sin(2π heure/24) | calendrier |
| `h_cos` | - | cos(2π heure/24) | calendrier |
| `jour_annee` | - | Rang du jour dans l'année | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `nebulosite_pct` | % | Couverture nuageuse moyenne | Open-Meteo (ERA5) |
| `nebulosite_basse_pct` | % | Couverture nuageuse basse (sous 2 km) | Open-Meteo (ERA5) |
| `nebulosite_moyenne_pct` | % | Couverture nuageuse moyenne (2 à 6 km) | Open-Meteo (ERA5) |
| `nebulosite_haute_pct` | % | Couverture nuageuse haute (au-dessus de 6 km) | Open-Meteo (ERA5) |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `precipitation_mm` | mm | Cumul de précipitations | Open-Meteo (ERA5) |
| `direction_vent_deg` | ° | Direction d'où vient le vent | Open-Meteo (ERA5) ou PVGIS |
| `pression_surface_hpa` | hPa | Pression au niveau du sol | Open-Meteo (ERA5) |
| `ghi_era5_w_m2` | W/m² | Éclairement global horizontal selon ERA5 (seconde source) | Open-Meteo (ERA5) |
| `dni_era5_w_m2` | W/m² | Éclairement direct normal selon ERA5 | Open-Meteo (ERA5) |
| `dhi_era5_w_m2` | W/m² | Éclairement diffus horizontal selon ERA5 | Open-Meteo (ERA5) |
| `temperature_ressentie_c` | °C | Température ressentie | Open-Meteo (ERA5) |

### tmy_9_villes.csv

Année météorologique type PVGIS (8 760 h par ville) enrichie : géométrie solaire, éclairage, point de rosée, vent, modules.

Lignes : 78 840 ; colonnes : 36 dont 28 variables explicatives ; valeurs manquantes : 2.943 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source)

| Variable | Unité | Description | Source |
|---|---|---|---|
| `heure_utc` | - | heure_utc | - |
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `t2m_c` | °C | Température de l'air à 2 m | PVGIS (ERA5) |
| `humidite_pct` | % | Humidité relative moyenne à 2 m | Open-Meteo (ERA5) |
| `ghi_w_m2` | W/m² | Éclairement global horizontal | PVGIS |
| `dni_w_m2` | W/m² | Éclairement direct normal | PVGIS |
| `dhi_w_m2` | W/m² | Éclairement diffus horizontal | PVGIS |
| `infrarouge_w_m2` | W/m² | Rayonnement infrarouge descendant | PVGIS |
| `vent_ms` | m/s | Vitesse du vent à 10 m | PVGIS (ERA5) |
| `direction_vent_deg` | ° | Direction d'où vient le vent | Open-Meteo (ERA5) ou PVGIS |
| `pression_pa` | Pa | Pression au sol | PVGIS |
| `annee_source` | - | Année d'où provient le mois retenu dans l'année type | PVGIS |
| `heure` | h | Heure UTC | PVGIS |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jour_annee` | - | Rang du jour dans l'année | calendrier |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `h_sin` | - | sin(2π heure/24) | calendrier |
| `h_cos` | - | cos(2π heure/24) | calendrier |
| `hauteur_soleil_deg` | ° | Hauteur du soleil sur l'horizon | PVGIS ou calcul astronomique |
| `bhi_w_m2` | W/m² | Éclairement direct horizontal (direct normal x sin de la hauteur du soleil) | calculé |
| `fraction_diffuse_h` | - | Part du diffus dans l'éclairement horizontal | PVGIS, calculé |
| `g0_horizontal_w_m2` | W/m² | Éclairement extraterrestre sur plan horizontal (calcul astronomique) | calculé |
| `indice_clarte_h` | - | Indice de clarté horaire (éclairement au sol / extraterrestre) | calculé |
| `eclairement_lux` | lux | Éclairement lumineux horizontal (100 lm/W direct, 125 lm/W diffus) | calculé |
| `lumiere_suffisante` | 0/1 | 1 si l'éclairement lumineux dépasse 10 000 lux (éclairage naturel suffisant) | calculé |
| `point_rosee_c` | °C | Point de rosée moyen à 2 m | Open-Meteo (ERA5) |
| `vent_u_ms` | m/s | Composante est-ouest du vent | calculé |
| `vent_v_ms` | m/s | Composante nord-sud du vent | calculé |
| `t_module_c` | °C | Température estimée des modules (modèle NOCT : T air + éclairement / 800 x 25 °C) | calculé |
| `pv_horizontale_estimee_w_kwc` | W/kWc | Puissance estimée d'1 kWc posé à plat (pertes 14 %, -0,4 %/°C au-delà de 25 °C) | calculé |

### pvgis_orientations_9_villes.csv

Scénarios d'installation PVGIS : production mensuelle d'1 kWc pour 27 inclinaisons et orientations par ville.

Lignes : 2 916 ; colonnes : 29 dont 23 variables explicatives ; valeurs manquantes : 0.0 %.

Sources : PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source)

| Variable | Unité | Description | Source |
|---|---|---|---|
| `site` | - | Identifiant du site | - |
| `ville` | - | Ville | - |
| `pays` | - | Pays | - |
| `code_pays` | - | Code ISO du pays | - |
| `latitude` | ° | Latitude | - |
| `longitude` | ° | Longitude | - |
| `inclinaison_deg` | ° | Inclinaison des modules (0 = à plat, 90 = façade verticale) | PVGIS |
| `azimut_deg` | ° | Orientation des modules (0 = sud, -90 = est, 90 = ouest) | PVGIS |
| `orientation` | - | Orientation en clair | PVGIS |
| `est_optimal` | 0/1 | 1 pour la pente optimale plein sud du site | PVGIS |
| `mois` | - | Mois (1 à 12) | calendrier |
| `mois_sin` | - | sin(2π mois/12) | calendrier |
| `mois_cos` | - | cos(2π mois/12) | calendrier |
| `e_jour_kwh_kwc` | kWh/kWc | Production journalière moyenne du mois | PVGIS |
| `e_mois_kwh_kwc` | kWh/kWc | Production mensuelle moyenne | PVGIS |
| `h_jour_kwh_m2` | kWh/m² | Irradiation journalière moyenne du mois sur le plan des modules | PVGIS |
| `h_mois_kwh_m2` | kWh/m² | Irradiation mensuelle moyenne sur le plan des modules | PVGIS |
| `ecart_type_mois_kwh` | kWh | Écart-type de la production mensuelle d'une année à l'autre | PVGIS |
| `e_an_kwh_kwc` | kWh/kWc | Production annuelle moyenne de ce scénario | PVGIS |
| `h_an_kwh_m2` | kWh/m² | Irradiation annuelle sur le plan des modules | PVGIS |
| `ecart_type_an_kwh` | kWh | Écart-type de la production annuelle | PVGIS |
| `perte_incidence_pct` | % | Pertes par angle d'incidence (réflexion) | PVGIS |
| `perte_spectrale_pct` | % | Effet spectral | PVGIS |
| `perte_temperature_pct` | % | Pertes dues à la température et au faible éclairement | PVGIS |
| `perte_totale_pct` | % | Pertes totales (y compris 14 % de pertes système) | PVGIS |
| `part_productible_optimal_pct` | % | Production annuelle du scénario rapportée à celle de la pente optimale plein sud | calculé |
| `ratio_mensuel_vs_optimal` | - | Production du mois rapportée à celle de la pente optimale plein sud le même mois | calculé |
| `pente_optimale_site_deg` | ° | Pente optimale du site (plein sud) | PVGIS |
| `productible_optimal_kwh_kwc` | kWh/kWc | Production annuelle à la pente optimale plein sud | PVGIS |

### fr_solaire_national_rte_journalier.csv

Production solaire nationale mesurée et mix électrique français (journalier, 2012-2026), avec la météo des 3 villes.

Lignes : 5 357 ; colonnes : 39 dont 38 variables explicatives ; valeurs manquantes : 2.819 %.

Sources : RTE éCO2mix via le portail ODRÉ, jeu eco2mix-national-cons-def - https://odre.opendatasoft.com (Licence Ouverte v2.0) ; PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source)

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `production_gwh` | GWh | Production solaire photovoltaïque nationale de la journée | RTE |
| `puissance_moyenne_mw` | MW | Puissance solaire moyenne de la journée (points à 30 min) | RTE |
| `puissance_max_mw` | MW | Puissance solaire maximale de la journée | RTE |
| `facteur_forme_solaire` | - | Puissance solaire moyenne / maximale (journée régulière ou hachée par les nuages) | RTE, calculé |
| `consommation_gwh` | GWh | Énergie journalière de la filière ou du poste « consommation » (puissance moyenne x 24 h) | RTE |
| `nucleaire_gwh` | GWh | Énergie journalière de la filière ou du poste « nucleaire » (puissance moyenne x 24 h) | RTE |
| `eolien_gwh` | GWh | Énergie journalière de la filière ou du poste « eolien » (puissance moyenne x 24 h) | RTE |
| `hydraulique_gwh` | GWh | Énergie journalière de la filière ou du poste « hydraulique » (puissance moyenne x 24 h) | RTE |
| `gaz_gwh` | GWh | Énergie journalière de la filière ou du poste « gaz » (puissance moyenne x 24 h) | RTE |
| `charbon_gwh` | GWh | Énergie journalière de la filière ou du poste « charbon » (puissance moyenne x 24 h) | RTE |
| `fioul_gwh` | GWh | Énergie journalière de la filière ou du poste « fioul » (puissance moyenne x 24 h) | RTE |
| `bioenergies_gwh` | GWh | Énergie journalière de la filière ou du poste « bioenergies » (puissance moyenne x 24 h) | RTE |
| `pompage_gwh` | GWh | Énergie journalière de la filière ou du poste « pompage » (puissance moyenne x 24 h) | RTE |
| `ech_physiques_gwh` | GWh | Énergie journalière de la filière ou du poste « ech physiques » (puissance moyenne x 24 h) | RTE |
| `ech_comm_espagne_gwh` | GWh | Énergie journalière de la filière ou du poste « ech comm espagne » (puissance moyenne x 24 h) | RTE |
| `ech_comm_italie_gwh` | GWh | Énergie journalière de la filière ou du poste « ech comm italie » (puissance moyenne x 24 h) | RTE |
| `ech_comm_angleterre_gwh` | GWh | Énergie journalière de la filière ou du poste « ech comm angleterre » (puissance moyenne x 24 h) | RTE |
| `ech_comm_suisse_gwh` | GWh | Énergie journalière de la filière ou du poste « ech comm suisse » (puissance moyenne x 24 h) | RTE |
| `gaz_ccg_gwh` | GWh | Énergie journalière de la filière ou du poste « gaz ccg » (puissance moyenne x 24 h) | RTE |
| `hydraulique_fil_eau_eclusee_gwh` | GWh | Énergie journalière de la filière ou du poste « hydraulique fil eau eclusee » (puissance moyenne x 24 h) | RTE |
| `hydraulique_lacs_gwh` | GWh | Énergie journalière de la filière ou du poste « hydraulique lacs » (puissance moyenne x 24 h) | RTE |
| `hydraulique_step_turbinage_gwh` | GWh | Énergie journalière de la filière ou du poste « hydraulique step turbinage » (puissance moyenne x 24 h) | RTE |
| `bioenergies_biomasse_gwh` | GWh | Énergie journalière de la filière ou du poste « bioenergies biomasse » (puissance moyenne x 24 h) | RTE |
| `taux_co2_g_kwh` | g/kWh | Intensité carbone moyenne de l'électricité produite | RTE |
| `part_solaire_conso_pct` | % | Part de la consommation couverte par le solaire | RTE, calculé |
| `part_renouvelable_conso_pct` | % | Part de la consommation couverte par solaire, éolien, hydraulique et bioénergies | RTE, calculé |
| `erreur_prevision_j1_pct` | % | Écart entre la prévision de consommation de RTE à J-1 et la consommation réalisée | RTE, calculé |
| `n_points` | - | Nombre de points à 30 min agrégés dans la journée (48 attendus) | RTE |
| `nature` | - | Statut des données RTE (définitives ou consolidées) | RTE |
| `jour_semaine` | - | Jour de la semaine (0 = lundi) | calendrier |
| `week_end` | 0/1 | 1 le samedi et le dimanche | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `pvgis_pv_moyen_kwh_kwc` | kWh/kWc | Production PVGIS moyenne des 3 villes du pays le même jour (lien avec la météo, jusqu'en 2023) | PVGIS |
| `pvgis_ghi_moyen_kwh_m2` | kWh/m² | Irradiation horizontale PVGIS moyenne des 3 villes du pays le même jour | PVGIS |
| `nebulosite_moyenne_pays_pct` | % | Nébulosité moyenne des 3 villes du pays le même jour | Open-Meteo (ERA5) |
| `t2m_moyenne_pays_c` | °C | Température moyenne des 3 villes du pays le même jour | PVGIS (ERA5) |

### es_fotovoltaica_ree_journalier.csv

Production photovoltaïque mesurée et bilan électrique espagnol péninsulaire (journalier, 2014-2026), avec la météo des 3 villes.

Lignes : 4 666 ; colonnes : 37 dont 36 variables explicatives ; valeurs manquantes : 11.485 %.

Sources : Red Eléctrica (REData API, bilan électrique) - https://apidatos.ree.es (réutilisation avec mention « Fuente: Red Eléctrica ») ; PVGIS 5.3, Commission européenne, Centre commun de recherche (JRC) - https://re.jrc.ec.europa.eu/pvg_tools/ (rayonnement PVGIS-SARAH3, météo ERA5 ; réutilisation autorisée avec mention de la source)

| Variable | Unité | Description | Source |
|---|---|---|---|
| `date` | jour | Date (jour UTC pour PVGIS, jour local pour Open-Meteo, heure solaire locale pour NASA POWER) | - |
| `hidraulica_gwh` | GWh | Énergie journalière du bilan électrique : « hidraulica » | REE |
| `eolica_gwh` | GWh | Énergie journalière du bilan électrique : « eolica » | REE |
| `solar_fotovoltaica_gwh` | GWh | Énergie journalière du bilan électrique : « solar fotovoltaica » | REE |
| `solar_termica_gwh` | GWh | Énergie journalière du bilan électrique : « solar termica » | REE |
| `otras_renovables_gwh` | GWh | Énergie journalière du bilan électrique : « otras renovables » | REE |
| `residuos_renovables_gwh` | GWh | Énergie journalière du bilan électrique : « residuos renovables » | REE |
| `generacion_renovable_gwh` | GWh | Énergie journalière du bilan électrique : « generacion renovable » | REE |
| `nuclear_gwh` | GWh | Énergie journalière du bilan électrique : « nuclear » | REE |
| `ciclo_combinado_gwh` | GWh | Énergie journalière du bilan électrique : « ciclo combinado » | REE |
| `carbon_gwh` | GWh | Énergie journalière du bilan électrique : « carbon » | REE |
| `fuel_gas_gwh` | GWh | Énergie journalière du bilan électrique : « fuel gas » | REE |
| `cogeneracion_gwh` | GWh | Énergie journalière du bilan électrique : « cogeneracion » | REE |
| `residuos_no_renovables_gwh` | GWh | Énergie journalière du bilan électrique : « residuos no renovables » | REE |
| `generacion_no_renovable_gwh` | GWh | Énergie journalière du bilan électrique : « generacion no renovable » | REE |
| `turbinacion_bombeo_gwh` | GWh | Énergie journalière du bilan électrique : « turbinacion bombeo » | REE |
| `consumo_bombeo_gwh` | GWh | Énergie journalière du bilan électrique : « consumo bombeo » | REE |
| `saldo_almacenamiento_gwh` | GWh | Énergie journalière du bilan électrique : « saldo almacenamiento » | REE |
| `enlace_peninsula_baleares_gwh` | GWh | Énergie journalière du bilan électrique : « enlace peninsula baleares » | REE |
| `saldo_i_internacionales_gwh` | GWh | Énergie journalière du bilan électrique : « saldo i internacionales » | REE |
| `demanda_en_b_c_gwh` | GWh | Énergie journalière du bilan électrique : « demanda en b c » | REE |
| `carga_bateria_gwh` | GWh | Énergie journalière du bilan électrique : « carga bateria » | REE |
| `entrega_bateria_gwh` | GWh | Énergie journalière du bilan électrique : « entrega bateria » | REE |
| `turbina_de_vapor_gwh` | GWh | Énergie journalière du bilan électrique : « turbina de vapor » | REE |
| `produccion_gwh` | GWh | Production photovoltaïque de la journée, système péninsulaire (copie de solar_fotovoltaica_gwh) | REE |
| `part_fotovoltaica_generacion_pct` | % | Part du photovoltaïque dans la production totale | REE, calculé |
| `part_renovable_generacion_pct` | % | Part des renouvelables dans la production totale | REE, calculé |
| `part_fotovoltaica_demanda_pct` | % | Part de la demande couverte par le photovoltaïque | REE, calculé |
| `jour_semaine` | - | Jour de la semaine (0 = lundi) | calendrier |
| `week_end` | 0/1 | 1 le samedi et le dimanche | calendrier |
| `mois` | - | Mois (1 à 12) | calendrier |
| `jds_sin` | - | sin(2π jour/365,25) | calendrier |
| `jds_cos` | - | cos(2π jour/365,25) | calendrier |
| `pvgis_pv_moyen_kwh_kwc` | kWh/kWc | Production PVGIS moyenne des 3 villes du pays le même jour (lien avec la météo, jusqu'en 2023) | PVGIS |
| `pvgis_ghi_moyen_kwh_m2` | kWh/m² | Irradiation horizontale PVGIS moyenne des 3 villes du pays le même jour | PVGIS |
| `nebulosite_moyenne_pays_pct` | % | Nébulosité moyenne des 3 villes du pays le même jour | Open-Meteo (ERA5) |
| `t2m_moyenne_pays_c` | °C | Température moyenne des 3 villes du pays le même jour | PVGIS (ERA5) |

## Transformations et précautions

- **PVGIS** : rayonnement estimé par satellite (base SARAH3) et non mesuré au sol ; température et vent issus de la réanalyse ERA5. La puissance P est simulée pour 1 kWc de modules au silicium cristallin, inclinés à la pente optimale du site et orientés plein sud, avec 14 % de pertes système (modèle de Huld et al., 2011, qui tient compte de la température des modules et des effets spectraux). Les heures dont le rayonnement a été reconstruit sont signalées (`heures_reconstruites`).
- **Trous de la base SARAH3** : certains jours, PVGIS renvoie un rayonnement nul pendant tout ou partie de la journée alors que le soleil est levé (images satellite manquantes). Deux contrôles les repèrent : la hauteur maximale du soleil fournie par PVGIS inférieure de plus de 5° à la hauteur astronomique à midi (les jours normaux, l'écart reste sous 3°), ou une irradiation PVGIS inférieure au quart de celles de NASA POWER et d'ERA5. Ces jours (11 à 13 par ville sur 6 939, surtout en 2008, 2009, 2014 et 2016) sont signalés (`jour_impute_pvgis` = 1) et remplacés : énergies par l'irradiation NASA POWER du jour multipliée par le rapport médian PVGIS/NASA des 31 jours voisins, autres grandeurs par interpolation linéaire.
- **Jour UTC** : PVGIS horodate en temps universel. À ces longitudes (-6° à +11°), le soleil ne se lève jamais avant minuit UTC ni ne se couche après : les sommes journalières d'énergie sont exactes.
- **Éclairement lumineux** : calculé à partir des composantes horizontales avec des efficacités lumineuses moyennes (100 lm/W pour le direct, 125 lm/W pour le diffus). C'est une approximation : l'efficacité réelle varie avec la hauteur du soleil et l'humidité (modèle de Perez et al., 1990).
- **Sources complémentaires** : les trous d'au plus 3 jours sont interpolés linéairement ; au-delà, la valeur reste manquante. Les trois sources d'irradiation (SARAH3, ERA5, NASA POWER) ne coïncident pas : leur écart mesure l'incertitude de la donnée elle-même.
- **Variables retardées** (`*_veille`, `*_passe`, `pv_j7`) : calculées uniquement sur le passé, elles sont manquantes les 7 premiers jours de chaque site.
- **RTE** : 22 champs du mix éCO2mix au pas de 30 min, agrégés par jour (énergie = puissance moyenne x 24 h). Données « définitives » puis « consolidées » (colonne `nature`). La production nationale croît avec le parc installé : elle n'est pas comparable d'une année à l'autre sans normalisation.
- **REE** : bilan électrique complet du système péninsulaire (hors Baléares et Canaries) ; certaines filières n'existent pas toutes les années (batteries), leurs colonnes sont alors vides.
- **Variables météo des séries nationales** : moyennes des 3 villes du pays, disponibles jusqu'en 2023 (fin de PVGIS) ; vides ensuite.
- **Horaire 2023** : les heures PVGIS (HH:10 UTC) sont ramenées à l'heure pleine pour la jointure avec la météo horaire ERA5 (HH:00 UTC). Température des modules par le modèle NOCT (approximation).
- **Année type (TMY)** : les mois proviennent d'années différentes (`annee_source`) ; la géométrie solaire est calculée pour une année de référence. La puissance « à plat » est une estimation simple, pas une sortie de PVGIS.
- **Scénarios d'orientation** : moyennes 2005-2023 calculées par l'outil PVcalc de PVGIS (pertes système 14 %), pour une inclinaison de 0 à 90° et une orientation de l'est à l'ouest.
- **Table de référence** `data/reference/pvgis_synthese_9_villes.csv` : pente optimale et productible par ville (9 lignes) ; utilisée par les notebooks, elle n'est pas comptée parmi les jeux de données.
