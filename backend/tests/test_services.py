from decimal import Decimal

from app.models import Acquisition, CatalogRef, Disposal, Item, ItemBanknote, ItemCoin, ItemImage
from app.services import build_title, collect_warnings, compute_completeness


def _item(**kwargs) -> Item:
    defaults = {"kind": "coin", "title": "", "status": "owned", "quantity": 1, "tags": [], "extra": {}}
    return Item(**{**defaults, **kwargs})


class TestBuildTitle:
    def test_uses_entity_denomination_and_year(self):
        item = _item(
            issuing_entity="Croatia",
            denomination_value=Decimal("5"),
            currency_unit="kuna",
            year=1994,
        )
        assert build_title(item) == "Croatia, 5 kuna, 1994"

    def test_falls_back_to_country_code(self):
        assert build_title(_item(country_code="HR", year=2001)) == "HR, 2001"

    def test_prefers_explicit_denomination_text(self):
        item = _item(country_code="DE", denomination_text="1/2 Mark", year=1905)
        assert build_title(item) == "DE, 1/2 Mark, 1905"

    def test_year_text_wins_over_numeric_year(self):
        item = _item(country_code="GB", year=1890, year_text="1890-1891")
        assert "1890-1891" in build_title(item)

    def test_empty_item_gets_placeholder(self):
        assert build_title(_item()) == "Untitled coin"
        assert build_title(_item(kind="banknote")) == "Untitled item"

    def test_decimal_denomination_is_not_scientific_notation(self):
        item = _item(country_code="US", denomination_value=Decimal("0.25"), currency_unit="dollar")
        assert "0.25" in build_title(item)


class TestCompleteness:
    def test_bare_item_scores_low(self):
        assert compute_completeness(_item()) == 0

    def test_never_exceeds_one_hundred(self):
        item = _item(
            country_code="HR",
            denomination_value=Decimal("1"),
            currency_unit="kuna",
            year=1995,
            grade_value="XF",
        )
        item.images = [ItemImage(role="obverse", original_path="a", status="ready"),
                       ItemImage(role="reverse", original_path="b", status="ready")]
        item.acquisition = Acquisition(price=Decimal("10"))
        item.catalog_refs = [CatalogRef(catalog="KM", number="20")]
        assert compute_completeness(item) == 100

    def test_two_images_score_higher_than_one(self):
        one = _item()
        one.images = [ItemImage(role="obverse", original_path="a", status="ready")]
        two = _item()
        two.images = [
            ItemImage(role="obverse", original_path="a", status="ready"),
            ItemImage(role="reverse", original_path="b", status="ready"),
        ]
        assert compute_completeness(two) > compute_completeness(one)

    def test_failed_images_do_not_count(self):
        item = _item()
        item.images = [ItemImage(role="obverse", original_path="a", status="failed")]
        assert compute_completeness(item) == 0

    def test_partial_identity_scores_partially(self):
        item = _item(country_code="HR", year=1994)
        assert 0 < compute_completeness(item) < 30


class TestWarnings:
    def test_flags_everything_missing(self):
        warnings = collect_warnings(_item())
        assert "missing_country" in warnings
        assert "missing_denomination" in warnings
        assert "missing_year" in warnings
        assert "no_images" in warnings

    def test_sold_without_disposal_is_flagged(self):
        item = _item(status="sold")
        assert "sold_without_disposal" in collect_warnings(item)

    def test_sold_with_disposal_is_clean(self):
        item = _item(status="sold")
        item.disposal = Disposal(price=Decimal("50"))
        assert "sold_without_disposal" not in collect_warnings(item)

    def test_coin_without_measurements(self):
        assert "coin_without_measurements" in collect_warnings(_item())

    def test_coin_with_weight_only_is_accepted(self):
        item = _item()
        item.coin = ItemCoin(weight_g=Decimal("5.5"))
        assert "coin_without_measurements" not in collect_warnings(item)

    def test_banknote_without_pick_or_serial(self):
        item = _item(kind="banknote")
        assert "banknote_without_pick_or_serial" in collect_warnings(item)

    def test_banknote_with_pick_is_accepted(self):
        item = _item(kind="banknote")
        item.banknote = ItemBanknote(pick_number="P-29")
        assert "banknote_without_pick_or_serial" not in collect_warnings(item)

    def test_warnings_are_advisory_not_exceptions(self):
        assert isinstance(collect_warnings(_item()), list)
