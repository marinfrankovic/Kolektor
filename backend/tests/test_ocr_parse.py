"""Field suggestion parsing. Runs without the tesseract binary."""

from __future__ import annotations

import pytest

from app.imaging.ocr import parse_suggestions


def values(suggestions, field):
    return [s["value"] for s in suggestions if s["field"] == field]


class TestYear:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("REPUBLIKA HRVATSKA 1994", 1994),
            ("5 KUNA 2020", 2020),
            ("ANNO 1789 LIBERTAS", 1789),
            ("1 EURO 2023 ITALIA", 2023),
        ],
    )
    def test_plausible_years_are_extracted(self, text, expected):
        assert expected in values(parse_suggestions(text, "coin"), "year")

    @pytest.mark.parametrize("text", ["SERIAL 9821 A", "PICK 1234", "VALUE 0500"])
    def test_implausible_numbers_are_not_years(self, text):
        assert not values(parse_suggestions(text, "coin"), "year")


class TestCurrency:
    @pytest.mark.parametrize(
        ("text", "unit"),
        [
            ("5 KUNA", "kuna"),
            ("20 LIPA", "lipa"),
            ("100 DINARA", "dinar"),
            ("50 PARA", "para"),
            ("500 FORINT", "forint"),
            ("2 ZLOTE", "zloty"),
            ("10 KORUN CESKYCH", "koruna"),
            ("1 EURO", "euro"),
        ],
    )
    def test_currency_units_are_recognised(self, text, unit):
        assert unit in values(parse_suggestions(text, "coin"), "currency_unit")

    def test_matching_ignores_diacritics(self):
        assert "kuna" in values(parse_suggestions("PET KUNÂ", "coin"), "currency_unit")

    def test_matching_ignores_case(self):
        assert "kuna" in values(parse_suggestions("pet kuna", "coin"), "currency_unit")


class TestCountry:
    @pytest.mark.parametrize(
        ("text", "code"),
        [
            ("REPUBLIKA HRVATSKA", "HR"),
            ("SOCIJALISTICKA FEDERATIVNA REPUBLIKA JUGOSLAVIJA", "RS"),
            ("HELVETIA 1968", "CH"),
            ("BUNDESREPUBLIK DEUTSCHLAND", "DE"),
        ],
    )
    def test_country_hints_map_to_iso_codes(self, text, code):
        assert code in values(parse_suggestions(text, "coin"), "country_code")

    def test_unknown_legend_yields_no_country(self):
        assert not values(parse_suggestions("QQQQ ZZZZ", "coin"), "country_code")


class TestDenomination:
    def test_denomination_value_is_extracted(self):
        assert "5" in values(parse_suggestions("5 KUNA 1994", "coin"), "denomination_value")

    def test_large_denomination_is_extracted(self):
        assert "1000" in values(parse_suggestions("1000 DINARA", "banknote"), "denomination_value")


class TestSerialNumbers:
    def test_banknote_serial_is_suggested(self):
        assert values(parse_suggestions("A1234567 100 KUNA", "banknote"), "banknote.serial_number")

    def test_serial_is_not_suggested_for_coins(self):
        assert not values(parse_suggestions("A1234567", "coin"), "banknote.serial_number")


class TestShape:
    def test_empty_text_yields_nothing(self):
        assert parse_suggestions("", "coin") == []
        assert parse_suggestions("   \n\t ", "coin") == []

    def test_suggestions_have_the_expected_keys(self):
        for suggestion in parse_suggestions("REPUBLIKA HRVATSKA 5 KUNA 1994", "coin"):
            assert set(suggestion) == {"field", "value", "confidence", "source"}
            assert 0.0 <= suggestion["confidence"] <= 1.0
            assert suggestion["source"] == "ocr"

    def test_no_field_is_suggested_twice(self):
        suggestions = parse_suggestions("REPUBLIKA HRVATSKA 5 KUNA 1994", "coin")
        fields = [s["field"] for s in suggestions]
        assert len(fields) == len(set(fields))

    def test_noise_does_not_crash_the_parser(self):
        assert isinstance(parse_suggestions("###@@@ ..-- \x00 ??", "banknote"), list)
