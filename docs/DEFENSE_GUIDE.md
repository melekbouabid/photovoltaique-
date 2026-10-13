# Guide de soutenance

Pour chaque choix du projet : l'explication en quelques lignes, où est le code, puis trois questions probables et
leur réponse. Les chiffres cités se relisent dans les fichiers indiqués ; revérifiez-les avant la soutenance.

## 1. Découpage chronologique 90/10

**En bref.** Les 90 % de jours les plus anciens servent à l'apprentissage, les 10 % les plus récents au test. La coupure
est à l'indice `int(n * 0.9)`. À Tunis : 6 245 jours d'apprentissage (jusqu'au 5 février 2022) et 694 jours de test.
Aucun tirage aléatoire, aucune validation croisée classique : dans une série temporelle, mélanger les dates revient à
donner au modèle une partie du futur.

**Où.** `src/solarvision/config.py` (`split_index`), `data/processed/splits_90_10.yaml`, `tests/leakage/`.

| Question | Réponse |
|---|---|
| Pourquoi pas un tirage aléatoire ? | Deux jours voisins se ressemblent. Tirés au hasard, l'un irait dans l'apprentissage et l'autre dans le test : le modèle « connaîtrait » déjà le test. L'erreur mesurée serait trop optimiste. |
| Comment prouvez-vous qu'il n'y a pas de fuite ? | Un test remplace toutes les observations à partir d'une date par une valeur absurde, recalcule les variables, et vérifie que les variables ex ante d'avant cette date n'ont pas changé. |
| 694 jours de test, est-ce assez ? | C'est près de deux années complètes, donc toutes les saisons deux fois. C'est une seule période : une limite, écrite dans le rapport. |

## 2. Ex ante et ex post

**En bref.** Un modèle *ex ante* n'utilise que ce qui est connu à la date d'émission : observations passées, calendrier,
astronomie, normale saisonnière. Un modèle *ex post* reçoit en plus la météo observée des jours visés. Seul le premier
mesure ce qu'on obtiendrait en exploitation. Le second est une borne optimiste : ce qu'apporterait une prévision météo parfaite.

**Où.** `src/solarvision/features/panel.py` (colonnes `expost_*`, `feature_roles`), colonne `scenario` de tous les tableaux.

| Question | Réponse |
|---|---|
| Pourquoi calculer un scénario ex post s'il n'est pas opérationnel ? | Pour savoir si la limite vient du modèle ou de l'information. Ex post, l'erreur baisse fortement : la limite est l'information sur la météo à venir, pas la classe de modèles. |
| Pourquoi exclure le rayonnement du scénario ex post ? | Le rayonnement PVGIS est l'entrée de la simulation de la production. Le donner au modèle reviendrait à lui donner la réponse. On garde nuages, pluie, humidité, température, aérosols. |
| Que donnerait une vraie prévision météo ? | Une erreur comprise entre l'ex ante et l'ex post. Pour le mesurer, il faudrait des prévisions météo archivées sur la période de test ; ce n'est pas fait. |

## 3. Imputation des trous de PVGIS

**En bref.** Certains jours, l'image satellitaire manque et PVGIS enregistre un rayonnement nul alors que le soleil est levé.
Un jour est corrigé si la hauteur du soleil donnée par PVGIS est inférieure de plus de 5° à la hauteur astronomique, ou si
l'irradiation PVGIS vaut moins du quart de celle de NASA POWER un jour clair. La valeur corrigée est l'irradiation NASA POWER
multipliée par le rapport médian PVGIS / NASA des 31 jours voisins. Le jour reste signalé (`jour_impute_pvgis`).

**Où.** `src/solarvision/data/process.py` (`impute_pvgis_gaps`), `configs/params.yaml` (seuils), `tests/data/`.

| Question | Réponse |
|---|---|
| Comment savez-vous que la règle est bonne ? | À Tunis, elle retrouve exactement les 13 dates de la première étude. Le test compare ces dates à l'ancien jeu de données, pas à la règle elle-même : ce n'est pas un test circulaire. Un second test efface un jour dont on connaît la vraie valeur et vérifie la correction. |
| Pourquoi ne pas supprimer ces jours ? | Les modèles ont besoin d'une série régulière, sans jour manquant. Et ces jours ne sont pas des journées sombres : ce sont des erreurs de données. |
| L'imputation change-t-elle les résultats ? | Non. Les modèles ont été réestimés sans ces jours puis évalués sur le même test : l'écart est dans `reports/sensitivity_imputed.csv`. Les jours imputés sont tous dans l'apprentissage. |

## 4. La normale saisonnière (climatologie)

**En bref.** C'est la moyenne de la production pour chaque jour de l'année, calculée sur l'apprentissage seul, puis lissée
par une moyenne mobile circulaire de 31 jours. C'est la référence à battre : un modèle qui ne fait pas mieux n'apporte rien.

**Où.** `src/solarvision/features/panel.py` (`climatology`), `reports/diagnostic_ecart_climatologie_tunis.csv`.

| Question | Réponse |
|---|---|
| Pourquoi lisser ? | Avec 17 années, la moyenne d'un jour donné repose sur 17 valeurs : elle est bruitée. À Tunis, sans lissage, le RMSE de la climatologie est de 1,1324 ; lissée, 1,1002. |
| Pourquoi 31 jours ? | Un mois lisse le bruit sans déformer le cycle annuel. Avec 15 jours, le RMSE est presque le même ; avec 7 jours, il remonte. Le tableau de diagnostic donne les valeurs. |
| La normale utilise-t-elle le test ? | Non. Un test falsifie les valeurs du test et vérifie que la normale ne change pas. |

## 5. Le modèle statistique : ARIMA(1,0,0) à termes de Fourier

**En bref.** Le cycle annuel est décrit par deux harmoniques de Fourier (sinus et cosinus). Ce qui reste, l'écart à la saison,
suit un AR(1) : l'écart d'un jour vaut une fraction de celui de la veille, plus un bruit. d = 0 parce que la série est
stationnaire autour de son cycle. La prévision à l'horizon h est le niveau saisonnier du jour visé, plus l'écart observé
multiplié par phi puissance h.

**Où.** `src/solarvision/models/statistical.py` ; identification complète dans `mini_projet_python.ipynb` et le notebook R.

| Question | Réponse |
|---|---|
| Comment avez-vous choisi les ordres ? | L'ACF de la série désaisonnalisée décroît dès le premier retard et la PACF se coupe après lui : signature d'un AR(1). Une grille d'ordres est ensuite classée par BIC, et `auto_arima` confirme. |
| Pourquoi pas une différenciation ? | L'ADF rejette la racine unitaire et le KPSS ne rejette pas la stationnarité. Différencier créerait une autocorrélation négative artificielle (sur-différenciation). |
| Pourquoi pas un SARIMA avec s = 365 ? | Une période de 365 rend l'estimation très lourde et instable. Les termes de Fourier décrivent la même saisonnalité avec quatre coefficients. Un SARIMA au sens strict (s = 12) est ajusté sur la série mensuelle. |

## 6. VAR, Granger, cointégration, GARCH (Tunis)

**En bref.** Le VAR relie production, nébulosité et température. Le test de Granger dit si le passé d'une série aide à prévoir
une autre. Le test de Johansen cherche une relation de long terme entre séries non stationnaires. Le GARCH modélise une
variance des erreurs qui change dans le temps.

**Où.** `mini_projet_python.ipynb`, notebook R, tableaux `resultats/py_*.csv` et `resultats/R_*.csv`.

| Question | Réponse |
|---|---|
| Granger prouve-t-il que les nuages causent la production ? | Non. Il prouve que le passé de la nébulosité aide à prévoir la production. Les trois séries décrivent le même état de l'atmosphère. |
| Pourquoi pas de VECM à Tunis ? | La cointégration concerne des séries non stationnaires. Ici le test de Johansen trouve un rang plein : le système est stationnaire, un VAR en niveaux suffit. Le VECM est estimé sur un cas réellement non stationnaire, les productions nationales française et espagnole. |
| Que montre le GARCH ? | La variance des erreurs est forte en hiver et faible en été. Un GARCH seul prend cette saison pour une persistance des chocs. En retirant d'abord la variance saisonnière, l'effet ARCH disparaît. |

## 7. Évaluation glissante et réajustement tous les 30 jours

**En bref.** Depuis chaque jour du test (688 origines), chaque modèle prévoit J+1 à J+7. **Chaque origine est évaluée.**
Les paramètres, eux, ne sont réestimés que tous les 30 jours : entre deux réajustements, le modèle garde ses coefficients
mais utilise les observations les plus récentes.

**Où.** `src/solarvision/models/protocol.py`, `reports/forecasts/<ville>.parquet`.

| Question | Réponse |
|---|---|
| Pourquoi ne pas réajuster chaque jour ? | Le coût serait trente fois plus élevé pour un gain négligeable : avec 17 ans d'historique, un jour de plus ne change presque pas les coefficients. |
| Pourquoi 688 origines et pas 694 ? | Il faut sept jours après l'origine pour mesurer l'erreur à J+7. Les sept derniers jours du test ne peuvent donc pas être des origines complètes. |
| Pourquoi enregistrer toutes les prévisions ? | Pour recalculer métriques et tests sans réentraîner, et pour que chaque chiffre du rapport puisse être revérifié. |

## 8. Diebold-Mariano et correction de Holm

**En bref.** Le test de Diebold-Mariano dit si l'écart d'erreur entre deux modèles est significatif. Hypothèse nulle : même
perte moyenne. À l'horizon h, les erreurs se chevauchent : la variance est donc calculée sur h - 1 retards, avec la
correction de Harvey-Leybourne-Newbold pour les petits échantillons. Comme plusieurs modèles sont comparés à la
climatologie, les p-values sont corrigées par la méthode de Holm.

**Où.** `src/solarvision/evaluation/significance.py`, `tests/unit/test_evaluation.py`, `reports/dm_tests.csv`.

| Question | Réponse |
|---|---|
| Qu'est-ce que la famille de Holm ? | Tous les modèles comparés à la climatologie pour une ville, une technologie, un horizon et une fonction de perte. Sa taille est écrite dans le tableau (`taille_famille`). |
| Le test est-il unilatéral ou bilatéral ? | Les deux sont calculés. Le rapport utilise le test unilatéral : l'alternative est que le modèle fait mieux que la climatologie. |
| Comment savez-vous que votre implémentation est juste ? | Un test compare ses résultats à ceux de `forecast::dm.test` en R, sur un jeu d'erreurs autocorrélées, pour trois horizons et deux pertes. À l'horizon 1, il retombe sur un test de Student. |

## 9. Réseaux récurrents et validation glissante

**En bref.** LSTM et GRU reçoivent les 14 derniers jours et prévoient les sept suivants. La cible est l'écart à la normale :
le réseau part de la climatologie et n'apprend que la correction. Les hyperparamètres sont choisis par validation glissante
(trois plis à fenêtre croissante), jamais par validation croisée aléatoire. Un LSTM global est entraîné sur toutes les villes.

**Où.** `src/solarvision/models/deep.py`, `reports/deep/`.

| Question | Réponse |
|---|---|
| Pourquoi une fenêtre de 14 jours ? | La météo ne persiste qu'un à deux jours. La validation glissante ne distingue pas 7, 14 et 28 jours : on garde une valeur moyenne, simple. |
| Pourquoi les réseaux ne font-ils pas beaucoup mieux ? | Sans météo à venir, il reste très peu de structure à apprendre. Les courbes de perte le montrent : ex ante, la validation cesse de progresser en quelques époques. |
| Comment évitez-vous le surapprentissage ? | Un petit réseau (une couche, 64 unités), un dropout, et un arrêt anticipé sur la dernière année de l'apprentissage. |

## 10. Intervalles de prévision

**En bref.** Deux méthodes. Pour l'AR(1), un intervalle analytique : plus ou moins 1,96 fois l'écart-type de l'erreur à l'horizon h.
Pour le LSTM global, un intervalle conforme : la marge est le quantile à 95 % des erreurs absolues sur l'année de validation.
La couverture réelle est ensuite mesurée sur le test.

**Où.** `src/solarvision/models/statistical.py`, `src/solarvision/models/deep.py` (`run_global`), `reports/coverage.csv`.

| Question | Réponse |
|---|---|
| Quelle différence entre les deux ? | L'intervalle analytique suppose des erreurs gaussiennes de variance constante, ce que le diagnostic contredit. L'intervalle conforme ne suppose aucune loi. |
| Une couverture de 95 % suffit-elle ? | Non. Elle peut être correcte en moyenne et fausse par saison : trop étroite en hiver, trop large en été. |
| Limite de l'intervalle conforme ? | Sa marge est la même toute l'année. Une marge par saison serait plus juste. |

## 11. Score de fiabilité des technologies

**En bref.** Pour chaque ville et chaque technologie, cinq critères sont calculés : erreur de prévision, variabilité, sensibilité
à la température, comportement par faible irradiation, production annuelle. Chacun est ramené entre 0 et 1 parmi les villes du
même pays, puis pondéré. L'incertitude vient d'un rééchantillonnage d'années entières. Si l'écart entre les deux premières
technologies tient dans la marge, elles sont déclarées ex æquo.

**Où.** `configs/reliability.yaml`, `src/solarvision/recommender/`, `reports/tech_recommendation.csv`.

| Question | Réponse |
|---|---|
| Les poids ne sont-ils pas arbitraires ? | Ils sont un choix, écrit dans la configuration. Leur influence est mesurée : on les fait varier et on compte combien de fois la technologie recommandée reste première. Le front de Pareto donne en plus un résultat sans aucun poids. |
| Pourquoi rééchantillonner des années et pas des jours ? | Les jours sont autocorrélés et saisonniers. Tirer des années entières garde la saison intacte. |
| Peut-on se fier à ces écarts ? | Avec prudence. PVGIS simule les technologies ; les écarts viennent de ses modèles de rendement. Ni la dégradation ni la fiabilité mécanique ne sont modélisées. |

## 12. Économie

**En bref.** Pour chaque ville et chaque technologie : économie sur la facture, revenu du surplus, temps de retour, valeur
actuelle nette, taux de rentabilité interne, coût actualisé de l'énergie, CO2 évité. Chaque hypothèse a une valeur basse,
centrale et haute ; une simulation de Monte-Carlo en tire 5 000 combinaisons et donne P10, P50 et P90.

**Où.** `configs/economics.yaml`, `src/solarvision/economics/`, `tests/unit/test_economics.py`.

| Question | Réponse |
|---|---|
| D'où viennent les prix ? | Ce sont des ordres de grandeur, tous marqués `TODO_VERIFY` avec la source à consulter. Ils ne sont pas vérifiés : c'est écrit dans le rapport et dans l'application. |
| Qu'est-ce que la valeur actuelle nette ? | La somme des gains futurs, chacun divisé par (1 + taux) puissance le nombre d'années, moins l'investissement. Positive : l'installation rapporte plus qu'elle ne coûte. |
| Comment avez-vous vérifié les formules ? | Par des cas calculés à la main : une annuité pour la VAN, un investissement divisé par un flux constant pour le temps de retour, un coût total divisé par une énergie totale pour le LCOE. |

## 13. Architecture et MLOps

**En bref.** Un paquet Python, une commande par étape, la configuration hors du code. Le cache brut n'est jamais réécrit.
Les modèles sont versionnés dans un registre ; un modèle n'est promu que s'il bat la climatologie et la version en place sur
les mêmes dates de test. L'empreinte du fichier est vérifiée à chaque chargement.

**Où.** `docs/architecture.md`, `src/solarvision/mlops/`, `src/solarvision/serving/`, `src/solarvision/monitoring/`.

| Question | Réponse |
|---|---|
| Pourquoi une règle de promotion codée ? | Pour qu'un modèle moins bon ne passe jamais en production par inadvertance. Un test vérifie les refus : modèle qui ne bat pas la climatologie, qui ne bat pas la version en place, ou évalué sur d'autres dates. |
| Qu'est-ce qui n'est pas fait ? | Tout est local. DVC n'est pas installé, donc `dvc repro` n'a pas tourné. L'image Docker de la v2 n'est pas construite et la chaîne d'intégration n'a pas tourné. Il n'y a pas de réentraînement automatique. |
| Comment détectez-vous une dérive ? | Par l'indice de stabilité de population et le test de Kolmogorov-Smirnov, sur l'écart à la moyenne du même mois, et par l'erreur sur 30 jours glissants rapportée à celle de la climatologie. |

## 14. Collecte et quotas

**En bref.** Chaque réponse d'API est mise en cache, écrite d'abord dans un fichier `.part` puis renommée. Un fichier présent
n'est jamais retéléchargé. Un quota dépassé arrête la source proprement et note l'heure de reprise dans `data/failures.json`.
Une ville incomplète est listée comme manquante ; elle n'est jamais simulée.

**Où.** `src/solarvision/data/ingest.py`, `data/failures.json`, `data/manifest.yaml`.

| Question | Réponse |
|---|---|
| Que s'est-il passé avec Open-Meteo ? | Une requête de 19 ans pèse lourd dans le quota gratuit : la limite horaire a été atteinte après une dizaine de villes. Le code s'est arrêté, a noté l'heure de reprise, et `--retry-failed` a repris plus tard. |
| Pourquoi un fichier `.part` ? | Si le téléchargement est coupé, il ne reste qu'un fichier `.part`, ignoré. Un fichier final présent est donc toujours complet. |
| Comment reconstruire les données ? | `python -m solarvision.cli ingest` télécharge ce qui manque ; `--reprocess` reconstruit les tables depuis le cache, sans réseau. |
