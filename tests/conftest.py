"""Éléments communs aux tests : où lire les données, quelles villes sont disponibles."""
from __future__ import annotations

from pathlib import Path

import pytest

from solarvision.config import DATA, load_cities


@pytest.fixture(scope="session")
def data_root() -> Path:
    """Dossier de données à tester : l'étude complète si elle existe, sinon le sous-ensemble rapide."""
    for root in (DATA, DATA / "fast"):
        if (root / "processed" / "tunis.csv").exists():
            return root
    pytest.skip("aucune table traitée : lancer python -m solarvision.cli ingest --fast")


@pytest.fixture(scope="session")
def processed_cities(data_root: Path) -> list[str]:
    return [c for c in load_cities() if (data_root / "processed" / f"{c}.csv").exists()]
