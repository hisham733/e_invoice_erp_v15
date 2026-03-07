from __future__ import unicode_literals
import pdb
import frappe
from frappe.model.document import Document
# from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import APICredentials
import requests
from frappe import _
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
    get_access_token_for_credential,
)

from frappe.utils import now_datetime, get_datetime
class CancelDocument(Document):
#     def on_update(self):
#         uuid = self.uuid
#         frappe.msgprint(f"Submission UID: {uuid}")
# cancel_document.py


    def before_save(self):
        # Ensure both fields are filled
        if not self.e_invoice_model or not self.e_invoice:
            frappe.throw("Please select both E Invoice Mode and E Invoice.")

        # Fetch the linked e-invoice document
        invoice = frappe.get_doc(self.e_invoice_model, self.e_invoice)

        # Check if it was submitted
        if invoice.docstatus != 1:
            frappe.throw("The selected invoice has not been submitted yet.")

        # Compare submission time (assumes 'modified' = submission time)
        submission_time = get_datetime(invoice.modified)
        time_diff_hours = (now_datetime() - submission_time).total_seconds() / 3600

        if time_diff_hours > 70:
            frappe.throw("The invoice was submitted more than 70 hours ago and cannot be cancelled automatically.")

    def before_submit(self):
        if not self.api_credentials:
            frappe.throw("Please select API Credentials before saving.")

        
        # Generate the API token by calling the fetch_api_token method
        token = get_access_token_for_credential(self.api_credentials)
        if token:
            # Set the fetched token in the api_access_token field
            self.api_access_token = token  # Ensure this matches the actual fieldname
            # frappe.msgprint(f"API Token fetched and saved successfully.")
        else:
            frappe.throw("Failed to fetch the API token.")


    def on_submit(self):
        try:
            response_data = self.cancel_document_in_lhdn()

            is_cancelled = (
                str(response_data.get("status", "")).lower() == "cancelled" or
                "already cancelled" in str(response_data).lower()
            )

            if is_cancelled:
                self.status = "Cancelled"
                self.save()

                if self.e_invoice_model in ["Sales E Invoice", "Consolidated E Invoice"]:
                    doc = frappe.get_doc(self.e_invoice_model, self.e_invoice)
                    doc.db_set("custom_lhdn_e_invoice_status", "Cancelled")
                    frappe.msgprint(f"LHDN cancellation successful. Status updated in {self.e_invoice_model}.")
                else:
                    frappe.throw("Invalid e-invoice type selected.")

            else:
                message = response_data.get("error", {}).get("message", "Unknown error")
                frappe.throw(f"LHDN did not cancel the document. Reason: {message}")

        except Exception as e:
            frappe.log_error(str(e), "Cancel E-Invoice Error")
            frappe.throw(f"Cancellation failed. Reason: {str(e)}")

    def cancel_document_in_lhdn(self):
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ERPNextPythonClient/1.0",
            "Authorization": f"Bearer {self.api_access_token}",
            "Accept": "application/json",
            "Accept-Language": "en",
        }

        body = {
            "status": "cancelled",
            "reason": self.reason
        }

        cred_doc = frappe.get_doc("API Credentials", self.api_credentials)
        api_base_url = "https://preprod-api.myinvois.hasil.gov.my"
        if cred_doc.environment == "PROD":
            api_base_url = "https://api.myinvois.hasil.gov.my"

        cancel_url = f"{api_base_url}/api/v1.0/documents/state/{self.uuid}/state"

        response = requests.put(cancel_url, headers=headers, json=body)
        self.response_content = response.json()

        print("Response from LHDN:", self.response_content)
        print(response.status_code)

        # ✅ Return if success
        if response.status_code == 200:
            return self.response_content

        # ✅ Gracefully handle "already cancelled"
        error_details = self.response_content.get("error", {}).get("details", [])
        for detail in error_details:
            if "already cancelled" in detail.get("message", "").lower():
                frappe.msgprint("This document was already cancelled in LHDN.")
                self.status = "Cancelled"
                return self.response_content  # treat as success

        # ❌ Otherwise handle as real error
        self.handle_validation_errors()
        raise Exception(f"Failed to cancel document. Status Code: {response.status_code}")


    def handle_validation_errors(self, *args, **kwargs):
        er = self.response_content
        error = er.get("error", {})
        details = error.get("details", [])

        messages = ""
        if details:
            for item in details:
                messages += item.get("message") + "\n"
            raise Exception(f"{messages}")
