<!-- modèle : qwen3-vl:8b-instruct (Ollama, local) | options : {'temperature': 0, 'seed': 42, 'num_ctx': 8192} | date : 2026-10-10 -->

Pour votre parc solaire à Tunis, le modèle **LSTM (ex post)** est le meilleur choix : il prévoit avec une précision exceptionnelle (erreur de 0,699 kWh/kWc/jour) quand vous avez les données météo avant la production. Cela signifie que, si vous savez à l’avance qu’il va être nuageux ou ensoleillé, vous pouvez ajuster la production avec une grande fiabilité — crucial pour gérer les contrats, les ventes, ou les batteries.

Le modèle **SARIMAX météo (ex post)** est aussi très bon (erreur 0,725), mais l’LSTM est légèrement plus précis et plus robuste. Les modèles « ex ante » (sans météo) sont moins fiables, car ils ne prennent pas en compte les conditions réelles — ce qui est inutile si vous avez déjà les données météo.

Pourquoi pas un modèle plus simple comme « Persistance » ? Parce qu’il ne fait que répéter la production du jour précédent — ce qui est très mauvais en hiver ou en cas de changements météo.

En résumé : **utilisez l’LSTM avec les données météo en amont**. Il est précis, adaptable, et vous permet de mieux anticiper les variations de production. Cela vous donne une marge de sécurité pour les ventes, les contrats, ou les batteries. Le modèle est aussi robuste aux saisons — il fonctionne bien même en hiver, quand la production est plus faible.

Investissez dans une intégration simple avec vos données météo — vous gagnerez en fiabilité, en réduction des erreurs, et en confiance pour vos décisions.
