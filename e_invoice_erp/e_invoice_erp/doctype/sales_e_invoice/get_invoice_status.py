# In e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/sales_e_invoice.py

import json
import frappe
import requests
from frappe import _
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
    get_access_token_for_credential,
)

# In e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/sales_e_invoice.py

@frappe.whitelist()
def get_lhdn_submission_status(doc):
    """
    Fetches the submission status of a Sales E-Invoice from the LHDN API
    and updates the document with the status and any validation errors.
    """
    try:
        if isinstance(doc, str):
            doc = json.loads(doc)

        api_credentials = doc.get("api_credentials")
        if not api_credentials:
            frappe.throw(_("API Credentials not found in the document."))

        submission_uid = doc.get("submission_uid")
        if not submission_uid:
            frappe.throw(_("Submission UID is missing. Cannot check status."))
        
        api_access_token = get_access_token_for_credential(api_credentials)

        cred_doc = frappe.get_doc("API Credentials", api_credentials)
        api_base_url = "https://preprod-api.myinvois.hasil.gov.my"
        if cred_doc.environment == "PROD":
            api_base_url = "https://api.myinvois.hasil.gov.my"

        api_url = f"{api_base_url}/api/v1.0/documentsubmissions/{submission_uid}"
        headers = {"Authorization": f"Bearer {api_access_token}"}

        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()

        response_data = response.json()
        
        # --- START OF CORRECTED LOGIC ---

        status = "Unknown"
        validation_result_text = ""

        # Get the document summary list, defaulting to an empty list
        document_summary_list = response_data.get("documentSummary", [])

        if document_summary_list:
            # Get the first document's summary (there's usually only one)
            first_doc_summary = document_summary_list[0]
            status = first_doc_summary.get("status", "Unknown")
            
            # If the status is Invalid, extract the reason
            if status == "Invalid":
                validation_results = first_doc_summary.get("validationResult", {})
                errors = validation_results.get("errors", [])
                
                if errors:
                    # Format the errors into a readable HTML list
                    error_messages = [f"<li><b>Code:</b> {e.get('code')} - <b>Message:</b> {e.get('message')}</li>" for e in errors]
                    validation_result_text = f"<b>Validation Errors:</b><ul>{''.join(error_messages)}</ul>"
                else:
                    validation_result_text = "Status is 'Invalid', but no specific error details were provided by the API."
        else:
            # Fallback to overall status if documentSummary is missing
            status = response_data.get("overallStatus", "Unknown")

        # Fetch the actual document from the database to update it
        sales_e_invoice_doc = frappe.get_doc("Sales E Invoice", doc.get("name"))
        sales_e_invoice_doc.custom_lhdn_e_invoice_status = status
        invoice_name = sales_e_invoice_doc.sales_invoice
        custom_lhdn_status = status

        frappe.set_value("Sales Invoice", invoice_name, {
            "sales_e_invoice_number": sales_e_invoice_doc.name,
            "custom_lhdn_status": custom_lhdn_status})


      #   sales_e_invoice_doc.lhdn_validation_result = validation_result_text
        sales_e_invoice_doc.save(ignore_permissions=True)

        # Provide a more helpful message to the user
        if status :
            frappe.msgprint(
                _("LHDN Status:LHDN submission status updated successfully: <b>{0}</b>").format(status),
                title=_("Status Update"), 
                indicator="green" # Use orange for warnings
            )

            
        # --- END OF CORRECTED LOGIC ---

        return response_data

    except requests.exceptions.HTTPError as e:
        error_message = f"API Error: {e.response.status_code} - {e.response.text}"
        frappe.log_error(title="LHDN Status Check Failed", message=error_message)
        frappe.throw(_("Failed to retrieve status from LHDN. {0}").format(error_message))
    except Exception as e:
        frappe.log_error(title="LHDN Status Check Failed", message=frappe.get_traceback())
        frappe.throw(_("An unexpected error occurred: {0}").format(str(e)))