"""Registre de modèles : versions, règle de promotion, retour arrière, contrôle d'intégrité."""
from __future__ import annotations

import pytest

from solarvision.mlops import registry


@pytest.fixture
def temp_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY", tmp_path / "registry")
    monkeypatch.setattr(registry, "CURRENT", tmp_path / "registry" / "current.json")
    return tmp_path


def _metrics(rmse: float, climatology: float = 1.10, dates: str = "2022-02-06 / 2023-12-31") -> dict:
    return {"technologie": "crystSi", "villes": 3, "dates_test": dates, "rmse_moyen": rmse,
            "rmse_climatologie_moyen": climatology, "gain_moyen_pct": 100 * (1 - rmse / climatology), "villes_gagnees": 3}


def _register(tmp_path, name: str, rmse: float, **kwargs) -> str:
    artifact = tmp_path / f"{name}.bin"
    artifact.write_bytes(f"{name}-{rmse}".encode())
    return registry.register(name, artifact, _metrics(rmse, **kwargs), "modèle de test", {"mode": "test"}).name


def test_versions_increase_and_files_are_written(temp_registry):
    assert _register(temp_registry, "a", 1.05) == "1.0.0"
    assert _register(temp_registry, "a", 1.04) == "1.1.0"
    folder = registry.REGISTRY / "a" / "1.1.0"
    assert {p.name for p in folder.iterdir()} == {"model.bin", "manifest.json", "metrics.json", "model_card.md"}
    assert "Limites et risques" in (folder / "model_card.md").read_text(encoding="utf-8")


def test_a_model_that_does_not_beat_climatology_is_refused(temp_registry):
    version = _register(temp_registry, "weak", 1.12)
    with pytest.raises(registry.PromotionRefused, match="climatologie"):
        registry.promote("weak", version)
    assert registry.current() is None


def test_promotion_requires_beating_the_production_version(temp_registry):
    registry.promote("a", _register(temp_registry, "a", 1.05))
    worse = _register(temp_registry, "b", 1.07)                              # bat la climatologie, pas la production
    with pytest.raises(registry.PromotionRefused, match="production"):
        registry.promote("b", worse)
    better = _register(temp_registry, "b", 1.03)
    pointer = registry.promote("b", better)
    assert (pointer["nom"], pointer["version"]) == ("b", better)
    assert pointer["historique"][-1]["nom"] == "a"


def test_promotion_is_refused_when_test_dates_differ(temp_registry):
    registry.promote("a", _register(temp_registry, "a", 1.05))
    other = _register(temp_registry, "b", 1.00, dates="2021-01-01 / 2021-12-31")
    with pytest.raises(registry.PromotionRefused, match="comparaison impossible"):
        registry.promote("b", other)


def test_rollback_restores_the_previous_version(temp_registry):
    first = _register(temp_registry, "a", 1.05)
    registry.promote("a", first)
    registry.promote("b", _register(temp_registry, "b", 1.03))
    pointer = registry.rollback()
    assert (pointer["nom"], pointer["version"]) == ("a", first)
    assert pointer["remplace"]["nom"] == "b"
    with pytest.raises(RuntimeError, match="aucune version précédente"):
        registry.rollback()


def test_a_tampered_model_file_is_detected(temp_registry):
    version = _register(temp_registry, "a", 1.05)
    registry.verify("a", version)
    (registry.REGISTRY / "a" / version / "model.bin").write_bytes(b"fichier modifie")
    with pytest.raises(registry.IntegrityError):
        registry.verify("a", version)
    with pytest.raises(registry.IntegrityError):
        registry.promote("a", version)
