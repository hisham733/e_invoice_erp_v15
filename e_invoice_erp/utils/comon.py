# yourapp/utils/common.py

import frappe
from frappe import _


def validate_required_fields(obj, fields, label="Object"):
    missing = [field for field in fields if not getattr(obj, field, None)]
    if missing:
        frappe.throw(
            _("{} is missing required fields: <b>{}</b>").format(
                label, ", ".join(missing)
            ),
            title=_("Missing Required Fields"),
        )


def extract_code_before_colon(value):
    return value.split(":", 1)[0].strip() if value and ":" in value else value


def assign_address_fields(doc, prefix, address):
    setattr(doc, f"{prefix}_address", address.name)
    setattr(doc, f"{prefix}_location", address.address_title)
    setattr(doc, f"{prefix}_city", address.city)
    setattr(doc, f"{prefix}_state", address.state)
    setattr(
        doc,
        f"{prefix}_state_code",
        extract_code_before_colon(address.custom_state_code),
    )
    setattr(doc, f"{prefix}_postal_code", address.pincode)
    setattr(doc, f"{prefix}_phone", address.phone)
    setattr(doc, f"{prefix}_email_address", address.email_id)
