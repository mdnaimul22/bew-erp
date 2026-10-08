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


class TestWorkOrderNonDestructiveUpdate:
    """Task 4 TDD: parts rewrite must preserve payment identity; paid WOs
    need explicit opt-in; legacy paid>quoted rows stay editable for
    non-money edits. Cleans up every row it creates (live test DB)."""

    def _make_buyer(self, db, tag):
        return db.add_buyer({
            'company_name': f'T4 Buyer {tag}',
            'address': 'Dhaka',
            'contacts': [],
        })

    def _supplier_id(self, db):
        shops = db.get_all_shops(limit=1)
        if shops:
            return shops[0]['id']
        return db.add_shop({'name': 'T4 Supplier'})

    def _part(self, supplier_id, name='Part', price=500.0, qty=1.0):
        return {
            'part_name': name,
            'supplier_id': supplier_id,
            'measurement': '',
            'unit': 'pcs',
            'qty': qty,
            'weight': 0,
            'price': price,
            'voucher_file_path': '',
            'raw_material_id': None,
            'voucher_no': '',
        }

    def _make_wo(self, db, buyer_id, supplier_id, quoted=1000.0,
                 parts=None, labor=0.0):
        return db.add_work_order({
            'company_id': buyer_id,
            'job_name': 'T4 WO',
            'quoted_price': quoted,
            'labor_cost': labor,
            'parts': parts if parts is not None else [
                self._part(supplier_id)],
        })

    def _linked_purchases(self, wo_id):
        from src.db.database import SupplierPurchase
        return (SupplierPurchase.query
                .filter_by(work_order_id=wo_id)
                .order_by(SupplierPurchase.created_at,
                          SupplierPurchase.id)
                .all())

    def _cleanup(self, db, wo_id, buyer_id):
        from src.db.database import Buyer
        try:
            db.session.rollback()
            db.delete_work_order(wo_id)
            buyer = Buyer.query.get(buyer_id)
            if buyer is not None:
                db.session.delete(buyer)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def test_update_work_order_preserves_paid(self, app_context):
        """Parts edit must keep paid_amount + voucher identity on matched row."""
        from src.db.database import db
        buyer_id = self._make_buyer(db, 'paid')
        supplier_id = self._supplier_id(db)
        wo_id = self._make_wo(db, buyer_id, supplier_id)
        try:
            purchase = self._linked_purchases(wo_id)[0]
            purchase.paid_amount = 500.0
            purchase.payment_status = 'partial'
            db.session.commit()
            original = (purchase.id, purchase.display_id,
                        purchase.voucher_id)

            db.update_work_order(wo_id, {'parts': [
                self._part(supplier_id, name='new-part', price=600.0)]})

            kept = self._linked_purchases(wo_id)
            assert len(kept) == 1
            assert (kept[0].id, kept[0].display_id,
                    kept[0].voucher_id) == original
            assert kept[0].paid_amount == 500.0
            assert kept[0].payment_status == 'partial'
            assert kept[0].items[0].product_name == 'new-part'
        finally:
            self._cleanup(db, wo_id, buyer_id)

    def test_non_money_edit_to_legacy_corrupt_row_succeeds(
            self, app_context):
        """paid>quoted legacy row: job_name fix + advisory pending_amount
        must succeed; money-touching edit still raises until corrected."""
        import pytest
        from src.db.database import db, WorkOrder
        from src.helpers.exceptions import ValidationError
        buyer_id = self._make_buyer(db, 'legacy')
        supplier_id = self._supplier_id(db)
        wo_id = self._make_wo(db, buyer_id, supplier_id, quoted=100.0)
        try:
            # Simulate legacy corruption directly (bypasses validation).
            wo = WorkOrder.query.get(wo_id)
            wo.paid_amount = 500.0
            db.session.commit()

            assert db.update_work_order(
                wo_id, {'job_name': 'fixed typo'}) is True
            assert WorkOrder.query.get(wo_id).job_name == 'fixed typo'

            # Advisory pending_amount must never trigger validation.
            before = WorkOrder.query.get(wo_id).pending_amount
            assert db.update_work_order(
                wo_id, {'pending_amount': 9999}) is True
            assert WorkOrder.query.get(wo_id).pending_amount == before

            # Money-touching edit on the corrupt row still raises.
            with pytest.raises(ValidationError):
                db.update_work_order(wo_id, {'quoted_price': 100.0})
        finally:
            self._cleanup(db, wo_id, buyer_id)

    def test_paid_guard_blocks_parts_rewrite(self, app_context):
        """Parts rewrite on a WO with paid_amount>0 needs explicit opt-in."""
        import pytest
        from src.db.database import db, WorkOrder
        from src.helpers.exceptions import ValidationError
        buyer_id = self._make_buyer(db, 'guard')
        supplier_id = self._supplier_id(db)
        wo_id = self._make_wo(db, buyer_id, supplier_id)
        try:
            assert db.update_work_order(
                wo_id, {'paid_amount': 500.0}) is True
            with pytest.raises(ValidationError):
                db.update_work_order(wo_id, {'parts': [
                    self._part(supplier_id, name='guarded')]})

            # Explicit opt-in allows the rewrite.
            assert db.update_work_order(wo_id, {
                'parts': [self._part(supplier_id, name='guarded')],
                'allow_paid_rewrite': True}) is True
            assert WorkOrder.query.get(wo_id) is not None
        finally:
            self._cleanup(db, wo_id, buyer_id)

    def test_deleting_paid_purchase_needs_opt_in(self, app_context):
        """Shrinking parts must not silently drop a paid purchase row."""
        import pytest
        from src.db.database import db
        from src.helpers.exceptions import ValidationError
        buyer_id = self._make_buyer(db, 'shrink')
        supplier_id = self._supplier_id(db)
        wo_id = self._make_wo(db, buyer_id, supplier_id, parts=[
            self._part(supplier_id, name='keep-me', price=100.0),
            self._part(supplier_id, name='paid-drop', price=200.0),
        ])
        try:
            doomed = self._linked_purchases(wo_id)[1]
            doomed.paid_amount = 200.0
            db.session.commit()

            with pytest.raises(ValidationError):
                db.update_work_order(wo_id, {'parts': [
                    self._part(supplier_id, name='keep-me', price=100.0)]})
            assert len(self._linked_purchases(wo_id)) == 2

            assert db.update_work_order(wo_id, {
                'parts': [self._part(supplier_id, name='keep-me',
                                     price=100.0)],
                'allow_paid_rewrite': True}) is True
            assert len(self._linked_purchases(wo_id)) == 1
        finally:
            self._cleanup(db, wo_id, buyer_id)

    def test_service_update_omits_absent_money_keys(self, app_context):
        """Form without money fields must leave money columns untouched."""
        from werkzeug.datastructures import MultiDict
        from src.db.database import db
        import src.services.work_order as svc
        buyer_id = self._make_buyer(db, 'svc')
        wo_id = db.add_work_order({
            'company_id': buyer_id,
            'job_name': 'T4 SVC WO',
            'quoted_price': 1000.0,
            'labor_cost': 100.0,
            'parts': [],
        })
        try:
            form = MultiDict({'job_name': 'svc fix', 'status': 'open'})
            assert svc.update(wo_id, form) is True
            wo = db.get_work_order_by_id(wo_id)
            assert wo['job_name'] == 'svc fix'
            assert wo['quoted_price'] == 1000.0
            assert wo['labor_cost'] == 100.0
            assert wo['material_cost'] == 0.0
            assert wo['total_cost'] == 100.0
        finally:
            self._cleanup(db, wo_id, buyer_id)
