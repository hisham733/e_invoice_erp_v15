# Copyright (c) 2025, Alharazi_hisham and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import logging
import pdb
import base64
import hashlib
import json
# from erpnext.utilities.regional import temporary_flag
from e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.on_cancel import cancel_lhdn_document
from frappe.utils import flt
import qrcode
import requests
import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
    get_access_token_for_credential,
)
from e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.build_invoice import (
    build_invoice,
)
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.serialization import pkcs12
import os

logger = logging.getLogger(__name__)
url = ""
token = ""
import base64
from io import BytesIO
# import qrcode
from PIL import Image
from frappe import _


class ConsolidatedEInvoice(Document):

    def validate(self):
        """
        Validates the document by fetching and verifying required details
        from linked Company and Customer documents.
        """
        # =========================================================================
        # 1. PRE-CHECKS & DOCUMENT FETCHING
        # =========================================================================

        if not self.company:
            frappe.throw(_("Please select a Company."), title=_("Missing Company"))

        if not self.customer:
            frappe.throw(_("Please select a Customer."), title=_("Missing Customer"))

        try:
            # Fetch all linked documents at once for efficiency.
            company_doc = frappe.get_doc("Company", self.company)
            # customer_doc = frappe.get_doc("Customer", self.customer)

            # primary_address_name = customer_doc.customer_primary_address
            # frappe.msgprint(f"primary_address_name: {primary_address_name}")

            address_name = frappe.db.get_value("Dynamic Link", {
                "link_doctype": "Company",
                "link_name": company_doc.name,
                "parenttype": "Address"
            }, "parent")

            if not address_name:
                # if primary_address_name:
                #     address_name = primary_address_name
                # else:
                frappe.throw("⚠️ Could not find the Supplier Address")

            address_doc = frappe.get_doc("Address", address_name)

        except frappe.DoesNotExistError as e:
            # This single block catches if Company, Customer, or the linked Address is missing.
            frappe.throw(
                _("Could not find a required document. Please ensure the selected Company and Customer are valid.")
                + f"<br><br><b>Error details:</b> {e}",
                title=_("Invalid Document Link")
            )

        # =========================================================================
        # 2. COMPANY DATA VALIDATION
        # =========================================================================

        required_company_fields = {
            "custom_taxpayer_name": "Taxpayer Name",
            "custom_msic_code_": "MSIC Code",
            "custom_company__registrationicpassport_number": "Company Registration/IC/Passport Number",
            "custom_company_tin_number": "Company TIN Number",
            "custom_tourism_tax_number": "Tourism Tax number",
        }

        missing_company_fields = [
            f"<li>{label}</li>"
            for fieldname, label in required_company_fields.items()
            if not getattr(company_doc, fieldname, None)
        ]

        if missing_company_fields:
            message = _(f"The selected Company <b>{self.company}</b> is missing required information:")
            message += "<ul>" + "".join(missing_company_fields) + "</ul>"
            message += _("Please update the Company record and try again.")
            frappe.throw(message, title=_("Incomplete Company Data"))

        # All company checks passed, assign values.
        self.registration_name = company_doc.custom_taxpayer_name

        msic_full_string = company_doc.custom_msic_code_
        if msic_full_string and ":" in msic_full_string:
            # Extract just the numeric part before the colon
            self.msic_codes = msic_full_string.split(':', 1)[0].strip()
        else:
            # If the format is unexpected, assign the original value as a fallback
            self.msic_codes = msic_full_string

        self.supplier_brn = company_doc.custom_company__registrationicpassport_number
        self.supplier_tin = company_doc.custom_company_tin_number
        self.tourism_tax_registration = company_doc.custom_tourism_tax_number

        # =========================================================================
        # 3. supplier ADDRESS VALIDATION & ASSIGNMENT
        # =========================================================================
        def validate_required_fields(obj, fields, label="Object"):
            """
            Checks that the given object has non-empty values for all fields.

            :param obj: The object (e.g. a Frappe Doc or dict) to validate.
            :param fields: A list of field names to check.
            :param label: Optional label to use in error messages.
            :return: List of missing field names.
            """
            missing = [field for field in fields if not getattr(obj, field, None)]
            if missing:
                frappe.throw(
                    _("{} is missing required fields: <b>{}</b>").format(
                        label, ", ".join(missing)
                    ),
                    title=_("Missing Required Fields"),
                )
        company_address_required_fields = [
            "name",
            "address_title",
            "city",
            "state",
            "custom_state_code",
            "pincode",
            "phone",
            "email_id",
        ]
        if address_doc:
            print(f"address_doc: {address_doc}")
                    # Validate address fields using the helper
            validate_required_fields(
                address_doc,
                company_address_required_fields,
                label=f"Address for Supplier {self.company}",
            )
            # The customer has a valid, linked primary address. Assign its details.
            self.supplier_address_name = address_doc.name
            self.supplier_location = address_doc.address_line1 + " " + address_doc.address_line2
            print(self.supplier_location)
            self.supplier_city = address_doc.city
            self.supplier_state = address_doc.state
            state_code = address_doc.custom_state_code
            if state_code and ":" in state_code:
                # Extract just the numeric part before the colon
                self.supplier_state_codes = state_code.split(":", 1)[0].strip()
            else:
                # If the format is unexpected, assign the original value as a fallback
                self.supplier_state_codes = state_code

            self.supplier_postal_code = address_doc.pincode
            self.suplier_mobile = address_doc.phone
            self.supplier_email_address = address_doc.email_id
            # Add any other address fields you need here, e.g.:
            # self.supplier_address_line2 = address_doc.address_line2
        else:
            # This means the customer is valid but has no primary address set.
            # This is a validation failure for this document.

            # First, clear any stale data.
            self.supplier_address_name = None
            self.supplier_city = None
            self.supplier_state = None
            self.supplier_pincode = None
            self.supplier_country = None

            # Then, throw a clear error.
            frappe.throw(
                _(f"The selected Supplier <b>{self.company}</b> does not have an Address set."),
                title=_("Missing Address")
            )

        # Finally, keep monetary totals in sync with the invoices child table.
        self.update_totals_from_invoices()
        self.check_con_in_siv()
    def check_con_in_siv(self):
            invoices = [d.original_invoice for d in self.invoices if d.original_invoice]

            if not invoices:
                return

            existing = frappe.get_all(
                "Sales Invoice",
                filters={
                    "name": ["in", invoices],
                    "custom_consolidate_invoice_number": ["is", "set"]
                },
                fields=["name", "custom_consolidate_invoice_number"]
            )

            if existing:
                inv = existing[0]
                frappe.throw(
                    f"Sales Invoice {inv.name} is already linked to Consolidated Invoice {inv.custom_consolidate_invoice_number}"
                )
    def update_totals_from_invoices(self):
        """Recalculate parent totals from the invoices child table."""
        total = 0.0
        total_taxes = 0.0
        total_charge = 0.0
        first_tax_category = None

        for row in self.invoices or []:
            total += flt(row.total or 0)
            total_taxes += flt(row.total_taxes or 0)
            total_charge += flt(getattr(row, "total_additional", 0) or 0)
            if not first_tax_category and getattr(row, "tax_catagory", None):
                first_tax_category = row.tax_catagory

        self.total = total
        self.total_taxes_and_charges = total_taxes
        self.total_charge = total_charge
        # Keep consistent with consolidation logic: total + taxes + additional charges
        self.grand_total = total + total_taxes + total_charge

        if first_tax_category:
            # `tax_category` is a Select; it must match an option exactly (e.g. "01 : Sales Tax"),
            # while child rows often store only the short code (e.g. "01").
            code = str(first_tax_category).strip().split(":", 1)[0].strip() if first_tax_category else ""
            meta = frappe.get_meta(self.doctype)
            df = meta.get_field("tax_category") if meta else None
            options = (df.options or "").splitlines() if df else []
            options = [opt.strip() for opt in options if opt and opt.strip()]
            match = next(
                (opt for opt in options if (opt.split(":", 1)[0].strip() if ":" in opt else opt) == code),
                None,
            )
            self.tax_category = match or str(first_tax_category).strip()
            
    def before_submit(self):

        try:
            # pdb.set_trace()
            build_e_invoice = build_invoice()
            utc_timestamp = build_e_invoice.get_utc_timestamp()
            sales_invoice_doc = self.fetch_sales_invoice_details()

            tax_subtotals, tax_category, item_prices = (
                build_e_invoice.get_sales_invoice_details_items_info(sales_invoice_doc)
            )

            # (
            #     X509Certificate,
            #     issuer_name,
            #     serial_number,
            #     cert_hash_base64,
            #     subject_name_string,
            self._fetch_and_store_credentials()
            X509Certificate = self.cert_base64
            issuer_name = self.cert_issuer
            serial_number = self.cert_serial
            cert_hash_base64 = self.cert_hash
            subject_name_string = self.cert_subject

            formatted_posting_date, formatted_issue_time = (
                build_e_invoice.fix_time_format(sales_invoice_doc)
            )
            invoice_data, info, base64_hash, document_info = (
                build_e_invoice.build_document_info(
                    sales_invoice_doc,
                    formatted_posting_date,
                    formatted_issue_time,
                    item_prices,
                    tax_subtotals,
                    tax_category,
                    utc_timestamp,
                    None,
                    X509Certificate,
                    issuer_name,
                    serial_number,
                    subject_name_string,
                    cert_hash_base64,
                    None,
                    None,
                )
            )

            docdigest = self.sign_document_digest(base64_hash)
            print("Invoice data built successfully in before_submit.")

            # invoice_data, info, base64_hash, document_info = (
            #     build_e_invoice.build_document_info(
            #         sales_invoice_doc,
            #         formatted_posting_date,
            #         formatted_issue_time,
            #         item_prices,
            #         tax_subtotals,
            #         tax_category,
            #         utc_timestamp,
            #         base64_hash,
            #         X509Certificate,
            #         issuer_name,
            #         serial_number,
            #         subject_name_string,
            #         cert_hash_base64,
            #         docdigest,
            #         None,
            #     )
            # )

            output_directory = "home/frappe/frappe-bench/apps/e_invoice_erp/e_invoice_erp/e_invoice_erp/doctype/consolidated_e_invoice/"
            # output_directory = os.path.join(
            # frappe.get_app_path("e_invoice_erp"),
            # "e_invoice_erp",
            # "doctype",
            # "consolidated_e_invoice"
            # )

            self.extract_target_and_signed_properties(document_info, output_directory)

            json_file_path = os.path.join(output_directory, "signed_properties.json")
            with open(json_file_path, "r", encoding="utf-8") as json_file:
                json_data = json.load(json_file)

            property_path = "SignedProperties.0.SignedSignatureProperties"
            extracted_property = self.extract_property(json_data, property_path)
            print("Extracted Property:", extracted_property)

            minified_json = self.minify_json(json_data)
            print("Minified JSON:", minified_json)

            props_digest = self.generate_sha256_base64(minified_json)
            print("Props Digest (Base64):", props_digest)

            self.invoice_data = build_e_invoice.build_document_info(
                sales_invoice_doc,
                formatted_posting_date,
                formatted_issue_time,
                item_prices,
                tax_subtotals,
                tax_category,
                utc_timestamp,
                base64_hash,
                X509Certificate,
                issuer_name,
                serial_number,
                subject_name_string,
                cert_hash_base64,
                docdigest,
                props_digest,
            )
            print(f"self.invoice_data: {self.invoice_data}")
        except Exception as e:
            frappe.throw(f"Error in before_submit: {str(e)}")

    def on_submit(self):
        """
        Handles document submission
        """
        try:
            if isinstance(self.invoice_data, tuple):
                self.invoice_data = self.invoice_data[0]

            if not isinstance(self.invoice_data, dict):
                frappe.throw(
                    f"❌ Error: invoice_data must be a dictionary but received type: {type(self.invoice_data)}"
                )

            if self.invoice_data:
                response = self.send_einvoice(self.invoice_data)
                if response:
                    self.submission_uid = response.get("submissionUid")
                    self.uuid = response.get("uuid")
                    self.invoicecodenumber = response.get("invoiceCodeNumber")

                    frappe.msgprint("✅ Invoice submitted successfully.")
                    self.save()
                else:
                    frappe.throw("No data returned from e-invoice service. Please check logs for details.")
            else:
                frappe.throw("Invoice data is missing.")
        except Exception as e:
            frappe.throw(f"Failed to send e-invoice: {str(e)}")

        # Additional post-submit actions
        self.update_sales_invoices_from_consolidated(clear=False)
        
    def on_trash(self):
        self.update_sales_invoices_from_consolidated(clear=True)


    def on_cancel(self):
        self.update_sales_invoices_from_consolidated(clear=True)
    def update_sales_invoices_from_consolidated(self, clear=False):
        """
        Updates or clears the consolidated invoice reference fields on linked Sales Invoices.
        If `clear=True`, removes the custom_consolidate_invoice_number and custom_lhdn_status.
        """
        for row in self.invoices:
            sales_invoice = row.original_invoice
            if not sales_invoice:
                continue

            if clear:
                frappe.db.set_value(
                    "Sales Invoice",
                    sales_invoice,
                    {
                        "custom_consolidate_invoice_number": "",
                        "custom_lhdn_status": ""
                    }
                )
            else:
                frappe.db.set_value(
                    "Sales Invoice",
                    sales_invoice,
                    {
                        "custom_consolidate_invoice_number": self.name,
                        "custom_lhdn_status": self.custom_lhdn_e_invoice_status or ""
                    }
                )
    def _fetch_and_store_credentials(self):
        """
        Gets API credentials, fetches a valid token and certificate info,
        and stores them on the instance (`self`) for use across methods.
        """
        if not self.api_credentials:
            frappe.throw(_("API Credentials must be selected before submitting."))

        # This single call cleanly handles token caching/renewal logic.
        self.api_access_token = get_access_token_for_credential(self.api_credentials)

        # Get the credential doc to extract certificate info.
        cred_doc = frappe.get_doc("API Credentials", self.api_credentials)
        if not cred_doc.cert or not cred_doc.get_password("cert_password"):
            frappe.throw(_("Certificate file or password is not set in API Credentials doc: {0}").format(cred_doc.name))
        
        # This assumes you have a method `get_cert_info` on your `APICredentials` doctype
        # that correctly parses the certificate and returns these values.
        (
            self.cert_base64,
            self.cert_issuer,
            self.cert_serial,
            self.cert_hash,
            self.cert_subject,
        ) = cred_doc.get_cert_info()
            # --- DEBUG PRINT ---
        print("="*60)
        print("Certificate Details from get_cert_info():")
        print(f"Base64: {self.cert_base64[:60]}...")  # Truncated for readability
        print(f"Issuer: {self.cert_issuer}")
        print(f"Serial: {self.cert_serial}")
        print(f"Hash: {self.cert_hash}")
        print(f"Subject: {self.cert_subject}")
        print("="*60)



    def sign_document_digest(self, docdigest: str) -> str:
        try:

            if not self.api_credentials:
                frappe.throw("❌ API Credentials are missing.")

            api_key_open = frappe.get_doc("API Credentials", self.api_credentials)
            if not api_key_open.cert or not api_key_open.cert_password:
                frappe.throw(
                    "❌ Certificate or password is missing in API Credentials."
                )
            # pdb.set_trace()
            cert_path = frappe.utils.get_site_path(api_key_open.cert.lstrip("/"))
            cert_password = api_key_open.get_password("cert_password").encode()
            print(f"cert_password: {cert_password}")
            if not os.path.exists(cert_path):
                frappe.throw(f"❌ Certificate file not found at: {cert_path}")

            with open(cert_path, "rb") as f:
                p12_data = f.read()

            private_key, certificate, additional_certs = (
                pkcs12.load_key_and_certificates(p12_data, cert_password)
            )

            if not private_key:
                frappe.throw("❌ Private key is missing in the certificate!")

            try:
                hash_bytes = base64.b64decode(docdigest)
            except Exception:
                frappe.throw("❌ Invalid Base64 hash format for document digest.")

            public_numbers = private_key.public_key().public_numbers()
            modulus_hex = (
                public_numbers.n.to_bytes(
                    (public_numbers.n.bit_length() + 7) // 8, byteorder="big"
                )
                .hex()
                .upper()
            )
            exponent = public_numbers.e

            signature_bytes = private_key.sign(
                hash_bytes, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256())
            )

            signature_base64 = base64.b64encode(signature_bytes).decode()
            logger.info(
                f"✅ Document successfully signed. Signature (Base64): {signature_base64}"
            )

            return signature_base64

        except FileNotFoundError as e:
            frappe.throw(f"❌ Certificate file not found: {str(e)}")
        except ValueError as e:
            frappe.throw(f"❌ Invalid certificate format: {str(e)}")
        except KeyError as e:
            frappe.throw(f"❌ Missing key in API credentials: {str(e)}")
        except Exception as e:
            frappe.throw(f"❌ Error while signing document: {str(e)}")

    # @frappe.whitelist()
    # def update_api_credentials_and_fetch_token(self):
    #     try:

    #         if not self.api_credentials:
    #             frappe.throw("⚠️ Please Select the 'API Credentials'.")
    #             # latest_record = frappe.db.get_value(
    #             #     "API Credentials", {}, "name", order_by="creation desc"
    #             # )
    #             # if not latest_record:
    #             #     frappe.throw(
    #             #         "⚠️ No records found in 'API Credentials'. Please configure API credentials."
    #             #     )

    #             # self.api_credentials = latest_record
    #             # frappe.db.commit()

    #         api_credentials_doc = frappe.get_doc(
    #             "API Credentials", self.api_credentials
    #         )

    #         if (
    #             not api_credentials_doc.client_id
    #             or not api_credentials_doc.client_secret
    #         ):
    #             frappe.throw(
    #                 "⚠️ Client ID or Client Secret is missing in API Credentials."
    #             )

    #         try:
    #             token, api_url = APICredentials.fetch_api_token(api_credentials_doc)
    #         except Exception as e:
    #             frappe.throw(f"❌ Failed to retrieve API token: {str(e)}")

    #         if not token:
    #             frappe.throw(
    #                 "⚠️ API token retrieval failed. Please check API Credentials configuration."
    #             )

    #         self.api_access_token = token
    #         logger.info(f"Successfully obtained API access token.")

    #         try:
    #             cert_info = APICredentials.get_cert_info(api_credentials_doc)
    #         except Exception as e:
    #             frappe.throw(f"❌ Failed to retrieve certificate information: {str(e)}")

    #         if not cert_info or len(cert_info) != 5:
    #             frappe.throw("⚠️ Certificate information is incomplete or missing.")

    #         return cert_info  # (X509Certificate, issuer_name, serial_number, cert_hash_base64 ,subject_name_string)

    #     except frappe.ValidationError as e:
    #         raise
    #     except Exception as e:
    #         logger.exception(
    #             "Unexpected error updating API credentials and fetching token."
    #         )
    #         frappe.throw(
    #             f"❌ Error updating API credentials and fetching token: {str(e)}"
    #         )

    @frappe.whitelist()
    def fetch_sales_invoice_details(self):
        try:
            sales_name = self.name
            sales_invoice_doc = frappe.get_doc("Consolidated E Invoice", sales_name)
            return sales_invoice_doc
        except Exception as e:
            frappe.throw(f"Error fetching Consolidated E Invoice details: {str(e)}")


    @frappe.whitelist()
    def send_einvoice(self, invoice_data):
        """
        Sends the e-invoice to LHDN MyInvois API.
        Logs all errors to Frappe Error Log automatically.
        """

        try:
            # Prepare headers & body
            api_access_token = self.api_access_token
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ERPNextPythonClient/1.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "Authorization": f"Bearer {api_access_token}",
                "Accept-Language": "en",
            }

            body = {
                "documents": [
                    {
                        "document": invoice_data["document"],
                        "codeNumber": invoice_data["invoice_id"],
                        "format": "JSON",
                        "documentHash": invoice_data["documentHash"],
                    }
                ]
            }

            # Get API base URL
            cred_doc = frappe.get_doc("API Credentials", self.api_credentials)
            api_base_url = "https://preprod-api.myinvois.hasil.gov.my"
            if cred_doc.environment == "PROD":
                api_base_url = "https://api.myinvois.hasil.gov.my"

            send_document_url = f"{api_base_url}/api/v1.0/documentsubmissions"

            # Send request
            response = requests.post(send_document_url, headers=headers, json=body)
            self.response_content = response.json()

            # Handle any validation errors and log them
            self.handle_validation_errors(
                response_json=self.response_content,
                response=response,
                request_body=body
            )

            # Process API response
            if response.status_code in [200, 202]:
                accepted_documents = self.response_content.get("acceptedDocuments", [])
                rejected_documents = self.response_content.get("rejectedDocuments", [])

                if accepted_documents:
                    doc = accepted_documents[0]
                    return {
                        "submissionUid": self.response_content.get("submissionUid"),
                        "uuid": doc.get("uuid"),
                        "invoiceCodeNumber": doc.get("invoiceCodeNumber"),
                    }

                if rejected_documents:
                    # Extract error message
                    error_msg = self.extract_einvoice_error_message(rejected_documents[0].get("error", {}))

                    # Log full response
                    frappe.log_error(
                        message=f"Invoice submission failed: {error_msg}\nRequest: {body}\nResponse: {response.text}",
                        title="E-Invoice Submission Error"
                    )

                    frappe.msgprint(f"❌ Invoice submission failed: {error_msg}")
                    return None

                # No accepted or rejected documents
                frappe.log_error(
                    message=f"No accepted or rejected documents returned.\nRequest: {body}\nResponse: {response.text}",
                    title="E-Invoice Submission Error"
                )
                frappe.throw("E-Invoice failed without a clear result. Please check the Error Log.")

            else:
                # Non-200 response
                frappe.log_error(
                    message=f"E-Invoice API request failed [{response.status_code}]: {response.text}\nRequest: {body}",
                    title="E-Invoice API Error"
                )
                frappe.throw(f"E-Invoice API request failed with status {response.status_code}")

        except Exception as e:
            frappe.log_error(message=str(e), title="Exception in send_einvoice")
            frappe.throw(f"Failed to send e-invoice: {str(e)}")


    def handle_validation_errors(self, response_json=None, response=None, request_body=None):
        """
        Parses API response for validation errors and logs them to Error Log
        """

        if response_json is None:
            response_json = self.response_content or {}

        error_messages = []

        # 1️⃣ Check rejectedDocuments
        rejected = response_json.get("rejectedDocuments")
        if rejected:
            for doc in rejected:
                error = doc.get("error", {})
                msg = self.extract_einvoice_error_message(error)
                if msg:
                    error_messages.append(f"Rejected document: {msg}")

        # 2️⃣ Top-level error.details[]
        error = response_json.get("error", {})
        details = error.get("details", [])
        if details:
            for item in details:
                msg = item.get("message")
                if msg:
                    error_messages.append(f"Error detail: {msg}")

        # 3️⃣ Top-level error.message
        if error.get("message"):
            error_messages.append(f"Error message: {error['message']}")

        # 4️⃣ Log & raise if any errors found
        if error_messages:
            full_message = "\n".join(error_messages)

            frappe.log_error(
                message=f"{full_message}\nRequest: {request_body}\nResponse: {response.text if response else response_json}",
                title="E-Invoice Validation Error"
            )

            raise Exception(full_message)


    def extract_einvoice_error_message(self, error):
        """
        Extracts the best error message from various e-invoice API formats
        """
        if not error:
            return None

        # Top-level message
        if error.get("message"):
            return error["message"]

        # Check details list
        details = error.get("details", [])
        if details and details[0].get("message"):
            return details[0]["message"]

        return "Unknown e-invoice validation error"


    # --------------------------------------------------------Validation Error-------------------------------
    # def handle_validation_errors(self, response_json, response=None, request_body=None):
    #         error = response_json.get("error", {})
    #         details = error.get("details", [])

    #         if not details:
    #             return  # ✅ no validation errors

    #         # Collect messages safely
    #         messages = []
    #         for item in details:
    #             if item.get("message"):
    #                 messages.append(item["message"])

    #         final_message = "\n".join(messages) or "Unknown validation error"

    #         # ✅ Log full response to system
    #         frappe.log_error(
    #             title="E-Invoice Validation Error",
    #             message=f"""
    #                     DocType: {self.doctype}
    #                     Document: {self.name}

    #                     HTTP Status:
    #                     {getattr(response, "status_code", "N/A")}

    #                     Validation Messages:
    #                     {final_message}

    #                     Full Response:
    #                     {frappe.as_json(response_json)}

    #                     Request Body:
    #                     {frappe.as_json(request_body) if request_body else "N/A"}
    #                     """
    #                 )

    #         # ✅ Stop execution with friendly error
    #         frappe.throw(f"E-Invoice rejected:\n{final_message}")

    # ------------------------------------------------------------------------------------

    def recursive_search(self, data, keys):
        """Recursively searches for specific keys in a nested dictionary."""
        if isinstance(data, dict):
            extracted = {key: data[key] for key in keys if key in data}
            if extracted:
                return extracted  # Stop searching once we find the keys
            for value in data.values():
                result = self.recursive_search(value, keys)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self.recursive_search(item, keys)
                if result:
                    return result
        return None

    def extract_target_and_signed_properties(self, data, output_path):
        """Extracts Target and SignedProperties from a nested dictionary and saves to a specified path."""
        try:
            if not isinstance(data, dict):
                print("❌ Error: Expected a dictionary but got something else.")
                return None

            extracted_data = self.recursive_search(data, ["Target", "SignedProperties"])

            if not extracted_data:
                print("❌ Target and SignedProperties section not found.")
                return None

            os.makedirs(output_path, exist_ok=True)

            output_file = os.path.join(output_path, "signed_properties.json")

            with open(output_file, "w", encoding="utf-8") as file:
                json.dump(extracted_data, file, indent=2)

            print(f"✅ Extracted Target & SignedProperties saved to {output_file}")

            return extracted_data

        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    def extract_property(self, json_data, property_path):
        """Extracts a nested property from JSON using dot notation and handles lists properly."""
        keys = property_path.split(".")
        value = json_data

        for key in keys:
            if isinstance(value, list):
                try:
                    key = int(key)
                    value = value[key]
                except (ValueError, IndexError):
                    raise KeyError(
                        f"Property '{property_path}' not found in JSON (Invalid list index: {key})"
                    )
            else:
                value = value.get(key, None)

            if value is None:
                raise KeyError(f"Property '{property_path}' not found in JSON")

        return value

    def minify_json(self, json_obj):
        """Convert JSON object to a minified string"""
        return json.dumps(json_obj, separators=(",", ":"))

    def generate_sha256_base64(self, input_str):
        """Generate SHA-256 hash and encode in Base64"""
        sha256_hash = hashlib.sha256(input_str.encode("utf-8")).digest()
        return base64.b64encode(sha256_hash).decode("utf-8")

    # -----------------------------------------------QR Funcion ----------------------------------------------------------
    # def qr_code_img(self, qr_link):
    #     qr = qrcode.QRCode(version=1, box_size=9, border=5)
    #     qr.add_data(qr_link)
    #     qr.make(fit=True)

    #     img = qr.make_image(fill="black", back_color="white")
    #     buffer = BytesIO()
    #     img.save(buffer, format="PNG")
    #     img_bytes = buffer.getvalue()
    #     buffer.close()

    #     return base64.b64encode(img_bytes)

    def create_get_document_details_if_not_exists(self, sales_invoice_name):
        """Check if submitted 'Get Document Details' exists. If not, create and submit it."""
        qr_doc = frappe.get_all(
            "Get Document Details",
            filters={"sales_e_invoice": sales_invoice_name, "docstatus": 1},
            fields=["name", "code"],
            limit=1,
        )

        if qr_doc:
            return frappe.get_doc("Get Document Details", qr_doc[0].name)

        # Create and submit new doc
        doc = frappe.new_doc("Get Document Details")
        doc.get_document_details_for = "Consolidated E Invoice"
        doc.sales_e_invoice = sales_invoice_name
        doc.api_credentials = self.api_credentials
        doc.uuid = self.uuid

        doc.insert(ignore_permissions=True)
        doc.save()
        doc.submit()
        frappe.msgprint("✅ Created and submitted 'Get Document Details'.")
        return doc
    # --------------------------------------------------------------------------
    # QR CODE GENERATION
    # --------------------------------------------------------------------------
    # In sales_e_invoice.py, inside the SalesEInvoice class

    def _fetch_lhdn_document_details(self):
        """
        Calls the LHDN API to get the full details of a submission,
        including the 'longId' and 'status'.
        Returns the first document summary object if successful.
        """
        if not self.api_credentials or not self.submission_uid:
            frappe.throw(_("Missing API Credentials or Submission UID to fetch details."))

        # This reuses the existing logic for getting credentials and tokens
        # pdb.set_trace()
        api_access_token = get_access_token_for_credential(self.api_credentials)
        print(f"api_access_token : {api_access_token}")
        cred_doc = frappe.get_doc("API Credentials", self.api_credentials)

        api_base_url = "https://preprod-api.myinvois.hasil.gov.my"
        if cred_doc.environment == "PROD":
            api_base_url = "https://api.myinvois.hasil.gov.my"

        api_url = f"{api_base_url}/api/v1.0/documentsubmissions/{self.submission_uid}"
        headers = {"Authorization": f"Bearer {api_access_token}"}
        
        try:
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status() # Throws HTTPError for bad responses (4xx or 5xx)
            
            response_data = response.json()
            document_summary_list = response_data.get("documentSummary", [])

            if document_summary_list:
                # Return the details of the first (and likely only) document
                return document_summary_list[0]
            else:
                frappe.throw(_("API response did not contain document summary details."))

        except requests.exceptions.HTTPError as e:
            frappe.throw(
                _("Failed to fetch document details from LHDN. API Error: {0}").format(e.response.text),
                title=_("API Error")
            )
        except Exception as e:
            logger.error(f"Failed to fetch LHDN details: {frappe.get_traceback()}")
            frappe.throw(_("An unexpected error occurred while fetching details: {0}").format(e))
    # In sales_e_invoice.py, inside the SalesEInvoice class

    @frappe.whitelist()
    def generate_qr_code(self):
        """
        Generates and attaches the QR code after validating status and fetching Long ID.
        """

        if self.docstatus != 1:
            frappe.throw(_("QR Code can only be generated for submitted documents."))

        if not self.uuid:
            frappe.throw(_("Document is missing a UUID."))

        try:
            # --- STEP 1: Fetch document details from LHDN ---
            doc_details = self._fetch_lhdn_document_details()

            # --- STEP 2: Validate response and extract data ---
            status = doc_details.get("status")
            long_id = doc_details.get("longId")

            self.db_set("custom_lhdn_e_invoice_status", status)

            if status != "Valid":
                frappe.throw(
                    _("Cannot generate QR code. The document status is '<span style=\"color:red;font-weight:bold\">{0}</span>', not '<span style=\"color:green;font-weight:bold\">Valid</span>'. Please check the validation results.").format(status),
                    title=_("Invalid Status"),
                    is_minimizable=True
                )

            if not long_id:
                frappe.throw(
                    _("LHDN has not assigned a Long ID yet. It may still be processing. Try again later."),
                    title=_("Missing Long ID")
                )

            # --- STEP 3: Construct QR code link ---
            cred_doc = frappe.get_doc("API Credentials", self.api_credentials)
            qr_base_url = "https://preprod.myinvois.hasil.gov.my"
            if cred_doc.environment == "PROD":
                qr_base_url = "https://myinvois.hasil.gov.my"

            qr_link = f"{qr_base_url}/{self.uuid}/share/{long_id}"

            # --- STEP 4: Generate and attach QR image ---
            img_b64 = self._create_qr_image_base64(qr_link)
            filename = f"QR_{self.name}.png"

            file_doc = frappe.new_doc("File")
            file_doc.file_name = filename
            file_doc.is_private = 0
            file_doc.content = base64.b64decode(img_b64)
            file_doc.attached_to_doctype = self.doctype
            file_doc.attached_to_name = self.name
            file_doc.save(ignore_permissions=True)

            self.db_set("validation_url", file_doc.file_url)

            frappe.msgprint(
                _("✅ QR code generated and attached successfully."),
                title=_("Success"),
                indicator="green"
            )

            return file_doc.file_url

        # except Exception as e:
        except frappe.ValidationError:
            raise  # Let Frappe handle this without logging again
        except Exception:
            frappe.throw(_("An unexpected error occurred while generating QR code. Please contact your administrator."))


    def _create_qr_image_base64(self, qr_link):
        """Generates a QR code and returns it as a base64 encoded string."""
        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(qr_link)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    # @frappe.whitelist()
    # def gr_link(self):
    #     # Step 1: Ensure 'Get Document Details' exists and is submitted
    #     qr_doc = self.create_get_document_details_if_not_exists(self.name)

    #     # Step 2: Validate 'code' field
    #     if not qr_doc.code:
    #         frappe.throw("❌ 'Get Document Details' is missing the 'code' field.")

    #     try:
    #         code_data = json.loads(qr_doc.code)
    #     except json.JSONDecodeError as err:
    #         frappe.throw(f"❌ Invalid JSON in 'code': {err}")

    #     # Step 3: Validate JSON content
    #     consolidated_e_invoice_status = code_data.get("status")
    #     self.submission_status = consolidated_e_invoice_status

    #     if consolidated_e_invoice_status != "Valid":
    #         frappe.msgprint(
    #             f"⚠️ {self.name} is not valid for QR generation. Please check."
    #         )
    #         return

    #     uuid = code_data.get("uuid")
    #     long_id = code_data.get("longId")
    #     if not uuid or not long_id:
    #         frappe.throw("❌ UUID or Long ID missing in QR code data.")

    #     qr_link = f"https://myinvois.hasil.gov.my/{uuid}/share/{long_id}"

    #     # Step 4: Generate QR image and attach it
    #     try:
    #         img_str = self.qr_code_img(qr_link)
    #         filename = f"QR_{uuid}.png"

    #         file_doc = frappe.get_doc(
    #             {
    #                 "doctype": "File",
    #                 "file_name": filename,
    #                 "is_private": 0,
    #                 "content": base64.b64decode(img_str),
    #                 "attached_to_doctype": "Consolidated E Invoice",
    #                 "attached_to_name": self.name,
    #             }
    #         )
    #         file_doc.save(ignore_permissions=True)

    #         # Step 5: Update document with QR file URL
    #         self.validation_url = file_doc.file_url
    #         self.save(ignore_permissions=True)

    #         return {
    #             "qr_link": qr_link,
    #             "file_url": file_doc.file_url,
    #             "message": "✅ QR code generated and saved.",
    #         }

    #     except Exception as e:
    #         frappe.throw(f"❌ Failed to generate or save QR code: {e}")

    # ---------------------------------------------------------------------------------------------------------------
