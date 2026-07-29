from __future__ import annotations

import uuid


def create_coin(client, **overrides) -> dict:
    payload = {
        "kind": "coin",
        "country_code": "hr",
        "denomination_value": "5",
        "currency_unit": "kuna",
        "year": 1994,
        "coin": {"weight_g": "7.45", "diameter_mm": "24.5", "material": "nickel-brass"},
    }
    payload.update(overrides)
    response = client.post("/api/items", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestCreate:
    def test_minimal_item_is_accepted(self, auth_client):
        response = auth_client.post("/api/items", json={"kind": "coin"})
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Untitled coin"
        assert body["status"] == "owned"
        assert body["quantity"] == 1

    def test_title_is_generated_from_identity_fields(self, auth_client):
        assert create_coin(auth_client)["title"] == "HR, 5 kuna, 1994"

    def test_country_code_is_upper_cased(self, auth_client):
        assert create_coin(auth_client)["country_code"] == "HR"

    def test_map_country_defaults_to_country(self, auth_client):
        assert create_coin(auth_client)["map_country_code"] == "HR"

    def test_coin_sub_table_is_persisted(self, auth_client):
        body = create_coin(auth_client)
        assert body["coin"]["material"] == "nickel-brass"
        assert body["banknote"] is None

    def test_banknote_sub_table_is_persisted(self, auth_client):
        response = auth_client.post(
            "/api/items",
            json={
                "kind": "banknote",
                "country_code": "HR",
                "denomination_value": "100",
                "currency_unit": "kuna",
                "year": 1993,
                "banknote": {"pick_number": "P-32", "serial_number": "A1234567", "printer": "G&D"},
            },
        )
        assert response.status_code == 201
        assert response.json()["banknote"]["pick_number"] == "P-32"
        assert response.json()["coin"] is None

    def test_unknown_kind_is_rejected(self, auth_client):
        assert auth_client.post("/api/items", json={"kind": "meteorite"}).status_code == 422

    def test_negative_quantity_is_rejected(self, auth_client):
        assert auth_client.post("/api/items", json={"kind": "coin", "quantity": -1}).status_code == 422

    def test_catalog_refs_are_deduplicated(self, auth_client):
        body = create_coin(
            auth_client,
            catalog_refs=[
                {"catalog": "KM", "number": "21"},
                {"catalog": "KM", "number": "21"},
                {"catalog": "Schon", "number": "5"},
            ],
        )
        assert len(body["catalog_refs"]) == 2

    def test_warnings_are_returned_with_the_item(self, auth_client):
        body = auth_client.post("/api/items", json={"kind": "coin"}).json()
        assert "missing_country" in body["warnings"]
        assert "no_images" in body["warnings"]

    def test_completeness_improves_with_more_data(self, auth_client):
        sparse = auth_client.post("/api/items", json={"kind": "coin"}).json()
        rich = create_coin(auth_client, grade_value="XF")
        assert rich["completeness"] > sparse["completeness"]


class TestReadUpdateDelete:
    def test_item_can_be_fetched(self, auth_client):
        created = create_coin(auth_client)
        assert auth_client.get(f"/api/items/{created['id']}").json()["id"] == created["id"]

    def test_missing_item_returns_404(self, auth_client):
        assert auth_client.get(f"/api/items/{uuid.uuid4()}").status_code == 404

    def test_malformed_uuid_returns_422(self, auth_client):
        assert auth_client.get("/api/items/not-a-uuid").status_code == 422

    def test_patch_updates_only_supplied_fields(self, auth_client):
        created = create_coin(auth_client)
        updated = auth_client.patch(f"/api/items/{created['id']}", json={"grade_value": "AU"}).json()
        assert updated["grade_value"] == "AU"
        assert updated["year"] == 1994
        assert updated["coin"]["material"] == "nickel-brass"

    def test_patch_can_change_the_sub_table(self, auth_client):
        created = create_coin(auth_client)
        updated = auth_client.patch(
            f"/api/items/{created['id']}", json={"coin": {"mintage": 250000}}
        ).json()
        assert updated["coin"]["mintage"] == 250000
        assert updated["coin"]["material"] == "nickel-brass"

    def test_acquisition_can_be_recorded(self, auth_client):
        created = create_coin(auth_client)
        updated = auth_client.patch(
            f"/api/items/{created['id']}",
            json={"acquisition": {"date": "2020-03-01", "price": "12.50", "currency": "EUR"}},
        ).json()
        assert updated["acquisition"]["currency"] == "EUR"

    def test_delete_removes_the_item(self, auth_client):
        created = create_coin(auth_client)
        assert auth_client.delete(f"/api/items/{created['id']}").status_code == 204
        assert auth_client.get(f"/api/items/{created['id']}").status_code == 404


class TestListing:
    def test_pagination_reports_totals(self, auth_client):
        for index in range(7):
            create_coin(auth_client, year=1990 + index)
        page = auth_client.get("/api/items", params={"page": 1, "page_size": 3}).json()
        assert page["total"] == 7
        assert len(page["rows"]) == 3

    def test_search_matches_the_title(self, auth_client):
        create_coin(auth_client)
        create_coin(auth_client, country_code="DE", currency_unit="mark", year=1950)
        rows = auth_client.get("/api/items", params={"q": "kuna"}).json()["rows"]
        assert len(rows) == 1

    def test_filter_by_kind(self, auth_client):
        create_coin(auth_client)
        auth_client.post("/api/items", json={"kind": "banknote", "country_code": "HR"})
        rows = auth_client.get("/api/items", params={"kind": "banknote"}).json()["rows"]
        assert len(rows) == 1
        assert rows[0]["kind"] == "banknote"

    def test_filter_by_country_is_case_insensitive(self, auth_client):
        create_coin(auth_client)
        assert auth_client.get("/api/items", params={"country": "hr"}).json()["total"] == 1

    def test_filter_by_missing_country(self, auth_client):
        create_coin(auth_client)
        auth_client.post("/api/items", json={"kind": "coin", "title": "Unplaced"})
        rows = auth_client.get("/api/items", params={"country": "none"}).json()["rows"]
        assert [r["title"] for r in rows] == ["Unplaced"]

    def test_filter_by_year_range(self, auth_client):
        create_coin(auth_client, year=1900)
        create_coin(auth_client, year=2000)
        rows = auth_client.get("/api/items", params={"year_from": 1950}).json()["rows"]
        assert len(rows) == 1
        assert rows[0]["year"] == 2000

    def test_filter_by_tag(self, auth_client):
        create_coin(auth_client, tags=["silver", "commemorative"])
        create_coin(auth_client, tags=["copper"])
        assert auth_client.get("/api/items", params={"tag": "silver"}).json()["total"] == 1

    def test_sorting_by_year_ascending(self, auth_client):
        create_coin(auth_client, year=2001)
        create_coin(auth_client, year=1971)
        rows = auth_client.get("/api/items", params={"sort": "year", "order": "asc"}).json()["rows"]
        assert [r["year"] for r in rows] == [1971, 2001]

    def test_unknown_sort_column_falls_back_safely(self, auth_client):
        create_coin(auth_client)
        assert auth_client.get("/api/items", params={"sort": "drop table"}).status_code == 200

    def test_page_size_is_capped(self, auth_client):
        assert auth_client.get("/api/items", params={"page_size": 5000}).status_code == 422

    def test_sql_injection_in_search_is_harmless(self, auth_client):
        create_coin(auth_client)
        response = auth_client.get("/api/items", params={"q": "'; DROP TABLE item; --"})
        assert response.status_code == 200
        assert auth_client.get("/api/items").json()["total"] == 1


class TestDuplicateHints:
    def test_similar_endpoint_finds_a_matching_coin(self, auth_client):
        first = create_coin(auth_client)
        create_coin(auth_client)
        similar = auth_client.get(f"/api/items/{first['id']}/similar").json()
        assert len(similar) == 1

    def test_serial_numbers_are_not_globally_unique(self, auth_client):
        payload = {
            "kind": "banknote",
            "country_code": "HR",
            "banknote": {"serial_number": "A1234567", "pick_number": "P-32"},
        }
        assert auth_client.post("/api/items", json=payload).status_code == 201
        assert auth_client.post("/api/items", json=payload).status_code == 201
