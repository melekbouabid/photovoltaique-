"""Données, modèles et prévisions servis par l'API : production PV et éclairement de 9 villes.

Les modèles sont entraînés hors ligne par python/entrainer_modeles_app.py (même découpage que le
notebook : 90 % des jours pour l'apprentissage) ; ce module ne fait que les charger et les appliquer :
- LSTM global univarié (un par variable) : lit les 28 derniers jours, prévoit jusqu'à 10 jours ;
  intervalle de prédiction empirique (quantiles des erreurs de validation) ;
- ARIMA-Fourier par ville : paramètres figés, filtre de Kalman appliqué à l'historique disponible ;
- références : climatologie (normale saisonnière) et persistance.

L'historique qui nourrit les modèles est celui des données jusqu'à la date d'origine. L'utilisateur peut
remplacer les derniers jours par ses propres valeurs (relevés de son installation) ; au-delà de la fin
des données (31/12/2023), les jours manquants sont remplacés par la normale saisonnière.
"""
from __future__ import annotations

import json
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from statsmodels.tsa.arima.model import ARIMA

RACINE = Path(__file__).resolve().parents[2]                 # dossier du projet
JEUX = RACINE / "data" / "datasets"
MODELES = Path(__file__).resolve().parent / "modeles"
RESULTATS = RACINE / "resultats"

VARIABLES = {
    "pv_kwh_kwc": {"libelle": "Production photovoltaïque", "unite": "kWh/kWc", "court": "production"},
    "ghi_kwh_m2": {"libelle": "Éclairement global horizontal", "unite": "kWh/m²", "court": "irradiation"},
}
NOMS_MODELES = {"lstm": "LSTM global (9 villes)", "arima": "ARIMA-Fourier", "climatologie": "Climatologie",
                "persistance": "Persistance"}
H_MAX = 10                        # horizon maximal, en jours
HISTORIQUE = 730                  # jours d'historique donnés au filtre de l'ARIMA
DATE_MAX = date(2030, 12, 31)     # au-delà de la fin des données, l'historique est complété par la normale
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]


def fmt(v: float, d: int = 1) -> str:
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def date_fr(d: date) -> str:
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


def fourier(t: np.ndarray, K: int) -> np.ndarray:
    return np.column_stack([fn(2 * np.pi * k * t / 365.25) for k in range(1, K + 1) for fn in (np.sin, np.cos)])


def normales(v: np.ndarray, index: pd.DatetimeIndex, fin: int) -> tuple[np.ndarray, np.ndarray]:
    """Moyenne et écart-type par jour de l'année (365 valeurs), calculés sur [0, fin) et lissés sur 31 jours."""
    base = pd.Series(np.asarray(v[:fin], dtype=float), index=index[:fin])
    jour = np.minimum(base.index.dayofyear, 365)
    m = base.groupby(jour).mean().reindex(range(1, 366)).interpolate(limit_direction="both").to_numpy()
    s = base.groupby(jour).std().reindex(range(1, 366)).interpolate(limit_direction="both").to_numpy()
    lisser = lambda a: pd.Series(np.tile(a, 3)).rolling(31, center=True).mean().to_numpy()[365:730]
    return lisser(m), lisser(s)


class Reseau(nn.Module):
    """Même architecture que python/entrainer_modeles_app.py."""

    def __init__(self, cache: int, h: int, n_seq: int = 3, dropout: float = 0.1):
        super().__init__()
        self.rnn = nn.LSTM(n_seq, cache, batch_first=True)
        self.tete = nn.Sequential(nn.Dropout(dropout), nn.Linear(cache + 2 * h, 64), nn.ReLU(), nn.Linear(64, h))

    def forward(self, xs, xf):
        sortie, _ = self.rnn(xs)
        return self.tete(torch.cat([sortie[:, -1], xf], dim=1))