#     def set_item_wise_tax_breakup(self):
#         self.other_charges_calculation = get_itemised_tax_breakup_html(self)

# def get_itemised_tax_breakup_html(doc):
#     if not doc.taxes:
#         return

#     # get headers
#     tax_accounts = []
#     for tax in doc.taxes:
#         if getattr(tax, "category", None) and tax.category == "Valuation":
#             continue
#         if tax.description not in tax_accounts:
#             tax_accounts.append(tax.description)

#     with temporary_flag("company", doc.company):
#         headers = get_itemised_tax_breakup_header(doc.doctype + " Item", tax_accounts)
#         itemised_tax_data = get_itemised_tax_breakup_data(doc)
#         get_rounded_tax_amount(itemised_tax_data, doc.precision("tax_amount", "taxes"))
#         update_itemised_tax_data(doc)

#     return frappe.render_template(
#         "templates/includes/itemised_tax_breakup.html",
#         dict(
#             headers=headers,
#             itemised_tax_data=itemised_tax_data,
#             tax_accounts=tax_accounts,
#             doc=doc,
#         ),
#     )


def update_itemised_tax_data(doc):
    # Don't delete this method, used for localization
    pass


def get_rounded_tax_amount(itemised_tax, precision):
    # Rounding based on tax_amount precision
    for taxes in itemised_tax:
        for row in taxes.values():
            if isinstance(row, dict) and isinstance(row["tax_amount"], float):
                row["tax_amount"] = flt(row["tax_amount"], precision)


