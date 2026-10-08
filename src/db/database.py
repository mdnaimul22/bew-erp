import datetime
import uuid
import json
from flask import url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from src.config import Settings, setup_logger, read_json, exists

logger = setup_logger(Settings.LOG_DIR / "db.log", name="bew.db.database")

# Search Service Imports
from src.helpers.semantic import SemanticSearch
from src.helpers.engine import normalize_text, tokenize, calculate_score
from src.helpers.utils import safe_float, safe_int, accept_or_recompute, compute_totals, derive_pending
from src.helpers.exceptions import ValidationError


class SQLAlchemy(SQLAlchemy):
    def get_all_categories(self):
        cats = Category.query.order_by(Category.id).all()
        return [c.to_dict() for c in cats]

    def add_category(self, name, name_english=''):
        existing = Category.query.filter_by(name=name).first()
        if existing:
            return existing.id
        try:
            new_cat = Category(name=name, name_english=name_english)
            self.session.add(new_cat)
            self.session.commit()
            return new_cat.id
        except Exception:
            self.session.rollback()
            raise

    def get_all_shops(self, limit=100000, offset=0):
        shops = Shop.query.order_by(Shop.id).limit(limit).offset(offset).all()
        return [s.to_dict() for s in shops]

    def get_shops_count(self):
        return Shop.query.count()

    def get_shop_by_id(self, shop_id):
        shop = Shop.query.get(shop_id)
        return shop.to_dict() if shop else None

    def get_shops_by_category(self, category_id):
        shops = Shop.query.filter_by(category_id=category_id).order_by(Shop.id).all()
        return [s.to_dict() for s in shops]

    def search_shops(self, query):
        if not query:
            return []
            
        normalized_query = normalize_text(query)
        query_tokens = tokenize(query)
        
        if not normalized_query:
            return []
            
        semantic_search = SemanticSearch()
        semantic_results = semantic_search.search(query)
        
        semantic_scores = {r['shop_id']: r['score'] * 100 for r in semantic_results} # Scale up 0-1 to 0-100 logic
        
        # Phase 3: Category-based search fallback
        # Match query against category names (Bengali + English)
        matching_categories = Category.query.filter(
            or_(
                Category.name.ilike(f'%{query}%'),
                Category.name_english.ilike(f'%{query}%')
            )
        ).all()
        category_ids = {c.id for c in matching_categories}
            
        shops = Shop.query.options(
             joinedload(Shop.shop_tags).joinedload(ShopTag.tag)
        ).all()
        
        scored_shops = []
        for shop in shops:
            tags_data = [{'name': st.tag.name, 'name_bn': st.tag.name_bn} for st in shop.shop_tags]
            
            search_data = {
                'name': shop.name,
                'products': shop.products,
                'tags': tags_data
            }
            
            score = calculate_score(search_data, query_tokens, normalized_query)
            
            # Category boost: if shop belongs to a matching category
            if shop.category_id in category_ids:
                score += 40
            
            sem_score = semantic_scores.get(shop.id, 0)
            
            if sem_score > 0:
                if score > 0:
                    score += sem_score + 20
                else:
                    if sem_score > 5:
                        score = sem_score
                        
            if score > 0:
                scored_shops.append((score, shop))
        
        scored_shops.sort(key=lambda x: x[0], reverse=True)
        
        return [item[1].to_dict() for item in scored_shops]

    def add_shop(self, data):
        try:
            new_shop = Shop(
                category_id=data.get('category_id'),
                serial_no=data.get('serial_no'),
                name=data.get('name'),
                proprietor=data.get('proprietor'),
                address=data.get('address'),
                mobile=data.get('mobile'),
                transaction_status=data.get('transaction_status'),
                whatsapp=data.get('whatsapp'),
                email_web=data.get('email_web'),
                products=data.get('products'),
                visiting_card=data.get('visiting_card')
            )
            self.session.add(new_shop)
            self.session.commit()
            return new_shop.id
        except Exception:
            self.session.rollback()
            raise

    def update_shop(self, shop_id, data):
        shop = Shop.query.get(shop_id)
        if not shop:
            return False

        try:
            shop.category_id = data.get('category_id')
            shop.serial_no = data.get('serial_no')
            shop.name = data.get('name')
            shop.proprietor = data.get('proprietor')
            shop.address = data.get('address')
            shop.mobile = data.get('mobile')
            shop.transaction_status = data.get('transaction_status')
            shop.whatsapp = data.get('whatsapp')
            shop.email_web = data.get('email_web')
            shop.products = data.get('products')
            if 'visiting_card' in data:
                shop.visiting_card = data.get('visiting_card')
            shop.updated_at = datetime.datetime.now()

            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def delete_shop(self, shop_id):
        shop = Shop.query.get(shop_id)
        if not shop:
            return False
        try:
            self.session.delete(shop)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def get_all_tags(self):
        tags = Tag.query.order_by(Tag.name).all()
        return [t.to_dict() for t in tags]

    def get_tag_by_id(self, tag_id):
        tag = Tag.query.get(tag_id)
        return tag.to_dict() if tag else None

    def add_tag(self, name, name_bn=''):
        existing = Tag.query.filter_by(name=name).first()
        if existing:
            return existing.id
        try:
            new_tag = Tag(name=name, name_bn=name_bn)
            self.session.add(new_tag)
            self.session.commit()
            return new_tag.id
        except Exception:
            self.session.rollback()
            raise

    def delete_tag(self, tag_id):
        tag = Tag.query.get(tag_id)
        if not tag:
            return False
        try:
            ShopTag.query.filter_by(tag_id=tag_id).delete()
            self.session.delete(tag)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def get_shop_tags(self, shop_id):
        shop = Shop.query.get(shop_id)
        if shop:
            return [t.to_dict() for t in shop.tags]
        return []

    def add_shop_tag(self, shop_id, tag_id):
        existing = ShopTag.query.filter_by(shop_id=shop_id, tag_id=tag_id).first()
        if existing:
            return existing.id
        try:
            new_shop_tag = ShopTag(shop_id=shop_id, tag_id=tag_id)
            self.session.add(new_shop_tag)
            self.session.commit()
            return new_shop_tag.id
        except Exception:
            self.session.rollback()
            raise

    def remove_shop_tag(self, shop_id, tag_id):
        shop_tag = ShopTag.query.filter_by(shop_id=shop_id, tag_id=tag_id).first()
        if not shop_tag:
            return False
        try:
            self.session.delete(shop_tag)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def search_shops_by_tag(self, tag_name):
        tag = Tag.query.filter(Tag.name.ilike(f'%{tag_name}%')).first()
        if not tag:
            return []
        shops = [st.shop for st in tag.shop_tags if st.shop]
        return [s.to_dict() for s in shops]

    def import_from_json(self, json_path=None):
        json_path = json_path or str(Settings.SHOPS_JSON_PATH)
        data = read_json(json_path)

        try:
            Shop.query.delete()
            Category.query.delete()

            try:
                self.session.execute(db.text("DELETE FROM sqlite_sequence WHERE name='shops' OR name='categories'"))
            except Exception as e:
                logger.warning(f"Failed to reset sqlite_sequence: {e}")

            for cat in data['categories']:
                new_cat = Category(
                    id=cat['id'],
                    name=cat['name'],
                    name_english=cat.get('name_english', '')
                )
                self.session.add(new_cat)

            self.session.flush()

            # Insert shops
            for shop in data['shops']:
                new_shop = Shop(
                    category_id=shop.get('category_id'),
                    serial_no=shop.get('serial_no', ''),
                    name=shop.get('name', ''),
                    proprietor=shop.get('proprietor', ''),
                    address=shop.get('address', ''),
                    mobile=shop.get('mobile', ''),
                    transaction_status=shop.get('transaction_status', ''),
                    whatsapp=shop.get('whatsapp', ''),
                    email_web=shop.get('email_web', ''),
                    products=shop.get('products', '')
                )
                self.session.add(new_shop)

            self.session.commit()
            return len(data['categories']), len(data['shops'])
        except Exception:
            self.session.rollback()
            raise

    # ==================== BUYER HELPERS ====================
    def get_all_buyers(self):
        buyers = Buyer.query.order_by(Buyer.company_name).all()
        return [b.to_dict() for b in buyers]

    def get_buyer_by_id(self, buyer_id):
        buyer = Buyer.query.get(buyer_id)
        return buyer.to_dict() if buyer else None

    def get_buyer_profile(self, buyer_id):
        
        buyer = Buyer.query.get(buyer_id)
        if not buyer:
            return None
        
        data = buyer.to_dict()
        
        # Transaction History
        history = []
        for s in buyer.sales:
            history.append({
                'date': s.sale_date,
                'id': s.display_id or f"S-{s.id}",
                'type': 'Sales Order',
                'description': f"{len(s.items)} Product(s)",
                'amount': s.total_amount,
                'status': 'Paid',
                'url': url_for('sales.sale_detail', sale_id=s.id)
            })
            
        
        work_orders = WorkOrder.query.filter_by(company_id=buyer_id).order_by(WorkOrder.job_date.desc()).all()
        for w in work_orders:
            history.append({
                'date': w.job_date,
                'id': w.display_id or w.id,
                'type': 'Work Order',
                'description': w.job_name,
                'amount': w.quoted_price,
                'status': w.status.title() if w.status else 'Open',
                'url': url_for('work_orders.work_order_detail', work_order_id=w.id)
            })
            
        # Sort history by date descending
        history.sort(key=lambda x: x['date'], reverse=True)
        
        # Format dates for display AFTER sorting
        for item in history:
            if isinstance(item['date'], (datetime.date, datetime.datetime)):
                item['date'] = item['date'].strftime('%d-%m-%Y')
            elif not item['date']:
                item['date'] = '-'

        data['history'] = history
        data['work_orders_count'] = len(work_orders)
        data['sales_count'] = len(buyer.sales)
        data['total_sales_amount'] = sum(s.total_amount for s in buyer.sales)
        data['created_at'] = buyer.created_at.strftime('%d-%m-%Y') if buyer.created_at else None
        return data

    def add_buyer(self, data):
        try:
            buyer = Buyer(
                display_id=generate_id(ID_PREFIX_BUYER),
                company_name=data.get('company_name'),
                address=data.get('address')
            )
            self.session.add(buyer)
            self.session.flush()

            contacts = data.get('contacts', [])
            for c in contacts:
                contact = BuyerContact(
                    buyer_id=buyer.id,
                    name=c.get('name'),
                    designation=c.get('designation'),
                    mobile=json.dumps(c.get('mobiles', [])),
                    whatsapp=c.get('whatsapp'),
                    email=c.get('email'),
                    is_primary=c.get('is_primary', False)
                )
                self.session.add(contact)

            self.session.commit()
            return buyer.id
        except Exception:
            self.session.rollback()
            raise

    def update_buyer(self, buyer_id, data):
        buyer = Buyer.query.get(buyer_id)
        if not buyer:
            return False

        try:
            buyer.company_name = data.get('company_name')
            buyer.address = data.get('address')
            buyer.updated_at = datetime.datetime.now()

            BuyerContact.query.filter_by(buyer_id=buyer_id).delete()

            contacts = data.get('contacts', [])
            for c in contacts:
                contact = BuyerContact(
                    buyer_id=buyer_id,
                    name=c.get('name'),
                    designation=c.get('designation'),
                    mobile=json.dumps(c.get('mobiles', [])),
                    whatsapp=c.get('whatsapp'),
                    email=c.get('email'),
                    is_primary=c.get('is_primary', False)
                )
                self.session.add(contact)

            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def delete_buyer(self, buyer_id):
        buyer = Buyer.query.get(buyer_id)
        if not buyer:
            return False, 'not_found'
            
        if buyer.sales:
            return False, 'has_sales'
            
        work_orders = WorkOrder.query.filter_by(company_id=buyer_id).first()
        if work_orders:
            return False, 'has_work_orders'
            
        try:
            self.session.delete(buyer)
            self.session.commit()
            return True, None
        except Exception:
            self.session.rollback()
            return False, 'error'

    # ==================== INVENTORY HELPERS ====================
    def get_all_inventory(self):
        inventory = InventoryItem.query.order_by(InventoryItem.purchase_date.desc()).all()
        return [i.to_dict() for i in inventory]

    def add_inventory(self, data):
        try:
            new_item = InventoryItem(
                shop_id=data.get('shop_id'),
                material_name=data.get('material_name'),
                purchase_date=data.get('purchase_date') or datetime.date.today(),
                quantity=data.get('quantity', 0),
                cost=data.get('cost', 0),
                tags=data.get('tags', '')
            )
            self.session.add(new_item)
            self.session.commit()
            return new_item.id
        except Exception:
            self.session.rollback()
            raise
    
    def get_inventory_by_id(self, item_id):
        item = InventoryItem.query.get(item_id)
        return item.to_dict() if item else None

    def delete_inventory(self, item_id):
        item = InventoryItem.query.get(item_id)
        if not item:
            return False
        try:
            self.session.delete(item)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    # ==================== SALES HELPERS ====================
    def get_all_sales(self, limit=100, offset=0):
        sales = Sale.query.order_by(Sale.sale_date.desc()).limit(limit).offset(offset).all()
        return [s.to_dict() for s in sales]
        
    def get_sales_count(self):
        return Sale.query.count()

    def get_sale_by_id(self, sale_id):
        sale = Sale.query.get(sale_id)
        if not sale:
            return None
        
        # Detailed dict for sale
        data = sale.to_dict()
        data['items'] = [i.to_dict() for i in sale.items]
        return data

    def add_sale(self, data):
        try:
            new_sale = Sale(
                display_id=generate_id(ID_PREFIX_SALE),
                voucher_id=generate_id(ID_PREFIX_VOUCHER_SALE),
                buyer_id=data.get('buyer_id'),
                sale_date=data.get('sale_date') or datetime.date.today(),
                voucher_image=data.get('voucher_image'),
                total_amount=0
            )
            self.session.add(new_sale)
            self.session.flush()

            total = 0
            if 'items' in data:
                for item in data['items']:
                    qty = safe_float(item.get('quantity'), field='quantity')
                    unit = safe_float(item.get('unit_price'), field='unit_price')
                    line_total = accept_or_recompute(qty * unit, item.get('total_price'))

                    total += line_total

                    new_item = SaleItem(
                        sale_id=new_sale.id,
                        product_name=item.get('product_name'),
                        quantity=qty,
                        unit_price=unit,
                        total_price=line_total,
                        weight=safe_float(item.get('weight'), field='weight'),
                        inventory_link_id=item.get('inventory_link_id')
                    )
                    self.session.add(new_item)

            new_sale.total_amount = accept_or_recompute(total, data.get('total_amount'))
            self.session.commit()
            return new_sale.id
        except Exception:
            self.session.rollback()
            raise

    def update_sale(self, sale_id, data):
        sale = Sale.query.get(sale_id)
        if not sale:
            return False

        try:
            sale.buyer_id = data.get('buyer_id')
            sale.sale_date = data.get('sale_date') or datetime.date.today()
            if 'voucher_image' in data and data.get('voucher_image'):
                sale.voucher_image = data.get('voucher_image')

            SaleItem.query.filter_by(sale_id=sale_id).delete()

            total = 0
            if 'items' in data:
                for item in data['items']:
                    qty = safe_float(item.get('quantity'), field='quantity')
                    unit = safe_float(item.get('unit_price'), field='unit_price')
                    line_total = accept_or_recompute(qty * unit, item.get('total_price'))

                    total += line_total

                    new_item = SaleItem(
                        sale_id=sale.id,
                        product_name=item.get('product_name'),
                        quantity=qty,
                        unit_price=unit,
                        total_price=line_total,
                        weight=safe_float(item.get('weight'), field='weight'),
                        inventory_link_id=item.get('inventory_link_id')
                    )
                    self.session.add(new_item)

            sale.total_amount = accept_or_recompute(total, data.get('total_amount'))
            sale.updated_at = datetime.datetime.now()
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def delete_sale(self, sale_id):
        sale = Sale.query.get(sale_id)
        if not sale:
            return False
        try:
            self.session.delete(sale)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def get_all_supplier_purchases(self, limit=1000, offset=0):
        purchases = SupplierPurchase.query.order_by(SupplierPurchase.purchase_date.desc()).limit(limit).offset(offset).all()
        return [p.to_dict(include_items=False) for p in purchases]

    def get_supplier_purchases(self, supplier_id, limit=1000, offset=0):
        purchases = SupplierPurchase.query.filter_by(supplier_id=supplier_id).order_by(SupplierPurchase.purchase_date.desc()).limit(limit).offset(offset).all()
        return [p.to_dict(include_items=False) for p in purchases]

    def get_supplier_purchase_by_id(self, purchase_id):
        purchase = SupplierPurchase.query.get(purchase_id)
        return purchase.to_dict(include_items=True) if purchase else None

    def add_supplier_purchase(self, data):
        try:
            display_id = generate_id(ID_PREFIX_PURCHASE)
            voucher_no = data.get('voucher_no') or ''
            voucher_file_path = data.get('voucher_file_path') or ''

            # If file is uploaded but no custom voucher_no provided, use display_id
            if voucher_file_path and not voucher_no:
                voucher_no = display_id

            purchase = SupplierPurchase(
                display_id=display_id,
                voucher_id=generate_id(ID_PREFIX_VOUCHER_PURCHASE),
                supplier_id=safe_int(data.get('supplier_id'), field='supplier_id'),
                purchase_date=data.get('purchase_date') or datetime.date.today(),
                voucher_no=voucher_no,
                voucher_file_path=voucher_file_path,
                work_order_id=data.get('work_order_id'),
                payment_status=data.get('payment_status') or 'pending',
                paid_amount=safe_float(data.get('paid_amount'), field='paid_amount'),
                notes=data.get('notes') or ''
            )
            self.session.add(purchase)
            self.session.flush()

            items = data.get('items') or []
            for item in items:
                qty = safe_float(item.get('quantity'), field='quantity')
                rate = safe_float(item.get('rate_per_unit'), field='rate_per_unit')
                total = accept_or_recompute(qty * rate, item.get('total_amount'))
                purchase_item = SupplierPurchaseItem(
                    purchase_id=purchase.id,
                    raw_material_id=item.get('raw_material_id'),  # Link to master material
                    product_name=item.get('product_name') or '',
                    specification=item.get('specification') or '',
                    quantity=qty,
                    weight=safe_float(item.get('weight'), field='weight'),
                    unit=item.get('unit') or '',
                    rate_per_unit=rate,
                    total_amount=total
                )
                self.session.add(purchase_item)

            self.session.commit()
            return purchase.id
        except Exception:
            self.session.rollback()
            raise

    def update_supplier_purchase(self, purchase_id, data):
        purchase = SupplierPurchase.query.get(purchase_id)
        if not purchase:
            return False

        try:
            if 'supplier_id' in data and data.get('supplier_id') is not None:
                purchase.supplier_id = safe_int(data.get('supplier_id'), field='supplier_id')

            if 'purchase_date' in data and data.get('purchase_date') is not None:
                purchase.purchase_date = data.get('purchase_date')

            if 'voucher_no' in data:
                purchase.voucher_no = data.get('voucher_no') or ''

            if 'voucher_file_path' in data:
                purchase.voucher_file_path = data.get('voucher_file_path') or ''

            # If file exists and voucher_no is empty, auto-fill it
            if purchase.voucher_file_path and not purchase.voucher_no:
                purchase.voucher_no = purchase.display_id

            if 'payment_status' in data:
                purchase.payment_status = data.get('payment_status') or 'pending'

            if 'paid_amount' in data:
                purchase.paid_amount = safe_float(data.get('paid_amount'), field='paid_amount')

            if 'notes' in data:
                purchase.notes = data.get('notes') or ''

            if 'work_order_id' in data:
                purchase.work_order_id = data.get('work_order_id') or None

            purchase.updated_at = datetime.datetime.now()

            if 'items' in data:
                SupplierPurchaseItem.query.filter_by(purchase_id=purchase_id).delete()
                for item in (data.get('items') or []):
                    qty = safe_float(item.get('quantity'), field='quantity')
                    rate = safe_float(item.get('rate_per_unit'), field='rate_per_unit')
                    total = accept_or_recompute(qty * rate, item.get('total_amount'))
                    purchase_item = SupplierPurchaseItem(
                        purchase_id=purchase.id,
                        raw_material_id=item.get('raw_material_id'),
                        product_name=item.get('product_name') or '',
                        specification=item.get('specification') or '',
                        quantity=qty,
                        weight=safe_float(item.get('weight'), field='weight'),
                        unit=item.get('unit') or '',
                        rate_per_unit=rate,
                        total_amount=total
                    )
                    self.session.add(purchase_item)

            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def delete_supplier_purchase(self, purchase_id):
        purchase = SupplierPurchase.query.get(purchase_id)
        if not purchase:
            return False
        try:
            self.session.delete(purchase)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def get_all_work_orders(self, limit=1000, offset=0):
        work_orders = WorkOrder.query.order_by(WorkOrder.job_date.desc()).limit(limit).offset(offset).all()
        return [w.to_dict(include_parts=False) for w in work_orders]

    def get_work_order_by_id(self, work_order_id):
        work_order = WorkOrder.query.get(work_order_id)
        return work_order.to_dict(include_parts=True) if work_order else None

    def add_work_order(self, data):
        try:
            wo_id = generate_id(ID_PREFIX_WORK_ORDER)
            quoted = safe_float(data.get('quoted_price'), field='quoted_price')
            paid = safe_float(data.get('paid_amount'), field='paid_amount')
            labor = safe_float(data.get('labor_cost'), field='labor_cost')
            parts = data.get('parts') or []
            material = compute_totals(parts) if 'parts' in data else safe_float(
                data.get('material_cost'), field='material_cost')
            material = accept_or_recompute(material, data.get('material_cost'))
            total = accept_or_recompute(
                labor + material, data.get('total_cost'))
            work_order = WorkOrder(
                id=wo_id,
                display_id=wo_id,
                voucher_id=generate_id(ID_PREFIX_VOUCHER_WORK_ORDER),
                company_id=safe_int(data.get('company_id'), field='company_id'),
                job_date=data.get('job_date') or datetime.date.today(),
                job_name=data.get('job_name') or '',
                job_description=data.get('job_description') or '',
                status=data.get('status') or 'open',
                payment_status=data.get('payment_status') or 'pending',
                paid_amount=paid,
                pending_amount=derive_pending(quoted, paid),
                quoted_price=quoted,
                delivery_date=data.get('delivery_date'),
                labor_cost=labor,
                material_cost=material,
                total_cost=total,
                hard_copy_path=data.get('hard_copy_path') or '',
                notes=data.get('notes') or ''
            )
            self.session.add(work_order)
            self.session.flush()

            for part in parts:
                s_id = part.get('supplier_id')

                # Common part data
                part_name = part.get('part_name') or ''
                measurement = part.get('measurement') or ''
                qty = safe_float(part.get('qty'), field='qty')
                weight = safe_float(part.get('weight'), field='weight')
                unit = part.get('unit') or ''
                price = safe_float(part.get('price'), field='price')
                voucher_file_path = part.get('voucher_file_path') or ''
                raw_mat_id = part.get('raw_material_id')

                if s_id:
                    purchase_display_id = generate_id(ID_PREFIX_PURCHASE)
                    voucher_no = part.get('voucher_no') or ''
                
                    # If file is uploaded but no custom voucher_no provided, use display_id
                    if voucher_file_path and not voucher_no:
                        voucher_no = purchase_display_id

                    # Create a unified Purchase record for this part
                    purchase = SupplierPurchase(
                        display_id=purchase_display_id,
                        voucher_id=generate_id(ID_PREFIX_VOUCHER_PURCHASE),
                        supplier_id=safe_int(s_id, field='supplier_id'),
                        purchase_date=work_order.job_date,
                        voucher_no=voucher_no,
                        voucher_file_path=voucher_file_path,
                        work_order_id=work_order.id,
                        notes=f"Project Part: {part_name}",
                        payment_status='pending',
                        paid_amount=0.0
                    )
                    self.session.add(purchase)
                    self.session.flush()

                    # Add the item to the purchase
                    purchase_item = SupplierPurchaseItem(
                        purchase_id=purchase.id,
                        raw_material_id=raw_mat_id,
                        product_name=part_name,
                        specification=measurement,
                        quantity=qty,
                        weight=weight,
                        unit=unit,
                        rate_per_unit=price / qty if qty > 0 else 0,
                        total_amount=price
                    )
                    self.session.add(purchase_item)
                else:
                    # No supplier selected, save to WorkOrderPart for tracking
                    new_part = WorkOrderPart(
                        work_order_id=work_order.id,
                        raw_material_id=raw_mat_id,
                        part_name=part_name,
                        voucher_file_path=voucher_file_path,
                        measurement=measurement,
                        unit=unit,
                        qty=qty,
                        weight=weight,
                        price=price
                    )
                    self.session.add(new_part)

            # Add Gallery Documents
            docs = data.get('documents') or []
            for doc in docs:
                f_path = doc.get('file_path')
                if not f_path:
                    continue
                new_doc = WorkOrderDocument(
                    work_order_id=work_order.id,
                    file_path=f_path,
                    document_type=doc.get('document_type') or 'Other',
                    notes=doc.get('notes') or ''
                )
                self.session.add(new_doc)

            self.session.commit()
            return work_order.id
        except Exception:
            self.session.rollback()
            raise

    def update_work_order(self, work_order_id, data):
        work_order = WorkOrder.query.get(work_order_id)
        if not work_order:
            return False

        try:
            if 'company_id' in data and data.get('company_id') is not None:
                work_order.company_id = safe_int(data.get('company_id'), field='company_id')

            if 'job_date' in data and data.get('job_date') is not None:
                work_order.job_date = data.get('job_date')

            if 'job_name' in data:
                work_order.job_name = data.get('job_name') or ''

            if 'job_description' in data:
                work_order.job_description = data.get('job_description') or ''

            if 'status' in data:
                work_order.status = data.get('status') or 'open'

            if 'payment_status' in data:
                work_order.payment_status = data.get('payment_status') or 'pending'

            if 'paid_amount' in data:
                work_order.paid_amount = safe_float(data.get('paid_amount'), field='paid_amount')

            if 'quoted_price' in data:
                work_order.quoted_price = safe_float(data.get('quoted_price'), field='quoted_price')

            if any(k in data for k in ('quoted_price', 'paid_amount')):
                # Client pending_amount is advisory only — always derived server-side.
                # It must never trigger validation on its own (legacy
                # paid>quoted rows stay editable for non-money edits).
                work_order.pending_amount = derive_pending(
                    work_order.quoted_price or 0, work_order.paid_amount or 0)

            if 'delivery_date' in data:
                work_order.delivery_date = data.get('delivery_date')

            if 'labor_cost' in data:
                work_order.labor_cost = safe_float(data.get('labor_cost'), field='labor_cost')

            if 'material_cost' in data:
                work_order.material_cost = safe_float(data.get('material_cost'), field='material_cost')

            if 'total_cost' in data or 'labor_cost' in data or 'material_cost' in data:
                # Server recomputes total = labor + material; client value is advisory.
                work_order.total_cost = accept_or_recompute(
                    (work_order.labor_cost or 0) + (work_order.material_cost or 0),
                    data.get('total_cost') if 'total_cost' in data else None)

            if 'hard_copy_path' in data:
                work_order.hard_copy_path = data.get('hard_copy_path') or ''

            if 'notes' in data:
                work_order.notes = data.get('notes') or ''

            work_order.updated_at = datetime.datetime.now()

            if 'parts' in data:
                # Paid-guard: rewriting parts recomputes material/total, so a
                # work order with recorded customer payments needs explicit
                # opt-in. Pure non-money edits omit 'parts' and are unaffected.
                if (work_order.paid_amount or 0) > 0 and not data.get(
                        'allow_paid_rewrite'):
                    raise ValidationError(
                        "Cannot rewrite parts on a work order with recorded "
                        "payments. Pass allow_paid_rewrite=True to confirm.")

                incoming = data.get('parts') or []
                supplier_parts = [p for p in incoming if p.get('supplier_id')]
                direct_parts = [p for p in incoming
                                if not p.get('supplier_id')]

                # Diff-by-id (positional: form rows carry no ids): matched
                # linked purchases keep display_id / voucher_id /
                # payment_status / paid_amount. Only the delta is
                # inserted/deleted — never a bulk-delete that resets payments.
                existing_purchases = (
                    SupplierPurchase.query
                    .filter_by(work_order_id=work_order.id)
                    .order_by(SupplierPurchase.created_at,
                              SupplierPurchase.id)
                    .all())

                parts_cost = 0.0
                for index, part in enumerate(supplier_parts):
                    s_id = part.get('supplier_id')

                    # Common part data
                    part_name = part.get('part_name') or ''
                    measurement = part.get('measurement') or ''
                    qty = safe_float(part.get('qty'), field='qty')
                    weight = safe_float(part.get('weight'), field='weight')
                    unit = part.get('unit') or ''
                    price = safe_float(part.get('price'), field='price')
                    voucher_file_path = part.get('voucher_file_path') or ''
                    raw_mat_id = part.get('raw_material_id')

                    if index < len(existing_purchases):
                        # Matched row: update details, preserve payment identity.
                        purchase = existing_purchases[index]
                        purchase.supplier_id = safe_int(
                            s_id, field='supplier_id')
                        purchase.purchase_date = work_order.job_date
                        if part.get('voucher_no'):
                            purchase.voucher_no = part.get('voucher_no')
                        purchase.voucher_file_path = voucher_file_path
                        purchase.notes = f"Project Part: {part_name}"
                        # If file exists and voucher_no is empty, auto-fill it
                        if (purchase.voucher_file_path
                                and not purchase.voucher_no):
                            purchase.voucher_no = purchase.display_id
                        SupplierPurchaseItem.query.filter_by(
                            purchase_id=purchase.id).delete()
                    else:
                        purchase_display_id = generate_id(ID_PREFIX_PURCHASE)
                        voucher_no = part.get('voucher_no') or ''

                        if voucher_file_path and not voucher_no:
                            voucher_no = purchase_display_id

                        purchase = SupplierPurchase(
                            display_id=purchase_display_id,
                            voucher_id=generate_id(ID_PREFIX_VOUCHER_PURCHASE),
                            supplier_id=safe_int(s_id, field='supplier_id'),
                            purchase_date=work_order.job_date,
                            voucher_no=voucher_no,
                            voucher_file_path=voucher_file_path,
                            work_order_id=work_order.id,
                            notes=f"Project Part: {part_name}",
                            payment_status='pending',
                            paid_amount=0.0
                        )
                        self.session.add(purchase)
                        self.session.flush()

                    purchase_item = SupplierPurchaseItem(
                        purchase_id=purchase.id,
                        raw_material_id=raw_mat_id,
                        product_name=part_name,
                        specification=measurement,
                        quantity=qty,
                        weight=weight,
                        unit=unit,
                        rate_per_unit=price / qty if qty > 0 else 0,
                        total_amount=price
                    )
                    self.session.add(purchase_item)

                    parts_cost += price

                # Delete delta only — never silently drop a paid purchase row.
                for stale in existing_purchases[len(supplier_parts):]:
                    if (stale.paid_amount or 0) > 0 and not data.get(
                            'allow_paid_rewrite'):
                        raise ValidationError(
                            "Cannot delete a linked purchase with recorded "
                            "payments. Pass allow_paid_rewrite=True to "
                            "confirm.")
                    self.session.delete(stale)

                # Direct (non-supplier) parts carry no payment identity, but
                # still diff positionally to avoid needless row churn.
                existing_direct = (
                    WorkOrderPart.query
                    .filter_by(work_order_id=work_order.id)
                    .order_by(WorkOrderPart.id)
                    .all())
                for index, part in enumerate(direct_parts):
                    part_name = part.get('part_name') or ''
                    measurement = part.get('measurement') or ''
                    qty = safe_float(part.get('qty'), field='qty')
                    weight = safe_float(part.get('weight'), field='weight')
                    unit = part.get('unit') or ''
                    price = safe_float(part.get('price'), field='price')
                    voucher_file_path = part.get('voucher_file_path') or ''
                    raw_mat_id = part.get('raw_material_id')

                    if index < len(existing_direct):
                        row = existing_direct[index]
                        row.raw_material_id = raw_mat_id
                        row.part_name = part_name
                        row.voucher_file_path = voucher_file_path
                        row.measurement = measurement
                        row.unit = unit
                        row.qty = qty
                        row.weight = weight
                        row.price = price
                    else:
                        # No supplier selected, save to WorkOrderPart
                        new_part = WorkOrderPart(
                            work_order_id=work_order.id,
                            raw_material_id=raw_mat_id,
                            part_name=part_name,
                            voucher_file_path=voucher_file_path,
                            measurement=measurement,
                            unit=unit,
                            qty=qty,
                            weight=weight,
                            price=price
                        )
                        self.session.add(new_part)

                    parts_cost += price

                for stale in existing_direct[len(direct_parts):]:
                    self.session.delete(stale)

                # Recompute material/total from the rebuilt parts (client values advisory).
                work_order.material_cost = accept_or_recompute(
                    parts_cost, data.get('material_cost'))
                work_order.total_cost = accept_or_recompute(
                    (work_order.labor_cost or 0) + work_order.material_cost,
                    data.get('total_cost'))

                # Update Gallery Documents
                # Simple approach: delete all and re-add (like parts)
                WorkOrderDocument.query.filter_by(work_order_id=work_order.id).delete()
                for doc in (data.get('documents') or []):
                    f_path = doc.get('file_path')
                    if not f_path:
                        continue
                    new_doc = WorkOrderDocument(
                        work_order_id=work_order.id,
                        file_path=f_path,
                        document_type=doc.get('document_type') or 'Other',
                        notes=doc.get('notes') or ''
                    )
                    self.session.add(new_doc)


            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def delete_work_order(self, work_order_id):
        work_order = WorkOrder.query.get(work_order_id)
        if not work_order:
            return False
        
        try:
            # Manually cleanup linked purchases (since they only have a nullable FK)
            SupplierPurchase.query.filter_by(work_order_id=work_order_id).delete()
        
            self.session.delete(work_order)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    # ==================== ANALYTICS & MESSAGES ====================
    def log_visit(self, url, ip, user_agent):
        try:
            visit = Analytics(page_url=url, visitor_ip=ip, user_agent=user_agent)
            self.session.add(visit)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def get_visit_stats(self):
        # Basic stats: total visits, visits today
        total = Analytics.query.count()
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = Analytics.query.filter(Analytics.visit_time >= today_start).count()
        
        return {
            'total_visits': total,
            'today_visits': today
        }

    def add_visitor_message(self, data):
        try:
            msg = VisitorMessage(
                name=data.get('name'),
                email=data.get('email'),
                subject=data.get('subject'),
                message=data.get('message')
            )
            self.session.add(msg)
            self.session.commit()
            return msg.id
        except Exception:
            self.session.rollback()
            raise

    def get_all_messages(self, limit=50):
        msgs = VisitorMessage.query.order_by(VisitorMessage.created_at.desc()).limit(limit).all()
        return [m.to_dict() for m in msgs]

    def mark_message_read(self, msg_id):
        msg = VisitorMessage.query.get(msg_id)
        try:
            if msg:
                msg.is_read = True
                self.session.commit()
                return True
        except Exception:
            self.session.rollback()
            raise
        return False

