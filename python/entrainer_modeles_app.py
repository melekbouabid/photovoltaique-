"""Entraîne les modèles servis par l'application web et mesure leur précision sur la période de test.

Pour chaque variable (production PV d'1 kWc, irradiation globale horizontale) :
- un LSTM global univarié, entraîné sur les 9 villes à la fois : il lit les 28 derniers jours (écart à
  la normale saisonnière) et prévoit les 10 jours suivants. Il est univarié à dessein : dans
  l'application, l'utilisateur peut saisir lui-même les valeurs récentes, mais pas la météo ;
- un ARIMA-Fourier par ville (même spécification que l'étude), dont seuls les paramètres sont stockés ;
- des intervalles de prédiction empiriques pour le LSTM : quantiles 2,5 % et 97,5 % des erreurs de
  validation, par horizon (un réseau ne fournit pas d'intervalle par lui-même).
Même découpage que le notebook : 90 % des jours pour l'apprentissage, 10 % pour le test.

Usage : python python/entrainer_modeles_app.py      (environ 10 minutes sur CPU)
"""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from statsmodels.tsa.arima.model import ARIMA

warnings.filterwarnings("ignore")
RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "app" / "backend" / "modeles"
SEED, H, L, CACHE = 42, 10, 28, 64
VARIABLES = {"pv_kwh_kwc": "production PV (kWh/kWc)", "ghi_kwh_m2": "irradiation horizontale (kWh/m²)"}
torch.manual_seed(SEED)
torch.set_num_threads(4)
torch.use_deterministic_algorithms(True)


def ordre_etude():
    """Ordre ARIMA et nombre d'harmoniques retenus par l'étude (premier rang de la grille du notebook)."""
    f = RACINE / "resultats" / "py_grille_arima.csv"
    if f.exists():
        g = pd.read_csv(f).iloc[0]
        return tuple(int(x) for x in g["ordre"].strip("()").split(",")), int(g["K"])
    return (2, 0, 1), 3


def fourier(t, K):
    return np.column_stack([fn(2 * np.pi * k * t / 365.25) for k in range(1, K + 1) for fn in (np.sin, np.cos)])


def normales(v, index, fin):
    """Moyenne et écart-type par jour de l'année sur [0, fin), lissés sur 31 jours (comme le notebook)."""
    base = pd.Series(np.asarray(v[:fin], dtype=float), index=index[:fin])
    jour = np.minimum(base.index.dayofyear, 365)
    m = base.groupby(jour).mean().reindex(range(1, 366)).interpolate(limit_direction="both").to_numpy()
    s = base.groupby(jour).std().reindex(range(1, 366)).interpolate(limit_direction="both").to_numpy()
    lisser = lambda a: pd.Series(np.tile(a, 3)).rolling(31, center=True).mean().to_numpy()[365:730]
    return lisser(m), lisser(s)


class Reseau(nn.Module):
    def __init__(self, n_seq=3, n_fut=2 * H, cache=CACHE, dropout=0.1):
        super().__init__()
        self.rnn = nn.LSTM(n_seq, cache, batch_first=True)
        self.tete = nn.Sequential(nn.Dropout(dropout), nn.Linear(cache + n_fut, 64), nn.ReLU(), nn.Linear(64, H))

    def forward(self, xs, xf):
        sortie, _ = self.rnn(xs)
        return self.tete(torch.cat([sortie[:, -1], xf], dim=1))


def fenetres(z, doy, origines):
    xs = np.stack([np.column_stack([z[t - L + 1:t + 1], doy[t - L + 1:t + 1]]) for t in origines])
    xf = np.stack([doy[t + 1:t + 1 + H].ravel() for t in origines])
    yd = np.stack([z[t + 1:t + 1 + H] for t in origines])
    return [torch.tensor(a, dtype=torch.float32) for a in (xs, xf, yd)]


def entrainer(app, val, epoques=60, patience=8, lr=2e-3, lot=256):
    torch.manual_seed(SEED)
    net = Reseau()
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)
    perte, gen = nn.MSELoss(), torch.Generator().manual_seed(SEED)
    meilleur, etat, attente, histo = np.inf, None, 0, []
    for _ in range(epoques):
        net.train()
        perm = torch.randperm(len(app[0]), generator=gen)
        for i in range(0, len(perm), lot):
            idx = perm[i:i + lot]
            opt.zero_grad()
            l = perte(net(app[0][idx], app[1][idx]), app[2][idx])
            l.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        net.eval()
        with torch.no_grad():
            lv = perte(net(val[0], val[1]), val[2]).item()
        histo.append(lv)
        if lv < meilleur - 1e-5:
            meilleur, attente, etat = lv, 0, {k: v.clone() for k, v in net.state_dict().items()}
        else:
            attente += 1
            if attente >= patience:
                break
    net.load_state_dict(etat)
    net.eval()
    return net, histo


