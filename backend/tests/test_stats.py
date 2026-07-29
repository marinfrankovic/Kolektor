from __future__ import annotations


def add(client, **fields):
    payload = {"kind": "coin", "country_code": "HR"}
    payload.update(fields)
    response = client.post("/api/items", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestMap:
    def test_countries_are_aggregated_by_kind(self, auth_client):
        add(auth_client, country_code="HR")
        add(auth_client, country_code="HR", kind="banknote")
        add(auth_client, country_code="DE")

        by_code = {row["code2"]: row for row in auth_client.get("/api/stats/map").json()["countries"]}
        assert by_code["HR"]["coins"] == 1
        assert by_code["HR"]["banknotes"] == 1
        assert by_code["HR"]["total"] == 2
        assert by_code["DE"]["coins"] == 1

    def test_wishlist_items_do_not_colour_the_map(self, auth_client):
        add(auth_client, country_code="FR", status="wish")
        codes = {row["code2"] for row in auth_client.get("/api/stats/map").json()["countries"]}
        assert "FR" not in codes

    def test_historical_issuer_counts_towards_its_successor(self, auth_client):
        add(auth_client, country_code="HR", map_country_code="RS")
        codes = {row["code2"] for row in auth_client.get("/api/stats/map").json()["countries"]}
        assert "RS" in codes

    def test_coverage_uses_sovereign_states_only(self, auth_client):
        body = auth_client.get("/api/stats/map").json()
        assert body["covered"] == 0
        assert 190 <= body["sovereign_total"] <= 200

        add(auth_client, country_code="HR")
        assert auth_client.get("/api/stats/map").json()["covered"] == 1

    def test_territories_do_not_inflate_coverage(self, auth_client):
        add(auth_client, country_code="AQ")
        body = auth_client.get("/api/stats/map").json()
        assert body["covered"] == 0
    def test_continent_breakdown_is_returned(self, auth_client):
        add(auth_client, country_code="HR")
        assert auth_client.get("/api/stats/map").json()["by_continent"]

    def test_empty_collection_returns_an_empty_map(self, auth_client):
        body = auth_client.get("/api/stats/map").json()
        assert body["countries"] == []
        assert body["covered"] == 0


class TestSummary:
    def test_counts_items_and_pieces_separately(self, auth_client):
        add(auth_client, quantity=3)
        add(auth_client, quantity=1, kind="banknote")
        body = auth_client.get("/api/stats/summary").json()
        assert body["items"] == 2
        assert body["pieces"] == 4
        assert body["coins"] == 1
        assert body["banknotes"] == 1

    def test_year_range_is_reported(self, auth_client):
        add(auth_client, year=1918)
        add(auth_client, year=2024)
        body = auth_client.get("/api/stats/summary").json()
        assert body["year_min"] == 1918
        assert body["year_max"] == 2024

    def test_spend_is_grouped_by_currency(self, auth_client):
        first = add(auth_client)
        second = add(auth_client)
        auth_client.patch(
            f"/api/items/{first['id']}", json={"acquisition": {"price": "10.00", "currency": "EUR"}}
        )
        auth_client.patch(
            f"/api/items/{second['id']}", json={"acquisition": {"price": "5.50", "currency": "EUR"}}
        )
        spend = auth_client.get("/api/stats/summary").json()["spend_by_currency"]
        assert float(spend["EUR"]) == 15.5

    def test_average_completeness_is_between_zero_and_hundred(self, auth_client):
        add(auth_client)
        value = auth_client.get("/api/stats/summary").json()["average_completeness"]
        assert 0 <= value <= 100

    def test_country_count_is_distinct(self, auth_client):
        add(auth_client, country_code="HR")
        add(auth_client, country_code="HR")
        assert auth_client.get("/api/stats/summary").json()["countries"] == 1

    def test_empty_collection_summary_is_all_zeros(self, auth_client):
        body = auth_client.get("/api/stats/summary").json()
        assert body["items"] == 0
        assert body["pieces"] == 0
        assert body["year_min"] is None


class TestReference:
    def test_all_iso_countries_are_available(self, auth_client):
        countries = auth_client.get("/api/reference/countries").json()
        assert len(countries) == 249
        assert {"code2", "code3", "name", "continent"} <= set(countries[0])

    def test_historical_entities_are_available(self, auth_client):
        entities = auth_client.get("/api/reference/historical-entities").json()
        names = {entity["name"] for entity in entities}
        assert "Yugoslavia (SFR)" in names or any("Yugoslavia" in name for name in names)
        assert any("Austria-Hungary" in name for name in names)

    def test_entities_point_at_a_successor_state(self, auth_client):
        entities = auth_client.get("/api/reference/historical-entities").json()
        assert all(len(entity["successor_code2"]) == 2 for entity in entities if entity["successor_code2"])
