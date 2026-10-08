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


class TestMergeSafeIdentity:
    """Task 6 TDD (RED first): merge-safe identity + additive constraint
    guards. Uses the live test DB via app_context (repo convention) and
    cleans up every row it creates in a finally block.

    Pre-flight ruling outcome: Sale/Buyer PKs stay Integer (changing PK
    type needs a table rebuild — rejected). Merge-safe identity rests on
    unique display_id + client_key idempotency.
    """

    def _make_buyer(self, db, tag):
        import uuid as _uuid
        return db.add_buyer({
            'company_name': f'T6 Buyer {tag} {_uuid.uuid4().hex[:6]}',
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

    def test_client_key_columns_exist(self, app_context):
        """Sale/SupplierPurchase expose client_key, incl. on legacy DBs."""
        from src.db.database import (
            db, Sale, SupplierPurchase, ensure_merge_safe_columns)
        ensure_merge_safe_columns()
        assert hasattr(Sale, 'client_key')
        assert hasattr(SupplierPurchase, 'client_key')
        cols = [r[1] for r in db.session.execute(
            db.text("PRAGMA table_info(sales)")).fetchall()]
        assert 'client_key' in cols
        cols = [r[1] for r in db.session.execute(
            db.text("PRAGMA table_info(supplier_purchases)")).fetchall()]
        assert 'client_key' in cols

    def test_duplicate_client_key_rejected_at_db(self, app_context):
        """The UNIQUE guard on client_key must reject a raw double-insert."""
        import uuid as _uuid
        import pytest
        from sqlalchemy.exc import IntegrityError
        from src.db.database import db, Sale, generate_id, ID_PREFIX_SALE
        buyer_id = self._make_buyer(db, 'uniq')
        key = f't6-uniq-{_uuid.uuid4().hex[:8]}'
        try:
            db.session.add(Sale(
                display_id=generate_id(ID_PREFIX_SALE),
                buyer_id=buyer_id, client_key=key))
            db.session.flush()
            db.session.add(Sale(
                display_id=generate_id(ID_PREFIX_SALE),
                buyer_id=buyer_id, client_key=key))
            with pytest.raises(IntegrityError):
                db.session.flush()
        finally:
            db.session.rollback()
            for row in Sale.query.filter_by(client_key=key).all():
                db.session.delete(row)
            db.session.commit()
            from src.db.database import Buyer
            buyer = Buyer.query.get(buyer_id)
            if buyer is not None:
                db.session.delete(buyer)
                db.session.commit()

    def test_add_sale_idempotent_same_client_key(self, app_context):
        """Lookup-or-create: same client_key returns the same row, once."""
        import uuid as _uuid
        from src.db.database import db, Sale
        buyer_id = self._make_buyer(db, 'idem')
        key = f't6-sale-{_uuid.uuid4().hex[:8]}'
        payload = {
            'buyer_id': buyer_id,
            'client_key': key,
            'items': [{'product_name': 'Rod', 'quantity': 2,
                       'unit_price': 100}],
        }
        sale_id = db.add_sale(dict(payload))
        try:
            again_id = db.add_sale(dict(payload))
            assert again_id == sale_id
            assert Sale.query.filter_by(client_key=key).count() == 1
        finally:
            from src.db.database import SaleItem
            db.session.rollback()
            for row in Sale.query.filter_by(client_key=key).all():
                SaleItem.query.filter_by(sale_id=row.id).delete()
                db.session.delete(row)
            db.session.commit()
            from src.db.database import Buyer
            buyer = Buyer.query.get(buyer_id)
            if buyer is not None:
                db.session.delete(buyer)
                db.session.commit()

    def test_add_purchase_idempotent_same_client_key(self, app_context):
        """Same lookup-or-create contract for supplier purchases."""
        import uuid as _uuid
        from src.db.database import db, SupplierPurchase
        shops = db.get_all_shops(limit=1)
        supplier_id = shops[0]['id'] if shops else db.add_shop(
            {'name': 'T6 Supplier'})
        key = f't6-pur-{_uuid.uuid4().hex[:8]}'
        payload = {
            'supplier_id': supplier_id,
            'client_key': key,
            'items': [{'product_name': 'Steel', 'quantity': 1,
                       'rate_per_unit': 50}],
        }
        purchase_id = db.add_supplier_purchase(dict(payload))
        try:
            again_id = db.add_supplier_purchase(dict(payload))
            assert again_id == purchase_id
            assert SupplierPurchase.query.filter_by(
                client_key=key).count() == 1
        finally:
            from src.db.database import SupplierPurchaseItem
            db.session.rollback()
            for row in SupplierPurchase.query.filter_by(
                    client_key=key).all():
                SupplierPurchaseItem.query.filter_by(
                    purchase_id=row.id).delete()
                db.session.delete(row)
            db.session.commit()

    def test_display_id_collision_retries(self, app_context):
        """A rewound id_sequences row (two machines, same DB file) must
        not blow up: the write retries with a fresh display_id."""
        from src.db.database import (
            db, Sale, IDSequence, ID_PREFIX_SALE)
        buyer_id = self._make_buyer(db, 'collide')
        seq = IDSequence.query.filter_by(prefix=ID_PREFIX_SALE).first()
        saved = seq.next_number if seq else None
        sale_id = None
        try:
            sale_id = db.add_sale({
                'buyer_id': buyer_id,
                'items': [{'product_name': 'Rod', 'quantity': 1,
                           'unit_price': 10}],
            })
            # Rewind the sequence so the next generate_id collides.
            seq = IDSequence.query.filter_by(prefix=ID_PREFIX_SALE).first()
            seq.next_number -= 1
            db.session.commit()
            sale_id2 = db.add_sale({
                'buyer_id': buyer_id,
                'items': [{'product_name': 'Pipe', 'quantity': 1,
                           'unit_price': 20}],
            })
            assert sale_id2 != sale_id
            assert (Sale.query.get(sale_id).display_id
                    != Sale.query.get(sale_id2).display_id)
            from src.db.database import SaleItem
            SaleItem.query.filter_by(sale_id=sale_id2).delete()
            sale2 = Sale.query.get(sale_id2)
            db.session.delete(sale2)
            db.session.commit()
        finally:
            if saved is not None:
                db.session.rollback()
                seq = IDSequence.query.filter_by(
                    prefix=ID_PREFIX_SALE).first()
                if seq is not None and seq.next_number < saved:
                    seq.next_number = saved
                    db.session.commit()
            if sale_id is not None:
                self._cleanup_sale(db, sale_id, buyer_id)

    def test_generate_id_distinct(self, app_context):
        """Successive generate_id calls must never repeat."""
        from src.db.database import generate_id
        id1 = generate_id("BEW-S-")
        id2 = generate_id("BEW-S-")
        assert id1 != id2

    def test_constraint_guards_in_metadata(self, app_context):
        """Additive guards exist on fresh-DB metadata (no table rewrite)."""
        from src.db.database import (
            Sale, SaleItem, BuyerContact, InventoryItem, StockMovement,
            SupplierPurchase, WorkOrder, SupplierPurchaseItem, WorkOrderPart)
        for model, col in [(BuyerContact, 'buyer_id'), (Sale, 'buyer_id'),
                           (SaleItem, 'sale_id'),
                           (InventoryItem, 'shop_id'),
                           (StockMovement, 'supplier_id')]:
            assert model.__table__.c[col].index, (model, col)
        assert Sale.__table__.c['display_id'].unique
        assert SupplierPurchase.__table__.c['display_id'].unique
        checks = ' '.join(str(c.sqltext)
                           for c in SaleItem.__table__.constraints
                           if type(c).__name__ == 'CheckConstraint')
        assert 'quantity' in checks
        checks = ' '.join(str(c.sqltext)
                           for c in StockMovement.__table__.constraints
                           if type(c).__name__ == 'CheckConstraint')
        assert 'movement_type' in checks
        uq = [c for c in StockMovement.__table__.constraints
              if type(c).__name__ == 'UniqueConstraint'
              and set(c.columns.keys()) == {'raw_material_id',
                                            'source_type', 'source_id'}]
        assert uq, 'StockMovement source-triple unique constraint missing'
        for model in (SupplierPurchase, WorkOrder):
            checks = ' '.join(
                str(c.sqltext) for c in model.__table__.constraints
                if type(c).__name__ == 'CheckConstraint')
            assert 'payment_status' in checks, model
        for model, col in [(SupplierPurchaseItem, 'quantity'),
                           (WorkOrderPart, 'qty')]:
            checks = ' '.join(
                str(c.sqltext) for c in model.__table__.constraints
                if type(c).__name__ == 'CheckConstraint')
            assert col in checks, model

    def test_zero_quantity_line_persists(self, app_context):
        """qty=0 lines persist on a fresh DB (CHECK is >= 0; Task 3
        handles qty=0 with a rate=0 fallback). Negatives stay rejected
        by the fresh-DB CHECK text (asserted on metadata: the shared
        test DB file predates CHECKs, which SQLite cannot backfill
        without a rewrite, so a live negative insert there proves
        nothing)."""
        from src.db.database import (
            db, SaleItem, StockMovement, SupplierPurchaseItem,
            WorkOrderPart)
        buyer_id = self._make_buyer(db, 'zeroqty')
        sale_id = None
        try:
            sale_id = db.add_sale({
                'buyer_id': buyer_id,
                'items': [{'product_name': 'Free sample', 'quantity': 0,
                           'unit_price': 100}],
            })
            line = SaleItem.query.filter_by(sale_id=sale_id).first()
            assert line is not None
            assert line.quantity == 0
        finally:
            db.session.rollback()
            if sale_id is not None:
                self._cleanup_sale(db, sale_id, buyer_id)
        for model, col in [(SaleItem, 'quantity'),
                           (SupplierPurchaseItem, 'quantity'),
                           (WorkOrderPart, 'qty'),
                           (StockMovement, 'quantity')]:
            texts = [str(c.sqltext).replace(' ', '')
                     for c in model.__table__.constraints
                     if type(c).__name__ == 'CheckConstraint'
                     and col in str(c.sqltext)]
            assert any(f'{col}>=0' in t for t in texts), (
                model, texts)

    def test_sale_create_route_idempotent(self, auth_client, app_context):
        """POST /dashboard/sales/new twice with one Idempotency-Key ->
        same sale (same redirect target), no duplicate row."""
        import uuid as _uuid
        import re
        from src.db.database import db, Sale
        buyer_id = self._make_buyer(db, 'route')
        key = f't6-route-{_uuid.uuid4().hex[:8]}'
        form = {'buyer_id': str(buyer_id), 'product_name': 'T6 Rod',
                'quantity': '2', 'unit_price': '100'}
        sale_id = None
        try:
            r1 = auth_client.post('/dashboard/sales/new', data=form,
                                  headers={'Idempotency-Key': key})
            r2 = auth_client.post('/dashboard/sales/new', data=form,
                                  headers={'Idempotency-Key': key})
            assert r1.status_code in (301, 302)
            assert r1.headers['Location'] == r2.headers['Location']
            m = re.search(r'/sales/(\d+)', r2.headers['Location'])
            assert m, r2.headers['Location']
            sale_id = int(m.group(1))
            assert Sale.query.filter_by(client_key=key).count() == 1
        finally:
            from src.db.database import Buyer, SaleItem
            db.session.rollback()
            for row in Sale.query.filter_by(buyer_id=buyer_id).all():
                SaleItem.query.filter_by(sale_id=row.id).delete()
                db.session.delete(row)
            db.session.commit()
            buyer = Buyer.query.get(buyer_id)
            if buyer is not None:
                db.session.delete(buyer)
                db.session.commit()
