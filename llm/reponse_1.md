<!-- modèle : qwen3-vl:8b-instruct (Ollama, local) | options : {'temperature': 0, 'seed': 42, 'num_ctx': 8192} | date : 2026-10-10 -->

**1. Hypothèses de modèles à tester :**  
- **Modèle ARIMA saisonnier (SARIMA)** : la série présente une forte autocorrélation à court terme (lag 1 : 0.512) et une saisonnalité annuelle (lag 365 : 0.329), avec une tendance visible.  
- **Modèle avec décomposition saisonnière (Fourier)** : la désaisonnalisée est stationnaire (ADF p=0.0, KPSS p=0.10) mais avec une tendance, suggérant un modèle avec tendance et composante saisonnière.  
- **Modèle GARCH pour la variance** : l’écart-type mensuel varie (ex. : 0.41 en juillet vs 1.25 en janvier), et la série présente une asymétrie (skewness = -0.815), indiquant une volatilité hétéroscédastique.  
- **Modèle à variables exogènes (SARIMAX)** : les séries météorologiques (nébulosité, température, aérosols) sont fortement corrélées à la production (corrélation >0.5 avec la production), et stationnaires après différenciation.

**2. Ordres de différenciation et traitement saisonnier :**  
- **d = 1** (différence simple) : la série originale est non stationnaire (ADF p=0.0, KPSS p=0.10), mais la différence d’ordre 1 est stationnaire (ADF p=0.0, KPSS p=0.10).  
- **D = 1** (différence saisonnière annuelle) : la série désaisonnalisée (Fourier) est stationnaire (ADF p=0.0, KPSS p=0.10), mais avec une tendance.  
- **Traitement saisonnier** : utiliser un modèle SARIMA(1,1,1)(1,1,1)12 ou SARIMAX avec variables exogènes, ou un modèle avec décomposition saisonnière (Fourier) et tendance.

**3. Transformation de la série ?**  
- **Non nécessaire** : la série est positive, mais la transformation log ou Box-Cox n’est pas justifiée ici car la variance n’est pas fortement hétéroscédastique (écart-type moyen = 1.402, variance = 1.965), et les tests de stationnarité sont satisfaisants après différenciation.

**4. Pièges à éviter :**  
- **Surajustement** : ne pas surajuster les modèles avec trop de paramètres (ex. : SARIMA(1,1,1)(1,1,1)12 avec trop de paramètres).  
- **Ignorer la saisonnalité** : ne pas négliger la saisonnalité annuelle (lag 365 = 0.329) ou la tendance (ADF p=0.0 pour la désaisonnalisée avec tendance).  
- **Ignorer les variables exogènes** : ne pas utiliser les variables météorologiques (nébulosité, température, aérosols) qui sont fortement corrélées à la production.  
- **Sur-estimer la stationnarité** : ne pas croire à la stationnarité de la série désaisonnalisée sans vérifier les tests de stationnarité (ADF et KPSS).
