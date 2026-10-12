"""Tests de l'API (pytest). Lancement, depuis app/backend : pytest -q"""
import pytest
from fastapi.testclient import TestClient

from main import app, demande_de_prevision


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:        # le bloc « with » déclenche le chargement des données et des modèles
        yield c


def test_sante_et_info(client):
    assert client.get("/api/health").json()["statut"] == "ok"
    info = client.get("/api/info").json()
    assert len(info["sites"]) == 9 and {s["pays"] for s in info["sites"]} == {"France", "Tunisie", "Espagne"}
    assert info["debut"] == "2005-01-01" and info["fin"] == "2023-12-31" and info["horizon_max"] == 10


def test_catalogue_au_moins_six_jeux(client):
    cat = client.get("/api/catalogue").json()
    noms = [j["fichier"].split("/")[-1] for j in cat["jeux"]]
    for pays in ("fr", "tn", "es"):
        assert f"{pays}_photovoltaique_journalier.csv" in noms and f"{pays}_eclairement_journalier.csv" in noms
    panel = next(j for j in cat["jeux"] if j["fichier"].endswith("panel_9_villes_journalier.csv"))
    assert panel["colonnes"] > 20
    assert any(l["categorie"] == "série temporelle" for l in cat["liens"])


def test_jeux_conformes(client):
    # Exigence du projet : chaque jeu de données a plus de 1 000 lignes et au moins 20 variables explicatives.
    jeux = client.get("/api/catalogue").json()["jeux"]
    assert len(jeux) == 14
    for j in jeux:
        assert j["lignes"] > 1000 and j["variables_explicatives"] >= 20 and j["conforme"], j["fichier"]
        assert len(j["variables"]) == j["colonnes"]


def test_telechargement_d_un_jeu(client):
    r = client.get("/donnees/pvgis_orientations_9_villes.csv")
    assert r.status_code == 200 and r.text.startswith("site,")
    assert client.get("/donnees/../../.env").status_code == 404        # seul data/datasets est exposé


def test_profil_horaire(client):
    r = client.get("/api/profil_horaire", params={"site": "tozeur", "mois": 6}).json()
    assert len(r["heures"]) == 24 and r["resume"]["production_jour_kwh_kwc"] > 4
    nuit, midi = r["heures"][0], max(r["heures"], key=lambda h: h["p_w_kwc"])
    assert nuit["p_w_kwc"] == 0 and 9 <= midi["heure"] <= 14
    assert client.get("/api/profil_horaire", params={"site": "rome"}).status_code == 422
    assert client.get("/api/profil_horaire", params={"mois": 13}).status_code == 422


def test_orientations(client):
    r = client.get("/api/orientations", params={"site": "tunis"}).json()
    assert len(r["scenarios"]) == 27 and sum(s["est_optimal"] for s in r["scenarios"]) == 1
    optimal = next(s for s in r["scenarios"] if s["est_optimal"])
    # Aucun scénario ne produit plus que la pente optimale plein sud ; chacun détaille ses 12 mois.
    assert all(s["e_an_kwh_kwc"] <= optimal["e_an_kwh_kwc"] + 0.5 and len(s["mensuel_kwh_kwc"]) == 12 for s in r["scenarios"])
    assert optimal["inclinaison"] == r["pente_optimale"]


def test_serie_et_profils(client):
    pts = client.get("/api/series", params={"site": "sfax", "debut": "2020-01-01", "fin": "2020-01-31"}).json()
    assert len(pts) == 31 and pts[0]["date"] == "2020-01-01"
    prof = client.get("/api/profils", params={"variable": "ghi_kwh_m2"}).json()
    assert len(prof) == 9 and all(len(p["mensuel"]) == 12 for p in prof)


def test_valeurs_recentes_dans_et_hors_donnees(client):
    v = client.get("/api/valeurs_recentes", params={"site": "tunis", "origine": "2023-06-30", "n": 14}).json()
    assert len(v) == 14 and v[-1]["date"] == "2023-06-30" and v[-1]["source"] == "données PVGIS"
    v = client.get("/api/valeurs_recentes", params={"site": "tunis", "origine": "2026-10-10", "n": 7}).json()
    assert {x["source"] for x in v} == {"normale saisonnière"}


