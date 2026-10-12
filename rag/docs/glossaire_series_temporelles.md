# Glossaire des séries temporelles utilisées dans le projet

## Stationnarité
Une série est stationnaire si sa moyenne, sa variance et ses autocorrélations ne dépendent pas du temps. La plupart des modèles classiques (ARMA, VAR) la supposent. La production photovoltaïque journalière n'est pas stationnaire au sens strict à cause du cycle annuel, mais elle l'est autour de ce cycle : on parle de saisonnalité déterministe, que l'on retire par des termes de Fourier plutôt que par différenciation.

## Test ADF (Dickey-Fuller augmenté)
Test de racine unitaire. Hypothèse nulle : la série possède une racine unitaire (elle n'est pas stationnaire, comme une marche aléatoire). Une p-value inférieure à 0,05 conduit à rejeter la racine unitaire.

## Test KPSS
Test de stationnarité de Kwiatkowski, Phillips, Schmidt et Shin. Son hypothèse nulle est l'inverse de celle de l'ADF : la série est stationnaire. On utilise les deux tests ensemble : ils ne concluent que s'ils racontent la même histoire. ADF qui rejette et KPSS qui rejette aussi signalent souvent une saisonnalité ou une rupture non prise en compte.

## ACF et PACF
La fonction d'autocorrélation (ACF) mesure la corrélation entre la série et elle-même décalée de k pas. La fonction d'autocorrélation partielle (PACF) mesure cette corrélation une fois retirés les effets des retards intermédiaires. Une PACF qui se coupe après p retards suggère un AR(p) ; une ACF qui se coupe après q retards suggère un MA(q).

## ARIMA et SARIMA
ARIMA(p, d, q) : modèle autorégressif (p retards de la série), intégré (d différenciations) et à moyenne mobile (q retards des erreurs). SARIMA(p, d, q)(P, D, Q)[s] ajoute une partie saisonnière de période s. Pour une série journalière à cycle annuel (s = 365), le SARIMA est impraticable ; on utilise la régression harmonique dynamique : un ARIMA dont le cycle annuel est porté par des termes de Fourier (sinus et cosinus de période 365,25 jours). Le SARIMA saisonnier est utilisé sur la série mensuelle (s = 12).

## SARIMAX
SARIMA avec variables exogènes (X) : ici la nébulosité, la pluie, l'humidité, l'amplitude thermique et les aérosols. Utilisé « ex post » : on lui fournit la météo réellement observée des jours à prévoir, ce qui équivaut à une prévision météo parfaite.

## Critères AIC et BIC
Critères d'information qui arbitrent entre la qualité d'ajustement et le nombre de paramètres. Plus ils sont petits, mieux c'est. Le BIC pénalise davantage la complexité que l'AIC et choisit des modèles plus simples. On ne compare que des modèles estimés sur les mêmes données avec la même différenciation.

## Diagnostic des résidus
Un modèle bien spécifié laisse des résidus qui ressemblent à un bruit blanc. Test de Ljung-Box : absence d'autocorrélation (hypothèse nulle). Test de Jarque-Bera ou de Shapiro-Wilk : normalité. Test ARCH-LM d'Engle : variance constante dans le temps (homoscédasticité conditionnelle).

## VAR (vecteur autorégressif)
Modèle où chaque variable dépend de ses propres retards et de ceux des autres variables. Dans le projet : production, nébulosité et température de Tunis, avec les termes de Fourier comme variables exogènes. L'ordre (nombre de retards) est choisi par AIC ou BIC.

## Causalité de Granger
X « cause au sens de Granger » Y si le passé de X améliore la prévision de Y au-delà du passé de Y. C'est une notion de prévisibilité, pas de causalité physique : deux mesures d'un même phénomène (la nébulosité et la production solaire décrivent toutes deux l'état du ciel) peuvent se « causer » mutuellement.

## Cointégration, Johansen, Engle-Granger
Deux séries non stationnaires (intégrées d'ordre 1) sont cointégrées si une combinaison linéaire d'entre elles est stationnaire : elles partagent une relation d'équilibre de long terme. Test d'Engle-Granger (deux séries) ou de Johansen (plusieurs séries, donne le rang de cointégration). Appliquer ces tests à des séries déjà stationnaires n'a pas de sens : le test de Johansen trouve alors un rang plein.

## VECM (modèle à correction d'erreur)
VAR en différences augmenté d'un terme qui ramène les séries vers leur relation de long terme. Le coefficient d'ajustement alpha mesure la vitesse de retour à l'équilibre ; la demi-vie vaut log(0,5) / log(1 + alpha).

## ARCH et GARCH
Modèles de variance conditionnelle : la variance de l'erreur de demain dépend des erreurs passées (ARCH) et de la variance passée (GARCH). GARCH(1,1) : sigma²(t) = omega + alpha e²(t-1) + beta sigma²(t-1). La persistance alpha + beta mesure la durée des chocs de volatilité. GJR-GARCH et EGARCH permettent un effet asymétrique (une mauvaise surprise augmente plus l'incertitude qu'une bonne). Pour la production solaire, la variance des erreurs est plus forte l'hiver (ciel changeant) que l'été (ciel clair stable).

## LSTM et GRU
Réseaux de neurones récurrents qui lisent une fenêtre de jours passés et gardent une mémoire interne. Le LSTM (Long Short-Term Memory) a trois portes (entrée, oubli, sortie) ; le GRU (Gated Recurrent Unit) en a deux et moins de paramètres. Ils exigent une normalisation des données, des fenêtres glissantes et une validation croisée temporelle.

## Validation croisée temporelle (walk-forward)
Chaque pli s'entraîne sur le passé et se valide sur la période qui suit immédiatement, avec un écart pour éviter tout chevauchement. Le k-fold classique, qui mélange passé et futur, est interdit pour une série temporelle.

## Approche hybride
Combinaison d'un modèle économétrique et d'un réseau de neurones : par exemple un ARIMA pour la structure linéaire, puis un LSTM entraîné sur les erreurs de l'ARIMA.

## Prophet
Modèle de Meta qui décompose une série en tendance, saisonnalités et effets de jours fériés. Il n'utilise pas les dernières observations pour corriger sa prévision, ce qui le pénalise à court horizon.

## XGBoost
Algorithme de gradient boosting sur arbres de décision. Utilisé ici en prévision directe (un modèle par horizon) avec une vingtaine de variables ; il fournit une importance des variables.

## Persistance et climatologie
Les deux références naïves des séries solaires. Persistance : demain comme aujourd'hui (difficile à battre à un jour). Climatologie : la normale saisonnière du jour, moyenne des années passées (difficile à battre à une semaine).

## Métriques MSE, RMSE, MAE, MAPE, WAPE
MSE : moyenne des erreurs au carré. RMSE : sa racine, dans l'unité de la série (kWh/kWc). MAE : moyenne des erreurs absolues. MAPE : moyenne des erreurs absolues relatives (%), instable quand la valeur observée est proche de zéro (journée très couverte). WAPE : somme des erreurs absolues divisée par la somme des observations, plus robuste.

## Test de Diebold-Mariano
Teste si deux modèles ont la même précision de prévision, à partir de la différence de leurs pertes (quadratique ou absolue) sur les mêmes jours. Correction de Harvey, Leybourne et Newbold pour les petits échantillons. Une p-value inférieure à 0,05 indique une différence significative.

## Ex ante et ex post
Ex ante : le modèle ne connaît du futur que ce qui est connu au moment de la prévision (la date, la position du soleil). Ex post : il reçoit aussi la météo observée des jours à prévoir ; c'est une borne optimiste de ce que permettrait une vraie prévision météo.

## Intervalle de prédiction et couverture
Fourchette qui doit contenir la valeur future avec une probabilité donnée (95 %). Sa couverture empirique est la part des valeurs observées tombées dedans ; un intervalle bien calibré couvre environ 95 % des cas.
