# Fiche de données — PVGIS

| Élément | Détail |
|---|---|
| Producteur | Commission européenne, Centre commun de recherche (JRC) |
| Version | PVGIS 5.3, base de rayonnement PVGIS-SARAH3, météo ERA5 |
| Accès | API publique `re.jrc.ec.europa.eu/api/v5_3` (outils `PVcalc` et `seriescalc`) |
| Licence | Réutilisation autorisée avec mention de la source |
| Période | 2005 à 2023 |
| Pas | Horaire, agrégé au jour (jour UTC) par le projet |
| Emplacement | `data/raw/pvgis/<ville>/` ; pour les 9 villes historiques, aussi `data/brut/pvgis/` |

## Contenu

- **`PVcalc`** : pente optimale du site et production annuelle moyenne d'1 kWc.
- **`seriescalc`**, une réponse par technologie (crystSi, CIS, CdTe) et par tranche d'années : puissance produite (W),
  éclairement sur le plan des modules (W/m²), hauteur du soleil, température à 2 m, vent à 10 m.
- **`seriescalc`** sur plan horizontal : éclairement global horizontal.

## Installation simulée

1 kWc, plein sud, pente optimale du site, 14 % de pertes système. Les trois technologies sont simulées avec la même
pente : elles se comparent à géométrie égale.

## Limites

- **Ce sont des simulations.** Le rayonnement est estimé par satellite, la production est calculée par un modèle. Aucune
  panne, aucun ombrage local, aucune salissure variable.
- **Trous de la base satellitaire.** Certains jours, l'image manque et PVGIS enregistre un rayonnement nul. Ces jours sont
  repérés et corrigés par le projet (colonne `jour_impute_pvgis`).
- **Technologies.** Les écarts entre technologies viennent des modèles de rendement de PVGIS (température, faible
  éclairement, spectre). La dégradation dans le temps n'est pas modélisée.
- **Révisions.** Les données d'une même version de base sont stables ; une nouvelle version de PVGIS peut les changer.
  L'empreinte SHA256 de chaque fichier est dans `data/manifest.yaml`.
