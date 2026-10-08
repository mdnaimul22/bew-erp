"""Shop routes — thin HTTP wrapper over shop service."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_babel import _
from src.helpers.utils import paginate_list, safe_int
from src.services import shop as shop_service
from src.helpers.exceptions import ValidationError
from src.config import setup_logger, Settings
from src.helpers.auth_middleware import admin_required

logger = setup_logger(Settings.LOG_DIR / "routers.log", name="bew.routers.shops")

shops_bp = Blueprint('shops', __name__)


@shops_bp.route('/')
def index():
    """Home page with search"""
    query = request.args.get('q', '')
    categories = shop_service.get_categories()

    if query:
        shops = shop_service.search(query)
    else:
        shops, _ = shop_service.list_all(limit=20)

    total_shops = shop_service.list_all(limit=1)[1]  # get total count

    return render_template('index.html',
                           shops=shops,
                           categories=categories,
                           query=query,
                           total_shops=total_shops)


@shops_bp.route('/shops')
def shop_list():
    """List all shops with pagination and search"""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20

    if query:
        all_shops = shop_service.search(query)
        shops, meta = paginate_list(all_shops, page, per_page=per_page)
        total = len(all_shops)
    else:
        offset = (page - 1) * per_page
        shops, total = shop_service.list_all(limit=per_page, offset=offset)
        total_pages = (total + per_page - 1) // per_page
        meta = {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }

    categories = shop_service.get_categories()

    return render_template('dashboard/shop/shop_list.html',
                           shops=shops,
                           categories=categories,
                           meta=meta,
                           search_query=query)


@shops_bp.route('/category/<int:category_id>')
def category_shops(category_id):
    """List shops in a category"""
    shops, categories, current_category = shop_service.list_by_category(category_id)

    meta = {
        'page': 1,
        'total_pages': 1,
        'total': len(shops),
        'per_page': len(shops) if shops else 20,
        'has_prev': False,
        'has_next': False
    }

    return render_template('dashboard/shop/shop_list.html',
                           shops=shops,
                           categories=categories,
                           current_category=current_category,
                           meta=meta)


@shops_bp.route('/shops/<int:shop_id>')
def shop_detail(shop_id):
    """View single shop details"""
    try:
        shop = shop_service.get(shop_id)
    except Exception:
        flash(_('দোকান খুঁজে পাওয়া যায়নি!'), 'error')
        return redirect(url_for('shops.index'))

    return render_template('dashboard/shop/shop_detail.html', shop=shop)


@shops_bp.route('/dashboard/shops/new', methods=['GET', 'POST'])
@admin_required
def new_shop():
    """Add new shop"""
    categories = shop_service.get_categories()

    if request.method == 'POST':
        try:
            shop_id = shop_service.create(request.form, request.files)
            flash(_('দোকান সফলভাবে যোগ করা হয়েছে!'), 'success')
            return redirect(url_for('shops.shop_detail', shop_id=shop_id))
        except ValidationError as e:
            flash(_(str(e)), 'error')
            return render_template('dashboard/shop/shop_form.html', categories=categories, shop=request.form, action='add')

    return render_template('dashboard/shop/shop_form.html', categories=categories, shop={}, action='add')


@shops_bp.route('/dashboard/shops/<int:shop_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_shop(shop_id):
    """Edit existing shop"""
    try:
        shop = shop_service.get(shop_id)
    except Exception:
        flash(_('দোকান খুঁজে পাওয়া যায়নি!'), 'error')
        return redirect(url_for('shops.index'))

    categories = shop_service.get_categories()

    if request.method == 'POST':
        try:
            shop_service.update(shop_id, request.form, request.files)
            flash(_('দোকানের তথ্য সফলভাবে আপডেট করা হয়েছে!'), 'success')
            return redirect(url_for('shops.shop_detail', shop_id=shop_id))
        except ValidationError as e:
            flash(_(str(e)), 'error')
            return render_template('dashboard/shop/shop_form.html', categories=categories, shop=request.form, action='edit', shop_id=shop_id)

    return render_template('dashboard/shop/shop_form.html', categories=categories, shop=shop, action='edit', shop_id=shop_id)


@shops_bp.route('/dashboard/shops/<int:shop_id>/delete', methods=['POST'])
@admin_required
def delete_shop(shop_id):
    """Delete a shop with password protection"""
    password = request.form.get('delete_password', '')
    try:
        if shop_service.delete(shop_id, password):
            flash(_('দোকান সফলভাবে মুছে ফেলা হয়েছে!'), 'success')
        else:
            flash(_('দোকান মুছে ফেলতে সমস্যা হয়েছে!'), 'error')
    except ValidationError as e:
        flash(_(str(e)), 'error')
        return redirect(url_for('shops.shop_detail', shop_id=shop_id))

    return redirect(url_for('shops.index'))


@shops_bp.route('/api/search')
def api_search():
    """API endpoint for search"""
    query = request.args.get('q', '')
    shops = shop_service.search(query) if query else []
    return jsonify(shops)


@shops_bp.route('/api/shops')
def api_shops():
    """API endpoint for all shops"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    shops, total = shop_service.list_all(limit=per_page, offset=offset)
    return jsonify({'shops': shops, 'total': total, 'page': page, 'per_page': per_page})


