"""Évaluation : métriques, tests de Diebold-Mariano et synthèse par ville, à partir des prévisions enregistrées."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from solarvision.config import load_cities, load_params
from solarvision.evaluation.metrics import METRICS
from solarvision.evaluation.significance import block_bootstrap_mean, diebold_mariano, holm

REFERENCE_MODEL = "climatologie"
SEASONS = {12: "hiver", 1: "hiver", 2: "hiver", 3: "printemps", 4: "printemps", 5: "printemps",
           6: "été", 7: "été", 8: "été", 9: "automne", 10: "automne", 11: "automne"}
KEYS = ["ville", "technologie", "modele", "scenario"]


def load_forecasts(reports: Path) -> pd.DataFrame:
    # Modèles classiques et réseaux récurrents sont enregistrés à part, puis évalués ensemble sur les mêmes origines.
    files = sorted((reports / "forecasts").glob("*.parquet")) + sorted((reports / "forecasts_deep").glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"aucune prévision dans {reports / 'forecasts'} : lancer la commande train")
    return pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)


def _aggregate(table: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Métriques par groupe, calculées en une passe à partir des erreurs élémentaires."""
    g = table.groupby(by, observed=True)
    out = pd.DataFrame({"MSE": g["sq"].mean(), "MAE": g["abs"].mean(), "MAPE": 100 * g["ape"].mean(),
                        "WAPE": 100 * g["abs"].sum() / g["obs_abs"].sum(), "n": g["sq"].size()})
    out["RMSE"] = np.sqrt(out["MSE"])
    return out.reset_index()


