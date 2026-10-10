"""Shop service — business logic for supplier/vendor management."""
from src.config import setup_logger, Settings
from src.db.database import db, Shop, Category, Tag, ShopTag
from src.helpers.exceptions import ValidationError, NotFoundError
from src.helpers.upload import save_upload
from src.helpers.auth import verify_delete_password

logger = setup_logger(Settings.LOG_DIR / "services.log", name="bew.services.shop")


def list_all(limit: int = 20, offset: int = 0):
    """Return paginated shop list."""
    shops = db.get_all_shops(limit=limit, offset=offset)
    total = db.get_shops_count()
    return shops, total


def list_by_category(category_id: int):
    """Return all shops in a specific category."""
    shops = db.get_shops_by_category(category_id)
    categories = db.get_all_categories()
    current_category = next((c for c in categories if c['id'] == category_id), None)
    return shops, categories, current_category


def get(shop_id: int):
    """Get a single shop by ID."""
    shop = db.get_shop_by_id(shop_id)
    if not shop:
        raise NotFoundError('Shop', shop_id)
    return shop


def search(query: str, limit: int = 200):
    """Search shops by keyword (SQL-prefiltered, capped at limit rows)."""
    if not query:
        return []
    return db.search_shops(query, limit=limit)


def get_categories():
    """Return all categories."""
    return db.get_all_categories()


def create(form_data, files=None) -> int:
    """Create a new shop from form data.

    Args:
        form_data: Flask request.form
        files: Flask request.files

    Returns:
        New shop ID.
    """
    name = form_data.get('name', '').strip()
    if not name:
        raise ValidationError("প্রতিষ্ঠানের নাম আবশ্যক!")

    category_id = _resolve_category(form_data)

    visiting_card_filename = None
    if files and 'visiting_card' in files:
        visiting_card_filename = save_upload(files['visiting_card'], 'visiting_card')

    shop_data = {
        'category_id': category_id,
        'serial_no': form_data.get('serial_no', ''),
        'name': name,
        'proprietor': form_data.get('proprietor', ''),
        'address': form_data.get('address', ''),
        'mobile': form_data.get('mobile', ''),
        'transaction_status': form_data.get('transaction_status', ''),
        'whatsapp': form_data.get('whatsapp', ''),
        'email_web': form_data.get('email_web', ''),
        'products': form_data.get('products', ''),
        'visiting_card': visiting_card_filename,
    }

    shop_id = db.add_shop(shop_data)
    _sync_tags(shop_id, form_data.get('tags', ''))

    logger.info(f"Created shop #{shop_id}: {name}")
    return shop_id


def update(shop_id: int, form_data, files=None) -> bool:
    """Update an existing shop."""
    name = form_data.get('name', '').strip()
    if not name:
        raise ValidationError("প্রতিষ্ঠানের নাম আবশ্যক!")

    category_id = _resolve_category(form_data)

    shop_data = {
        'category_id': category_id,
        'serial_no': form_data.get('serial_no', ''),
        'name': name,
        'proprietor': form_data.get('proprietor', ''),
        'address': form_data.get('address', ''),
        'mobile': form_data.get('mobile', ''),
        'transaction_status': form_data.get('transaction_status', ''),
        'whatsapp': form_data.get('whatsapp', ''),
        'email_web': form_data.get('email_web', ''),
        'products': form_data.get('products', ''),
    }

    if files and 'visiting_card' in files:
        vc = save_upload(files['visiting_card'], 'visiting_card')
        if vc:
            shop_data['visiting_card'] = vc

    db.update_shop(shop_id, shop_data)
    _sync_tags(shop_id, form_data.get('tags', ''))

    logger.info(f"Updated shop #{shop_id}")
    return True


def delete(shop_id: int, password: str = '') -> bool:
    """Delete a shop after password verification."""
    verify_delete_password(password)

    if db.delete_shop(shop_id):
        logger.info(f"Deleted shop #{shop_id}")
        return True
    return False


# ---- Tag operations ----

def get_all_tags():
    return db.get_all_tags()

def add_tag(name: str, name_bn: str = ''):
    if not name:
        raise ValidationError("Tag name is required")
    return db.add_tag(name, name_bn)

def delete_tag(tag_id: int) -> bool:
    return db.delete_tag(tag_id)

def get_shop_tags(shop_id: int):
    return db.get_shop_tags(shop_id)

def add_shop_tag(shop_id: int, tag_id: int):
    return db.add_shop_tag(shop_id, tag_id)

def remove_shop_tag(shop_id: int, tag_id: int):
    return db.remove_shop_tag(shop_id, tag_id)

def search_by_tag(tag_name: str):
    return db.search_shops_by_tag(tag_name)


_TOOL_NAMES = ("shop_search", "shop_detail", "shop_all")


def _tool_row(shop):
    tags = shop.get("tags") or []
    return {
        "shop_id": shop.get("id"),
        "name": shop.get("name"),
        "proprietor": shop.get("proprietor"),
        "address": shop.get("address"),
        "mobile": shop.get("mobile"),
        "whatsapp": shop.get("whatsapp"),
        "products": shop.get("products"),
        "category_name": shop.get("category_name"),
        "tags": [t.get("name") for t in tags if isinstance(t, dict)],
    }


def execute(action):
    action = action or {}
    name = action.get("tool_name", "")
    if name == "shop_search":
        query = (action.get("query") or "").strip()
        if not query:
            raise ValidationError("query is required for shop_search.")
        return {"ok": True, "tool": name, "query": query,
                "shops": [_tool_row(s) for s in search(query, limit=action.get("limit", 20))]}
    if name == "shop_detail":
        if action.get("shop_id") is None:
            raise ValidationError("shop_id is required for shop_detail.")
        return {"ok": True, "tool": name, "shop": get(action.get("shop_id"))}
    if name == "shop_all":
        shops, total = list_all(limit=action.get("limit", 20), offset=action.get("offset", 0))
        return {"ok": True, "tool": name, "total": total, "shops": [_tool_row(s) for s in shops]}
    raise ValidationError(f"Unknown tool {name!r}. Available: {', '.join(_TOOL_NAMES)}.")


# ---- Private helpers ----

def _resolve_category(form_data):
    """Resolve category_id from form, handling 'new' category creation."""
    category_id = form_data.get('category_id')
    new_category_name = form_data.get('new_category_name', '').strip()

    if category_id == 'new' and new_category_name:
        return db.add_category(new_category_name)
    try:
        return int(category_id) if category_id else None
    except ValueError:
        return None


def _sync_tags(shop_id: int, tags_input: str | None):
    """Sync tags for a shop: remove old, add new from comma-separated string."""
    if tags_input is None:
        return

    existing_tags = db.get_shop_tags(shop_id)
    for t in existing_tags:
        db.remove_shop_tag(shop_id, t['id'])

    tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
    for tag_name in tag_names:
        tag_id = db.add_tag(tag_name)
        db.add_shop_tag(shop_id, tag_id)