db = SQLAlchemy()

# ==================== ID SEQUENCE SYSTEM ====================
class IDSequence(db.Model):
    """Stores the next sequence number for each ID type"""
    __tablename__ = 'id_sequences'
    prefix = db.Column(db.String(20), primary_key=True)  # 'BEW-B-', 'BEW-WO-', etc.
    next_number = db.Column(db.Integer, default=1)

def generate_id(prefix):
    """Thread-safe ID generation"""
    seq = IDSequence.query.filter_by(prefix=prefix).first()
    if not seq:
        seq = IDSequence(prefix=prefix, next_number=1)
        db.session.add(seq)
        db.session.flush()
    current = seq.next_number
    seq.next_number += 1
    db.session.flush()
    return f"{prefix}{current}"

# ID Prefix Constants
ID_PREFIX_BUYER = 'BEW-B-'
ID_PREFIX_WORK_ORDER = 'BEW-WO-'
ID_PREFIX_SALE = 'BEW-TRX-'
ID_PREFIX_PURCHASE = 'BEW-BUY-'
ID_PREFIX_RAW_MATERIAL = 'BEW-ITEM-'
ID_PREFIX_VOUCHER_PURCHASE = 'BEW-VCH-P-'
ID_PREFIX_VOUCHER_SALE = 'BEW-VCH-S-'
ID_PREFIX_VOUCHER_WORK_ORDER = 'BEW-VCH-W-'

