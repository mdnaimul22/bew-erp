"""Purchase service — business logic for supplier purchase vouchers."""
import datetime
from pydantic import ValidationError as PydanticValidationError
from src.config import setup_logger, Settings
from src.db.database import db
from src.helpers.exceptions import ValidationError
from src.helpers.upload import save_upload
from src.helpers.auth import verify_delete_password
from src.helpers.utils import safe_float
from src.schema.purchase import PurchaseItemCreate

logger = setup_logger(Settings.LOG_DIR / "services.log", name="bew.services.purchase")


def list_all(query: str = '', limit: int = 1000, offset: int = 0):
    """Return all supplier purchases, optionally filtered."""
    if query:
        from src.db.database import SupplierPurchase, Shop
        from sqlalchemy import or_
        items = SupplierPurchase.query.join(Shop, SupplierPurchase.supplier_id == Shop.id, isouter=True).filter(
            or_(
                SupplierPurchase.display_id.ilike(f'%{query}%'),
                SupplierPurchase.voucher_no.ilike(f'%{query}%'),
                SupplierPurchase.notes.ilike(f'%{query}%'),
                Shop.name.ilike(f'%{query}%')
            )
        ).order_by(SupplierPurchase.purchase_date.desc()).limit(limit).offset(offset).all()
        return [p.to_dict() for p in items]

    return db.get_all_supplier_purchases(limit=limit, offset=offset)


def list_by_supplier(shop_id: int):
    """Return purchases from a specific supplier."""
    return db.get_supplier_purchases(shop_id)


def get_supplier(shop_id: int):
    """Get supplier (shop) details."""
    return db.get_shop_by_id(shop_id)


def get(purchase_id):
    """Get a single purchase by ID."""
    return db.get_supplier_purchase_by_id(purchase_id)


def get_shops():
    """Return all shops for supplier dropdown."""
    return db.get_all_shops()


def create(form_data, files=None):
    """Create a new purchase voucher.

    Returns:
        The new purchase ID.
    """
    supplier_id = form_data.get('supplier_id')
    if not supplier_id:
        raise ValidationError("Supplier is required!")

    purchase_date = _parse_date(form_data.get('purchase_date'))

    voucher_path = ''
    if files and 'voucher_file' in files:
        vp = save_upload(files['voucher_file'], 'purchase_voucher')
        if vp:
            voucher_path = vp

    items = _parse_purchase_items(form_data)
    _validate_items(items)

    purchase_data = {
        'supplier_id': supplier_id,
        'purchase_date': purchase_date,
        'voucher_no': form_data.get('voucher_no'),
        'voucher_file_path': voucher_path,
        'payment_status': form_data.get('payment_status'),
        'paid_amount': form_data.get('paid_amount'),
        'notes': form_data.get('notes'),
        'items': items,
    }

    purchase_id = db.add_supplier_purchase(purchase_data)
    logger.info(f"Created purchase #{purchase_id}")
    return purchase_id


def update(purchase_id, form_data, files=None, existing_purchase=None):
    """Update an existing purchase voucher."""
    purchase_date = _parse_date(form_data.get('purchase_date'))

    voucher_path = (existing_purchase or {}).get('voucher_file_path', '')
    if files and 'voucher_file' in files:
        vp = save_upload(files['voucher_file'], 'purchase_voucher')
        if vp:
            voucher_path = vp

    items = _parse_purchase_items(form_data)
    _validate_items(items)

    purchase_data = {
        'supplier_id': form_data.get('supplier_id') or (existing_purchase or {}).get('supplier_id'),
        'purchase_date': purchase_date,
        'voucher_no': form_data.get('voucher_no'),
        'voucher_file_path': voucher_path,
        'payment_status': form_data.get('payment_status'),
        'paid_amount': form_data.get('paid_amount'),
        'notes': form_data.get('notes'),
        'items': items,
    }

    db.update_supplier_purchase(purchase_id, purchase_data)
    logger.info(f"Updated purchase #{purchase_id}")
    return True


def delete(purchase_id, password: str = ''):
    """Delete a purchase record."""
    verify_delete_password(password)

    if db.delete_supplier_purchase(purchase_id):
        logger.info(f"Deleted purchase #{purchase_id}")
        return True
    return False


def _parse_date(date_str: str | None):
    """Parse a YYYY-MM-DD date string."""
    if not date_str:
        return None
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError("Invalid date format. Use YYYY-MM-DD.")


def _validate_items(items: list[dict]) -> None:
    """Run parsed line items through the existing PurchaseItemCreate validators."""
    for item in items:
        try:
            PurchaseItemCreate.model_validate(item)
        except PydanticValidationError as e:
            raise ValidationError(f"Invalid purchase item: {e.errors()[0]['msg']}") from None


def _parse_purchase_items(form_data) -> list[dict]:
    """Parse dynamic purchase item rows from form data."""
    product_names = form_data.getlist('product_name')
    specifications = form_data.getlist('specification')
    quantities = form_data.getlist('quantity')
    units = form_data.getlist('unit')
    rates = form_data.getlist('rate_per_unit')
    stock_statuses = form_data.getlist('stock_status')

    items = []
    for i in range(len(product_names)):
        if not product_names[i]:
            continue
        qty = safe_float(quantities[i], field='quantity') if i < len(quantities) else 0
        rate = safe_float(rates[i], field='rate_per_unit') if i < len(rates) else 0
        items.append({
            'product_name': product_names[i],
            'specification': specifications[i] if i < len(specifications) else '',
            'quantity': qty,
            'unit': units[i] if i < len(units) else '',
            'rate_per_unit': rate,
            'total_amount': qty * rate,
            'stock_status': stock_statuses[i] if i < len(stock_statuses) else 'IN_STOCK',
        })

    return items
