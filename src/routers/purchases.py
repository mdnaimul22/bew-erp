"""Purchase routes — thin HTTP wrapper over purchase service."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_babel import _
from src.services import purchase as purchase_service
from src.helpers.exceptions import ValidationError
from src.config import setup_logger, Settings

from src.helpers.auth_middleware import admin_required

logger = setup_logger(Settings.LOG_DIR / "routers.log", name="bew.routers.purchases")

purchases_bp = Blueprint('purchases', __name__, url_prefix='/dashboard')

@purchases_bp.before_request
@admin_required
def before_request():
    pass


@purchases_bp.route('/purchases')
def purchase_list():
    """List all supplier purchases"""
    query = request.args.get('q', '').strip()
    purchases = purchase_service.list_all(query)
    page = request.args.get('page', 1, type=int)
    from src.helpers.utils import paginate_list
    purchases, meta = paginate_list(purchases, page, per_page=10)
    return render_template('dashboard/purchase/purchase_list.html', purchases=purchases, supplier=None, meta=meta, search_query=query)


@purchases_bp.route('/shops/<int:shop_id>/purchases')
def shop_purchases(shop_id):
    """List purchases from a specific supplier"""
    supplier = purchase_service.get_supplier(shop_id)
    if not supplier:
        flash(_('দোকান খুঁজে পাওয়া যায়নি!'), 'error')
        return redirect(url_for('shops.shop_list'))
    purchases = purchase_service.list_by_supplier(shop_id)
    page = request.args.get('page', 1, type=int)
    from src.helpers.utils import paginate_list
    purchases, meta = paginate_list(purchases, page, per_page=10)
    return render_template('dashboard/purchase/purchase_list.html', purchases=purchases, supplier=supplier, meta=meta)


@purchases_bp.route('/purchases/new', methods=['GET', 'POST'])
def new_purchase():
    """Log a new purchase voucher"""
    shops = purchase_service.get_shops()
    preselected_supplier_id = request.args.get('supplier_id', type=int)

    if request.method == 'POST':
        try:
            purchase_id = purchase_service.create(
                request.form, request.files,
                client_key=request.headers.get('Idempotency-Key'))
            flash(_('Purchase saved successfully!'), 'success')
            return redirect(url_for('purchases.purchase_detail', purchase_id=purchase_id))
        except ValidationError as e:
            flash(_(str(e)), 'error')
            return render_template('dashboard/purchase/purchase_form.html', action='add', purchase={},
                                   shops=shops, preselected_supplier_id=preselected_supplier_id)

    return render_template('dashboard/purchase/purchase_form.html', action='add', purchase={},
                           shops=shops, preselected_supplier_id=preselected_supplier_id)


@purchases_bp.route('/purchases/<purchase_id>')
def purchase_detail(purchase_id):
    """View purchase voucher details"""
    purchase = purchase_service.get(purchase_id)
    if not purchase:
        flash(_('Purchase not found!'), 'error')
        return redirect(url_for('purchases.purchase_list'))
    return render_template('dashboard/purchase/purchase_detail.html', purchase=purchase)


@purchases_bp.route('/purchases/<purchase_id>/edit', methods=['GET', 'POST'])
def edit_purchase(purchase_id):
    """Update purchase voucher details"""
    purchase = purchase_service.get(purchase_id)
    if not purchase:
        flash(_('Purchase not found!'), 'error')
        return redirect(url_for('purchases.purchase_list'))

    shops = purchase_service.get_shops()

    if request.method == 'POST':
        try:
            purchase_service.update(purchase_id, request.form, request.files, existing_purchase=purchase)
            flash(_('Purchase updated successfully!'), 'success')
            return redirect(url_for('purchases.purchase_detail', purchase_id=purchase_id))
        except ValidationError as e:
            flash(_(str(e)), 'error')

    return render_template('dashboard/purchase/purchase_form.html', action='edit', purchase=purchase,
                           shops=shops, preselected_supplier_id=purchase.get('supplier_id'))


@purchases_bp.route('/purchases/<purchase_id>/delete', methods=['POST'])
def delete_purchase(purchase_id):
    """Delete purchase record"""
    password = request.form.get('delete_password', '')
    try:
        if purchase_service.delete(purchase_id, password):
            flash(_('Purchase deleted successfully!'), 'success')
        else:
            flash(_('Error deleting purchase!'), 'error')
    except ValidationError as e:
        flash(_(str(e)), 'error')
    return redirect(url_for('purchases.purchase_list'))