def get_itemised_tax_breakup_header(item_doctype, tax_accounts):
    return [("Item"), ("Taxable Amount"), *tax_accounts]


def get_itemised_tax(taxes, with_tax_account=False):
    itemised_tax = {}
    for tax in taxes:
        if getattr(tax, "category", None) and tax.category == "Valuation":
            continue

        item_tax_map = (
            json.loads(tax.item_wise_tax_detail) if tax.item_wise_tax_detail else {}
        )
        if item_tax_map:
            for item_code, tax_data in item_tax_map.items():
                itemised_tax.setdefault(item_code, frappe._dict())

                tax_rate = 0.0
                tax_amount = 0.0

                if isinstance(tax_data, list):
                    tax_rate = flt(tax_data[0])
                    tax_amount = flt(tax_data[1])
                else:
                    tax_rate = flt(tax_data)

                itemised_tax[item_code][tax.description] = frappe._dict(
                    dict(tax_rate=tax_rate, tax_amount=tax_amount)
                )

                if with_tax_account:
                    itemised_tax[item_code][
                        tax.description
                    ].tax_account = tax.account_head

    return itemised_tax


def get_itemised_taxable_amount(items):
    itemised_taxable_amount = frappe._dict()
    for item in items:
        item_code = item.item_code or item.item_name
        itemised_taxable_amount.setdefault(item_code, 0)
        itemised_taxable_amount[item_code] += item.net_amount

    return itemised_taxable_amount


