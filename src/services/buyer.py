"""Buyer service — business logic for client/buyer management."""
from src.config import setup_logger, Settings
from src.db.database import db
from src.helpers.exceptions import ValidationError, NotFoundError
from src.helpers.auth import verify_delete_password

logger = setup_logger(Settings.LOG_DIR / "services.log", name="bew.services.buyer")


def list_all(query: str = '', limit: int = 1000, offset: int = 0):
    """List all buyers, optionally filtered by search query."""
    if query:
        from sqlalchemy import or_
        from src.db.database import Buyer, BuyerContact
        buyers_query = Buyer.query.filter(
            or_(
                Buyer.company_name.ilike(f'%{query}%'),
                Buyer.contacts.any(BuyerContact.name.ilike(f'%{query}%'))
            )
        ).order_by(Buyer.company_name).limit(limit).offset(offset).all()

        return [b.to_dict() for b in buyers_query]

    return db.get_all_buyers(limit=limit, offset=offset)


def get(buyer_id: int):
    """Get buyer by ID for edit form."""
    buyer = db.get_buyer_by_id(buyer_id)
    if not buyer:
        raise NotFoundError('Buyer', buyer_id)
    return buyer


def get_profile(buyer_id: int):
    """Get buyer profile with transaction history."""
    profile = db.get_buyer_profile(buyer_id)
    if not profile:
        raise NotFoundError('Buyer', buyer_id)
    return profile


def create(form_data) -> int:
    """Create a new buyer from form data.

    Args:
        form_data: Flask request.form object.

    Returns:
        The new buyer's ID.

    Raises:
        ValidationError: If company name is missing.
    """
    company_name = form_data.get('company_name', '').strip()
    if not company_name:
        raise ValidationError("Company name is required!")

    buyer_data = {
        'company_name': company_name,
        'address': form_data.get('address', '').strip(),
        'contacts': _parse_contacts(form_data),
    }

    buyer_id = db.add_buyer(buyer_data)
    logger.info(f"Created buyer #{buyer_id}: {company_name}")
    return buyer_id


def update(buyer_id: int, form_data) -> bool:
    """Update an existing buyer.

    Args:
        buyer_id: ID of buyer to update.
        form_data: Flask request.form object.

    Returns:
        True if updated successfully.

    Raises:
        ValidationError: If company name is missing.
        NotFoundError: If buyer does not exist.
    """
    company_name = form_data.get('company_name', '').strip()
    if not company_name:
        raise ValidationError("Company name is required!")

    buyer_data = {
        'company_name': company_name,
        'address': form_data.get('address', '').strip(),
        'contacts': _parse_contacts(form_data),
    }

    if db.update_buyer(buyer_id, buyer_data):
        logger.info(f"Updated buyer #{buyer_id}")
        return True
    raise NotFoundError('Buyer', buyer_id)


def delete(buyer_id: int, password: str = ''):
    """Delete a buyer after password verification.

    Returns:
        Tuple (success: bool, reason: str | None)
    """
    verify_delete_password(password)

    success, reason = db.delete_buyer(buyer_id)
    if success:
        logger.info(f"Deleted buyer #{buyer_id}")
    return success, reason


def _parse_contacts(form_data) -> list[dict]:
    """Parse dynamic contact fields from form data."""
    names = form_data.getlist('contact_name') if hasattr(form_data, 'getlist') else []
    designations = form_data.getlist('contact_designation') if hasattr(form_data, 'getlist') else []
    whatsapps = form_data.getlist('contact_whatsapp') if hasattr(form_data, 'getlist') else []
    emails = form_data.getlist('contact_email') if hasattr(form_data, 'getlist') else []
    primary_index = form_data.get('primary_contact_index')

    contacts = []
    for i in range(len(names)):
        name = names[i].strip()
        if not name:
            continue

        mobiles_key = f'contact_mobiles_{i}[]'
        mobiles = form_data.getlist(mobiles_key) if hasattr(form_data, 'getlist') else []
        mobiles = [m.strip() for m in mobiles if m.strip()]

        contacts.append({
            'name': name,
            'designation': designations[i].strip() if i < len(designations) else '',
            'mobiles': mobiles,
            'whatsapp': whatsapps[i].strip() if i < len(whatsapps) else '',
            'email': emails[i].strip() if i < len(emails) else '',
            'is_primary': str(i) == primary_index,
        })

    return contacts
