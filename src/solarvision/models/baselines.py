"""Modèles de référence : tout modèle plus compliqué doit d'abord battre ces deux-là."""
from __future__ import annotations

import numpy as np

from solarvision.models.protocol import horizons


def persistence(values: np.ndarray, origin_positions: np.ndarray) -> np.ndarray:
    """Persistance : les sept jours suivants ressemblent au dernier jour observé."""
    return np.repeat(np.asarray(values)[origin_positions][:, None], len(horizons()), axis=1)


def climatology(normal: np.ndarray, origin_positions: np.ndarray) -> np.ndarray:
    """Climatologie : la normale saisonnière du jour visé, calculée sur l'apprentissage seulement."""
    return np.asarray(normal)[origin_positions[:, None] + horizons()[None, :]]
