"""Prévision à la demande avec le modèle en production (scénario ex ante uniquement)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from solarvision.config import load_params
from solarvision.models.protocol import CitySeries, horizons
from solarvision.models.statistical import Z_95
from solarvision.serving.store import Store


class PredictionError(ValueError):
    """Demande impossible à satisfaire (ville, date ou modèle)."""


class Predictor:
    """Charge le modèle en production une fois, puis prévoit J+1 à J+7 depuis une date d'origine."""

    def __init__(self, store: Store):
        self.store = store
        self.model = store.production_model()
        self._loaded = None

    def _load(self):
        if self.model is None:
            raise PredictionError("aucun modèle en production : lancer python -m solarvision.cli register")
        if not self.model["sha256_verifie"]:
            raise PredictionError("le fichier du modèle ne correspond plus à son empreinte : prévision refusée")
        if self._loaded is None:
            path = self.model["dossier"] / self.model["fichier"]
            if self.model["nom"] == "lstm_global":
                import torch

                from solarvision.models.deep import Recurrent
                saved = torch.load(path, weights_only=False)
                network = Recurrent("lstm", saved["n_features"], saved["n_static"], saved["taille_cachee"], saved["dropout"],
                                    n_cities=len(saved["villes"]))
                network.load_state_dict(saved["state_dict"])
                self._loaded = {"network": network, **saved}
            else:
                self._loaded = json.loads(path.read_text(encoding="utf-8"))
        return self._loaded

    def origin_bounds(self, city: str) -> tuple[str, str]:
        """Premières et dernières dates d'origine acceptées (il faut 14 jours avant et 7 jours après)."""
        dates = pd.DatetimeIndex(self.store.city_frame(city)["date"])
        window = load_params()["deep"]["window_days"]
        return str(dates[window].date()), str(dates[-int(horizons().max()) - 1].date())

    def predict(self, city: str, origin: str | None = None, peak_kwp: float = 1.0) -> dict:
        if city not in self.store.available_cities:
            raise PredictionError(f"ville inconnue ou non traitée : {city}")
        loaded = self._load()
        frame = self.store.city_frame(city)
        dates = pd.DatetimeIndex(frame["date"])
        first, last = self.origin_bounds(city)
        origin = origin or last
        if not first <= origin <= last:
            raise PredictionError(f"date d'origine hors de la plage disponible ({first} à {last})")
        position = int(np.flatnonzero(dates == pd.Timestamp(origin))[0])
        technology, h = load_params()["pv"]["reference_technology"], horizons()
        targets = position + h
        normal = frame[f"normale_{technology}"].to_numpy()[targets]
        if self.model["nom"] == "lstm_global":
            from solarvision.models.deep import CityArrays, predict
            if city not in loaded["villes"]:
                raise PredictionError(f"{city} ne fait pas partie des villes du modèle en production")
            arrays = CityArrays(CitySeries(city, frame, self.store.splits[city]["n_train"]), technology)
            pos = np.array([position])
            seq, static, _ = arrays.windows(pos, loaded["fenetre"], False)
            index = np.array([loaded["villes"].index(city)], dtype="int64")
            forecast = arrays.to_production(predict(loaded["network"], seq, static, index), pos)[0]
            margin = np.asarray(loaded["marges_conformes"][city])
            interval = "conforme (quantile des erreurs de validation)"
        else:
            p = loaded["villes"][city]
            level = p["const"] + frame[loaded["termes_fourier"]].to_numpy() @ np.asarray(p["beta"])
            gap = frame[f"pv_{technology}_kwh_kwc"].to_numpy()[position] - level[position]
            forecast = np.clip(level[targets] + gap * p["phi"] ** h, 0, None)
            margin = Z_95 * np.sqrt(p["sigma2"] * (1 - p["phi"] ** (2 * h)) / (1 - p["phi"] ** 2))
            interval = "analytique (loi normale)"
        observed = frame[f"pv_{technology}_kwh_kwc"].to_numpy()[targets]
        history = frame.iloc[max(0, position - 20): position + 1]
        return {
            "ville": city, "technologie": technology, "scenario": "ex_ante", "origine": origin, "puissance_kwc": peak_kwp,
            "modele": {"nom": self.model["nom"], "version": self.model["version"]}, "type_intervalle": interval,
            "niveau_intervalle": 0.95, "unite": "kWh par jour",
            "historique": [{"date": str(d.date()), "observation": float(v * peak_kwp)}
                           for d, v in zip(history["date"], history[f"pv_{technology}_kwh_kwc"], strict=True)],
            "previsions": [{"date": str(dates[t].date()), "horizon": int(k), "prevision": float(f * peak_kwp),
                            "borne_basse": float(max(f - m, 0) * peak_kwp), "borne_haute": float((f + m) * peak_kwp),
                            "normale": float(n * peak_kwp), "observation": float(o * peak_kwp)}
                           for t, k, f, m, n, o in zip(targets, h, forecast, margin, normal, observed, strict=True)],
        }
