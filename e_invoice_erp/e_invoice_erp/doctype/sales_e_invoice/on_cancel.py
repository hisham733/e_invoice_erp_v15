import requests
import frappe
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
    get_access_token_for_credential,
)
def cancel_lhdn_document(api_credentials, uuid, reason, status="cancelled"):
    """
    Cancel a document in LHDN using MyInvois API.

    Args:
        api_credentials (str): The name of the API Credentials doctype.
        uuid (str): The UUID of the document to be cancelled.
        reason (str): Reason for cancellation.
        status (str): Desired document state, default is "cancelled".

    Returns:
        dict: LHDN response JSON.
    Raises:
        Exception: If the cancellation fails and is not already cancelled.
    """

    # Get credentials
    access_token = get_access_token_for_credential(api_credentials)

    # Headers
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ERPNextPythonClient/1.0",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Accept-Language": "en",
    }

    # Request body
    body = {
        "status": status,
        "reason": reason
    }

    # Base URL selection
    cred_doc = frappe.get_doc("API Credentials", api_credentials)
    api_base_url = "https://preprod-api.myinvois.hasil.gov.my"
    if cred_doc.environment == "PROD":
      api_base_url = "https://api.myinvois.hasil.gov.my"

    # Build URL
    cancel_url = f"{api_base_url}/api/v1.0/documents/state/{uuid}/state"

    # Send request
    response = requests.put(cancel_url, headers=headers, json=body)
    response_json = response.json()

    # ✅ Return if successful
    if response.status_code == 200:
        return response_json

    # ✅ Handle already cancelled
    error_details = response_json.get("error", {}).get("details", [])
    for detail in error_details:
        if "already cancelled" in detail.get("message", "").lower():
            frappe.msgprint("This document was already cancelled in LHDN.")
            return response_json

    # ❌ Raise other validation errors
    messages = "\n".join([d.get("message", "") for d in error_details])
    raise Exception(f"LHDN Cancellation Error:\n{messages or response_json.get('message', 'Unknown Error')}")
