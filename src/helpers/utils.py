"""General utility functions for the BEW application."""
from src.config import Settings, setup_logger
from src.helpers.exceptions import ValidationError

logger = setup_logger(Settings.LOG_DIR / "helpers.log", name="bew.helpers.utils")


def safe_float(raw: str | None, field: str) -> float:
    """Coerce form input to float; empty/None → 0.0, garbage → ValidationError."""
    if raw is None:
        return 0.0
    if isinstance(raw, str) and not raw.strip():
        return 0.0
    try:
        return float(raw)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid number for '{field}'.") from None


def safe_int(raw: str | None, field: str) -> int:
    """Coerce form input to int; empty/None → 0, garbage → ValidationError."""
    if raw is None:
        return 0
    if isinstance(raw, str) and not raw.strip():
        return 0
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid number for '{field}'.") from None


# --- Server-side money recompute (Task 3: ERP hardening) ---
# Client-supplied line/invoice totals are advisory only. The server recomputes
# every total as quantity x rate and accepts a client value solely when it
# agrees with the recomputed figure within 0.01 (rounding tolerance).

_QTY_KEYS = ("quantity", "qty")
_RATE_KEYS = ("rate", "rate_per_unit", "unit_price")
_LINE_TOTAL_KEYS = ("total_amount", "total_price", "price")

_ADVISORY_TOLERANCE = 0.01


def _coerce_money(value, field: str) -> float:
    """Coerce a qty/rate value to float; empty/None → 0.0, garbage → ValidationError."""
    if value is None:
        return 0.0
    if isinstance(value, str) and not value.strip():
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid number for '{field}'.") from None


def _first_present(item: dict, keys: tuple) -> object:
    """Return the first present (non-None) value for keys, else None."""
    for key in keys:
        if key in item and item[key] is not None:
            val = item[key]
            if isinstance(val, str) and not val.strip():
                continue
            return val
    return None


def line_total(item: dict) -> float:
    """Recompute one line total as qty x rate, ignoring advisory client totals.

    Falls back to the client line total when no qty/rate pair is present
    (e.g. work-order parts carry ``price`` as the line total, not a unit rate).
    A client total that agrees with the recomputed figure within 0.01 is kept
    so rounding is preserved; anything further off is discarded.
    """
    qty_raw = _first_present(item, _QTY_KEYS)
    rate_raw = _first_present(item, _RATE_KEYS)
    client_raw = _first_present(item, _LINE_TOTAL_KEYS)

    if qty_raw is not None and rate_raw is not None:
        recomputed = _coerce_money(qty_raw, 'quantity') * _coerce_money(rate_raw, 'rate')
        if client_raw is not None:
            try:
                client = float(client_raw)
            except (ValueError, TypeError):
                return recomputed
            if abs(client - recomputed) <= _ADVISORY_TOLERANCE:
                return client
        return recomputed

    if client_raw is not None:
        return _coerce_money(client_raw, 'total_amount')
    return 0.0


def compute_totals(items: list[dict]) -> float:
    """Recompute an invoice total as the sum of server-side line totals."""
    return float(sum(line_total(item) for item in (items or [])))


def accept_or_recompute(recomputed: float, client_raw) -> float:
    """Keep an advisory client total iff it is within 0.01 of recomputed."""
    if client_raw is None:
        return float(recomputed)
    if isinstance(client_raw, str) and not client_raw.strip():
        return float(recomputed)
    try:
        client = float(client_raw)
    except (ValueError, TypeError):
        return float(recomputed)
    if abs(client - float(recomputed)) <= _ADVISORY_TOLERANCE:
        return client
    return float(recomputed)


