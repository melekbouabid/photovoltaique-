---
title: "Rapport détaillé — SolarVision"
subtitle: "Prévision de la production photovoltaïque journalière"
date: "12 octobre 2026"
lang: fr
---

# Résumé exécutif

SolarVision est une chaîne reproductible de prévision de production photovoltaïque journalière. Elle couvre 30 villes
de France, d'Espagne et de Tunisie, trois technologies de modules photovoltaïques et les horizons J+1 à J+7. Le projet
combine une étude statistique en R, une implémentation Python, une application web/API, un registre de modèles et un
suivi de dérive.

Le meilleur modèle opérationnel **ex ante** est le LSTM global version 1.0.0. Il est entraîné sur les 30 villes à la
fois, obtient un RMSE moyen de **1,1674 kWh/kWc**, contre **1,1934** pour la climatologie, soit un gain moyen de **2,18 %**.
Ce gain est surtout visible à J+1 et devient presque nul à J+7. Lorsque la météo observée des jours prévus est fournie
dans le scénario **ex post**, l'erreur descend fortement ; cette comparaison est une borne optimiste et ne représente
pas une prévision opérationnelle.

La conclusion principale est que la limite actuelle vient moins du choix entre LSTM, GRU, XGBoost ou ARIMA que de
l'information disponible sur la météo future. Le système est reproductible et semi-automatisé, mais le réentraînement,
la validation finale et la promotion d'un modèle restent contrôlés par un opérateur.

# 1. Objectifs et questions

Le projet répond à quatre questions :

1. Peut-on prévoir la production d'une installation de 1 kWc de J+1 à J+7 ?
2. Les modèles apprennent-ils quelque chose de plus utile qu'une normale saisonnière ?
3. Le choix de la technologie photovoltaïque dépend-il de la ville et du climat ?
4. Quelle est la valeur économique de la prévision et de l'incertitude ?

Le périmètre v2 porte sur la période 2005-2023, 30 villes et les technologies `crystSi`, `CIS` et `CdTe`. L'étude
historique v1 sur neuf villes, notamment Tunis, est conservée pour les diagnostics classiques détaillés et la
reproductibilité R.

# 2. Données et hypothèses

## 2.1 Sources

Les données principales sont :

- **PVGIS 5.3/JRC** : production simulée d'une installation de 1 kWc, rayonnement, température et vent ;
- **Open-Meteo/ERA5** : nébulosité, pluie, humidité, pression et rafales ;
- **NASA POWER** : rayonnement de contrôle, indice de clarté et aérosols.

La production PVGIS est une simulation basée notamment sur des données satellitaires et ERA5. Elle ne représente donc
pas une mesure réelle avec pannes, ombrages, salissures ou indisponibilité de l'installation.

Les hypothèses communes sont :

- puissance crête : 1 kWc ;
- orientation : plein sud ;
- pertes système : 14 % ;
- période : 1er janvier 2005 au 31 décembre 2023 ;
- graine aléatoire : 42 ;
- horizons : 1 à 7 jours.

## 2.2 Villes et volumes

L'étude comprend 10 villes par pays, soit 30 villes au total. Chaque ville contient 6 939 jours. Le panel de
modélisation compte 208 170 lignes et 61 colonnes.

Le découpage est chronologique :

- apprentissage : 6 245 jours, jusqu'au 5 février 2022 ;
- test : 694 jours, du 6 février 2022 au 31 décembre 2023 ;
- fraction d'apprentissage : 90 % ;
- fraction de test : 10 %.

Un découpage aléatoire est volontairement interdit : il mélangerait passé et futur et produirait une erreur
artificiellement optimiste.

## 2.3 Qualité et imputation

Les contrôles vérifient les dates, les valeurs, les coordonnées, les sources et la cohérence entre PVGIS et les sources
indépendantes. Certains jours PVGIS contiennent un rayonnement nul alors que les indicateurs astronomiques et NASA
POWER montrent une journée ensoleillée. Ces jours sont corrigés avec une règle documentée basée sur :

1. l'écart de hauteur solaire ;
2. le rapport PVGIS/NASA POWER ;
3. une fenêtre médiane de 31 jours ;
4. un contrôle ERA5 quand il est disponible.

Les jours corrigés restent signalés par `jour_impute_pvgis`. À Tunis, les 13 dates identifiées sont cohérentes avec
l'étude historique. Une analyse de sensibilité montre que leur effet sur le RMSE est au plus de 0,002 kWh/kWc.

# 3. Construction des variables et prévention des fuites