def compute_all(forecasts: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Tous les tableaux d'évaluation. Aucune valeur n'est saisie : tout vient des prévisions."""
    params = load_params()
    f = forecasts.copy()
    error = f["observation"].astype("float64") - f["prevision"].astype("float64")
    f["sq"], f["abs"], f["obs_abs"] = error ** 2, error.abs(), f["observation"].abs().astype("float64")
    f["ape"] = f["abs"] / f["obs_abs"]
    f["saison"] = pd.DatetimeIndex(f["date_cible"]).month.map(SEASONS)
    f["inside"] = ((f["observation"] >= f["borne_basse"]) & (f["observation"] <= f["borne_haute"])).where(f["borne_basse"].notna())
    countries = {c.id: c.pays for c in load_cities().values()}

    # ---- métriques par horizon et tous horizons confondus
    per_h = _aggregate(f, [*KEYS, "horizon"])
    per_h["horizon"] = per_h["horizon"].astype(str)
    overall = _aggregate(f, KEYS).assign(horizon="tous")
    wide = pd.concat([per_h, overall], ignore_index=True)
    coverage = f.groupby(KEYS, observed=True)["inside"].mean().mul(100).rename("couverture_ic95").reset_index()
    tidy = wide.melt(id_vars=[*KEYS, "horizon"], value_vars=METRICS, var_name="metrique", value_name="valeur")
    cov_tidy = coverage.dropna().assign(horizon="tous", metrique="couverture_ic95").rename(columns={"couverture_ic95": "valeur"})
    tidy = pd.concat([tidy, cov_tidy], ignore_index=True)
    tidy.insert(1, "pays", tidy["ville"].map(countries))
    tidy = tidy[["ville", "pays", "technologie", "modele", "horizon", "scenario", "metrique", "valeur"]]

    # ---- Diebold-Mariano contre la climatologie
    alpha = params["evaluation"]["holm_alpha"]
    rows = []
    for (city, technology), block in f.groupby(["ville", "technologie"], observed=True):
        errors = block.assign(e=block["observation"].astype("float64") - block["prevision"].astype("float64")) \
            .pivot_table(index=["horizon", "origine"], columns="modele", values="e")
        scenario = block.drop_duplicates("modele").set_index("modele")["scenario"]
        for horizon in sorted(block["horizon"].unique()):
            e = errors.loc[horizon]
            for loss in params["evaluation"]["dm_losses"]:
                family = []
                for model in [m for m in e.columns if m != REFERENCE_MODEL]:
                    r = diebold_mariano(e[REFERENCE_MODEL].to_numpy(), e[model].to_numpy(), int(horizon), loss)
                    family.append({"ville": city, "technologie": technology, "modele": model, "scenario": scenario[model],
                                   "reference": REFERENCE_MODEL, "horizon": int(horizon), "perte": loss,
                                   "dm_stat": r.statistic, "p_unilaterale": r.p_one_sided, "p_bilaterale": r.p_two_sided,
                                   "n": r.n, "ecart_perte_moyen": r.mean_loss_difference, "noyau": r.kernel})
                # Famille de Holm : tous les modèles comparés à la climatologie pour cette ville, cette technologie,
                # cet horizon et cette fonction de perte.
                one, two = holm([x["p_unilaterale"] for x in family]), holm([x["p_bilaterale"] for x in family])
                for x, a, b in zip(family, one, two, strict=True):
                    x.update(p_holm_unilaterale=a, p_holm_bilaterale=b, taille_famille=len(family),
                             meilleur_que_reference=bool(a < alpha),
                             different_de_reference=bool(b < alpha))
                rows += family
    dm = pd.DataFrame(rows)
    dm.insert(1, "pays", dm["ville"].map(countries))

    # ---- synthèse par ville, sur la technologie de référence
    reference_tech = params["pv"]["reference_technology"]
    ref = wide[wide["technologie"] == reference_tech]
    season = _aggregate(f[f["technologie"] == reference_tech], [*KEYS, "saison"])
    summary = []
    for city, block in ref.groupby("ville"):
        total = block[block["horizon"] == "tous"].set_index("modele")
        ex_ante = total[total["scenario"] == "ex_ante"]
        best = ex_ante["RMSE"].idxmin()
        clim = total.loc[REFERENCE_MODEL, "RMSE"]
        by_h = block[block["modele"] == best].set_index("horizon")["RMSE"]
        clim_h = block[block["modele"] == REFERENCE_MODEL].set_index("horizon")["RMSE"]
        # Intervalle de l'écart d'erreur quadratique avec la climatologie, par bootstrap à blocs sur les origines.
        sub = f[(f["ville"] == city) & (f["technologie"] == reference_tech)]
        per_origin = sub.pivot_table(index="origine", columns="modele", values="sq", aggfunc="mean")
        _, low, high = block_bootstrap_mean((per_origin[REFERENCE_MODEL] - per_origin[best]).to_numpy(),
                                            params["evaluation"]["bootstrap_block_days"],
                                            params["evaluation"]["bootstrap_replicates"], params["seed"])
        tests = dm[(dm["ville"] == city) & (dm["technologie"] == reference_tech) & (dm["modele"] == best)
                   & (dm["perte"] == "squared")].set_index("horizon")
        row = {"ville": city, "pays": countries[city], "technologie": reference_tech, "meilleur_modele_ex_ante": best,
               "rmse_meilleur": ex_ante.loc[best, "RMSE"], "rmse_climatologie": clim,
               "gain_vs_climatologie_pct": 100 * (clim - ex_ante.loc[best, "RMSE"]) / clim,
               "ecart_mse_ic95_bas": low, "ecart_mse_ic95_haut": high,
               "wape_meilleur": ex_ante.loc[best, "WAPE"],
               **{f"rmse_h{h}": by_h.get(str(h), np.nan) for h in params["horizons"]},
               **{f"gain_h{h}_pct": 100 * (clim_h.get(str(h), np.nan) - by_h.get(str(h), np.nan)) / clim_h.get(str(h), np.nan)
                  for h in (1, 7)},
               **{f"p_holm_h{h}": tests["p_holm_unilaterale"].get(h, np.nan) for h in (1, 7) if best != REFERENCE_MODEL},
               **{f"rmse_{s}": season[(season["ville"] == city) & (season["modele"] == best) & (season["saison"] == s)]["RMSE"].mean()
                  for s in ("hiver", "printemps", "été", "automne")}}
        post = total[total["scenario"] == "ex_post"]
        if len(post):
            row["rmse_meilleur_ex_post"] = post["RMSE"].min()
        summary.append(row)
    return {"metrics_tidy": tidy, "metrics_wide": wide, "dm_tests": dm, "synthese_ville": pd.DataFrame(summary),
            "coverage": coverage.dropna()}


def run(reports: Path) -> dict[str, pd.DataFrame]:
    tables = compute_all(load_forecasts(reports))
    for name, table in tables.items():
        table.to_csv(reports / f"{name}.csv", index=False, float_format="%.6g")
    return tables
