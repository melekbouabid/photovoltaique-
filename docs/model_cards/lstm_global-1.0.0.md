# Fiche du modèle lstm_global — version 1.0.0

Fiche générée automatiquement le 2026-10-11T17:44:25.

## Description

LSTM à une couche entraîné sur toutes les villes à la fois. Chaque ville est ramenée à sa propre normale saisonnière ; un vecteur appris par ville adapte la réponse au climat local. Intervalles conformes calibrés sur la dernière année de l'apprentissage.

## Usage prévu

Prévoir la production journalière d'une installation photovoltaïque de 1 kWc, de J+1 à J+7, pour les villes de l'étude.
Scénario **ex ante** : le modèle n'utilise aucune information postérieure à la date d'émission.

## Entraînement

| Élément | Valeur |
|---|---|
| fenetre_jours | 14 |
| taille_cachee | 64 |
| dropout | 0.1 |
| epoques_max | 30 |
| validation | dernière année de l'apprentissage, arrêt anticipé |
| mode | complet |
| Graine | 42 |
| Commit Git | `c6a14b72beb378607370f96ddc236b43bd0a462c` |
| Bibliothèques | python 3.14.2, numpy 2.3.5, pandas 2.3.3, torch 2.12.1, statsmodels 0.15.0, xgboost 3.1.3, prophet 1.5.0, scikit-learn 1.8.0 |

## Données

Voir `data/manifest.yaml` (empreinte `7ba85bbe60929d31…`).
Production simulée par PVGIS 5.3 à partir d'images satellitaires ; météo ERA5 ; contrôle par NASA POWER.

## Résultats sur l'échantillon de test

| Mesure | Valeur |
|---|---|
| Villes | 30 |
| Dates de test | 2022-02-06 / 2023-12-31 |
| RMSE moyen du modèle (kWh/kWc) | 1.1674 |
| RMSE moyen de la climatologie (kWh/kWc) | 1.1934 |
| Gain moyen sur la climatologie | 2.18 % |
| Villes où le modèle bat la climatologie | 30 sur 30 |

## Limites et risques

- **Données simulées.** La production vient d'une simulation, pas de mesures d'installations réelles : pannes, ombrages et salissures ne sont pas représentés.
- **Faible prévisibilité.** Au-delà de deux jours, la production suit surtout la saison : le gain sur la climatologie est faible et peut être nul.
- **Pas de météo à venir.** Le modèle ne connaît pas la prévision météo ; l'associer à une prévision météo réduirait nettement l'erreur.
- **Validité limitée aux villes et à la période de l'étude** (2005-2023). Une ville nouvelle demande un réentraînement.
- **Pas de réentraînement automatique.** Une dérive des données est signalée par le suivi, la décision de réentraîner reste humaine.
- **Intégrité.** L'empreinte SHA256 du fichier est vérifiée à chaque chargement : `76b63f879124ed64…`
