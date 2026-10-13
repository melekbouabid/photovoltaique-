"""Diagnostic : pourquoi une première version du protocole donnait une climatologie plus mauvaise à Tunis.

L'étude historique obtenait un RMSE de 1,1002 pour la climatologie de Tunis ; une réécriture du protocole
donnait 1,131. On fait varier un seul choix à la fois (lissage de la normale, période de calcul, façon de
mesurer l'erreur) et on regarde lequel reproduit l'écart.

Usage : python scripts/diagnose_climatology_gap.py
Sortie : reports/diagnostic_ecart_climatologie_tunis.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from solarvision.config import DATA, REPORTS, load_params
from solarvision.features.panel import climatology
from solarvision.models.protocol import origins, target_matrix
from solarvision.models.train import load_city

HISTORICAL_RMSE = 1.1002          # valeur de resultats/py_metriques.csv (étude historique)


def main() -> None:
    root = DATA if (DATA / "processed" / "panel_journalier.parquet").exists() else DATA / "fast"
    series = load_city("tunis", root)
    column = f"pv_{load_params()['pv']['reference_technology']}_kwh_kwc"
    values, n_train = series.frame[column].to_numpy(), series.n_train
    pos = origins(series.n, n_train)
    observed = target_matrix(values, pos)
    daily = pd.Series(values, index=series.dates)

    def rmse_on_origins(normal: np.ndarray) -> float:
        return float(np.sqrt(np.mean((observed - target_matrix(normal, pos)) ** 2)))

    def rmse_on_test_dates(normal: np.ndarray) -> float:
        return float(np.sqrt(np.mean((values[n_train:] - normal[n_train:]) ** 2)))

    rows = [(f"moyenne par jour de l'année sur l'apprentissage, lissage {w} j", rmse_on_origins(climatology(daily, n_train, window=w)))
            for w in (31, 15, 7, 1)]
    until_2020 = int((series.dates <= "2020-12-31").sum())
    rows.append(("normale 2005-2020, lissage 31 j", rmse_on_origins(climatology(daily, until_2020, window=31))))
    monthly = daily.iloc[:n_train].groupby(series.dates[:n_train].month).mean()
    rows.append(("moyenne mensuelle de l'apprentissage", rmse_on_origins(monthly.reindex(series.dates.month).to_numpy())))
    rows.append(("lissage 31 j, erreur sur les dates de test", rmse_on_test_dates(climatology(daily, n_train, window=31))))
    rows.append(("sans lissage, erreur sur les dates de test", rmse_on_test_dates(climatology(daily, n_train, window=1))))
    table = pd.DataFrame(rows, columns=["variante", "rmse_tunis"])
    table["ecart_a_l_etude_historique"] = table["rmse_tunis"] - HISTORICAL_RMSE
    REPORTS.mkdir(exist_ok=True)
    table.to_csv(REPORTS / "diagnostic_ecart_climatologie_tunis.csv", index=False, float_format="%.6g")
    print(table.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