def derive_pending(quoted, paid) -> float:
    """Derive ``pending = quoted - paid``; paid must satisfy ``0 <= paid <= quoted``.

    Raises:
        ValidationError: if paid is negative or exceeds quoted.
    """
    quoted_amount = _coerce_money(quoted, 'quoted_price')
    paid_amount = _coerce_money(paid, 'paid_amount')
    if quoted_amount < 0:
        raise ValidationError("Quoted price cannot be negative.")
    if paid_amount < 0:
        raise ValidationError("Paid amount cannot be negative.")
    if paid_amount > quoted_amount:
        raise ValidationError("Paid amount cannot exceed quoted price.")
    return float(quoted_amount - paid_amount)


def parse_tags(tags_string: str) -> list[dict]:
    """Parse a comma-separated tags string into a list of dicts."""
    if not tags_string:
        return []
    return [{'type': 'tag', 'value': t.strip()} for t in tags_string.split(',') if t.strip()]


def parse_contact_info(value: str) -> dict:
    """Detect if contact info is email, website, or text."""
    if not value or not str(value).strip():
        return {'type': 'text', 'value': '-'}

    val = str(value).strip()
    value_lower = val.lower()

    if '@' in value_lower and '.' in value_lower.split('@')[-1]:
        return {'type': 'email', 'value': val}

    if '.com' in value_lower or 'http' in value_lower or 'www.' in value_lower:
        return {'type': 'web', 'value': val}

    return {'type': 'text', 'value': val}


def is_truthy(value) -> bool:
    """Check if a form value represents a truthy boolean."""
    if not value:
        return False
    value_lower = str(value).lower().strip()
    return any(x in value_lower for x in ('true', '1', 'yes', 'on'))


def expand_designation(value: str) -> str:
    """Expand abbreviated designations to their full forms.

    Args:
        value: The raw designation string (e.g. 'pm', 'md', 'gm').

    Returns:
        The expanded designation, or the original value if no match found.
    """
    if not value:
        return ''

    mappings = {
        'pm': 'Production Manager',
        'p.m': 'Production Manager',
        'p.m.': 'Production Manager',

        'md': 'Managing Director',
        'm.d': 'Managing Director',
        'm.d.': 'Managing Director',

        'dgm': 'Deputy General Manager',
        'd.g.m': 'Deputy General Manager',
        'd.g.m.': 'Deputy General Manager',

        'gm': 'General Manager',
        'g.m': 'General Manager',
        'g.m.': 'General Manager',

        'ceo': 'Chief Executive Officer',
        'c.e.o': 'Chief Executive Officer',
        'c.e.o.': 'Chief Executive Officer',

        'cfo': 'Chief Financial Officer',
        'c.f.o': 'Chief Financial Officer',
        'c.f.o.': 'Chief Financial Officer',

        'coo': 'Chief Operating Officer',
        'c.o.o': 'Chief Operating Officer',
        'c.o.o.': 'Chief Operating Officer',

        'hr': 'Human Resources',
        'h.r': 'Human Resources',
        'h.r.': 'Human Resources',

        'agm': 'Assistant General Manager',
        'a.g.m': 'Assistant General Manager',
        'a.g.m.': 'Assistant General Manager',

        'mgr': 'Manager',
        'asst': 'Assistant',
        'sr': 'Senior',
        'jr': 'Junior',
        'exec': 'Executive',
        'dir': 'Director',
        'vp': 'Vice President',
        'v.p': 'Vice President',
        'v.p.': 'Vice President',
    }

    lower_val = value.lower().strip()
    if lower_val in mappings:
        return mappings[lower_val]

    return value


def paginate_list(data_list: list, page: int, per_page: int = 10) -> tuple[list, dict]:
    """Paginate a list of dictionaries/objects.
    
    Args:
        data_list: The full list of data to paginate.
        page: The current page number (1-indexed).
        per_page: Number of items per page.
        
    Returns:
        Tuple of (paginated_data_slice, pagination_metadata_dict)
    """
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
        
    total_items = len(data_list)
    total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 1
    
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
        
    start = (page - 1) * per_page
    end = start + per_page
    
    metadata = {
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'total_items': total_items,
        'has_prev': page > 1,
        'has_next': page < total_pages
    }
    
    return data_list[start:end], metadata