Les variables comprennent les retards de production, les fenêtres glissantes, la normale saisonnière, les termes de
Fourier, le calendrier et les variables météorologiques autorisées.

La climatologie est calculée sur l'apprentissage uniquement puis lissée par une moyenne mobile circulaire de 31 jours.
Elle constitue la référence minimale qu'un modèle doit battre.

Deux scénarios sont séparés :

- **ex ante** : uniquement les informations disponibles à la date de prévision ;
- **ex post** : météo observée des jours visés, utilisée uniquement comme borne de comparaison.

Les variables de rayonnement sont exclues du scénario ex post : le rayonnement PVGIS est directement lié à la
simulation de la production et le fournir reviendrait à donner la réponse au modèle.

Un test anti-fuite remplace les valeurs futures par des valeurs absurdes et vérifie que les variables ex ante calculées
avant la coupure ne changent pas.

# 4. Modèles étudiés

## 4.1 Références

La **persistance** reprend la dernière observation. Elle est simple mais ignore la saisonnalité et le caractère
irrégulier de la météo.

La **climatologie** prévoit la normale saisonnière du jour de l'année. Elle est plus robuste que la persistance et
constitue la référence principale.

## 4.2 ARIMA-Fourier

Le cycle annuel quotidien est décrit par deux harmoniques de Fourier, soit quatre coefficients sinus/cosinus. L'écart
à la saison est modélisé par un AR(1), équivalent à une structure ARIMA(1,0,0) autour d'une régression harmonique.

Cette approche est préférée à un SARIMA de période 365, qui serait plus lourd et moins stable. Les tests ADF et KPSS
justifient l'absence de différenciation. Le BIC retient la configuration ARIMA(1,0,0) avec deux harmoniques.

Résultat du modèle enregistré :

- RMSE moyen : 1,1777 kWh/kWc ;
- gain contre la climatologie : 1,32 % ;
- villes gagnées : 30/30.

Les résidus n'ont plus d'autocorrélation importante au test de Ljung-Box, mais ils ne sont pas gaussiens et présentent
une variance conditionnelle.

## 4.3 SARIMA et SARIMAX

Le SARIMA est utilisé principalement sur la série mensuelle, avec une saisonnalité de période 12. Le SARIMAX ajoute
des variables météo explicatives. Dans l'étude historique, le SARIMAX avec météo observée obtient une erreur très
faible, mais il s'agit d'un résultat ex post et non d'une performance directement exploitable en temps réel.

## 4.4 VAR, Granger et cointégration

Le VAR relie la production, la nébulosité et la température. Le critère d'information retient trois retards. Le test
de Granger montre notamment que la nébulosité améliore fortement la prévision de la production ; ce résultat signifie
une prévisibilité temporelle, pas une preuve de causalité physique.

Le test de Johansen trouve un rang plein pour le système de Tunis : un VECM n'est donc pas nécessaire pour ce cas
stationnaire. Le VECM est conservé comme vérification sur un autre système non stationnaire.

## 4.5 XGBoost

XGBoost utilise les retards, le calendrier, la normale et les variables météorologiques autorisées. Il modélise des
relations non linéaires. Il est compétitif ex ante et devient le meilleur modèle dans l'expérience ex post, où il
reçoit la météo observée.

## 4.6 Prophet

Prophet modélise principalement une tendance et une saisonnalité annuelle. Dans la configuration du projet, la
saisonnalité annuelle est activée et les composantes hebdomadaire et quotidienne sont désactivées. Il fournit une
prévision centrale et un intervalle, mais n'exploite pas directement les dernières observations météo futures.

## 4.7 LSTM et GRU

Les réseaux reçoivent une fenêtre de 14 jours et prévoient directement les sept jours suivants. Ils apprennent
l'écart à la normale plutôt que le niveau brut. La configuration principale est :

- 64 unités cachées ;
- dropout 0,1 ;
- maximum 30 époques ;
- arrêt anticipé ;
- Adam et erreur quadratique ;
- validation glissante sur trois fenêtres ;
- normalisation calculée sur l'apprentissage.

Le LSTM possède une mémoire cellulaire et trois mécanismes de porte. Le GRU utilise une structure plus simple avec deux
portes et moins de paramètres. Dans les résultats ex ante, ils sont très proches. Le LSTM global est retenu car un seul
réseau entraîné sur toutes les villes obtient la meilleure performance moyenne.

# 5. Résultats de prévision

Les résultats ci-dessous sont des moyennes sur les 30 villes pour `crystSi`.

