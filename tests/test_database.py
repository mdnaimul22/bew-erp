"""Tests for src/db/database.py — all CRUD operations."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestDatabaseShops:
    """Verify shop CRUD operations against the live DB."""

    def test_get_all_shops_returns_list(self, app_context):
        from src.db.database import db
        shops = db.get_all_shops()
        assert isinstance(shops, (list, type(None)))

    def test_get_all_shops_with_limit(self, app_context):
        from src.db.database import db
        shops = db.get_all_shops(limit=5)
        assert isinstance(shops, list)
        assert len(shops) <= 5

    def test_get_shops_count(self, app_context):
        from src.db.database import db
        count = db.get_shops_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_get_shop_by_id_valid(self, app_context):
        from src.db.database import db
        shops = db.get_all_shops(limit=1)
        if shops:
            shop = db.get_shop_by_id(shops[0]['id'])
            assert shop is not None
            assert 'name' in shop

    def test_get_shop_by_id_invalid(self, app_context):
        from src.db.database import db
        shop = db.get_shop_by_id(999999)
        assert shop is None

    def test_search_shops(self, app_context):
        from src.db.database import db
        results = db.search_shops("test")
        assert isinstance(results, list)


class TestDatabaseCategories:
    """Verify category operations."""

    def test_get_all_categories(self, app_context):
        from src.db.database import db
        categories = db.get_all_categories()
        assert isinstance(categories, list)

    def test_get_shops_by_category(self, app_context):
        from src.db.database import db
        categories = db.get_all_categories()
        if categories:
            shops = db.get_shops_by_category(categories[0]['id'])
            assert isinstance(shops, list)


class TestDatabaseBuyers:
    """Verify buyer CRUD operations."""

    def test_get_all_buyers(self, app_context):
        from src.db.database import db
        buyers = db.get_all_buyers()
        assert isinstance(buyers, list)

    def test_get_buyer_by_id_invalid(self, app_context):
        from src.db.database import db
        buyer = db.get_buyer_by_id(999999)
        assert buyer is None

    def test_get_buyer_by_id_valid(self, app_context):
        from src.db.database import db
        buyers = db.get_all_buyers()
        if buyers:
            buyer = db.get_buyer_by_id(buyers[0]['id'])
            assert buyer is not None


class TestDatabaseInventory:
    """Verify inventory operations."""

    def test_get_all_inventory(self, app_context):
        from src.db.database import db
        items = db.get_all_inventory()
        assert isinstance(items, list)


class TestDatabasePurchases:
    """Verify purchase operations."""

    def test_get_all_supplier_purchases(self, app_context):
        from src.db.database import db
        purchases = db.get_all_supplier_purchases()
        assert isinstance(purchases, list)


class TestDatabaseSales:
    """Verify sales operations."""

    def test_get_all_sales(self, app_context):
        from src.db.database import db
        sales = db.get_all_sales()
        assert isinstance(sales, list)


class TestDatabaseWorkOrders:
    """Verify work order operations."""

    def test_get_all_work_orders(self, app_context):
        from src.db.database import db
        orders = db.get_all_work_orders()
        assert isinstance(orders, list)

    def test_get_work_order_by_id_invalid(self, app_context):
        from src.db.database import db
        order = db.get_work_order_by_id("nonexistent-uuid")
        assert order is None


class TestDatabaseTags:
    """Verify tag operations."""

    def test_get_all_tags(self, app_context):
        from src.db.database import db
        if hasattr(db, 'get_all_tags'):
            tags = db.get_all_tags()
            assert isinstance(tags, list)


class TestDatabaseInit:
    """Verify DB initialization."""

    def test_db_has_init_app(self):
        from src.db.database import db
        assert hasattr(db, 'init_app')

    def test_db_has_create_all(self):
        from src.db.database import db
        assert hasattr(db, 'create_all')

    def test_db_has_session(self, app_context):
        from src.db.database import db
        # Just verify no crash
        assert db is not None


class TestAtomicTransactions:
    """Task 2 TDD: failed multi-row writes must roll back, leaving original rows intact.

    Uses the live test DB via app_context (repo convention) but cleans up every
    row it creates in a finally block so the suite stays repeatable.
    """

    def _make_buyer(self, db, tag):
        return db.add_buyer({
            'company_name': f'T2 Buyer {tag}',
            'address': 'Dhaka',
            'contacts': [],
        })

    def _cleanup_sale(self, db, sale_id, buyer_id):
        from src.db.database import Sale, SaleItem, Buyer
        try:
            db.session.rollback()
            SaleItem.query.filter_by(sale_id=sale_id).delete()
            sale = Sale.query.get(sale_id)
            if sale is not None:
                db.session.delete(sale)
            buyer = Buyer.query.get(buyer_id)
            if buyer is not None:
                db.session.delete(buyer)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def test_update_sale_rollback_on_bad_item(self, app_context):
        """DELETE-items-then-fail must not leave the header with zero lines."""
        import pytest
        from src.db.database import db, SaleItem

        buyer_id = self._make_buyer(db, 'sale')
        sale_id = db.add_sale({
            'buyer_id': buyer_id,
            'items': [
                {'product_name': 'Rod', 'quantity': 2, 'unit_price': 100},
                {'product_name': 'Pipe', 'quantity': 1, 'unit_price': 50},
            ],
        })
        try:
            assert SaleItem.query.filter_by(sale_id=sale_id).count() == 2
            with pytest.raises(Exception):
                db.update_sale(sale_id, {
                    'buyer_id': buyer_id,
                    'items': [{'product_name': 'Bad', 'quantity': 'abc',
                               'unit_price': 10}],
                })
            assert SaleItem.query.filter_by(sale_id=sale_id).count() == 2
        finally:
            self._cleanup_sale(db, sale_id, buyer_id)

    def _cleanup_purchase(self, db, purchase_id):
        from src.db.database import SupplierPurchase, SupplierPurchaseItem
        try:
            db.session.rollback()
            SupplierPurchaseItem.query.filter_by(
                purchase_id=purchase_id).delete()
            purchase = SupplierPurchase.query.get(purchase_id)
            if purchase is not None:
                db.session.delete(purchase)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def test_update_purchase_rollback_on_bad_item(self, app_context):
        """Same delete-then-fail hazard on the purchase update path."""
        import pytest
        from src.db.database import db, SupplierPurchaseItem

        shops = db.get_all_shops(limit=1)
        if shops:
            supplier_id = shops[0]['id']
        else:
            supplier_id = db.add_shop({'name': 'T2 Supplier'})
        purchase_id = db.add_supplier_purchase({
            'supplier_id': supplier_id,
            'items': [
                {'product_name': 'Steel', 'quantity': 2,
                 'rate_per_unit': 100, 'total_amount': 200},
                {'product_name': 'Iron', 'quantity': 1,
                 'rate_per_unit': 50, 'total_amount': 50},
            ],
        })
        try:
            assert SupplierPurchaseItem.query.filter_by(
                purchase_id=purchase_id).count() == 2
            with pytest.raises(Exception):
                db.update_supplier_purchase(purchase_id, {
                    'items': [{'product_name': 'Bad', 'quantity': 'abc',
                               'rate_per_unit': 10}],
                })
            assert SupplierPurchaseItem.query.filter_by(
                purchase_id=purchase_id).count() == 2
        finally:
            self._cleanup_purchase(db, purchase_id)