# ==================== RAW MATERIAL CATEGORY ====================
class RawMaterialCategory(db.Model):
    """Categories for raw materials (Steel, Iron, Electrical, etc.)"""
    __tablename__ = 'raw_material_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    name_bn = db.Column(db.String(200))  # Bengali name
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    materials = db.relationship('RawMaterial', backref='category', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_bn': self.name_bn,
            'description': self.description,
            'material_count': len(self.materials) if self.materials else 0
        }

# ==================== RAW MATERIAL (MASTER) ====================
class RawMaterial(db.Model):
    """Master list of all raw materials - single source of truth for product names"""
    __tablename__ = 'raw_materials'
    id = db.Column(db.Integer, primary_key=True)
    display_id = db.Column(db.String(50), unique=True, index=True)  # BEW-ITEM-1
    category_id = db.Column(db.Integer, db.ForeignKey('raw_material_categories.id'), nullable=True)
    name = db.Column(db.String(500), nullable=False, index=True)
    name_bn = db.Column(db.String(500))  # Bengali name
    default_unit = db.Column(db.String(50))  # kg, pcs, feet, etc.
    description = db.Column(db.Text)
    min_stock_level = db.Column(db.Float, default=0)  # Alert threshold
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    # Relationships
    stock_movements = db.relationship('StockMovement', backref='raw_material', lazy=True)
    supplier_rates = db.relationship('SupplierMaterialRate', backref='raw_material', lazy=True)

    @property
    def current_stock(self):
        """Calculate current stock from movements"""
        from sqlalchemy import func
        in_qty = db.session.query(func.coalesce(func.sum(StockMovement.quantity), 0))\
            .filter(StockMovement.raw_material_id == self.id, 
                    StockMovement.movement_type == 'IN').scalar() or 0
        out_qty = db.session.query(func.coalesce(func.sum(StockMovement.quantity), 0))\
            .filter(StockMovement.raw_material_id == self.id, 
                    StockMovement.movement_type == 'OUT').scalar() or 0
        return float(in_qty) - float(out_qty)

    def to_dict(self):
        return {
            'id': self.id,
            'display_id': self.display_id,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'name': self.name,
            'name_bn': self.name_bn,
            'default_unit': self.default_unit,
            'description': self.description,
            'min_stock_level': self.min_stock_level,
            'current_stock': self.current_stock,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# ==================== STOCK MOVEMENT ====================
class StockMovement(db.Model):
    """Tracks all stock IN/OUT movements for accurate inventory"""
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False, index=True)
    movement_type = db.Column(db.String(10), nullable=False)  # 'IN', 'OUT', 'ADJUST'
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50))
    
    # Source tracking
    source_type = db.Column(db.String(50))  # 'purchase', 'sale', 'work_order', 'adjustment'
    source_id = db.Column(db.String(50))    # Reference to source record (display_id)
    
    # For purchases: track supplier and rate
    supplier_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=True)
    rate_per_unit = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, default=0)
    
    notes = db.Column(db.Text)
    movement_date = db.Column(db.Date, default=datetime.date.today)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    # Relationships
    supplier = db.relationship('Shop')

    def to_dict(self):
        return {
            'id': self.id,
            'raw_material_id': self.raw_material_id,
            'raw_material_name': self.raw_material.name if self.raw_material else None,
            'movement_type': self.movement_type,
            'quantity': self.quantity,
            'unit': self.unit,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else None,
            'rate_per_unit': self.rate_per_unit,
            'total_amount': self.total_amount,
            'movement_date': self.movement_date.isoformat() if self.movement_date else None,
            'movement_date_display': self.movement_date.strftime('%d-%m-%Y') if self.movement_date else '-',
            'notes': self.notes
        }

