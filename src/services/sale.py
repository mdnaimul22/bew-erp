"""Sale service — business logic for customer invoice/sales management."""
import datetime
from pydantic import ValidationError as PydanticValidationError
from src.config import setup_logger, Settings
from src.db.database import db
from src.helpers.exceptions import ValidationError
from src.helpers.upload import save_upload
from src.helpers.auth import verify_delete_password
from src.helpers.utils import safe_float
from src.schema.sale import SaleItemCreate

logger = setup_logger(Settings.LOG_DIR / "services.log", name="bew.services.sale")


def list_all(query: str = '', limit: int = 1000, offset: int = 0):
    """Return all sales records, optionally filtered."""
    if query:
        from src.db.database import Sale, Buyer
        from sqlalchemy import or_
        items = Sale.query.join(Buyer, Sale.buyer_id == Buyer.id, isouter=True).filter(
            or_(
                Sale.display_id.ilike(f'%{query}%'),
                Sale.voucher_id.ilike(f'%{query}%'),
                Buyer.company_name.ilike(f'%{query}%')
            )
        ).order_by(Sale.sale_date.desc()).limit(limit).offset(offset).all()
        return [s.to_dict() for s in items]

    return db.get_all_sales(limit=limit, offset=offset)


def get(sale_id: int):
    """Get a single sale by ID."""
    return db.get_sale_by_id(sale_id)


def get_buyers():
    """Return all buyers for the sale form dropdown."""
    return db.get_all_buyers()


def get_inventory():
    """Return all inventory items for the sale form dropdown."""
    return db.get_all_inventory()


def create(form_data, files=None):
    """Create a new sale record.

    Returns:
        The new sale ID.
    """
    voucher_filename = None
    if files and 'voucher_image' in files:
        voucher_filename = save_upload(files['voucher_image'], 'sales_voucher')

    items = _parse_sale_items(form_data)
    _validate_items(items)
    parsed_date = _parse_date(form_data.get('sale_date'))

    sale_data = {
        'buyer_id': form_data.get('buyer_id'),
        'sale_date': parsed_date or datetime.date.today(),
        'voucher_image': voucher_filename,
        'items': items,
    }

    sale_id = db.add_sale(sale_data)
    logger.info(f"Created sale #{sale_id}")
    return sale_id


def update(sale_id: int, form_data, files=None, existing_sale=None):
    """Update an existing sale record."""
    voucher_filename = (existing_sale or {}).get('voucher_image')
    if files and 'voucher_image' in files:
        vf = save_upload(files['voucher_image'], 'sales_voucher')
        if vf:
            voucher_filename = vf

    items = _parse_sale_items(form_data)
    _validate_items(items)
    parsed_date = _parse_date(form_data.get('sale_date'))

    sale_data = {
        'buyer_id': form_data.get('buyer_id'),
        'sale_date': parsed_date or datetime.date.today(),
        'voucher_image': voucher_filename,
        'items': items,
    }

    db.update_sale(sale_id, sale_data)
    logger.info(f"Updated sale #{sale_id}")
    return True


def delete(sale_id: int, password: str = ''):
    """Delete a sale record."""
    verify_delete_password(password)

    if db.delete_sale(sale_id):
        logger.info(f"Deleted sale #{sale_id}")
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
    """Run parsed line items through the existing SaleItemCreate validators."""
    for item in items:
        try:
            SaleItemCreate.model_validate(item)
        except PydanticValidationError as e:
            raise ValidationError(f"Invalid sale item: {e.errors()[0]['msg']}") from None


def _parse_sale_items(form_data) -> list[dict]:
    """Parse dynamic sale item rows from form data."""
    product_names = form_data.getlist('product_name')
    quantities = form_data.getlist('quantity')
    unit_prices = form_data.getlist('unit_price')
    weights = form_data.getlist('weight')
    inventory_links = form_data.getlist('inventory_link_id')

    items = []
    for i in range(len(product_names)):
        if not product_names[i]:
            continue
        items.append({
            'product_name': product_names[i],
            'quantity': safe_float(quantities[i], field='quantity') if i < len(quantities) else 0,
            'unit_price': safe_float(unit_prices[i], field='unit_price') if i < len(unit_prices) else 0,
            'weight': safe_float(weights[i], field='weight') if i < len(weights) else 0,
            'inventory_link_id': inventory_links[i] if i < len(inventory_links) and inventory_links[i] else None,
        })

    return items
