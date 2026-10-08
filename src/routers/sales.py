"""Sales routes — thin HTTP wrapper over sale service."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_babel import _
from src.services import sale as sale_service
from src.helpers.exceptions import ValidationError
from src.config import setup_logger, Settings

from src.helpers.auth_middleware import admin_required

logger = setup_logger(Settings.LOG_DIR / "routers.log", name="bew.routers.sales")

sales_bp = Blueprint('sales', __name__, url_prefix='/dashboard')

@sales_bp.before_request
@admin_required
def before_request():
    pass


@sales_bp.route('/sales')
def sale_list():
    """Record of all material/product sales"""
    query = request.args.get('q', '').strip()
    sales = sale_service.list_all(query)
    page = request.args.get('page', 1, type=int)
    from src.helpers.utils import paginate_list
    sales, meta = paginate_list(sales, page, per_page=10)
    return render_template('dashboard/sales/sale_list.html', sales=sales, meta=meta, search_query=query)


@sales_bp.route('/sales/new', methods=['GET', 'POST'])
def new_sale():
    """Create a new sales entry"""
    buyers = sale_service.get_buyers()
    inventory_items = sale_service.get_inventory()

    if request.method == 'POST':
        try:
            sale_id = sale_service.create(
                request.form, request.files,
                client_key=request.headers.get('Idempotency-Key'))
            flash(_('Sale created successfully!'), 'success')
            return redirect(url_for('sales.sale_detail', sale_id=sale_id))
        except ValidationError as e:
            flash(_(str(e)), 'error')

    pre_selected_buyer_id = request.args.get('buyer_id', type=int)
    sale = {'buyer_id': pre_selected_buyer_id} if pre_selected_buyer_id else {}

    return render_template('dashboard/sales/sale_form.html', buyers=buyers, inventory=inventory_items,
                           sale=sale, action='add')


@sales_bp.route('/sales/<int:sale_id>/edit', methods=['GET', 'POST'])
def edit_sale(sale_id):
    """Modify existing sales entry"""
    sale = sale_service.get(sale_id)
    if not sale:
        flash(_('Sale record not found!'), 'error')
        return redirect(url_for('sales.sale_list'))

    buyers = sale_service.get_buyers()
    inventory_items = sale_service.get_inventory()

    if request.method == 'POST':
        try:
            sale_service.update(sale_id, request.form, request.files, existing_sale=sale)
            flash(_('Sale record updated successfully!'), 'success')
            return redirect(url_for('sales.sale_detail', sale_id=sale_id))
        except ValidationError as e:
            flash(_(str(e)), 'error')

    return render_template('dashboard/sales/sale_form.html', buyers=buyers, inventory=inventory_items,
                           sale=sale, action='edit')


@sales_bp.route('/sales/<int:sale_id>')
def sale_detail(sale_id):
    """Invoice/Sale detailed view"""
    sale = sale_service.get(sale_id)
    if not sale:
        flash(_('Sale not found!'), 'error')
        return redirect(url_for('sales.sale_list'))
    return render_template('dashboard/sales/sale_detail.html', sale=sale)


@sales_bp.route('/sales/<int:sale_id>/delete', methods=['POST'])
def delete_sale(sale_id):
    """Remove sales record"""
    password = request.form.get('delete_password', '')
    try:
        if sale_service.delete(sale_id, password):
            flash(_('Sale deleted successfully!'), 'success')
        else:
            flash(_('Error deleting sale!'), 'error')
    except ValidationError as e:
        flash(_(str(e)), 'error')
    return redirect(url_for('sales.sale_list'))