# ==================== SUPPLIER MATERIAL RATE ====================
class SupplierMaterialRate(db.Model):
    """Historical rates for each material from each supplier"""
    __tablename__ = 'supplier_material_rates'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False, index=True)
    rate = db.Column(db.Float, nullable=False)
    effective_date = db.Column(db.Date, default=datetime.date.today)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    supplier = db.relationship('Shop')

    def to_dict(self):
        return {
            'id': self.id,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else None,
            'raw_material_id': self.raw_material_id,
            'raw_material_name': self.raw_material.name if self.raw_material else None,
            'rate': self.rate,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'effective_date_display': self.effective_date.strftime('%d-%m-%Y') if self.effective_date else '-',
            'notes': self.notes
        }

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(10000), nullable=False)
    name_english = db.Column(db.String(10000))
    shops = db.relationship('Shop', backref='category', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_english': self.name_english
        }

class Shop(db.Model):
    __tablename__ = 'shops'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    serial_no = db.Column(db.String(5000))
    name = db.Column(db.String(20000))
    proprietor = db.Column(db.String(10000))
    address = db.Column(db.Text)
    mobile = db.Column(db.String(10000))
    transaction_status = db.Column(db.String(10000))
    whatsapp = db.Column(db.String(5000))
    email_web = db.Column(db.String(10000))
    products = db.Column(db.Text)
    visiting_card = db.Column(db.String(5000))
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    # Tag relationship (many-to-many via ShopTag)
    shop_tags = db.relationship('ShopTag', backref='shop', lazy=True, cascade='all, delete-orphan')
    tags = db.relationship('Tag', secondary='shop_tags', viewonly=True, lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else '',
            'category_name_english': self.category.name_english if self.category else '',
            'serial_no': self.serial_no,
            'name': self.name,
            'proprietor': self.proprietor,
            'address': self.address,
            'mobile': self.mobile,
            'transaction_status': self.transaction_status,
            'whatsapp': self.whatsapp,
            'email_web': self.email_web,
            'products': self.products,
            'visiting_card': self.visiting_card,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'tags': [t.to_dict() for t in self.tags] if self.tags else []
        }


