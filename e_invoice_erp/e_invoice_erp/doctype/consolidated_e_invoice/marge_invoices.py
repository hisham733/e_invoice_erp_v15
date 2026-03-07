import pdb
import frappe
from frappe import _
import datetime


def _tax_category_code(raw_value):
    """Return just the tax category code (e.g. '01') from '01 : Sales Tax'."""
    if raw_value is None:
        return ""
    value = str(raw_value).strip()
    if not value:
        return ""
    return value.split(":", 1)[0].strip() if ":" in value else value


def _tax_category_select_value(raw_value):
    """
    Convert a tax category code like '01' to the exact Select option string
    defined on Consolidated E Invoice.tax_category (e.g. '01 : Sales Tax').
    """
    value = str(raw_value).strip() if raw_value is not None else ""
    if not value:
        return ""

    code = _tax_category_code(value)

    meta = frappe.get_meta("Consolidated E Invoice")
    df = meta.get_field("tax_category") if meta else None
    options = (df.options or "").splitlines() if df else []
    options = [opt.strip() for opt in options if opt and opt.strip()]

    for opt in options:
        if _tax_category_code(opt) == code:
            return opt

    # Fall back to original value. If it's only a code, Frappe may still reject it,
    # but this makes failures obvious instead of silently changing meaning.
    return value


def _ensure_general_public_customer():
    """
    Checks if the 'General Public' customer exists. If not, it creates one.
    Returns the name of the customer.
    This is a private helper function.
    """
    customer_name = "General Publics"

    if not frappe.db.exists("Customer", customer_name):
        # The customer does not exist, so we create it.
        # We must provide the mandatory fields for a Customer DocType.
        customer = frappe.new_doc("Customer")
        customer.customer_name = customer_name
        customer.customer_group = "All Customer Groups"  # A safe default group
        customer.customer_type = "Company"  # A sensible default type
        customer.custom_tourism_tax_number = "NA"
        customer.custom_sst_number = "NA"
        customer.custom_customer__registrationicpassport_type = "BRN"
        customer.Custom_registrationicpassport_number = "NA"
        customer.custom_customer_tin_number = "EI00000000010"
        customer.custom_customer_taxpayer_name = "General Public"
        customer.insert(ignore_permissions=True)  # Save the new customer

        if not customer.customer_primary_address:
            primary_address = create_customer_address(customer_name)
            print(f"primary_address: {primary_address}")
        customer.customer_primary_address = primary_address

        customer.save(ignore_permissions=True)  # Save the new customer
        # customer.save()

        frappe.msgprint(_("Created default customer: {0}").format(customer_name))

    return customer_name
def create_customer_address(customer_name):
    address = frappe.new_doc("Address")
    address.address_title = customer_name
    address.address_line1 = "NA"
    address.city = "NA"
    address.insert(ignore_permissions=True)
    address.save()
    return address.name


import datetime
import frappe
from frappe import _
# from e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.marge_invoices import validate_invoice_statuses


@frappe.whitelist()
def create_consolidated_invoice(invoice_numbers, force=False):
    """
    Creates a new "Consolidated E-Invoice" document, summarizing selected Sales Invoices.
    Will perform validations unless `force=True` is passed (e.g. user confirmed override).
    """
    if isinstance(invoice_numbers, str):
        invoice_numbers = frappe.parse_json(invoice_numbers)

    force = frappe.parse_json(force)

    if not invoice_numbers or len(invoice_numbers) < 1:
        frappe.throw(_("Please select at least one Sales Invoice."))

    # --- Validation Phase (if not force) ---
    if not force:
        validation = validate_invoice_statuses(invoice_numbers)
        if validation["blocks"]:
            frappe.throw(_("One or more invoices are blocked from consolidation."))
        if validation["warnings"]:
            frappe.throw(_("Warning invoices detected. Please confirm to proceed."))

    # --- Fetch invoice data ---
    source_invoices = frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", invoice_numbers]},
        fields=[
            "name", "customer", "company", "net_total",
            "total_taxes_and_charges", "custom_tax_category", "taxes_and_charges"
        ],
    )

    for inv in source_invoices:
        inv["taxes"] = frappe.get_all(
            "Sales Taxes and Charges",
            filters={"parent": inv.name},
            fields=["rate", "tax_amount_after_discount_amount","custom_is_tax"]
        )

    source_invoices = sorted(source_invoices, key=lambda x: x.name)
    if not source_invoices:
        frappe.throw(_("No valid Sales Invoices found."))

    # --- Create new Consolidated E-Invoice ---
    consolidated_doc = frappe.new_doc("Consolidated E Invoice")
    consolidated_doc.company = source_invoices[0].company
    consolidated_doc.posting_date = datetime.date.today()

    # -- Ensure "General Public" customer exists --
    consolidated_doc.customer = _ensure_general_public_customer()

    total_grand_amount = 0.0
    total_tax_amount = 0.0
    total_charges = 0.0
    validate_uniform_tax_category(source_invoices)

    # validate_uniform_tax_category(source_invoices)
    first_tax_category = source_invoices[0].get("custom_tax_category")

    # new tax logic 
    for inv in source_invoices:
        total_tax = 0.0
        total_add = 0.0
        tax_rate = 0.0
        print(f"inv: {inv}")
        if inv.taxes:
            print("inv.taxes")
            counter = 0 
            for tax in inv.taxes:
                print(f"tax.tax_amount_after_discount_amount : {tax.tax_amount_after_discount_amount}")
                if tax.custom_is_tax:
                    print("yes")
                    counter +=1
                    total_tax = tax.tax_amount_after_discount_amount or 0
                    tax_rate = tax.rate or 0
            if counter > 1:
                frappe.throw(f"Invoice {inv.name} has multiple tax rows marked as 'Tax'. Consolidation requires uniform tax.")
            if inv.net_total:
                tax_rate = round((total_tax / inv.net_total) * 100, 2)
            else:
                tax_rate = 0
        
            
            total_add = sum(t.tax_amount_after_discount_amount or 0 for t in inv.taxes if not t.custom_is_tax)

        print(total_add)
        category = inv.custom_tax_category
        if category and ":" in category:
            category_num = category.split(":", 1)[0].strip()
        else:
            category_num = category

        consolidated_doc.append("invoices", {
            "original_invoice": inv.name,
            "total": inv.net_total,
            "total_taxes": total_tax,
            "tax_catagory": category_num,
            "tax_rate": tax_rate,
            "total_additional": total_add
        })

        total_grand_amount += inv.net_total
        total_tax_amount += total_tax
        total_charges += total_add

    consolidated_doc.total = total_grand_amount
    consolidated_doc.total_taxes_and_charges = total_tax_amount
    consolidated_doc.total_charge = total_charges
    # Grand total should include *all* additional charges (not only the last invoice's total_add).
    consolidated_doc.grand_total = total_grand_amount + total_tax_amount + total_charges
    consolidated_doc.tax_category = _tax_category_select_value(first_tax_category)

    consolidated_doc.insert(ignore_permissions=True)
    # consolidated_doc.submit()  # Optional: enable if required

    # --- Link original Sales Invoices back to the new Consolidated one ---
    # for inv in source_invoices:
    #     frappe.db.set_value(
    #         "Sales Invoice",
    #         inv.name,
    #         "custom_consolidate_invoice_number",
    #         consolidated_doc.name,
    #     )

    frappe.msgprint(
        msg=_('Successfully created <a href="/desk#Form/Consolidated E Invoice/{0}" style="font-weight:bold;">Consolidated E Invoice: {0}</a>').format(consolidated_doc.name),
        indicator="green",
        title=_("Success")
    )

    return consolidated_doc.name

