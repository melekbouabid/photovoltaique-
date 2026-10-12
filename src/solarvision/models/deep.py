"""Réseaux récurrents (LSTM, GRU) : par ville, puis un LSTM global entraîné sur toutes les villes.

Choix de conception, repris de l'étude historique et justifiés par la validation glissante :
- **cible = écart à la normale saisonnière**, divisé par son écart-type : le réseau part de la
  climatologie et n'apprend que la correction ;
- **fenêtre de 14 jours** : la météo ne persiste qu'un à deux jours, une fenêtre plus longue n'apporte rien ;
- **prévision directe des 7 jours** en une seule sortie ;
- **une couche de 64 unités et un dropout de 0,1** : peu de signal, donc un petit réseau régularisé ;
- **arrêt anticipé** sur une validation chronologique (la dernière année de l'apprentissage) ;
- normalisation avec les statistiques de l'apprentissage seulement ;
- deux scénarios séparés : ex ante (rien du futur) et ex post (météo observée des 7 jours visés).
Les réseaux sont entraînés une fois sur l'apprentissage : ils ne sont pas réajustés tous les 30 jours,
mais chaque prévision utilise les 14 derniers jours observés avant son origine.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from solarvision.config import load_params
from solarvision.models.protocol import CitySeries, horizons, origins, to_long
from solarvision.models.train import EX_ANTE, EX_POST, data_dir, load_city, reports_dir

SEQUENCE_WEATHER = ["nebulosite_pct", "t2m_moy_c", "humidite_pct", "precipitation_mm", "aerosols_aod"]
TARGET_DAY_WEATHER = ["nebulosite_pct", "nebulosite_nasa_pct", "precipitation_mm", "humidite_pct",
                      "amplitude_thermique_c", "aerosols_aod", "t2m_moy_c"]
VALIDATION_DAYS = 365          # dernière année de l'apprentissage, réservée à l'arrêt anticipé


def set_seed(seed: int) -> None:
    """Résultats reproductibles : même graine, calcul déterministe, sur processeur."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.use_deterministic_algorithms(True)