def get_itemised_tax_breakup_data(doc):
    itemised_tax = get_itemised_tax(doc.taxes)

    itemised_taxable_amount = get_itemised_taxable_amount(doc.items)

    itemised_tax_data = []
    for item_code, taxes in itemised_tax.items():
        itemised_tax_data.append(
            frappe._dict(
                {
                    "item": item_code,
                    "taxable_amount": itemised_taxable_amount.get(item_code, 0),
                    **taxes,
                }
            )
        )

    return itemised_tax_data




import traceback

@frappe.whitelist()
def cancel_from_button(docname, reason):
    try:
        doc = frappe.get_doc("Consolidated E Invoice", docname)

        if doc.custom_lhdn_e_invoice_status == "Cancelled":
            frappe.throw(_("This document is already marked as Cancelled."))

        if not doc.api_credentials:
            frappe.throw(_("Missing API credentials. Please set the API credentials on the document."))

        if not doc.uuid:
            frappe.throw(_("Missing UUID. Cannot proceed with cancellation without a valid UUID."))

        if not reason or not reason.strip():
            frappe.throw(_("Cancellation reason is required."))

        # Call the cancellation logic
        response = cancel_lhdn_document(
            api_credentials=doc.api_credentials,
            uuid=doc.uuid,
            reason=reason
        )

        # Update document status
        # doc.custom_lhdn_e_invoice_status = "Cancelled"
        doc.response_content = response
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.msgprint(_("LHDN cancellation successful. Status updated to 'Cancelled'."), alert=True)

        return response

    except frappe.ValidationError as ve:
        frappe.log_error(title="Validation Error - Cancel E-Invoice", message=traceback.format_exc())
        frappe.throw(_("Validation Error: {0}").format(str(ve)))

    except frappe.DoesNotExistError:
        frappe.throw(_("Consolidated E Invoice {0} does not exist.".format(docname)))

    except Exception as e:
        frappe.log_error(title="Error Cancelling LHDN E-Invoice", message=traceback.format_exc())
        frappe.throw(_("Failed to cancel document in LHDN. Error: {0}").format(str(e)))