# ==================== TAG API ROUTES ====================

@shops_bp.route('/api/tags')
def api_tags():
    tags = shop_service.get_all_tags()
    return jsonify({'tags': tags})


@shops_bp.route('/api/tag/add', methods=['POST'])
@admin_required
def api_add_tag():
    data = request.get_json() or request.form
    name = data.get('name', '').strip()
    name_bn = data.get('name_bn', '').strip()
    if not name:
        return jsonify({'error': 'Tag name is required'}), 400
    tag_id = shop_service.add_tag(name, name_bn)
    return jsonify({'id': tag_id, 'name': name, 'name_bn': name_bn})


@shops_bp.route('/api/tag/delete/<int:tag_id>', methods=['POST', 'DELETE'])
@admin_required
def api_delete_tag(tag_id):
    if shop_service.delete_tag(tag_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Tag not found'}), 404


@shops_bp.route('/api/shop/<int:shop_id>/tags')
def api_shop_tags(shop_id):
    tags = shop_service.get_shop_tags(shop_id)
    return jsonify({'shop_id': shop_id, 'tags': tags})


@shops_bp.route('/api/shop/<int:shop_id>/tag/add', methods=['POST'])
@admin_required
def api_add_shop_tag(shop_id):
    data = request.get_json() or request.form
    tag_id = data.get('tag_id')
    if not tag_id:
        return jsonify({'error': 'tag_id is required'}), 400
    try:
        shop_tag_id = shop_service.add_shop_tag(shop_id, safe_int(tag_id, field='tag_id'))
        return jsonify({'success': True, 'shop_tag_id': shop_tag_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@shops_bp.route('/api/shop/<int:shop_id>/tag/remove', methods=['POST', 'DELETE'])
@admin_required
def api_remove_shop_tag(shop_id):
    data = request.get_json() or request.form
    tag_id = data.get('tag_id')
    if not tag_id:
        return jsonify({'error': 'tag_id is required'}), 400
    try:
        tag_id_int = safe_int(tag_id, field='tag_id')
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    if shop_service.remove_shop_tag(shop_id, tag_id_int):
        return jsonify({'success': True})
    return jsonify({'error': 'Tag not found on shop'}), 404


@shops_bp.route('/search/tag/<tag_name>')
def search_by_tag(tag_name):
    shops = shop_service.search_by_tag(tag_name)
    meta = {
        'page': 1,
        'total_pages': 1,
        'total': len(shops),
        'per_page': len(shops) if shops else 20,
        'has_prev': False,
        'has_next': False
    }
    return render_template('dashboard/shop/shop_list.html',
                           shops=shops,
                           categories=shop_service.get_categories(),
                           current_tag=tag_name,
                           meta=meta)