| Modèle | Scénario | RMSE | MAE | WAPE | RMSE J+1 | RMSE J+7 |
|---|---|---:|---:|---:|---:|---:|
| LSTM global | ex ante | 1,1674 | 0,9097 | 22,3 % | 1,078 | 1,191 |
| GRU | ex ante | 1,1695 | 0,9100 | 22,3 % | 1,084 | 1,192 |
| LSTM individuel | ex ante | 1,1696 | 0,9116 | 22,3 % | 1,085 | 1,194 |
| XGBoost | ex ante | 1,1753 | 0,9150 | 22,4 % | 1,076 | 1,200 |
| AR(1)+Fourier | ex ante | 1,1777 | 0,9217 | 22,6 % | 1,113 | 1,191 |
| Climatologie | ex ante | 1,1934 | 0,9390 | 23,0 % | 1,194 | 1,193 |
| Prophet | ex ante | 1,1952 | 0,9341 | 22,9 % | 1,195 | 1,195 |
| Persistance | ex ante | 1,5617 | 1,0926 | 26,8 % | 1,350 | 1,617 |
| XGBoost + météo | ex post | 0,6274 | 0,4375 | 10,7 % | 0,621 | 0,629 |
| GRU + météo | ex post | 0,7062 | 0,5368 | 13,0 % | 0,699 | 0,718 |
| LSTM + météo | ex post | 0,7127 | 0,5425 | 13,1 % | 0,707 | 0,715 |

Le gain ex ante du LSTM global est réel mais modéré. À J+1, plusieurs modèles battent significativement la
climatologie dans la majorité des villes ; à J+7, ce gain devient faible ou inexistant. Le MAPE est à interpréter avec
prudence lorsque la production réelle est proche de zéro ; le WAPE est plus représentatif.

# 6. Incertitude et volatilité

Le test ARCH-LM est très significatif sur les résidus de l'étude classique : la variance change dans le temps.
ARCH et GARCH modélisent cette variance, pas le niveau moyen de production. L'EGARCH permet d'ajouter une réponse
asymétrique aux chocs et une variance logarithmique. La loi de Student représente mieux les queues épaisses et les
valeurs extrêmes que la loi normale.

Dans la v2, le LSTM global fournit également un intervalle conforme calibré sur les erreurs de validation. Les intervalles
doivent être contrôlés sur des données futures, car la couverture peut se dégrader en cas de dérive ou de changement
climatique.

L'AIC et le BIC servent à comparer des modèles ajustés sur les mêmes données :

`AIC = -2 log(L) + 2k`

`BIC = -2 log(L) + k log(n)`

Le BIC pénalise davantage la complexité et a été utilisé pour sélectionner la structure ARIMA-Fourier et les
spécifications de volatilité. Ni l'AIC ni le BIC ne remplacent l'évaluation sur une période de test.

# 7. Technologies photovoltaïques et économie

Les technologies `crystSi`, `CIS` et `CdTe` sont comparées selon cinq critères :

1. erreur de prévision rapportée à la production ;
2. variabilité journalière, mensuelle et interannuelle ;
3. sensibilité aux températures élevées ;
4. performance relative sous faible irradiation ;
5. production annuelle moyenne.

Les critères sont normalisés et pondérés. Le choix est fait ville par ville, avec une estimation de l'incertitude par
rééchantillonnage des années et une analyse de sensibilité aux poids. Le CIS est recommandé dans 9 villes françaises
sur 10 ; le CdTe dans 9 villes tunisiennes et 8 villes espagnoles sur 10. Cinq villes sont ex aequo.

L'analyse économique utilise la production simulée, la VAN, le temps de retour, le LCOE, le CO2 évité et une
simulation Monte-Carlo des prix et pénalités. Les hypothèses économiques restent marquées `TODO_VERIFY` et doivent
être confirmées avant toute décision réelle. Le silicium cristallin a la VAN médiane la plus élevée dans tous les pays,
mais l'écart n'est statistiquement concluant que dans une ville sur 30.

# 8. Architecture logicielle et MLOps

Le code Python est organisé dans le paquet `src/solarvision/`. Le flux principal est :

```text
ingest -> qualité/imputation -> features -> train -> evaluate
       -> recommend -> economics -> register -> serve -> monitor
```

Les sorties sont séparées en cache brut, tables intermédiaires, tables traitées, rapports, modèles et journaux.
La configuration est dans `configs/` et les fichiers bruts ne sont jamais réécrits.

Les contrôles MLOps comprennent :