class Tag(db.Model):
    """Master tag list for shop products/services"""
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500), unique=True, nullable=False, index=True)
    name_bn = db.Column(db.String(500))  # Bengali name
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    
    # Relationship to shops via ShopTag
    shop_tags = db.relationship('ShopTag', backref='tag', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_bn': self.name_bn,
            'shop_count': len(self.shop_tags) if self.shop_tags else 0
        }


class ShopTag(db.Model):
    """Many-to-many relationship between Shop and Tag"""
    __tablename__ = 'shop_tags'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    
    __table_args__ = (db.UniqueConstraint('shop_id', 'tag_id', name='unique_shop_tag'),)

class Buyer(db.Model):
    __tablename__ = 'buyers'
    id = db.Column(db.Integer, primary_key=True)
    display_id = db.Column(db.String(50), unique=True, index=True)  # BEW-B-1
    company_name = db.Column(db.String(500), nullable=False)
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    contacts = db.relationship('BuyerContact', backref='buyer', lazy=True, cascade='all, delete-orphan')
    sales = db.relationship('Sale', backref='buyer', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'display_id': self.display_id,
            'company_name': self.company_name,
            'address': self.address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'contacts': [c.to_dict() for c in self.contacts]
        }

class BuyerContact(db.Model):
    __tablename__ = 'buyer_contacts'
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('buyers.id'), nullable=False)
    name = db.Column(db.String(500))
    designation = db.Column(db.String(500))
    mobile = db.Column(db.Text)  # JSON-encoded list of mobiles
    whatsapp = db.Column(db.String(200))
    email = db.Column(db.String(200))
    is_primary = db.Column(db.Boolean, default=False)

    def to_dict(self):
        mobiles = []
        try:
            if self.mobile:
                mobiles = json.loads(self.mobile)
                if isinstance(mobiles, str): # Handle legacy single string mobile
                    mobiles = [mobiles]
        except:
            if self.mobile:
                mobiles = [self.mobile]

        return {
            'id': self.id,
            'buyer_id': self.buyer_id,
            'name': self.name,
            'designation': self.designation,
            'mobiles': mobiles,
            'mobile_display': ", ".join(mobiles) if mobiles else "-",
            'whatsapp': self.whatsapp,
            'email': self.email,
            'is_primary': self.is_primary
        }

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)
    material_name = db.Column(db.String(1000), nullable=False)
    purchase_date = db.Column(db.Date, default=datetime.date.today)
    quantity = db.Column(db.Float, default=0.0)
    cost = db.Column(db.Float, default=0.0)
    tags = db.Column(db.String(2000)) # Comma separated for now, or link to Tag? keeping simple as string for specific material tags
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    
    # Relationship to shop
    shop = db.relationship('Shop', backref='inventory_supplied')

    def to_dict(self):
        return {
            'id': self.id,
            'shop_id': self.shop_id,
            'shop_name': self.shop.name if self.shop else 'Unknown',
            'material_name': self.material_name,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'purchase_date_display': self.purchase_date.strftime('%d-%m-%Y') if self.purchase_date else '-',
            'quantity': self.quantity,
            'cost': self.cost,
            'tags': self.tags
        }

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    display_id = db.Column(db.String(50), unique=True, index=True)  # BEW-TRX-1
    voucher_id = db.Column(db.String(50))  # BEW-VCH-S-1
    buyer_id = db.Column(db.Integer, db.ForeignKey('buyers.id'), nullable=False)
    sale_date = db.Column(db.Date, default=datetime.date.today)
    voucher_image = db.Column(db.String(5000))
    total_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'display_id': self.display_id,
            'voucher_id': self.voucher_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.company_name if self.buyer else 'Unknown',
            'sale_date': self.sale_date.isoformat() if self.sale_date else None,
            'sale_date_display': self.sale_date.strftime('%d-%m-%Y') if self.sale_date else '-',
            'voucher_image': self.voucher_image,
            'total_amount': self.total_amount,
            'item_count': len(self.items) if self.items else 0
        }

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=True)  # Link to master
    product_name = db.Column(db.String(1000))  # Kept for backward compatibility
    quantity = db.Column(db.Float, default=0.0)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    weight = db.Column(db.Float, default=0.0)
    
    # Traceability: Link to inventory item used (deprecated, use raw_material_id)
    inventory_link_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=True)
    inventory_item = db.relationship('InventoryItem')
    raw_material = db.relationship('RawMaterial')

    def to_dict(self):
        return {
            'id': self.id,
            'sale_id': self.sale_id,
            'raw_material_id': self.raw_material_id,
            'product_name': self.raw_material.name if self.raw_material else self.product_name,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total_price': self.total_price,
            'weight': self.weight,
            'inventory_link_id': self.inventory_link_id,
            'inventory_material_name': self.inventory_item.material_name if self.inventory_item else None
        }


