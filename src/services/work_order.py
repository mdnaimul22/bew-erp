"""Work order service — business logic for production job management."""
import datetime
from src.config import setup_logger, Settings, exists, delete
from src.db.database import db
from src.helpers.exceptions import ValidationError
from src.helpers.upload import save_upload
from src.helpers.auth import verify_delete_password
from src.helpers.utils import safe_float

logger = setup_logger(Settings.LOG_DIR / "services.log", name="bew.services.work_order")


def list_all(query: str = ''):
    """Return all work orders, optionally filtered."""
    if query:
        from src.db.database import WorkOrder, Buyer
        from sqlalchemy import or_
        items = WorkOrder.query.join(Buyer, WorkOrder.company_id == Buyer.id, isouter=True).filter(
            or_(
                WorkOrder.display_id.ilike(f'%{query}%'),
                WorkOrder.voucher_id.ilike(f'%{query}%'),
                WorkOrder.job_name.ilike(f'%{query}%'),
                WorkOrder.status.ilike(f'%{query}%'),
                Buyer.company_name.ilike(f'%{query}%')
            )
        ).order_by(WorkOrder.job_date.desc()).all()
        return [w.to_dict() for w in items]
        
    return db.get_all_work_orders()


def get(work_order_id):
    """Get a single work order by ID."""
    return db.get_work_order_by_id(work_order_id)


def get_buyers():
    """Return all buyers/companies for work order form."""
    return db.get_all_buyers()


def get_suppliers():
    """Return all shops/suppliers for work order form."""
    return db.get_all_shops()


def create(form_data, files=None):
    """Create a new work order.

    Returns:
        The new work order ID.
    """
    company_id = form_data.get('company_id')
    if not company_id:
        raise ValidationError("Company is required!")

    job_date = _parse_date(form_data.get('job_date'))
    delivery_date = _parse_date(form_data.get('delivery_date'))
    parts = _parse_parts(form_data, files)
    hard_copy_path = _handle_hard_copy(form_data, files)
    documents = _parse_gallery_documents(form_data, files)

    data = {
        'company_id': company_id,
        'job_date': job_date,
        'job_name': form_data.get('job_name'),
        'job_description': form_data.get('job_description'),
        'status': form_data.get('status'),
        'quoted_price': safe_float(form_data.get('quoted_price'), field='quoted_price'),
        'delivery_date': delivery_date,
        'labor_cost': safe_float(form_data.get('labor_cost'), field='labor_cost'),
        'material_cost': safe_float(form_data.get('material_cost'), field='material_cost'),
        'total_cost': safe_float(form_data.get('total_cost'), field='total_cost'),
        'hard_copy_path': hard_copy_path,
        'parts': parts,
        'documents': documents,
    }

    work_order_id = db.add_work_order(data)
    logger.info(f"Created work order #{work_order_id}")
    return work_order_id


def update(work_order_id, form_data, files=None):
    """Update an existing work order."""
    job_date = _parse_date(form_data.get('job_date'))
    delivery_date = _parse_date(form_data.get('delivery_date'))
    parts = _parse_parts(form_data, files)
    hard_copy_path = _handle_hard_copy(form_data, files)
    documents = _parse_gallery_documents(form_data, files)

    data = {
        'company_id': form_data.get('company_id'),
        'job_date': job_date,
        'job_name': form_data.get('job_name'),
        'job_description': form_data.get('job_description'),
        'status': form_data.get('status'),
        'delivery_date': delivery_date,
        'hard_copy_path': hard_copy_path,
        'parts': parts,
        'documents': documents,
    }

    # Omit money keys the form did not submit: safe_float(None) -> 0.0 would
    # otherwise zero real values and re-trigger pending validation on legacy
    # paid>quoted rows. A field present-but-empty still coerces to 0.0.
    for key in ('quoted_price', 'labor_cost', 'material_cost', 'total_cost'):
        raw = form_data.get(key)
        if raw is not None:
            data[key] = safe_float(raw, field=key)

    db.update_work_order(work_order_id, data)
    logger.info(f"Updated work order #{work_order_id}")
    return True


def delete(work_order_id, password: str = ''):
    """Delete a work order."""
    verify_delete_password(password)

    if db.delete_work_order(work_order_id):
        logger.info(f"Deleted work order #{work_order_id}")
        return True
    return False


def _parse_date(date_str: str | None):
    """Parse YYYY-MM-DD date string."""
    if not date_str:
        return None
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError("Invalid date format. Use YYYY-MM-DD.")


def _parse_parts(form_data, files=None) -> list[dict]:
    """Parse dynamic part rows from form data, including voucher uploads."""
    part_names = form_data.getlist('part_name')
    supplier_ids = form_data.getlist('supplier_id')
    voucher_file_paths = form_data.getlist('voucher_file_path')
    measurements = form_data.getlist('measurement')
    units = form_data.getlist('unit')
    qtys = form_data.getlist('qty')
    weights = form_data.getlist('weight')
    prices = form_data.getlist('price')

    parts = []
    for i in range(len(part_names)):
        if not part_names[i]:
            continue

        voucher_path = voucher_file_paths[i] if i < len(voucher_file_paths) else ''

        if files:
            file = files.get(f'voucher_file_{i}')
            if file:
                vp = save_upload(file, 'purchase_voucher')
                if vp:
                    # Delete old file if being replaced
                    delete_upload(voucher_path)
                    voucher_path = vp

        parts.append({
            'part_name': part_names[i],
            'supplier_id': supplier_ids[i] if i < len(supplier_ids) and supplier_ids[i] else None,
            'voucher_no': '',
            'voucher_file_path': voucher_path,
            'measurement': measurements[i] if i < len(measurements) else '',
            'unit': units[i] if i < len(units) else '',
            'qty': safe_float(qtys[i], field='qty') if i < len(qtys) else 0,
            'weight': safe_float(weights[i], field='weight') if i < len(weights) else 0,
            'price': safe_float(prices[i], field='price') if i < len(prices) else 0,
        })

    return parts


def _handle_hard_copy(form_data, files=None) -> str:
    """Handle hard copy scan upload."""
    hard_copy_path = form_data.get('hard_copy_path', '')

    if files:
        hard_copy_file = files.get('hard_copy_file')
        if hard_copy_file:
            hc = save_upload(hard_copy_file, 'work_orders')
            if hc:
                delete_upload(hard_copy_path)
                hard_copy_path = hc

    return hard_copy_path


def _parse_gallery_documents(form_data, files=None) -> list[dict]:
    """Parse gallery/document attachments from form data."""
    doc_types = form_data.getlist('doc_type')
    doc_notes = form_data.getlist('doc_notes')
    doc_file_paths = form_data.getlist('doc_file_path')

    documents = []
    for i in range(len(doc_types)):
        doc_path = doc_file_paths[i] if i < len(doc_file_paths) else ''

        if files:
            file = files.get(f'gallery_file_{i}')
            if file:
                dp = save_upload(file, 'gallery')
                if dp:
                    delete_upload(doc_path)
                    doc_path = dp

        if doc_path:
            documents.append({
                'file_path': doc_path,
                'document_type': doc_types[i] if i < len(doc_types) else 'Other',
                'notes': doc_notes[i] if i < len(doc_notes) else '',
            })

    return documents


def delete_upload(file_path: str):
    """Delete an uploaded file if it exists."""
    if not file_path:
        return
    rel_path = f"{Settings.upload_dir_rel}/{file_path}"
    if exists(rel_path):
        try:
            delete(rel_path)
            logger.info(f"Deleted upload: {rel_path}")
        except OSError as e:
            logger.warning(f"Failed to delete {rel_path}: {e}")
