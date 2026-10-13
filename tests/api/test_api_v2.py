"""API /v1 et application multi-pages, testées sur le sous-ensemble rapide (3 villes)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from solarvision.config import DATA, MODELS, REPORTS
from solarvision.mlops import registry
from solarvision.serving.api import PAGES, create_app
from solarvision.serving.store import Store

FAST_DATA, FAST_REPORTS, FAST_REGISTRY = DATA / "fast", REPORTS / "fast", MODELS / "registry_fast"


@pytest.fixture(scope="module")
def client():
    needed = [FAST_DATA / "processed" / "panel_journalier.parquet", FAST_REPORTS / "metrics_wide.csv",
              FAST_REPORTS / "tech_recommendation.csv", FAST_REPORTS / "economics_by_city.csv", FAST_REGISTRY / "current.json"]
    if not all(p.exists() for p in needed):
        pytest.skip("parcours rapide incomplet : lancer python -m solarvision.cli pipeline --fast")
    previous = (registry.REGISTRY, registry.CURRENT)
    registry.use(FAST_REGISTRY)
    yield TestClient(create_app(Store(FAST_DATA, FAST_REPORTS)))
    registry.REGISTRY, registry.CURRENT = previous


def test_health_reports_a_verified_model(client):
    body = client.get("/health").json()
    assert body["statut"] == "ok" and body["villes_disponibles"] == 3
    assert body["modele"]["sha256_verifie"] is True
    assert {"nom", "version", "entraine_le", "donnees"} <= set(body["modele"])


def test_cities_and_models(client):
    cities = client.get("/v1/cities").json()
    assert {c["id"] for c in cities} == {"paris", "tunis", "madrid"}
    assert all(c["productible_crystSi"] > 800 for c in cities)
    models = client.get("/v1/models").json()
    assert models["production"]["nom"] and any(v["statut"] == "production" for v in models["versions"])


def test_predict_returns_seven_ex_ante_days_with_intervals(client):
    body = client.post("/v1/predict", json={"ville": "tunis", "origine": "2023-06-15", "puissance_kwc": 3}).json()
    assert body["scenario"] == "ex_ante" and len(body["previsions"]) == 7
    assert [p["horizon"] for p in body["previsions"]] == [1, 2, 3, 4, 5, 6, 7]
    assert body["previsions"][0]["date"] == "2023-06-16"
    for p in body["previsions"]:
        assert 0 <= p["borne_basse"] <= p["prevision"] <= p["borne_haute"]
        assert 0 < p["prevision"] < 3 * 8                                   # 3 kWc ne produisent pas 24 kWh un jour d'été


def test_predict_rejects_bad_requests(client):
    assert client.post("/v1/predict", json={"ville": "atlantide"}).status_code == 422
    assert client.post("/v1/predict", json={"ville": "tunis", "origine": "1999-01-01"}).status_code == 422
    assert client.post("/v1/predict", json={"ville": "tunis", "puissance_kwc": -1}).status_code == 422


def test_recommendation_and_economics(client):
    reco = client.get("/v1/recommend-tech", params={"ville": "tunis"}).json()
    assert reco["technologie_recommandee"] in {"crystSi", "CIS", "CdTe"} and len(reco["indicateurs"]) == 3
    assert client.get("/v1/recommend-tech", params={"ville": "atlantide"}).status_code == 404
    base = client.get("/v1/economics", params={"ville": "tunis"}).json()
    dearer = client.get("/v1/economics", params={"ville": "tunis", "prix_achat": 0.30}).json()
    assert "TODO_VERIFY" in base["avertissement"]
    assert dearer["cas_central"]["van_eur"] > base["cas_central"]["van_eur"]    # électricité plus chère : économies plus grandes
    assert base["simulation"]["van_eur_p10"] <= base["simulation"]["van_eur_p50"] <= base["simulation"]["van_eur_p90"]


@pytest.mark.parametrize("path", [p for p, _ in PAGES])
def test_every_page_loads_with_the_common_navigation(client, path):
    response = client.get(path)
    assert response.status_code == 200
    for href, label in PAGES:
        assert f'href="{href}"' in response.text and label in response.text


def test_ex_ante_and_ex_post_are_labelled(client):
    forecasts = client.get("/previsions", params={"ville": "tunis"}).text
    assert "ex ante" in forecasts and "ex post" in forecasts and "borne optimiste" in forecasts
    models = client.get("/modeles").text
    assert "ex ante (opérationnel)" in models and "ex post (météo observée, borne optimiste)" in models
    assert "TODO_VERIFY" in client.get("/economie").text