class CityArrays:
    """Tableaux d'une ville, normalisés avec les statistiques de l'apprentissage seulement."""

    def __init__(self, series: CitySeries, technology: str):
        frame, n_train = series.frame, series.n_train
        self.series, self.technology, self.n_train, self.n = series, technology, n_train, series.n
        self.values = frame[f"pv_{technology}_kwh_kwc"].to_numpy(float)
        self.normal = frame[f"normale_{technology}"].to_numpy(float)
        anomaly = self.values - self.normal
        self.scale = float(anomaly[:n_train].std())                  # écart-type de l'écart à la normale, sur l'apprentissage
        angle = 2 * np.pi * frame["jour_annee"].to_numpy() / 365.25

        def standardize(columns: list[str]) -> np.ndarray:
            x = frame[[f"expost_{c}" for c in columns]].to_numpy(float)
            if "precipitation_mm" in columns:                        # la pluie est très asymétrique : on la compresse
                k = columns.index("precipitation_mm")
                x[:, k] = np.log1p(x[:, k])
            mean, std = np.nanmean(x[:n_train], axis=0), np.nanstd(x[:n_train], axis=0)
            return np.nan_to_num((x - mean) / np.where(std > 0, std, 1.0))   # une valeur manquante vaut la moyenne

        self.sequence = np.column_stack([anomaly / self.scale, standardize(SEQUENCE_WEATHER), np.sin(angle), np.cos(angle)])
        self.target_weather = standardize(TARGET_DAY_WEATHER)
        self.target = anomaly / self.scale
        self.season = np.column_stack([np.sin(angle), np.cos(angle)])

    def windows(self, positions: np.ndarray, window: int, ex_post: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Pour chaque origine : les `window` derniers jours, les entrées statiques, et les 7 cibles."""
        h = horizons()
        seq = self.sequence[positions[:, None] - np.arange(window - 1, -1, -1)[None, :]]
        static = self.season[positions]
        if ex_post:
            future = self.target_weather[positions[:, None] + h[None, :]].reshape(len(positions), -1)
            static = np.concatenate([static, future], axis=1)
        return seq.astype("float32"), static.astype("float32"), self.target[positions[:, None] + h[None, :]].astype("float32")

    def training_positions(self, window: int, end: int | None = None) -> np.ndarray:
        """Origines dont les 7 cibles sont dans l'apprentissage (ou avant `end`)."""
        end = self.n_train if end is None else end
        return np.arange(window - 1, end - int(horizons().max()))

    def to_production(self, scaled: np.ndarray, positions: np.ndarray) -> np.ndarray:
        """Retour à l'unité d'origine : normale du jour visé plus écart prévu, borné à zéro."""
        return np.clip(self.normal[positions[:, None] + horizons()[None, :]] + scaled * self.scale, 0, None)


class Recurrent(nn.Module):
    """Une couche récurrente, puis une couche linéaire qui reçoit aussi les entrées statiques."""

    def __init__(self, cell: str, n_features: int, n_static: int, hidden: int, dropout: float, n_cities: int = 0):
        super().__init__()
        self.rnn = (nn.LSTM if cell == "lstm" else nn.GRU)(n_features, hidden, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        # Modèle global : un petit vecteur appris par ville lui permet d'ajuster sa réponse au climat local.
        self.embedding = nn.Embedding(n_cities, 4) if n_cities else None
        self.head = nn.Linear(hidden + n_static + (4 if n_cities else 0), len(horizons()))

    def forward(self, seq: torch.Tensor, static: torch.Tensor, city: torch.Tensor | None = None) -> torch.Tensor:
        out, _ = self.rnn(seq)
        parts = [self.dropout(out[:, -1]), static]
        if self.embedding is not None:
            parts.append(self.embedding(city))
        return self.head(torch.cat(parts, dim=1))


def _tensors(arrays: tuple) -> tuple:
    return tuple(None if a is None else torch.as_tensor(a) for a in arrays)


def fit(model: Recurrent, train: tuple, validation: tuple, max_epochs: int, seed: int) -> list[dict]:
    """Entraînement avec arrêt anticipé. Renvoie l'historique des pertes ; le modèle garde ses meilleurs poids."""
    cfg = load_params()["deep"]
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["learning_rate"])
    loss_fn = nn.MSELoss()
    x_seq, x_static, y, city = _tensors(train)
    v_seq, v_static, v_y, v_city = _tensors(validation)
    generator = torch.Generator().manual_seed(seed)
    best, best_state, wait, history = float("inf"), None, 0, []
    for epoch in range(1, max_epochs + 1):
        model.train()
        order, total = torch.randperm(len(y), generator=generator), 0.0
        for i in range(0, len(y), cfg["batch_size"]):
            batch = order[i:i + cfg["batch_size"]]
            optimizer.zero_grad()
            loss = loss_fn(model(x_seq[batch], x_static[batch], None if city is None else city[batch]), y[batch])
            loss.backward()
            optimizer.step()
            total += loss.item() * len(batch)
        model.eval()
        with torch.no_grad():
            val = loss_fn(model(v_seq, v_static, v_city), v_y).item()
        history.append({"epoque": epoch, "perte_apprentissage": total / len(y), "perte_validation": val})
        if val < best - 1e-5:
            best, wait = val, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
            if wait >= cfg["patience"]:                    # la validation ne progresse plus : on s'arrête
                break
    model.load_state_dict(best_state)
    for row in history:
        row["meilleure_epoque"] = int(np.argmin([r["perte_validation"] for r in history]) + 1)
    return history


def predict(model: Recurrent, seq: np.ndarray, static: np.ndarray, city: np.ndarray | None = None) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return model(*_tensors((seq, static, city))).numpy()


def _split_train_validation(arrays: CityArrays, window: int, end: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Découpe chronologique de l'apprentissage ; un écart de 7 jours évite qu'une cible serve des deux côtés."""
    positions = arrays.training_positions(window, end)
    cut = len(positions) - VALIDATION_DAYS
    return positions[: cut - int(horizons().max())], positions[cut:]


def train_one(arrays: CityArrays, cell: str, ex_post: bool, window: int, hidden: int, dropout: float,
              max_epochs: int, seed: int, end: int | None = None) -> tuple[Recurrent, list[dict]]:
    set_seed(seed)
    train_pos, val_pos = _split_train_validation(arrays, window, end)
    train, validation = arrays.windows(train_pos, window, ex_post), arrays.windows(val_pos, window, ex_post)
    model = Recurrent(cell, train[0].shape[2], train[1].shape[1], hidden, dropout)
    history = fit(model, (*train, None), (*validation, None), max_epochs, seed)
    return model, history


def run_city(city: str, fast: bool = False, force: bool = False) -> dict:
    """LSTM et GRU d'une ville, ex ante et ex post, sur la technologie de référence."""
    out = reports_dir(fast) / "forecasts_deep" / f"{city}.parquet"
    if out.exists() and not force:
        return {"ville": city, "statut": "déjà fait"}
    torch.set_num_threads(2)                               # plusieurs villes tournent en parallèle
    cfg, seed = load_params()["deep"], load_params()["seed"]
    technology = load_params()["pv"]["reference_technology"]
    series = load_city(city, data_dir(fast))
    arrays, pos = CityArrays(series, technology), origins(series.n, series.n_train)
    epochs = cfg["fast_max_epochs"] if fast else cfg["max_epochs"]
    parts, curves, t0 = [], [], time.time()
    for cell in ("lstm", "gru"):
        for ex_post in (False, True):
            name = f"{cell}_expost" if ex_post else cell
            model, history = train_one(arrays, cell, ex_post, cfg["window_days"], cfg["hidden_size"], cfg["dropout"], epochs, seed)
            seq, static, _ = arrays.windows(pos, cfg["window_days"], ex_post)
            parts.append(to_long(series, technology, name, EX_POST if ex_post else EX_ANTE,
                                 arrays.to_production(predict(model, seq, static), pos)))
            curves += [{"ville": city, "modele": name, **row} for row in history]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    pd.concat(parts, ignore_index=True).to_parquet(tmp, index=False)
    tmp.replace(out)
    pd.DataFrame(curves).to_csv(out.with_suffix(".curves.csv"), index=False)
    return {"ville": city, "statut": "fait", "duree_s": round(time.time() - t0, 1)}


def run_global(cities: list[str], fast: bool = False, force: bool = False) -> dict:
    """Un seul LSTM ex ante pour toutes les villes : chaque ville est ramenée à ses propres normales."""
    out_dir = reports_dir(fast) / "forecasts_deep"
    out = out_dir / "_lstm_global.parquet"
    if out.exists() and not force:
        return {"statut": "déjà fait"}
    torch.set_num_threads(8)
    cfg, seed = load_params()["deep"], load_params()["seed"]
    technology, window = load_params()["pv"]["reference_technology"], cfg["window_days"]
    set_seed(seed)
    t0 = time.time()
    loaded = [(i, load_city(c, data_dir(fast))) for i, c in enumerate(cities)]
    arrays = [(i, CityArrays(s, technology)) for i, s in loaded]
    train_parts, val_parts, val_positions = [], [], {}
    for i, a in arrays:
        train_pos, val_pos = _split_train_validation(a, window)
        val_positions[i] = val_pos
        for positions, bucket in ((train_pos, train_parts), (val_pos, val_parts)):
            bucket.append((*a.windows(positions, window, False), np.full(len(positions), i, dtype="int64")))
    stack = lambda parts: tuple(np.concatenate([p[k] for p in parts]) for k in range(4))   # noqa: E731
    train, validation = stack(train_parts), stack(val_parts)
    model = Recurrent("lstm", train[0].shape[2], train[1].shape[1], cfg["hidden_size"], cfg["dropout"], n_cities=len(cities))
    history = fit(model, train, validation, cfg["fast_max_epochs"] if fast else cfg["max_epochs"], seed)
    parts, margins = [], {}
    level = load_params()["deep"]["interval_level"]
    for i, a in arrays:
        # Intervalle conforme : la marge est le quantile des erreurs absolues sur l'année de validation, que le
        # réseau n'a pas apprise. Aucune hypothèse de loi ; la couverture réelle est ensuite mesurée sur le test.
        v_seq, v_static, _ = a.windows(val_positions[i], window, False)
        v_pred = a.to_production(predict(model, v_seq, v_static, np.full(len(val_positions[i]), i, dtype="int64")), val_positions[i])
        v_true = a.values[val_positions[i][:, None] + horizons()[None, :]]
        margin = np.quantile(np.abs(v_true - v_pred), level, axis=0)
        margins[a.series.city] = [float(m) for m in margin]
        pos = origins(a.n, a.n_train)
        seq, static, _ = a.windows(pos, window, False)
        forecast = a.to_production(predict(model, seq, static, np.full(len(pos), i, dtype="int64")), pos)
        parts.append(to_long(a.series, technology, "lstm_global", EX_ANTE, forecast,
                             np.clip(forecast - margin[None, :], 0, None), forecast + margin[None, :]))
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(parts, ignore_index=True).to_parquet(out, index=False)
    pd.DataFrame([{"ville": "toutes", "modele": "lstm_global", **row} for row in history]).to_csv(
        out_dir / "_lstm_global.curves.csv", index=False)
    torch.save({"state_dict": model.state_dict(), "villes": cities, "technologie": technology, "fenetre": window,
                "taille_cachee": cfg["hidden_size"], "dropout": cfg["dropout"], "n_features": int(train[0].shape[2]),
                "n_static": int(train[1].shape[1]), "marges_conformes": margins, "niveau_intervalle": level},
               out_dir / "_lstm_global.pt")
    info = {"statut": "fait", "villes": len(cities), "fenetres_apprentissage": int(len(train[2])),
            "epoques": len(history), "duree_s": round(time.time() - t0, 1)}
    (out_dir / "_lstm_global.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def walk_forward(city: str, fast: bool = False) -> pd.DataFrame:
    """Validation glissante sur l'apprentissage, pour choisir fenêtre, taille et dropout sans toucher au test.

    Trois plis à fenêtre croissante : on entraîne sur le début, on mesure sur l'année suivante, puis on
    avance. Jamais de k-fold aléatoire : il mélangerait le futur et le passé.
    """
    cfg, seed = load_params()["deep"], load_params()["seed"]
    technology = load_params()["pv"]["reference_technology"]
    arrays = CityArrays(load_city(city, data_dir(fast)), technology)
    folds = cfg["walk_forward_folds"]
    h_max = int(horizons().max())
    grid = [(7, 64, 0.1), (14, 32, 0.1), (14, 64, 0.0), (14, 64, 0.1), (14, 64, 0.3), (28, 64, 0.1)]
    rows = []
    for window, hidden, dropout in ([(14, 64, 0.1)] if fast else grid):
        for fold in range(folds):
            # Fin de l'entraînement du pli, puis une année d'évaluation juste après, sans chevauchement de cibles.
            end = arrays.n_train - (folds - fold) * 365
            model, history = train_one(arrays, "lstm", False, window, hidden, dropout,
                                       cfg["fast_max_epochs"] if fast else cfg["max_epochs"], seed, end=end)
            test_pos = np.arange(end + h_max - 1, end + 365 - h_max)
            seq, static, target = arrays.windows(test_pos, window, False)
            error = (predict(model, seq, static) - target) * arrays.scale
            rows.append({"ville": city, "fenetre": window, "taille_cachee": hidden, "dropout": dropout, "pli": fold + 1,
                         "fin_apprentissage": str(arrays.series.dates[end - 1].date()),
                         "rmse_validation": float(np.sqrt(np.mean(error ** 2))),
                         "rmse_climatologie": float(np.sqrt(np.mean((target * arrays.scale) ** 2))),
                         "epoques": len(history), "meilleure_epoque": history[0]["meilleure_epoque"]})
    table = pd.DataFrame(rows)
    out = reports_dir(fast) / "deep"
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / f"walk_forward_{city}.csv", index=False)
    return table


def collect_curves(fast: bool = False) -> Path:
    """Rassemble les courbes de perte de toutes les villes dans un seul fichier."""
    folder = reports_dir(fast) / "forecasts_deep"
    curves = pd.concat((pd.read_csv(f) for f in sorted(folder.glob("*.curves.csv"))), ignore_index=True)
    out = reports_dir(fast) / "deep"
    out.mkdir(parents=True, exist_ok=True)
    curves.to_csv(out / "loss_curves.csv", index=False)
    return out / "loss_curves.csv"