def validate_uniform_tax_category(source_invoices):
    if not source_invoices:
        return
    unique_tax_category = set()
    for inv in source_invoices:
        raw = inv.get("custom_tax_category")
        if raw:
            unique_tax_category.add(_tax_category_code(raw))
    if len(unique_tax_category) > 1:
        
        frappe.throw(f"Invoice have different tax categories please consolidate invoices with the same tax category")
@frappe.whitelist()
def validate_invoice_statuses(invoice_numbers):
    warning_invoices = []
    blocking_invoices = []

    for invoice_name in frappe.parse_json(invoice_numbers):
        # ----- Check Consolidated E-Invoice Link -----
        consolidated_entry = frappe.get_value(
            "Consolidated Invoice Entry",
            {"original_invoice": invoice_name},
            ["parent"]
        )

        if consolidated_entry:
            parent_doc = frappe.get_doc("Consolidated E Invoice", consolidated_entry)
            status = parent_doc.get("custom_lhdn_e_invoice_status") or "Unknown"

            if parent_doc.docstatus == 1:
                if status not in ["Valid", "Submitted", "InProgress"]:
                    warning_invoices.append({
                        "name": invoice_name,
                        "error": f"Invoice <b>{invoice_name}</b> is in submitted Consolidated E Invoice <b>{parent_doc.name}</b> with status <b>{status}</b>. Please delete or revise that document manually.",
                        "type": "warning"
                    })
                else:
                    blocking_invoices.append({
                        "name": invoice_name,
                        "error": f"Invoice <b>{invoice_name}</b> is already in submitted Consolidated E Invoice <b>{parent_doc.name}</b> with status <b>{status}</b>. Cannot create again.",
                        "type": "block"
                    })
            else:
                blocking_invoices.append({
                    "name": invoice_name,
                    "error": f"Invoice <b>{invoice_name}</b> is linked to draft Consolidated E Invoice <b>{parent_doc.name}</b>. Please submit or delete it.",
                    "type": "block"
                })

        # ----- Check Sales E-Invoice Link -----
        sei = frappe.get_all(
            "Sales E Invoice",
            filters={"sales_invoice": invoice_name},
            fields=["name", "custom_lhdn_e_invoice_status", "docstatus"],
            limit=1
        )

        if sei:
            sei_doc = sei[0]
            sei_status = sei_doc.custom_lhdn_e_invoice_status or "Unknown"
            sei_docstatus = sei_doc.docstatus

            if sei_docstatus == 1:
                if sei_status not in ["Valid", "Submitted", "InProgress"]:
                    warning_invoices.append({
                        "name": invoice_name,
                        "error": f"Invoice <b>{invoice_name}</b> is linked to submitted Sales E Invoice <b>{sei_doc.name}</b> with status <b>{sei_status}</b>. Please delete or revise that document manually.",
                        "type": "warning"
                    })
                else:
                    blocking_invoices.append({
                        "name": invoice_name,
                        "error": f"Invoice <b>{invoice_name}</b> is already linked to submitted Sales E Invoice <b>{sei_doc.name}</b> with status <b>{sei_status}</b>. Cannot create again.",
                        "type": "block"
                    })
            else:
                blocking_invoices.append({
                    "name": invoice_name,
                    "error": f"Invoice <b>{invoice_name}</b> is linked to draft Sales E Invoice <b>{sei_doc.name}</b>. Please submit or delete it.",
                    "type": "block"
                })

    return {
        "warnings": warning_invoices,
        "blocks": blocking_invoices
    }