@pytest.mark.parametrize("modele", ["lstm", "arima", "climatologie", "persistance"])
def test_prevision_dans_le_test(client, modele):
    r = client.post("/api/prevision", json={"site": "tunis", "origine": "2023-05-31", "modele": modele,
                                            "horizon": 7, "puissance_kwc": 3}).json()
    assert [p["horizon"] for p in r["previsions"]] == list(range(1, 8))
    assert all(p["observe"] is not None for p in r["previsions"]) and r["mae_prevision"] is not None
    if modele != "persistance":
        assert all(p["bas"] <= p["prevision"] <= p["haut"] for p in r["previsions"])
    # Le total est exprimé pour 3 kWc : trois fois la somme des prévisions par kWc.
    assert r["total"] == pytest.approx(3 * sum(p["prevision"] for p in r["previsions"]), rel=1e-3)
    assert "Tunis" in r["reponse"] and "kWc" in r["reponse"]


def test_prevision_au_dela_des_donnees_et_saisie(client):
    base = {"site": "madrid", "origine": "2026-10-10", "modele": "lstm", "horizon": 5}
    r = client.post("/api/prevision", json=base).json()
    assert r["hors_donnees"] and all(p["observe"] is None for p in r["previsions"])
    # Une semaine saisie très sombre doit faire baisser la prévision du lendemain.
    sombre = client.post("/api/prevision", json={**base, "valeurs_recentes": [0.5] * 14}).json()
    assert sombre["valeurs_saisies"] == 14
    assert sombre["previsions"][0]["prevision"] < r["previsions"][0]["prevision"]


def test_eclairement(client):
    r = client.post("/api/prevision", json={"site": "paris", "variable": "ghi_kwh_m2", "origine": "2023-12-20",
                                            "modele": "arima", "horizon": 10}).json()
    assert r["unite"] == "kWh/m²" and len(r["previsions"]) == 10 and "lux" in r["reponse"]


def test_erreurs(client):
    ok = {"site": "tunis", "origine": "2023-06-01"}
    assert client.post("/api/prevision", json={**ok, "origine": "2004-01-01"}).status_code == 422
    assert client.post("/api/prevision", json={**ok, "site": "rome"}).status_code == 422
    assert client.post("/api/prevision", json={**ok, "horizon": 30}).status_code == 422
    assert client.post("/api/prevision", json={**ok, "modele": "xgboost"}).status_code == 422
    assert client.post("/api/prevision", json={**ok, "valeurs_recentes": [-1.0]}).status_code == 422


def test_assistant_extractif(client):
    r = client.post("/api/assistant", json={"question": "Quelle ville a la plus forte production annuelle ?",
                                           "llm": False}).json()
    assert r["mode"] == "extractif" and r["sources"] and r["reponse"]


def test_assistant_sans_cle_groq(client, monkeypatch):
    # Sans clé, la rédaction par le LLM est demandée mais l'assistant se replie sur la réponse extractive.
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert client.get("/api/health").json()["llm"] == {"fournisseur": "Groq", "modele": "openai/gpt-oss-120b",
                                                      "cle_configuree": False}
    r = client.post("/api/assistant", json={"question": "Qu'est-ce que le test KPSS ?"}).json()
    assert r["mode"] == "extractif" and "stationn" in r["reponse"] and " | " not in r["reponse"]
    assert r["sources"][0]["titre"].endswith("Test KPSS")


def test_assistant_detecte_une_prevision(client):
    r = client.post("/api/assistant", json={"question": "Combien produira une installation de 5 kWc à Séville "
                                                        "les 3 prochains jours ?", "llm": False}).json()
    assert r["prevision"]["site"] == "seville" and r["prevision"]["horizon"] == 3
    assert r["prevision"]["puissance_kwc"] == 5


def test_detection_sans_ville():
    assert demande_de_prevision("Quelle est la prévision ?", None) is None