class SupplierPurchase(db.Model):
    __tablename__ = 'supplier_purchases'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_id = db.Column(db.String(50), unique=True, index=True)  # BEW-BUY-1
    voucher_id = db.Column(db.String(50))  # BEW-VCH-P-1
    supplier_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    purchase_date = db.Column(db.Date, default=datetime.date.today, nullable=False)
    work_order_id = db.Column(db.String(36), db.ForeignKey('work_orders.id'), nullable=True, index=True)
    voucher_no = db.Column(db.String(200))
    voucher_file_path = db.Column(db.String(5000))
    payment_status = db.Column(db.String(50), default='pending')
    paid_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    supplier = db.relationship('Shop')
    items = db.relationship('SupplierPurchaseItem', backref='purchase', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'display_id': self.display_id,
            'voucher_id': self.voucher_id,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else 'Unknown',
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'purchase_date_display': self.purchase_date.strftime('%d-%m-%Y') if self.purchase_date else '-',
            'work_order_id': self.work_order_id,
            'voucher_no': self.voucher_no,
            'voucher_file_path': self.voucher_file_path,
            'payment_status': self.payment_status,
            'paid_amount': self.paid_amount,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_items:
            items = [i.to_dict() for i in self.items]
            data['items'] = items
            data['total_amount'] = sum(float(i.get('total_amount') or 0) for i in items)
        else:
            data['item_count'] = len(self.items) if self.items else 0
            data['total_amount'] = sum(float(i.total_amount or 0) for i in self.items) if self.items else 0

        return data


class SupplierPurchaseItem(db.Model):
    __tablename__ = 'supplier_purchase_items'
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.String(36), db.ForeignKey('supplier_purchases.id', ondelete='CASCADE'), nullable=False, index=True)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=True)  # Link to master
    product_name = db.Column(db.String(1000))  # Kept for backward compatibility
    specification = db.Column(db.String(2000))
    quantity = db.Column(db.Float, default=0.0)
    weight = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(100))
    rate_per_unit = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    # stock_status removed - now tracked via StockMovement
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    raw_material = db.relationship('RawMaterial')

    def to_dict(self):
        return {
            'id': self.id,
            'purchase_id': self.purchase_id,
            'raw_material_id': self.raw_material_id,
            'product_name': self.raw_material.name if self.raw_material else self.product_name,
            'specification': self.specification,
            'quantity': self.quantity,
            'weight': self.weight,
            'unit': self.unit,
            'rate_per_unit': self.rate_per_unit,
            'total_amount': self.total_amount,
            'current_stock': self.raw_material.current_stock if self.raw_material else None
        }