- contrats de données ;
- tests anti-fuite ;
- graine reproductible ;
- suivi des expériences ;
- fiches de modèles ;
- empreintes SHA256 ;
- registre et promotion conditionnelle ;
- retour arrière ;
- suivi de dérive ;
- journalisation des requêtes de l'API.

Le registre contient notamment AR(1)+Fourier 1.0.0 et LSTM global 1.0.0. Le LSTM global est le modèle en production.
La règle de promotion exige qu'un candidat batte la climatologie et le modèle en place sur les mêmes dates de test.

# 9. Application et exécution

Le projet propose une API FastAPI versionnée `/v1` et une application multi-pages. Les principales commandes sont :

```text
python -m solarvision.cli pipeline --fast
python -m solarvision.cli ingest
python -m solarvision.cli features
python -m solarvision.cli train
python -m solarvision.cli evaluate
python -m solarvision.cli register
python -m solarvision.cli serve
python -m pytest -m "not data and not slow"
```

L'option `--fast` utilise Paris, Tunis et Madrid pour les essais et l'intégration continue. Le dépôt contient également
un Dockerfile, un compose, un pipeline DVC et une configuration d'intégration continue.

Le dossier `r_standalone/` est autonome. Il exécute l'analyse classique de Tunis avec :

```text
Rscript run_all.R
```

Il produit les diagnostics ADF/KPSS, ARIMA, SARIMA, VAR/VECM, Granger, GARCH, prévisions et métriques dans `outputs/`.

# 10. Automatisation actuelle et cible

Le projet est **semi-automatisé** :

- les données peuvent être collectées et retraitées par commande ;
- les modèles peuvent être entraînés et évalués par pipeline ;
- les rapports, métriques, registres et prévisions sont produits par le code ;
- l'API peut servir le modèle enregistré.

Ne sont pas encore entièrement automatisés :

- la planification périodique de bout en bout ;
- le réentraînement déclenché automatiquement par la dérive ;
- l'envoi d'alertes ;
- l'exécution réelle de DVC, Docker v2 et de la CI sur la machine de développement ;
- l'approbation finale d'un nouveau modèle.

Une automatisation de production devrait collecter les données, vérifier les contrats, produire les prévisions, comparer
les erreurs sur une fenêtre glissante, réentraîner selon une fréquence contrôlée, promouvoir uniquement un modèle
meilleur, puis conserver un rollback et notifier les anomalies.

# 11. Limites et risques

1. **Production simulée** : la validation sur des mesures réelles reste nécessaire.
2. **Météo future absente** : les résultats ex ante sont proches de la climatologie à long horizon.
3. **Ex post non opérationnel** : les scores avec météo observée ne doivent pas être présentés comme une prévision réelle.
4. **Généralisation** : une ville nouvelle ou une autre période nécessite une validation et éventuellement un réentraînement.
5. **Hypothèses économiques** : les tarifs, coûts, pénalités et taux doivent être vérifiés.
6. **Dérive** : le suivi signale les changements, mais aucune action automatique n'est encore déclenchée.
7. **Dépendances externes** : les quotas des API météo peuvent interrompre une collecte et nécessitent une reprise.
8. **Deux générations de code** : la v1 historique et la v2 coexistent ; leurs métriques ne doivent pas être mélangées.

# 12. Conclusion

SolarVision démontre une démarche complète de séries temporelles appliquée à l'énergie : qualité des données,
diagnostics statistiques, modèles classiques, apprentissage automatique, réseaux récurrents, incertitude, comparaison
de technologies, économie, API et pratiques MLOps.

Le résultat le plus important n'est pas seulement le classement des modèles. Il montre que la saisonnalité fournit déjà
une référence forte, que le LSTM global apporte un gain moyen limité mais reproductible, et que l'information météo
future est le principal levier d'amélioration. La prochaine évolution prioritaire est donc d'intégrer des prévisions
météorologiques archivées ou opérationnelles, de valider sur des productions mesurées et de mettre en place un
réentraînement surveillé plutôt qu'un réentraînement aveugle.

## Références internes

- `README.md` : démarrage rapide et carte du dépôt ;
- `docs/architecture.md` : architecture et commandes ;
- `reports/rapport/rapport_v2.md` : rapport v2 détaillé avec figures ;
- `docs/PROGRESS.md` : avancement, résultats et limites ;
- `docs/DEFENSE_GUIDE.md` : justification des choix ;
- `r_standalone/README.md` : analyse R autonome ;
- `docs/model_cards/` : fiches des modèles enregistrés.