@frappe.whitelist()
def make_sales_e_invoice(source_name, target_doc=None, ignore_permissions=False):

    def set_missing_values(source, target):
        target.flags.ignore_permissions = ignore_permissions
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        # target.other_charges_calculation = source.other_charges_calculation

        # Get target as a dictionary
        data = target.as_dict()
        non_empty_data = {k: v for k, v in data.items() if v not in [None, "", 0, []]}

    try:
        doclist = get_mapped_doc(
            "Sales Invoice",
            source_name,
            {
                "Sales Invoice": {
                    "doctype": "Consolidated E Invoice",
                    "validation": {"docstatus": ["=", 1]},
                },
                "Sales Invoice Item": {
                    "doctype": "Sales Invoice Item",
                    "field_map": {
                        "name": "si_detail",
                        "parent": "sales_invoice",
                    },
                    "condition": lambda doc: doc.qty > 0,
                },
                "Sales Taxes and Charges": {
                    "doctype": "Sales Taxes and Charges",
                    "reset_value": True,
                },
                "Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
            },
            target_doc,
            set_missing_values,
            ignore_permissions=ignore_permissions,
        )
        print(
            "Mapping successful. New Consolidated E Invoice created with name (ID):",
            doclist.name,
        )
        return doclist
    except Exception as e:
        print("Error in make_sales_e_invoice:", e)
        frappe.throw(
            "An error occurred while creating Consolidated E Invoice: {}".format(e)
        )


