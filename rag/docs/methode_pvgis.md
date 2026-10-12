# PVGIS : d'où viennent les séries photovoltaïques et d'éclairement

## Qu'est-ce que PVGIS ?

PVGIS (Photovoltaic Geographical Information System) est un outil public et gratuit développé par le Centre commun de recherche (JRC) de la Commission européenne. Il estime le rayonnement solaire et la production d'une installation photovoltaïque pour n'importe quel point de l'Europe, de l'Afrique et d'une grande partie de l'Asie et des Amériques. C'est le lien « série temporelle » du rapport SolarVision (re.jrc.ec.europa.eu/pvg_tools). Le projet utilise la version 5.3 de son API, sans clé d'accès.

## Bases de données utilisées

- **Rayonnement : PVGIS-SARAH3.** Base satellitaire produite par EUMETSAT (CM SAF) à partir des images des satellites géostationnaires Meteosat, avec une résolution d'environ 5 km. Elle couvre 2005 à 2023 : c'est la raison pour laquelle les séries du projet commencent le 1er janvier 2005 et s'arrêtent le 31 décembre 2023.
- **Température de l'air à 2 m et vent à 10 m : réanalyse ERA5** du Centre européen de prévision météorologique à moyen terme (ECMWF).
- **Ombrage de l'horizon** : calculé à partir d'un modèle numérique de terrain.

Le rayonnement est donc **estimé par satellite et non mesuré au sol**. Les heures dont la valeur a été reconstruite par PVGIS (trous dans les images) sont signalées par l'indicateur `Int` ; dans le projet, elles sont comptées dans la variable `heures_reconstruites`.

## Modèle de production photovoltaïque

La puissance horaire P est simulée pour 1 kWc de modules au silicium cristallin. Le modèle (Huld et al., 2011) fait dépendre le rendement de l'éclairement reçu et de la température des modules, elle-même calculée à partir de la température de l'air, de l'éclairement et du vent. Il tient compte des pertes par réflexion selon l'angle d'incidence et des effets spectraux. Les pertes système (câbles, onduleur, salissures, vieillissement) sont fixées à 14 %, valeur par défaut de PVGIS.

Dans le projet, les modules sont orientés plein sud et inclinés à la pente optimale de chaque site, calculée par PVGIS : 33° pour Tunis, Sfax et Tozeur, 35° pour Séville, 37° pour Lyon et Madrid, 38° pour Paris et Barcelone, 39° pour Marseille.

## Grandeurs fournies et unités

- P : puissance de l'installation (W pour 1 kWc), moyenne horaire. La somme des 24 valeurs d'une journée divisée par 1 000 donne l'énergie journalière en kWh/kWc (variable `pv_kwh_kwc`).
- Gb(i), Gd(i), Gr(i) : éclairement énergétique direct, diffus et réfléchi sur le plan des modules (W/m²).
- Sur le plan horizontal (inclinaison 0°), Gb + Gd donne l'éclairement global horizontal (GHI). Sa somme journalière divisée par 1 000 est l'irradiation globale horizontale en kWh/m² (variable `ghi_kwh_m2`).
- H_sun : hauteur du soleil (degrés) ; T2m : température (°C) ; WS10m : vent (m/s).
- Horodatage en temps universel (UTC).

## Éclairement énergétique et éclairement lumineux

L'éclairement énergétique (irradiance) se mesure en W/m² ; l'irradiation est son cumul, en kWh/m². L'éclairement lumineux (illuminance), perçu par l'œil, se mesure en lux. Le projet convertit l'un en l'autre avec des efficacités lumineuses moyennes : 100 lumens par watt pour le rayonnement direct et 125 lm/W pour le diffus. Un ciel clair de midi en été donne environ 100 000 lux. Au-dessus de 10 000 lux à l'extérieur, la lumière du jour suffit à éclairer un local courant (facteur de lumière du jour d'environ 2 %) : c'est le seuil de la variable `heures_lumiere_10klux`, et `besoin_eclairage_h` compte les heures restantes où un éclairage artificiel peut être nécessaire.

## Synthèse annuelle (PVcalc)

L'outil PVcalc de PVGIS donne la production annuelle moyenne d'1 kWc (E_y, en kWh/kWc/an), l'irradiation annuelle sur le plan des modules (H(i)_y, en kWh/m²/an), la variabilité d'une année à l'autre (SD_y) et le détail des pertes. Ces valeurs sont dans la table de référence `data/reference/pvgis_synthese_9_villes.csv`. Le jeu `pvgis_orientations_9_villes.csv` donne la même chose pour 27 inclinaisons et orientations par ville (de la toiture plate à la façade verticale, de l'est à l'ouest).

## Limites à connaître

- Rayonnement satellitaire : l'erreur journalière par rapport à une mesure au sol est de l'ordre de quelques pour cent en moyenne, plus forte par ciel nuageux et dans les régions côtières.
- Installation théorique : pas de pannes, pas d'ombrage local, pas de salissure variable, puissance constante sur 19 ans. Une installation réelle produit moins certains jours et se dégrade avec l'âge.
- La production simulée est une fonction presque déterministe de l'éclairement et de la température : utiliser l'éclairement PVGIS du jour pour prévoir la production du jour serait tautologique. C'est pourquoi les modèles « ex post » du projet utilisent la nébulosité, la pluie, l'humidité et les aérosols (sources indépendantes), et non l'éclairement PVGIS.
