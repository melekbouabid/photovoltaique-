"""Parcours rapide de bout en bout (3 villes). Long : lancé seulement avec `pytest -m slow`."""
from __future__ import annotations

import subprocess
import sys

import pytest

from solarvision.config import DATA, MODELS, REPORTS, ROOT


@pytest.mark.slow
def test_fast_pipeline_runs_from_ingestion_to_monitoring():
    result = subprocess.run([sys.executable, "-m", "solarvision.cli", "pipeline", "--fast", "--workers", "3"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    expected = [DATA / "fast" / "processed" / "panel_journalier.parquet", DATA / "fast" / "manifest.yaml",
                REPORTS / "fast" / "metrics_tidy.csv", REPORTS / "fast" / "dm_tests.csv", REPORTS / "fast" / "synthese_ville.csv",
                REPORTS / "fast" / "tech_recommendation.csv", REPORTS / "fast" / "economics_by_city.csv",
                REPORTS / "fast" / "monitoring" / "summary.json", MODELS / "registry_fast" / "current.json"]
    missing = [str(p.relative_to(ROOT)) for p in expected if not p.exists()]
    assert not missing, f"sorties absentes après le parcours rapide : {missing}"
