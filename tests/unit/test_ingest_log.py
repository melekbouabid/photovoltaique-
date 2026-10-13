"""Journal des échecs de la collecte : une exécution partielle ne doit pas effacer les échecs des autres villes."""
from __future__ import annotations

from solarvision.data.ingest import merge_failures

OLD = [{"ville": "gafsa", "source": "open_meteo"}, {"ville": "palma", "source": "open_meteo"}]


def test_failures_of_cities_not_retried_are_kept():
    # On relance la collecte sur trois autres villes, sans échec : les deux échecs anciens doivent rester.
    assert merge_failures(OLD, [], {"paris", "tunis", "madrid"}, {"paris", "tunis", "madrid"}) == OLD


def test_a_city_that_becomes_complete_leaves_the_log():
    assert merge_failures(OLD, [], {"gafsa"}, {"gafsa"}) == [OLD[1]]


def test_a_city_that_fails_again_is_replaced_not_duplicated():
    again = [{"ville": "gafsa", "source": "open_meteo", "erreur": "quota"}]
    assert merge_failures(OLD, again, {"gafsa", "palma"}, {"palma"}) == again