class WorkOrder(db.Model):
    __tablename__ = 'work_orders'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_id = db.Column(db.String(50), unique=True, index=True)  # BEW-WO-1
    voucher_id = db.Column(db.String(50))  # BEW-VCH-W-1
    company_id = db.Column(db.Integer, db.ForeignKey('buyers.id'), nullable=False, index=True)
    job_date = db.Column(db.Date, default=datetime.date.today, nullable=False)
    job_name = db.Column(db.String(1000), nullable=False)
    job_description = db.Column(db.Text)
    status = db.Column(db.String(50), default='open')
    payment_status = db.Column(db.String(50), default='pending')
    paid_amount = db.Column(db.Float, default=0.0)
    pending_amount = db.Column(db.Float, default=0.0)
    quoted_price = db.Column(db.Float, default=0.0)
    delivery_date = db.Column(db.Date)
    labor_cost = db.Column(db.Float, default=0.0)
    material_cost = db.Column(db.Float, default=0.0)
    total_cost = db.Column(db.Float, default=0.0)
    hard_copy_path = db.Column(db.String(5000))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    company = db.relationship('Buyer')
    parts = db.relationship('WorkOrderPart', backref='work_order', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('WorkOrderDocument', backref='work_order', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_parts=False):
        data = {
            'id': self.id,
            'display_id': self.display_id,
            'voucher_id': self.voucher_id,
            'company_id': self.company_id,
            'company_name': self.company.company_name if self.company else 'Unknown',
            'job_date': self.job_date.isoformat() if self.job_date else None,
            'job_date_display': self.job_date.strftime('%d-%m-%Y') if self.job_date else '-',
            'job_name': self.job_name,
            'job_description': self.job_description,
            'status': self.status,
            'payment_status': self.payment_status,
            'paid_amount': self.paid_amount,
            'pending_amount': self.pending_amount,
            'quoted_price': self.quoted_price,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None,
            'delivery_date_display': self.delivery_date.strftime('%d-%m-%Y') if self.delivery_date else '-',
            'labor_cost': self.labor_cost,
            'material_cost': self.material_cost,
            'total_cost': self.total_cost,
            'hard_copy_path': self.hard_copy_path,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_parts:
            # Fetch parts from linked SupplierPurchase (Unified Procurement)
            linked_purchases = SupplierPurchase.query.filter_by(work_order_id=self.id).all()
            parts = []
            for p in linked_purchases:
                for item in p.items:
                    item_dict = item.to_dict()
                    # Map to legacy WorkOrderPart field names for UI compatibility
                    item_dict['supplier_id'] = p.supplier_id
                    item_dict['supplier_name'] = p.supplier.name if p.supplier else None
                    item_dict['voucher_no'] = p.voucher_no
                    item_dict['voucher_file_path'] = p.voucher_file_path
                    item_dict['qty'] = item.quantity
                    item_dict['price'] = item.total_amount
                    item_dict['measurement'] = item.specification
                    item_dict['part_name'] = item.product_name
                    # Mark as linked purchase
                    item_dict['is_linked_purchase'] = True
                    parts.append(item_dict)
            
            # Also include direct parts (WorkOrderPart)
            if self.parts:
                parts.extend([p.to_dict() for p in self.parts])
                
            data['parts'] = parts
            data['parts_cost_total'] = sum(float(p.get('price') or 0) for p in parts)
        else:
            # Count from both sources
            items_count = 0
            linked_purchases = SupplierPurchase.query.filter_by(work_order_id=self.id).all()
            for p in linked_purchases:
                items_count += len(p.items)
            
            legacy_count = len(self.parts) if self.parts else 0
            data['parts_count'] = items_count + legacy_count

        # Always include documents (for both detail and edit views)
        data['documents'] = [d.to_dict() for d in self.documents]

        return data


class WorkOrderDocument(db.Model):
    __tablename__ = 'work_order_documents'
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey('work_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    file_path = db.Column(db.String(5000), nullable=False)
    document_type = db.Column(db.String(200))  # e.g., 'Drawing', 'Photo', 'HardCopy'
    notes = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'work_order_id': self.work_order_id,
            'file_path': self.file_path,
            'document_type': self.document_type,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class WorkOrderPart(db.Model):
    __tablename__ = 'work_order_parts'
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey('work_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=True)  # Link to master
    part_name = db.Column(db.String(1000))  # Kept for backward compatibility
    supplier_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=True, index=True)
    voucher_no = db.Column(db.String(200))
    voucher_file_path = db.Column(db.String(5000))
    measurement = db.Column(db.String(200))
    unit = db.Column(db.String(100))
    qty = db.Column(db.Float, default=0.0)
    weight = db.Column(db.Float, default=0.0)
    price = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    supplier = db.relationship('Shop')
    raw_material = db.relationship('RawMaterial')

    def to_dict(self):
        return {
            'id': self.id,
            'work_order_id': self.work_order_id,
            'raw_material_id': self.raw_material_id,
            'part_name': self.raw_material.name if self.raw_material else self.part_name,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else None,
            'voucher_no': self.voucher_no,
            'voucher_file_path': self.voucher_file_path,
            'measurement': self.measurement,
            'unit': self.unit,
            'qty': self.qty,
            'weight': self.weight,
            'price': self.price,
            'current_stock': self.raw_material.current_stock if self.raw_material else None
        }

# ==================== ANALYTICS & VISITOR MESSAGES ====================
class Analytics(db.Model):
    __tablename__ = 'analytics'
    id = db.Column(db.Integer, primary_key=True)
    page_url = db.Column(db.String(500), nullable=False)
    visitor_ip = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    visit_time = db.Column(db.DateTime, default=datetime.datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'page_url': self.page_url,
            'visitor_ip': self.visitor_ip,
            'user_agent': self.user_agent,
            'visit_time': self.visit_time.isoformat()
        }

class VisitorMessage(db.Model):
    __tablename__ = 'visitor_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(500))
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'subject': self.subject,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat(),
            'created_at_display': self.created_at.strftime('%d-%m-%Y %H:%M')
        }

if __name__ == '__main__':
    from main import app, db as app_db
    from src.config import Settings, setup_logger, read_json, exists
    
    logger = setup_logger(Settings.LOG_DIR / "db.log", name=__name__)
    json_path = str(Settings.SHOPS_JSON_PATH)
    
    if exists(json_path):
        logger.info(f"Found {json_path}, importing...")
        with app.app_context():
            app_db.create_all() # Ensure tables exist
            cat_count, shop_count = app_db.import_from_json(json_path)
            logger.info(f"Successfully imported {cat_count} categories and {shop_count} shops.")
    else:
        logger.error(f"Error: {json_path} not found.")
        logger.info("Please run 'python odt_parser.py' first to generate the data.")