# ------------------------------------------------------------------------------
@frappe.whitelist()
def get_sales_invoice_items(sales_invoices, consolidated_invoice_name=None):
    import json
    from frappe.utils import flt

    if isinstance(sales_invoices, str):
        sales_invoices = json.loads(sales_invoices)

    items = []
    taxes = []
    sales_team = []

    for si_name in sales_invoices:
        si = frappe.get_doc("Sales Invoice", si_name)

        if si.docstatus != 1:
            frappe.throw(f"{si.name} is not submitted.")

        # Collect Items
        for item in si.items:
            if item.qty <= 0:
                continue
            items.append(
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "description": item.description,
                    "qty": flt(item.qty),
                    "rate": flt(item.rate),
                    "amount": flt(item.amount),
                    "uom": item.uom,
                    "conversion_factor": item.conversion_factor,
                    "base_rate": flt(item.base_rate),
                    "base_amount": flt(item.base_amount),
                    "net_amount":flt(item.net_amount),
                    "si_detail": item.name,
                    "income_account": item.income_account,
                    "sales_invoice": si.name,
                }
            )

        # Collect Taxes
        for tax in si.get("taxes", []):
            taxes.append(
                {
                    "charge_type": tax.charge_type,
                    "account_head": tax.account_head,
                    "rate": flt(tax.rate),
                    "tax_amount": flt(tax.tax_amount),
                    "description": tax.description,
                }
            )

        # Collect Sales Team
        for member in si.get("sales_team", []):
            sales_team.append(
                {
                    "sales_person": member.sales_person,
                    "allocated_percentage": flt(member.allocated_percentage),
                }
            )

    return {"items": items, "taxes": taxes, "sales_team": sales_team}


