"""Tests for src/services — business logic layer."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestShopService:
    """Verify shop service functions."""

    def test_list_all(self, app_context):
        import src.services.shop as svc
        shops, total = svc.list_all(limit=5)
        assert isinstance(shops, list)
        assert isinstance(total, int)

    def test_get_categories(self, app_context):
        import src.services.shop as svc
        cats = svc.get_categories()
        assert isinstance(cats, list)

    def test_search_empty(self, app_context):
        import src.services.shop as svc
        result = svc.search("")
        assert result == []

    def test_get_nonexistent(self, app_context):
        import src.services.shop as svc
        from src.helpers.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            svc.get(999999)

    def test_create_validation(self, app_context):
        """Creating shop without name should raise ValidationError."""
        import src.services.shop as svc
        from src.helpers.exceptions import ValidationError
        from werkzeug.datastructures import MultiDict
        with pytest.raises(ValidationError):
            svc.create(MultiDict({'name': '', 'category_id': '1'}))


class TestBuyerService:
    """Verify buyer service functions."""

    def test_list_all(self, app_context):
        import src.services.buyer as svc
        result = svc.list_all()
        assert isinstance(result, list)

    def test_get_nonexistent(self, app_context):
        import src.services.buyer as svc
        from src.helpers.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            svc.get(999999)

    def test_list_all_nonexistent_query_returns_empty(self, app_context):
        """Searching for a non-existent buyer query must return [] rather than all buyers."""
        import src.services.buyer as svc
        result = svc.list_all("NonExistentBuyerQuery12345XYZ")
        assert result == []

    def test_execute_bayer_all_returns_tool_rows(self, app_context):
        import src.services.buyer as svc
        result = svc.execute({"tool_name": "bayer_all"})
        assert result["ok"] is True
        assert result["tool"] == "bayer_all"
        assert isinstance(result["buyers"], list)
        for row in result["buyers"]:
            assert {"buyer_id", "profile_id", "company_name", "address",
                    "primary_contact", "contacts_count"} <= set(row)

    def test_execute_bayer_search_requires_query(self, app_context):
        import src.services.buyer as svc
        from src.helpers.exceptions import ValidationError
        with pytest.raises(ValidationError):
            svc.execute({"tool_name": "bayer_search", "query": "   "})
        result = svc.execute({"tool_name": "bayer_search", "query": "NonExistentBuyerQuery12345XYZ"})
        assert result["buyers"] == []

    def test_execute_unknown_tool_rejected(self, app_context):
        import src.services.buyer as svc
        from src.helpers.exceptions import ValidationError
        with pytest.raises(ValidationError):
            svc.execute({"tool_name": "nope_nope"})

    def test_execute_bayer_profile_not_found(self, app_context):
        import src.services.buyer as svc
        from src.helpers.exceptions import NotFoundError, ValidationError
        with pytest.raises(NotFoundError):
            svc.execute({"tool_name": "bayer_profile", "buyer_id": 999999})
        with pytest.raises(ValidationError):
            svc.execute({"tool_name": "bayer_profile"})


class TestInventoryService:
    """Verify inventory service functions."""

    def test_list_all(self, app_context):
        import src.services.inventory as svc
        result = svc.list_all()
        assert isinstance(result, list)


class TestPurchaseService:
    """Verify purchase service functions."""

    def test_list_all(self, app_context):
        import src.services.purchase as svc
        result = svc.list_all()
        assert isinstance(result, list)

    def test_get_nonexistent(self, app_context):
        import src.services.purchase as svc
        result = svc.get("nonexistent-id")
        assert result is None


class TestSaleService:
    """Verify sale service functions."""

    def test_list_all(self, app_context):
        import src.services.sale as svc
        result = svc.list_all()
        assert isinstance(result, list)

    def test_get_nonexistent(self, app_context):
        import src.services.sale as svc
        result = svc.get(999999)
        assert result is None

    def test_execute_sale_all_returns_tool_rows(self, app_context):
        import src.services.sale as svc
        result = svc.execute({"tool_name": "sale_all"})
        assert result["ok"] is True
        assert isinstance(result["sales"], list)
        for row in result["sales"]:
            assert {"sale_id", "voucher_id", "buyer_id", "buyer_name",
                    "sale_date", "total_amount", "item_count"} <= set(row)

    def test_execute_sale_search_and_detail(self, app_context):
        import src.services.sale as svc
        from src.helpers.exceptions import NotFoundError, ValidationError
        with pytest.raises(ValidationError):
            svc.execute({"tool_name": "sale_search", "query": "  "})
        with pytest.raises(ValidationError):
            svc.execute({"tool_name": "sale_detail"})
        with pytest.raises(NotFoundError):
            svc.execute({"tool_name": "sale_detail", "sale_id": 999999})
        with pytest.raises(ValidationError):
            svc.execute({"tool_name": "nope"})
        result = svc.execute({"tool_name": "sale_search", "query": "ZZZ-no-match-123"})
        assert result["sales"] == []


class TestMoneyRecompute:
    """Task 3: server-side money recompute helpers (src/helpers/utils.py)."""

    def test_purchase_total_ignores_client_total(self):
        from src.helpers.utils import compute_totals
        total = compute_totals([{"quantity": 2, "rate": 100, "total_amount": 9999}])
        assert total == 200.0

    def test_pending_derived(self):
        import pytest as _pytest
        from src.helpers.utils import derive_pending
        from src.helpers.exceptions import ValidationError
        assert derive_pending(quoted=1000, paid=300) == 700.0
        with _pytest.raises(ValidationError):
            derive_pending(quoted=1000, paid=1500)

    def test_sale_total_ignores_client_total_price(self):
        from src.helpers.utils import compute_totals
        total = compute_totals([{"quantity": 3, "unit_price": 50, "total_price": 1}])
        assert total == 150.0

    def test_client_total_accepted_within_tolerance(self):
        from src.helpers.utils import compute_totals
        # Rounding-level agreement (<= 0.01) keeps the client value.
        total = compute_totals([{"quantity": 3, "rate": 10.003, "total_amount": 30.01}])
        assert total == 30.01

    def test_pending_rejects_negative_paid(self):
        import pytest as _pytest
        from src.helpers.utils import derive_pending
        from src.helpers.exceptions import ValidationError
        with _pytest.raises(ValidationError):
            derive_pending(quoted=1000, paid=-5)

    def test_sale_write_path_recomputes_total(self, app_context):
        """DB write path must ignore advisory client totals (cleanup after)."""
        from src.db.database import db
        buyers = db.get_all_buyers()
        if not buyers:
            pytest.skip("no buyers in dev DB")
        sale_id = None
        try:
            sale_id = db.add_sale({
                'buyer_id': buyers[0]['id'],
                'sale_date': None,
                'items': [
                    {'product_name': 'T3 probe', 'quantity': 2, 'unit_price': 100,
                     'total_price': 9999, 'weight': 0},
                ],
                'total_amount': 9999,
            })
            sale = db.get_sale_by_id(sale_id)
            assert sale['total_amount'] == 200.0
            assert sale['items'][0]['total_price'] == 200.0
        finally:
            if sale_id is not None:
                db.delete_sale(sale_id)


class TestWorkOrderService:
    """Verify work order service functions."""

    def test_list_all(self, app_context):
        import src.services.work_order as svc
        result = svc.list_all()
        assert isinstance(result, list)

    def test_create_validation(self, app_context):
        """Creating work order without company should raise ValidationError."""
        import src.services.work_order as svc
        from src.helpers.exceptions import ValidationError
        from werkzeug.datastructures import MultiDict
        with pytest.raises(ValidationError):
            svc.create(MultiDict({'company_id': ''}))

    def test_get_buyers(self, app_context):
        import src.services.work_order as svc
        buyers = svc.get_buyers()
        assert isinstance(buyers, list)

    def test_get_suppliers(self, app_context):
        import src.services.work_order as svc
        suppliers = svc.get_suppliers()
        assert isinstance(suppliers, list)