def prev_arima_toutes(res, h_max=H):
    """Prévision à 1..h_max pas depuis chaque origine, à partir des états filtrés (voir le notebook)."""
    fr = res.filter_results
    a = fr.filtered_state.copy()
    T, Z, c = fr.transition[:, :, 0], fr.design[:, :, 0], fr.state_intercept[:, :1]
    d = np.broadcast_to(fr.obs_intercept, (1, a.shape[1]))[0]
    out = np.full((a.shape[1], h_max), np.nan)
    for h in range(1, h_max + 1):
        a = T @ a + c
        out[:-h, h - 1] = (Z @ a).ravel()[:-h] + d[h:]
    return out


def main():
    t_debut = time.time()
    SORTIE.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(RACINE / "data" / "datasets" / "panel_9_villes_journalier.csv", parse_dates=["date"],
                        usecols=["date", "site", *VARIABLES])
    sites = list(dict.fromkeys(panel["site"]))
    index = pd.DatetimeIndex(sorted(panel["date"].unique()))
    n = len(index)
    n_train = int(n * 0.9)
    t_jour = np.arange(n)
    jour = np.minimum(index.dayofyear, 365) - 1
    doy = np.column_stack([np.sin(2 * np.pi * index.dayofyear / 365.25), np.cos(2 * np.pi * index.dayofyear / 365.25)])
    ordre, K = ordre_etude()
    orig_app = np.arange(L - 1, n_train - H)
    coupe = int(len(orig_app) * 0.9)
    origines_test = np.arange(n_train - 1, n - H)
    validation = {"ordre_arima": list(ordre), "K_fourier": K, "horizon": H, "fenetre": L, "fin_apprentissage":
                  str(index[n_train - 1].date()), "rmse_test": {}, "mae_test": {}, "quantiles_z": {}, "epoques": {}}
    for var, libelle in VARIABLES.items():
        t0 = time.time()
        series, clim = {}, {}
        for s in sites:
            y = panel[panel["site"] == s].set_index("date")[var].reindex(index).interpolate().to_numpy()
            m, sd = normales(y, index, n_train)
            series[s], clim[s] = y, (m[jour], sd[jour])
        # LSTM global : fenêtres de toutes les villes réunies, chaque ville ramenée à ses normales.
        z = {s: (series[s] - clim[s][0]) / clim[s][1] for s in sites}
        app = [torch.cat(x) for x in zip(*[fenetres(z[s], doy, orig_app[:coupe - H]) for s in sites])]
        val = [torch.cat(x) for x in zip(*[fenetres(z[s], doy, orig_app[coupe:]) for s in sites])]
        net, histo = entrainer(app, val)
        with torch.no_grad():
            err_val = (val[2] - net(val[0], val[1])).numpy()
        q = np.quantile(err_val, [0.025, 0.975], axis=0)          # erreurs de validation, par horizon
        torch.save({"etat": net.state_dict(), "L": L, "H": H, "cache": CACHE, "variable": var}, SORTIE / f"lstm_{var}.pt")
        validation["quantiles_z"][var] = {"bas": q[0].round(4).tolist(), "haut": q[1].round(4).tolist()}
        validation["epoques"][var] = len(histo)

        # ARIMA-Fourier par ville : paramètres estimés sur l'apprentissage, prévision par états filtrés.
        params, rmse, mae = {}, {}, {}
        for s in sites:
            y = series[s]
            X = fourier(t_jour, K)
            res = ARIMA(y[:n_train], exog=X[:n_train], order=ordre, trend="c").fit(method="innovations_mle", gls=True)
            params[s] = res.params.tolist()
            p_arima = prev_arima_toutes(res.apply(y, exog=X))[origines_test]
            with torch.no_grad():
                zc = net(*fenetres(z[s], doy, origines_test)[:2]).numpy()
            m_, sd_ = clim[s]
            P_lstm = np.stack([m_[t + 1:t + 1 + H] for t in origines_test]) + zc * np.stack([sd_[t + 1:t + 1 + H] for t in origines_test])
            P_clim = np.stack([m_[t + 1:t + 1 + H] for t in origines_test])
            P_pers = np.stack([np.repeat(y[t], H) for t in origines_test])
            Y = np.stack([y[t + 1:t + 1 + H] for t in origines_test])
            rmse[s], mae[s] = {}, {}
            for nom, P in (("lstm", np.clip(P_lstm, 0, None)), ("arima", np.clip(p_arima, 0, None)),
                           ("climatologie", P_clim), ("persistance", P_pers)):
                rmse[s][nom] = float(np.sqrt(np.mean((Y[:, :7] - P[:, :7]) ** 2)))
                mae[s][nom] = float(np.mean(np.abs(Y[:, :7] - P[:, :7])))
        (SORTIE / f"arima_{var}.json").write_text(json.dumps({"ordre": list(ordre), "K": K, "params": params}, indent=1),
                                                  encoding="utf-8")
        validation["rmse_test"][var], validation["mae_test"][var] = rmse, mae
        moy = pd.DataFrame(rmse).T.mean()
        print(f"{libelle} : LSTM {len(histo)} époques, {time.time() - t0:.0f} s ; RMSE moyen (7 j, 9 villes) : "
              + ", ".join(f"{k} {v:.3f}" for k, v in moy.items()))
    (SORTIE / "validation_app.json").write_text(json.dumps(validation, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Modèles écrits dans {SORTIE} ({time.time() - t_debut:.0f} s)")


if __name__ == "__main__":
    main()