def before_cancel_consolidated_e_invoice_hook(doc, method):

    sales_invoice_name = doc.name

    try:
        child_entries = frappe.get_all(
            "Consolidated Invoice Entry",
            filters={"original_invoice": sales_invoice_name},
            fields=["parent", "name"]  # Get the parent (Consolidated E-Invoice) and the child row name
        )

        if not child_entries:
            return # This Sales Invoice is not in any Consolidated E-Invoice, so do nothing.

        for entry in child_entries:
            parent_consolidated_doc_name = entry.parent
            child_row_name = entry.name

            parent_doc = frappe.get_doc("Consolidated E-Invoice", parent_consolidated_doc_name)
            
            row_to_remove = None
            for row in parent_doc.invoices:
                if row.name == child_row_name:
                    row_to_remove = row
                    break
            
            if row_to_remove:
                parent_doc.remove(row_to_remove)
                
                parent_doc.save(ignore_permissions=True)


        doc.custom_consolidate_invoice_number = None
        doc.custom_lhdn_status = None

    except Exception:
        frappe.throw("Could not unlink from the Consolidated E-Invoice. Cancellation aborted.")


def validate_tax_type(doc, method=None):
    TaxCategory = doc.tax_category
    if TaxCategory and ":" in TaxCategory:
                # Extract just the numeric part before the colon
        TaxCategory = TaxCategory.split(":", 1)[0].strip()
    else:
        # If the format is unexpected, assign the original value as a fallback
        TaxCategory = doc.tax_category
    if doc.total_taxes_and_charges == 0 and TaxCategory != "06":
        
        frappe.throw(_("Tax Category must be '06 : Not Applicable' when there are no taxes applied."))