class Previsionniste:
    """Charge les données et les modèles, puis calcule une prévision depuis une date d'origine."""

    def __init__(self):
        panel_f = JEUX / "panel_9_villes_journalier.csv"
        if not panel_f.exists():
            raise FileNotFoundError(f"{panel_f} introuvable : lancer d'abord python/collecte_donnees.py")
        if not (MODELES / "validation_app.json").exists():
            raise FileNotFoundError("modèles absents : lancer d'abord python/entrainer_modeles_app.py")
        cols = ["date", "site", "ville", "pays", "code_pays", "latitude", "longitude", "nebulosite_pct",
                "t2m_moy_c", "heures_lumiere_10klux", *VARIABLES]
        panel = pd.read_csv(panel_f, parse_dates=["date"], usecols=cols)
        self.index = pd.DatetimeIndex(sorted(panel["date"].unique()))
        self.debut = self.index[0]
        self.n = len(self.index)
        self.n_train = int(self.n * 0.9)
        synth = pd.read_csv(RACINE / "data" / "reference" / "pvgis_synthese_9_villes.csv", index_col="site")
        self.validation = json.loads((MODELES / "validation_app.json").read_text(encoding="utf-8"))
        self.sites, self.series, self.clim, self.lux = {}, {}, {}, {}
        for s, d in panel.groupby("site", sort=False):
            d = d.set_index("date").reindex(self.index)
            self.sites[s] = {"site": s, "ville": d["ville"].iloc[0], "pays": d["pays"].iloc[0],
                             "code_pays": d["code_pays"].iloc[0], "latitude": float(d["latitude"].iloc[0]),
                             "longitude": float(d["longitude"].iloc[0]),
                             "pente_optimale_deg": float(synth.loc[s, "pente_optimale_deg"]),
                             "productible_kwh_kwc_an": float(synth.loc[s, "productible_kwh_kwc_an"]),
                             "irradiation_plan_kwh_m2_an": float(synth.loc[s, "irradiation_plan_kwh_m2_an"])}
            for var in VARIABLES:
                y = d[var].interpolate().to_numpy()
                self.series[(s, var)] = y
                self.clim[(s, var)] = normales(y, self.index, self.n_train)
            self.lux[s] = normales(d["heures_lumiere_10klux"].to_numpy(), self.index, self.n_train)[0]
        self.lstm, self.arima = {}, {}
        for var in VARIABLES:
            ck = torch.load(MODELES / f"lstm_{var}.pt", weights_only=True)
            net = Reseau(ck["cache"], ck["H"])
            net.load_state_dict(ck["etat"])
            net.eval()
            self.lstm[var] = (net, ck["L"], ck["H"])
            self.arima[var] = json.loads((MODELES / f"arima_{var}.json").read_text(encoding="utf-8"))
        self.horaire = self._profils_horaires()
        self.orientations = self._orientations()

    # ------------------------------------------------------------------ jeux complémentaires
    @staticmethod
    def _profils_horaires() -> pd.DataFrame | None:
        """Profil moyen d'une journée (heure solaire) par ville et par mois, à partir de l'année horaire 2023."""
        f = JEUX / "horaire_9_villes_2023.csv.gz"
        if not f.exists():
            return None
        cols = ["heure_utc", "site", "p_w_kwc", "ghi_w_m2", "eclairement_lux", "lumiere_suffisante", "heure_solaire",
                "nebulosite_pct", "t_module_c", "t2m_c"]
        h = pd.read_csv(f, parse_dates=["heure_utc"], usecols=lambda c: c in cols)
        h["mois"] = h["heure_utc"].dt.month
        h["heure"] = np.floor(h["heure_solaire"]).astype(int) % 24
        return h.groupby(["site", "mois", "heure"]).mean(numeric_only=True)

    @staticmethod
    def _orientations() -> pd.DataFrame | None:
        f = JEUX / "pvgis_orientations_9_villes.csv"
        return pd.read_csv(f) if f.exists() else None

    def profil_horaire(self, site: str, mois: int) -> dict:
        if self.horaire is None:
            raise ValueError("jeu horaire absent : lancer python/collecte_donnees.py")
        if site not in self.sites or not 1 <= mois <= 12:
            raise ValueError("site ou mois invalide")
        p = self.horaire.loc[(site, mois)].reindex(range(24))
        heures = [{"heure": int(k), "p_w_kwc": round(float(r.p_w_kwc), 1), "ghi_w_m2": round(float(r.ghi_w_m2), 1),
                   "eclairement_klux": round(float(r.eclairement_lux) / 1000, 2),
                   "part_lumiere_suffisante": round(float(r.lumiere_suffisante), 3),
                   "nebulosite_pct": None if pd.isna(r.nebulosite_pct) else round(float(r.nebulosite_pct), 1),
                   "t_module_c": round(float(r.t_module_c), 1), "t2m_c": round(float(r.t2m_c), 1)}
                  for k, r in p.fillna(0).iterrows()]
        jour = [x for x in heures if x["ghi_w_m2"] > 1]
        return {"site": site, "ville": self.sites[site]["ville"], "mois": mois, "heures": heures,
                "resume": {"heures_lumiere_10klux": round(sum(x["part_lumiere_suffisante"] for x in heures), 1),
                           "premiere_heure_jour": jour[0]["heure"] if jour else None,
                           "derniere_heure_jour": jour[-1]["heure"] if jour else None,
                           "eclairement_max_klux": max(x["eclairement_klux"] for x in heures),
                           "production_jour_kwh_kwc": round(sum(x["p_w_kwc"] for x in heures) / 1000, 2)}}

    def scenarios_orientation(self, site: str) -> dict:
        if self.orientations is None:
            raise ValueError("jeu des orientations absent : lancer python/collecte_donnees.py")
        if site not in self.sites:
            raise ValueError(f"site inconnu : {site}")
        o = self.orientations[self.orientations["site"] == site]
        scen = []
        for (inc, azi), g in o.groupby(["inclinaison_deg", "azimut_deg"], sort=True):
            g = g.sort_values("mois")
            r = g.iloc[0]
            scen.append({"inclinaison": float(inc), "azimut": float(azi), "orientation": r["orientation"],
                         "est_optimal": bool(r["est_optimal"]), "e_an_kwh_kwc": round(float(r["e_an_kwh_kwc"]), 1),
                         "part_optimal_pct": round(float(r["part_productible_optimal_pct"]), 1),
                         "mensuel_kwh_kwc": [round(float(v), 1) for v in g["e_mois_kwh_kwc"]]})
        r0 = o.iloc[0]
        return {"site": site, "ville": self.sites[site]["ville"], "pente_optimale": float(r0["pente_optimale_site_deg"]),
                "productible_optimal_kwh_kwc": float(r0["productible_optimal_kwh_kwc"]), "scenarios": scen}

    # ------------------------------------------------------------------ informations
    def bornes(self) -> dict:
        return {"debut": self.index[0].date(), "fin": self.index[-1].date(),
                "fin_apprentissage": self.index[self.n_train - 1].date(),
                "origine_min": self.index[60].date(), "origine_max": DATE_MAX, "horizon_max": H_MAX}

    def _normale(self, site: str, var: str, dates: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
        m, s = self.clim[(site, var)]
        j = np.minimum(dates.dayofyear, 365) - 1
        return m[j], s[j]

    def historique(self, site: str, var: str, origine: date, n_jours: int) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
        """Valeurs des n_jours finissant à `origine` : données si disponibles, sinon normale saisonnière."""
        dates = pd.date_range(end=pd.Timestamp(origine), periods=n_jours, freq="D")
        y = self.series[(site, var)]
        pos = (dates - self.debut).days.to_numpy()
        dispo = (pos >= 0) & (pos < self.n)
        valeurs = self._normale(site, var, dates)[0].copy()
        valeurs[dispo] = y[pos[dispo]]
        return dates, valeurs, dispo

    def valeurs_recentes(self, site: str, var: str, origine: date, n_jours: int = 14) -> list[dict]:
        self._verifier(site, var, origine)
        dates, v, dispo = self.historique(site, var, origine, n_jours)
        return [{"date": d.date(), "valeur": round(float(x), 3), "source": "données PVGIS" if ok else "normale saisonnière"}
                for d, x, ok in zip(dates, v, dispo)]

    def serie(self, site: str, var: str, debut: date | None, fin: date | None, pas: str) -> list[dict]:
        s = pd.Series(self.series[(site, var)], index=self.index).loc[debut:fin]
        if pas == "semaine":
            s = s.resample("W-MON", label="left", closed="left").mean()
        elif pas == "mois":
            s = s.resample("MS").mean()
        return [{"date": i.date(), "valeur": round(float(v), 4)} for i, v in s.dropna().items()]

    def profils_mensuels(self, var: str) -> list[dict]:
        out = []
        for s, info in self.sites.items():
            y = pd.Series(self.series[(s, var)], index=self.index)
            prof = y.groupby(y.index.month).mean()
            out.append({**info, "mensuel": [round(float(v), 3) for v in prof.to_numpy()],
                        "annuel": round(float(y.groupby(y.index.year).sum().mean()), 1)})
        return out

    def _verifier(self, site: str, var: str, origine: date) -> None:
        if site not in self.sites:
            raise ValueError(f"site inconnu : {site} (choisir parmi {', '.join(self.sites)})")
        if var not in VARIABLES:
            raise ValueError(f"variable inconnue : {var}")
        b = self.bornes()
        if not b["origine_min"] <= origine <= b["origine_max"]:
            raise ValueError(f"origine hors limites : choisir une date entre {b['origine_min']} et {b['origine_max']}")

    # ------------------------------------------------------------------ prévision
    def prevoir(self, site: str, var: str, modele: str, origine: date, horizon: int = 7,
                puissance_kwc: float = 1.0, conso_kwh_jour: float | None = None,
                valeurs_recentes: list[float] | None = None) -> dict:
        self._verifier(site, var, origine)
        if modele not in NOMS_MODELES:
            raise ValueError(f"modèle inconnu : {modele}")
        if not 1 <= horizon <= H_MAX:
            raise ValueError(f"horizon entre 1 et {H_MAX} jours")
        dates, y_hist, dispo = self.historique(site, var, origine, HISTORIQUE)
        saisies = 0
        if valeurs_recentes:
            v = np.asarray([x for x in valeurs_recentes if x is not None], dtype=float)[-28:]
            if (v < 0).any():
                raise ValueError("les valeurs saisies doivent être positives ou nulles")
            y_hist[-len(v):] = v
            saisies = len(v)
        futur = pd.date_range(pd.Timestamp(origine) + pd.Timedelta(days=1), periods=H_MAX, freq="D")
        m_f, s_f = self._normale(site, var, futur)

        if modele == "lstm":
            net, L, h_net = self.lstm[var]
            m_h, s_h = self._normale(site, var, dates[-L:])
            z = (y_hist[-L:] - m_h) / s_h
            doy = lambda d: np.column_stack([np.sin(2 * np.pi * d.dayofyear / 365.25), np.cos(2 * np.pi * d.dayofyear / 365.25)])
            xs = torch.tensor(np.column_stack([z, doy(dates[-L:])])[None], dtype=torch.float32)
            xf = torch.tensor(doy(futur).ravel()[None], dtype=torch.float32)
            with torch.no_grad():
                zc = net(xs, xf).numpy()[0]
            q = self.validation["quantiles_z"][var]
            moy, bas, haut = m_f + zc * s_f, m_f + (zc + np.array(q["bas"])) * s_f, m_f + (zc + np.array(q["haut"])) * s_f
        elif modele == "arima":
            a = self.arima[var]
            t_h = (dates - self.debut).days.to_numpy()
            t_f = (futur - self.debut).days.to_numpy()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = ARIMA(y_hist, exog=fourier(t_h, a["K"]), order=tuple(a["ordre"]), trend="c").filter(np.asarray(a["params"][site]))
                p = res.get_forecast(H_MAX, exog=fourier(t_f, a["K"]))
            moy, ic = np.asarray(p.predicted_mean), np.asarray(p.conf_int(alpha=0.05))
            bas, haut = ic[:, 0], ic[:, 1]
        elif modele == "climatologie":
            moy, bas, haut = m_f, m_f - 1.96 * s_f, m_f + 1.96 * s_f
        else:
            moy = np.repeat(y_hist[-1], H_MAX)
            bas = haut = None
        moy = np.clip(moy, 0, None)[:horizon]
        if bas is not None:
            bas, haut = np.clip(bas, 0, None)[:horizon], np.clip(haut, 0, None)[:horizon]

        y = self.series[(site, var)]
        pos_f = (futur[:horizon] - self.debut).days.to_numpy()
        points = []
        for h in range(horizon):
            obs = float(y[pos_f[h]]) if 0 <= pos_f[h] < self.n else None
            points.append({"date": futur[h].date(), "horizon": h + 1, "prevision": round(float(moy[h]), 4),
                           "bas": None if bas is None else round(float(bas[h]), 4),
                           "haut": None if haut is None else round(float(haut[h]), 4),
                           "normale": round(float(m_f[h]), 4), "observe": None if obs is None else round(obs, 4)})
        n_aff = 21
        hist = [{"date": d.date(), "valeur": round(float(v), 4), "source": "saisie" if i >= HISTORIQUE - saisies else
                 ("données PVGIS" if ok else "normale saisonnière")}
                for i, (d, v, ok) in enumerate(zip(dates, y_hist, dispo)) if i >= HISTORIQUE - n_aff]
        connus = [p for p in points if p["observe"] is not None]
        mae_prev = float(np.mean([abs(p["observe"] - p["prevision"]) for p in connus])) if connus else None
        sortie = {"site": site, "ville": self.sites[site]["ville"], "pays": self.sites[site]["pays"], "variable": var,
                  "unite": VARIABLES[var]["unite"], "modele": modele, "nom_modele": NOMS_MODELES[modele],
                  "origine": origine, "horizon": horizon, "puissance_kwc": puissance_kwc,
                  "conso_kwh_jour": conso_kwh_jour, "valeurs_saisies": saisies,
                  "hors_donnees": bool(not dispo[-1]), "dans_apprentissage": bool(dispo[-1] and (pd.Timestamp(origine) - self.debut).days < self.n_train),
                  "mae_prevision": mae_prev, "historique": hist, "previsions": points}
        sortie.update(self._synthese(sortie))
        return sortie

    def _synthese(self, p: dict) -> dict:
        """Totaux, comparaison à la normale et réponse rédigée en français."""
        pts, var, kwc = p["previsions"], p["variable"], p["puissance_kwc"]
        info = self.sites[p["site"]]
        mult = kwc if var == "pv_kwh_kwc" else 1.0
        total = sum(x["prevision"] for x in pts) * mult
        normale = sum(x["normale"] for x in pts) * mult
        a_ic = all(x["bas"] is not None for x in pts)
        # Somme des bornes : majorant de l'incertitude du total (les erreurs de jours voisins sont corrélées).
        total_bas = sum(x["bas"] for x in pts) * mult if a_ic else None
        total_haut = sum(x["haut"] for x in pts) * mult if a_ic else None
        jmax = max(pts, key=lambda x: x["prevision"])
        jmin = min(pts, key=lambda x: x["prevision"])
        ecart = 100 * (total / normale - 1) if normale > 0 else 0.0
        mae_ref = self.validation["mae_test"][var][p["site"]].get(p["modele"])
        d1, dn = pts[0]["date"], pts[-1]["date"]
        unite_j = "kWh/kWc" if var == "pv_kwh_kwc" else "kWh/m²"
        lignes = [f"{VARIABLES[var]['libelle']} prévue à {info['ville']} ({info['pays']}) du {date_fr(d1)} au "
                  f"{date_fr(dn)}, modèle {p['nom_modele']}, à partir des données jusqu'au {date_fr(p['origine'])}."]
        if var == "pv_kwh_kwc":
            phrase = f"Pour une installation de {fmt(kwc, 1)} kWc, la production totale attendue est de {fmt(total)} kWh"
            if a_ic:
                phrase += f" (fourchette prudente {fmt(total_bas)} à {fmt(total_haut)} kWh)"
            lignes.append(phrase + f", soit {fmt(total / len(pts))} kWh par jour en moyenne.")
            lignes.append(f"Jour le plus productif : {date_fr(jmax['date'])} ({fmt(jmax['prevision'], 2)} kWh/kWc, "
                          f"{fmt(jmax['prevision'] * kwc)} kWh) ; le plus faible : {date_fr(jmin['date'])} "
                          f"({fmt(jmin['prevision'], 2)} kWh/kWc).")
            if p.get("conso_kwh_jour"):
                besoin = p["conso_kwh_jour"] * len(pts)
                lignes.append(f"Avec une consommation de {fmt(p['conso_kwh_jour'])} kWh par jour, la production couvrirait "
                              f"environ {fmt(min(100 * total / besoin, 999), 0)} % des besoins sur la période "
                              f"(bilan en énergie, sans tenir compte des heures de consommation).")
        else:
            lux = self.lux[p["site"]][np.minimum(pd.DatetimeIndex([x["date"] for x in pts]).dayofyear, 365) - 1].mean()
            lignes.append(f"Irradiation horizontale moyenne attendue : {fmt(total / len(pts), 2)} kWh/m² par jour "
                          f"(jour le plus lumineux : {date_fr(jmax['date'])}, {fmt(jmax['prevision'], 2)} kWh/m² ; le plus "
                          f"sombre : {date_fr(jmin['date'])}, {fmt(jmin['prevision'], 2)} kWh/m²).")
            lignes.append(f"En cette saison, la lumière naturelle extérieure dépasse 10 000 lux environ {fmt(lux)} heures "
                          f"par jour à {info['ville']} (normale 2005-2020).")
        unite_tot = "kWh" if var == "pv_kwh_kwc" else "kWh/m²"
        if abs(ecart) < 1:
            lignes.append(f"La prévision est proche de la normale saisonnière ({fmt(normale)} {unite_tot} sur la période, "
                          f"écart inférieur à 1 %).")
        else:
            lignes.append(f"Par rapport à la normale saisonnière ({fmt(normale)} {unite_tot} sur la période), la prévision "
                          f"est {'supérieure' if ecart >= 0 else 'inférieure'} de {fmt(abs(ecart), 0)} %.")
        if mae_ref is not None:
            lignes.append(f"Fiabilité : sur la période de test 2022-2023, ce modèle s'est trompé en moyenne de "
                          f"{fmt(mae_ref, 2)} {unite_j} par jour à {info['ville']} (erreur absolue moyenne à 1-7 jours).")
        if p["hors_donnees"]:
            lignes.append("Attention : l'origine est postérieure aux données PVGIS (fin 2023) ; les jours non saisis sont "
                          "remplacés par la normale saisonnière.")
        if p["valeurs_saisies"]:
            lignes.append(f"Les {p['valeurs_saisies']} dernières valeurs proviennent de votre saisie.")
        return {"total": round(total, 3), "total_bas": None if total_bas is None else round(total_bas, 3),
                "total_haut": None if total_haut is None else round(total_haut, 3), "total_normale": round(normale, 3),
                "ecart_normale_pct": round(ecart, 1), "mae_test_modele": mae_ref, "reponse": " ".join(lignes)}


def metriques_etude() -> list[dict]:
    """Tableau comparatif des modèles produit par le notebook (resultats/py_metriques.csv)."""
    f = RESULTATS / "py_metriques.csv"
    if not f.exists():
        return []
    t = pd.read_csv(f)
    h = pd.read_csv(RESULTATS / "py_rmse_par_horizon.csv", index_col=0)
    out = []
    for _, r in t.iterrows():
        couv = r["couverture IC 95 % (%)"]
        out.append({"modele": r["modèle"], "information": r["information"], "famille": r["famille"],
                    "rmse": float(r["RMSE"]), "mae": float(r["MAE"]), "mape_pct": float(r["MAPE (%)"]),
                    "couverture_ic95_pct": None if pd.isna(couv) else float(couv),
                    "nb_parametres": int(r["nb paramètres"]),
                    "rmse_par_horizon": [float(v) for v in h.loc[r["modèle"]].to_numpy()]})
    return out


def catalogue() -> dict:
    cat = json.loads((RACINE / "data" / "catalogue_datasets.json").read_text(encoding="utf-8"))
    liens_f = RACINE / "sources" / "liens_rapport_solarvision.json"
    liens = json.loads(liens_f.read_text(encoding="utf-8")) if liens_f.exists() else []
    return {"jeux": [{k: c.get(k) for k in ("fichier", "description", "theme", "pays", "lignes", "colonnes", "periode",
                                            "taille_ko", "valeurs_manquantes_pct", "variables_explicatives", "conforme")}
                     | {"variables": [{"nom": v["nom"], "unite": v["unite"], "description": v["description"]}
                                      for v in c["variables"]]}
                     for c in cat],
            "liens": [{k: l.get(k, "") for k in ("url", "categorie", "statut", "titre", "usage")} for l in liens]}
