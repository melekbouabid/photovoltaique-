# Prompt 2 — Explication pour un décideur

Tu t'adresses au responsable d'un parc de toitures solaires, qui n'est pas statisticien.
En 200 mots au plus, explique-lui ce que disent les résultats ci-dessous : peut-il se fier à une prévision à 7 jours,
et que gagnerait-il à disposer d'une prévision météo ?
N'invente aucun chiffre : n'utilise que ceux qui te sont donnés.

Série : production journalière d'une installation photovoltaïque de 1 kWc à Tunis (silicium cristallin, plein sud, pente
optimale), simulée par PVGIS, de 2005 à 2023. Les statistiques sont
calculées sur l'échantillon d'apprentissage.

## Statistiques descriptives

| Statistique | Valeur |
|---|---|
| Nombre de jours (apprentissage) | 6 245 |
| Moyenne (kWh/kWc par jour) | 4,295 |
| Variance | 1,965 |
| Écart-type | 1,402 |
| Minimum | 0,211 |
| Maximum | 6,427 |
| Skewness | -0,815 |
| Kurtosis (excès) | -0,278 |
| Mois le plus bas (décembre) | 3,06 |
| Mois le plus haut (juillet) | 5,43 |
| Part de la variance portée par la normale saisonnière (%) | 34,2 |
| Autocorrélation à 1 jour de l'écart à la normale | 0,258 |
| Autocorrélation à 2 jours | 0,071 |
| Autocorrélation à 7 jours | -0,020 |

## Tests de stationnarité

ADF : hypothèse nulle = racine unitaire. KPSS : hypothèse nulle = stationnarité. La p-value du KPSS est bornée entre 0,01 et 0,10.

| Série | ADF (stat) | ADF (p) | KPSS (stat) | KPSS (p) |
|---|---|---|---|---|
| production brute | -5,84 | 0,0000 | 0,027 | 0,100 |
| écart à la normale saisonnière | -34,87 | 0,0000 | 0,395 | 0,079 |

## Erreurs de prévision sur l'échantillon de test (J+1 à J+7, kWh/kWc)

« Ex ante » : le modèle ne connaît rien du futur. « Ex post » : il reçoit la météo observée des jours visés.

| Modèle | Scénario | RMSE | MAE | WAPE (%) | RMSE à J+1 | RMSE à J+7 |
|---|---|---|---|---|---|---|
| LSTM global | ex ante | 1,0776 | 0,8279 | 18,5 | 0,988 | 1,099 |
| LSTM | ex ante | 1,0831 | 0,8376 | 18,7 | 0,991 | 1,104 |
| XGBoost | ex ante | 1,0861 | 0,8373 | 18,7 | 0,992 | 1,108 |
| AR(1) + Fourier | ex ante | 1,0884 | 0,8387 | 18,7 | 1,030 | 1,098 |
| GRU | ex ante | 1,0913 | 0,8362 | 18,7 | 1,000 | 1,111 |
| Climatologie | ex ante | 1,1002 | 0,8558 | 19,1 | 1,102 | 1,097 |
| Prophet | ex ante | 1,1009 | 0,8364 | 18,7 | 1,102 | 1,098 |
| Persistance | ex ante | 1,4335 | 0,9841 | 22,0 | 1,236 | 1,466 |
| XGBoost + météo | ex post | 0,5994 | 0,4090 | 9,1 | 0,591 | 0,601 |
| GRU + météo | ex post | 0,6453 | 0,4850 | 10,8 | 0,647 | 0,665 |
| LSTM + météo | ex post | 0,6547 | 0,4931 | 11,0 | 0,663 | 0,656 |
