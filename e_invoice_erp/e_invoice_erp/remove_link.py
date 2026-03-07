import frappe
import traceback

from e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.sales_e_invoice import before_cancel_sales_e_invoice_hook
from e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.consolidated_e_invoice import before_cancel_consolidated_e_invoice_hook

def unlink_all_from_sales_invoice(doc, method):
    """
    This is the main orchestrator function called by hooks.py.
    It calls all the necessary unlinking functions in order.
    """
    before_cancel_sales_e_invoice_hook(doc, method)
    before_cancel_consolidated_e_invoice_hook(doc, method)


def clear_sales_invoice_fields(doc, method=None):
    # Check if the insert is a result of duplication
    doc.sales_e_invoice_number = None
    doc.custom_lhdn_status = None
    doc.custom_consolidate_invoice_number = None
    doc.save(ignore_permissions=True)