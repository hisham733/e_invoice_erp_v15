from __future__ import unicode_literals
import logging
import pdb
import base64
import hashlib
import json
from e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.on_cancel import cancel_lhdn_document
from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import get_party_tax_withholding_details
# from frappe.api import utils
import pytz
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import APICredentials  
from e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.run_invoice import remove_signature_and_ublextensions
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
    get_access_token_for_credential,
)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.serialization import pkcs12
import os
logger = logging.getLogger(__name__)
url =""
token = ""
import re
from io import BytesIO
import qrcode
from frappe import _

from PIL import Image
class SalesEInvoice(Document):
    def validate(self):
        # Validate Customer Phone
        if self.customer_phone:
            self.customer_phone = validate_phone(self.customer_phone, "Customer Phone")

        # Validate Supplier Mobile
        if self.suplier_mobile:
            self.suplier_mobile = validate_phone(self.suplier_mobile, "Supplier Mobile")

        # Validate Supplier Postal Code
        if self.supplier_postal_code:
            self.supplier_postal_code = validate_postal(self.supplier_postal_code, "Supplier Postal Code")

        # Validate Customer Postal Code
        if self.customer_postal_code:
            self.customer_postal_code = validate_postal(self.customer_postal_code, "Customer Postal Code")
    



    def before_submit(self):
        try:
            utc_timestamp = self.get_utc_timestamp()
            sales_invoice_doc = self.fetch_sales_invoice_details()
            
            (formatted_posting_date,
            formatted_issue_time,
            item_prices,
            tax_subtotals,
            tax_category) = self.get_sales_invoice_details(sales_invoice_doc)
            
            # X509Certificate, issuer_name, serial_number, cert_hash_base64 = self.update_api_credentials_and_fetch_token()
            self._fetch_and_store_credentials()
            X509Certificate = self.cert_base64
            issuer_name = self.cert_issuer
            serial_number = self.cert_serial
            cert_hash_base64 = self.cert_hash
            cert_subject = self.cert_subject

            # print()


            invoice_data, info, base64_hash, document_info = self.build_document_info(
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
                cert_hash_base64,
                None,
                None,
                cert_subject
            )
            
            docdigest = self.sign_document_digest(base64_hash)
            print("Invoice data built successfully in before_submit.")

            # invoice_data, info, base64_hash, document_info = self.build_document_info(
            #     sales_invoice_doc,
            #     formatted_posting_date,
            #     formatted_issue_time,
            #     item_prices,
            #     tax_subtotals,
            #     tax_category,
            #     utc_timestamp,
            #     base64_hash,
            #     X509Certificate,
            #     issuer_name,
            #     serial_number,
            #     cert_hash_base64,
            #     docdigest,
            #     None,
            #     cert_subject
            # )

            output_directory = "home/frappe/frappe-bench/apps/e_invoice_erp/e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/"

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

            self.invoice_data = self.build_document_info(
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
                cert_hash_base64,
                docdigest,
                props_digest,
                cert_subject
            )

        except Exception as e:
            frappe.throw(f"Error in before_submit: {str(e)}")

    def on_submit(self):
        try:

            if isinstance(self.invoice_data, tuple):
                self.invoice_data = self.invoice_data[0]  

            if not isinstance(self.invoice_data, dict):
                frappe.throw(f"❌ Error: invoice_data must be a dictionary but received type: {type(self.invoice_data)}")

            print("self.invoice_data",self.invoice_data)
            if self.invoice_data:
                response = self.send_einvoice(self.invoice_data,)
                if response:
                    print("response:", frappe.as_json(response, indent=2))
                    self.submission_uid = response.get("submissionUid")
                    self.uuid = response.get("uuid")
                    self.invoicecodenumber = response.get("invoiceCodeNumber")
                    logger.info(f"Invoice submission successful: UID: {self.submission_uid}, UUID: {self.uuid}")
                    frappe.msgprint("✅ Invoice submitted successfully.")
                    self.save()
                else:
                    frappe.throw("No data returned from e-invoice service. Please check logs for details.")
            else:
                print("cannot print")
        except Exception as e:
            frappe.throw(f"Failed to send e-invoice: {str(e)}")


        self.update_sales_invoice()

    def update_sales_invoice(self):
        if self.docstatus == 1:
            sales_name = self.sales_invoice
            if sales_name:
                frappe.db.set_value(
                    "Sales Invoice",
                    sales_name,
                    {
                        "sales_e_invoice_number": self.name,
                        "custom_lhdn_status" : self.custom_lhdn_e_invoice_status
                    },
                )

    def before_cancel(self):
        print("on cancel")
        self.update_sales_invoice(clear=True)

    def update_sales_invoice(self, clear=False):
        sales_name = self.sales_invoice
        if sales_name and frappe.db.exists("Sales Invoice", sales_name):
            frappe.db.set_value(
                "Sales Invoice",
                sales_name,
                {
                    "sales_e_invoice_number": "" if clear else self.name,
                    "custom_lhdn_status": ""
                },
            )
        else:
            frappe.logger().warning(
                f"Sales Invoice '{sales_name}' not found — nothing updated."
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


    def sign_document_digest(self, docdigest: str) -> str:
        try:
            # pdb.set_trace()
            logger.info("Starting document signature process.")

            if not self.api_credentials:
                frappe.throw("❌ API Credentials are missing.")

            api_key_open = frappe.get_doc("API Credentials", self.api_credentials)
            if not api_key_open.cert or not api_key_open.cert_password:
                frappe.throw("❌ Certificate or password is missing in API Credentials.")

            cert_path = frappe.utils.get_site_path(api_key_open.cert.lstrip('/'))
            cert_password = api_key_open.get_password("cert_password").encode()  
            if not os.path.exists(cert_path):
                frappe.throw(f"❌ Certificate file not found at: {cert_path}")

            with open(cert_path, "rb") as f:
                p12_data = f.read()

            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                p12_data, cert_password
            )

            if not private_key:
                frappe.throw("❌ Private key is missing in the certificate!")

            try:
                hash_bytes = base64.b64decode(docdigest)
            except Exception:
                frappe.throw("❌ Invalid Base64 hash format for document digest.")

            logger.info(f"🔹 Decoded Hash Bytes (Hex): {hash_bytes.hex().upper()}")

            public_numbers = private_key.public_key().public_numbers()
            modulus_hex = public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, byteorder="big").hex().upper()
            exponent = public_numbers.e

            logger.info(f"🔹 RSA Key Modulus (Hex): {modulus_hex}")
            logger.info(f"🔹 RSA Public Exponent: {exponent}")

            signature_bytes = private_key.sign(
                hash_bytes,
                padding.PKCS1v15(),
                utils.Prehashed(hashes.SHA256())  
            )

            signature_base64 = base64.b64encode(signature_bytes).decode()
            logger.info(f"✅ Document successfully signed. Signature (Base64): {signature_base64}")

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
    #         logger.info("Starting API credentials update process.")

    #         if not self.api_credentials:
    #             latest_record = frappe.db.get_value("API Credentials", {}, "name", order_by="creation desc")
    #             if not latest_record:
    #                 frappe.throw("⚠️ No records found in 'API Credentials'. Please configure API credentials.")

    #             self.api_credentials = latest_record
    #             logger.info(f"Using latest API Credentials: {latest_record}")
    #             frappe.db.commit()  

            
    #         api_credentials_doc = frappe.get_doc("API Credentials", self.api_credentials)
    #         logger.info(f"Fetched API Credentials: {api_credentials_doc.name}")

    #         if not api_credentials_doc.client_id or not api_credentials_doc.client_secret:
    #             frappe.throw("⚠️ Client ID or Client Secret is missing in API Credentials.")

    #         try:
    #             token, api_url = APICredentials.fetch_api_token(api_credentials_doc)
    #         except Exception as e:
    #             frappe.throw(f"❌ Failed to retrieve API token: {str(e)}")

    #         if not token:
    #             frappe.throw("⚠️ API token retrieval failed. Please check API Credentials configuration.")

    #         self.api_access_token = token
    #         logger.info(f"Successfully obtained API access token.")

    #         try:
    #             cert_info = APICredentials.get_cert_info(api_credentials_doc)
    #         except Exception as e:
    #             frappe.throw(f"❌ Failed to retrieve certificate information: {str(e)}")

    #         if not cert_info or len(cert_info) != 4:
    #             frappe.throw("⚠️ Certificate information is incomplete or missing.")

    #         logger.info("Successfully fetched certificate information.")

    #         return cert_info  # (X509Certificate, issuer_name, serial_number, cert_hash_base64)

    #     except frappe.ValidationError as e:
    #         logger.exception("Validation error in API credentials update.")
    #         frappe.throw(f"Validation Error: {str(e)}")
    #     except Exception as e:
    #         logger.exception("Unexpected error updating API credentials and fetching token.")
    #         frappe.throw(f"❌ Error updating API credentials and fetching token: {str(e)}")


    @frappe.whitelist()
    def fetch_sales_invoice_details(self):
        try:
            sales_name = self.name
            sales_invoice_doc = frappe.get_doc("Sales E Invoice", sales_name)
            return sales_invoice_doc
        except Exception as e:
            frappe.throw(f"Error fetching Sales E Invoice details: {str(e)}")

    @frappe.whitelist()
    def get_sales_invoice_details(self, sales_invoice_doc):
        try:
            TaxCategory = sales_invoice_doc.custom_tax_category
            if TaxCategory and ":" in TaxCategory:
                # Extract just the numeric part before the colon
                TaxCategory = TaxCategory.split(":", 1)[0].strip()
            else:
                # If the format is unexpected, assign the original value as a fallback
                TaxCategory = sales_invoice_doc.custom_tax_category

            tax_category = str(TaxCategory).strip()
            other_charges_html = sales_invoice_doc.other_charges_calculation or ""
            soup = BeautifulSoup(other_charges_html, 'html.parser')
            tax_table = soup.find('table', {'class': 'table table-bordered table-hover'})
            if not tax_table:
                frappe.throw(f"No tax table found for Sales Invoice {sales_invoice_doc.name}")
            tax_rates = []
            for row in tax_table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) > 2:
                    tax_rate_text = cells[2].text.strip().split()[-1]
                    tax_rates.append(tax_rate_text)
                else:
                    tax_rates.append('0.00')
            tax_subtotals = []
            for tax_rate in tax_rates:

                print(f"before tax_rate: {tax_rate}")
                if tax_category == "06":
                    tax_rate = '0'
                print(f"after tax_rate: {tax_rate}")
                tax_rate_float = float(tax_rate.replace('RM', '').replace(',', ''))
                tax_amount_dict = {"_": tax_rate_float, "currencyID": "MYR"}
                tax_subtotal_dict = {
                    "TaxableAmount": [{"_": sales_invoice_doc.net_total, "currencyID": "MYR"}],
                    "TaxAmount": [tax_amount_dict],
                    "TaxCategory": [{
                        "ID": [{"_": tax_category}],
                        "TaxScheme": [{
                            "ID": [{
                                "_": "OTH",
                                "schemeID": "UN/ECE 5153",
                                "schemeAgencyID": "6",
                            }]
                        }],
                    }],
                }
                tax_subtotals.append(tax_subtotal_dict)

            item_prices = []
            for index, item in enumerate(sales_invoice_doc.items):
                item_tax_subtotal = tax_subtotals[index] if index < len(tax_subtotals) else {}
                tax_and_charge = 0
                tax_total_amount = 0
                print(f"tax_and_charge: {tax_and_charge}")
                for row in sales_invoice_doc.taxes:
                # Example Logic: If description contains "Delivery" or "Service", treat as Fee
                # Or check if row.charge_type == "Actual" and not SST
                    custom_is_tax = False
                    if row.custom_is_tax:
                        custom_is_tax = True
                    
                    if custom_is_tax:
                        tax_val = row.tax_amount
                        tax_total_amount += tax_val

                if not tax_category == "06":
                    tax_and_charge = tax_total_amount


                invoice_item = {
                    "ID": [{"_": str(index + 1)}],
                    "Item": [{
                        "CommodityClassification": [{
                            "ItemClassificationCode": [{
                                "_": extract_code(item.custom_item_classification_codes),
                                "listID": "CLASS"
                            }]
                        }] if hasattr(item, 'custom_item_classification_codes') and isinstance(item.custom_item_classification_codes, str) else [],
                        "Description": [{"_": item.description}] if hasattr(item, 'description') and isinstance(item.description, str) else []
                    }],
                    "LineExtensionAmount": [{"_": item.net_amount, "currencyID": "MYR"}] if hasattr(item, 'net_amount') and isinstance(item.net_amount, (int, float)) else [],
                    "TaxTotal": [{
                        "TaxAmount": [{"_": tax_and_charge, "currencyID": "MYR"}],
                        "TaxSubtotal": [{
                            "TaxAmount": [{"_": item_tax_subtotal.get("TaxAmount", [{}])[0].get("_", 0), "currencyID": "MYR"}],
                            "TaxCategory": [{
                                "ID": [{"_": tax_category}],
                                "Percent": [{"_": (item_tax_subtotal.get("TaxAmount", [{}])[0].get("_", 0) / item.amount * 100)}] if hasattr(item, 'amount') and isinstance(item.amount, (int, float)) else [],
                                "TaxScheme": [{
                                    "ID": [{
                                        "_": "OTH",
                                        "schemeID": "UN/ECE 5153",
                                        "schemeAgencyID": "6",
                                    }]
                                }],
                            }],
                        }],
                    }],
                    "Price": [{"PriceAmount": [{"_": item.price_list_rate, "currencyID": "MYR"}]}] if hasattr(item, 'price_list_rate') and isinstance(item.price_list_rate, (int, float)) else [],
                    "ItemPriceExtension": [{"Amount": [{"_": item.custom_total_amount_before_discount, "currencyID": "MYR"}]}] if hasattr(item, 'custom_total_amount_before_discount') and isinstance(item.custom_total_amount_before_discount, (int, float)) else [],
                }
                item_prices.append(invoice_item)

            # Process posting date and time
            posting_date = sales_invoice_doc.posting_date
            posting_time = sales_invoice_doc.posting_time
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")
            if isinstance(posting_time, str):
                hours, minutes, seconds = map(int, posting_time.split(':'))
                posting_time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            posting_time_str = (datetime.min + posting_time).time().strftime("%H:%M:%S") if isinstance(posting_time, timedelta) else posting_time.strftime("%H:%M:%S")
            combined_datetime = datetime.combine(posting_date, datetime.strptime(posting_time_str, "%H:%M:%S").time())
            local_timezone = pytz.timezone("Asia/Kuala_Lumpur")
            local_datetime = local_timezone.localize(combined_datetime, is_dst=None)
            utc_datetime = local_datetime.astimezone(pytz.utc)
            formatted_posting_date = utc_datetime.strftime("%Y-%m-%d")
            formatted_issue_time = utc_datetime.strftime("%H:%M:%SZ")
            logger.info(f"Formatted Posting Date in UTC: {formatted_posting_date}")
            logger.info(f"Formatted Issue Time in UTC: {formatted_issue_time}")
            return formatted_posting_date, formatted_issue_time, item_prices, tax_subtotals, tax_category
        except Exception as e:
            frappe.throw(f"Error in get_sales_invoice_details: {str(e)}")

    def get_utc_timestamp(self):
        utc_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return utc_timestamp
    

    def build_document_info(self, sales_invoice_doc, formatted_posting_date, formatted_issue_time, item_prices, tax_subtotals, tax_category,utc_timestamp,base64_hash,X509Certificate,
            issuer_name,serial_number,cert_hash_base64,docdigest,props_digest,cert_subject):
        try:
            total_tax = sales_invoice_doc.total_taxes_and_charges
            additional_amount = 0
            if tax_category == "06":
                total_tax  = 0
                additional_amount = sales_invoice_doc.total_taxes_and_charges

            allowance_charges_list = []
            charge_total_amount = 0.0
            
            # Loop through ERPNext Taxes table to find Fees (not standard taxes)
            # You might need to adjust the 'if' condition based on your Tax Account names
            for row in sales_invoice_doc.taxes:
                # Example Logic: If description contains "Delivery" or "Service", treat as Fee
                # Or check if row.charge_type == "Actual" and not SST
                is_fee = False
                if not row.custom_is_tax:
                    is_fee = True
                
                if is_fee:
                    charge_val = row.tax_amount
                    charge_total_amount += charge_val
                    
                    allowance_charges_list.append({
                        "ChargeIndicator": [{"_": True}], # MUST BE AN ARRAY
                        "AllowanceChargeReason": [{"_": row.description}], # MUST BE AN ARRAY
                        "Amount": [{
                            "_": charge_val,
                            "currencyID": "MYR"
                        }], # MUST BE AN ARRAY

                    })

            # Recalculate Tax Exclusive Amount (Items + Fees)
            # Ensure net_total is float
            net_items_total = float(sales_invoice_doc.net_total)
            tax_exclusive_amount = net_items_total + charge_total_amount

            document_info = {
                    "_D": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
                    "_A": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
                    "_B": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
                    "_E": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
                    "Invoice": [
                        {
                            "ID": [{"_": sales_invoice_doc.name}],
                            "IssueDate": [{"_": formatted_posting_date}],
                            "IssueTime": [{"_": formatted_issue_time}],
                            "InvoiceTypeCode": [{"_": "01", "listVersionID": "1.1"}],
                            "DocumentCurrencyCode": [{"_": "MYR"}],
                            "BillingReference": [
                                {
                                    "AdditionalDocumentReference": [
                                        {"ID": [{"_": sales_invoice_doc.additional_document_reference}]}
                                    ]
                                }
                            ],
                            "AccountingSupplierParty": [
                                {
                                    "Party": [
                                        {
                                            "IndustryClassificationCode": [
                                                {"_": sales_invoice_doc.msic_codes, "name": sales_invoice_doc.company}
                                            ],
                                            "PartyIdentification": [
                                                {"ID": [{"_": sales_invoice_doc.supplier_tin, "schemeID": "TIN"}]},
                                                {"ID": [{"_": sales_invoice_doc.supplier_brn, "schemeID": "BRN"}]},
                                                {
                                                    "ID": [
                                                        {
                                                            "_": sales_invoice_doc.tourism_tax_registration,
                                                            "schemeID": "SST",
                                                        }
                                                    ]
                                                },
                                            ],
                                            "PostalAddress": [
                                                {
                                                    "CityName": [{"_": sales_invoice_doc.supplier_city}],
                                                    "PostalZone": [{"_": sales_invoice_doc.supplier_postal_code}],
                                                    "CountrySubentityCode": [{"_": sales_invoice_doc.supplier_state_codes}],
                                                    "AddressLine": [{"Line": [{"_": sales_invoice_doc.supplier_location}]}],
                                                    "Country": [
                                                        {
                                                            "IdentificationCode": [
                                                                {"_": "MYS", "listID": "ISO3166-1", "listAgencyID": "6"}
                                                            ]
                                                        }
                                                    ],
                                                }
                                            ],
                                            "PartyLegalEntity": [
                                                {"RegistrationName": [{"_": sales_invoice_doc.registration_name}]}
                                            ],
                                            "Contact": [
                                                {"Telephone": [{"_": sales_invoice_doc.suplier_mobile}], "ElectronicMail": [{"_": sales_invoice_doc.supplier_email_address}]}
                                            ],
                                        }
                                    ]
                                }
                            ],
                            "AccountingCustomerParty": [
                                {
                                    "Party": [
                                        {
                                            "PostalAddress": [
                                                {
                                                    "CityName": [{"_": sales_invoice_doc.city_customer}],
                                                    "PostalZone": [{"_": sales_invoice_doc.customer_postal_code}],
                                                    "CountrySubentityCode": [{"_": sales_invoice_doc.customer_state_code}],
                                                    "AddressLine": [{"Line": [{"_": sales_invoice_doc.address_line1}]}],
                                                    "Country": [
                                                        {
                                                            "IdentificationCode": [
                                                                {"_": "MYS", "listID": "ISO3166-1", "listAgencyID": "6"}
                                                            ]
                                                        }
                                                    ],
                                                }
                                            ],
                                            "PartyLegalEntity": [{"RegistrationName": [{"_": sales_invoice_doc.customer_name}]}],
                                            "PartyIdentification": [
                                                {"ID": [{"_": sales_invoice_doc.customer_tin, "schemeID": "TIN"}]},
                                                {"ID": [{"_": sales_invoice_doc.customer_brn, "schemeID": "BRN"}]},
                                            ],
                                            "Contact": [
                                                {"Telephone": [{"_": sales_invoice_doc.customer_phone}], "ElectronicMail": [{"_": sales_invoice_doc.customer_email_address}]}
                                            ],
                                        }
                                    ]
                                }
                            ],
                            "TaxTotal": [
                                {
                                    "TaxAmount": [{"_": total_tax, "currencyID": "MYR"}],
                                    "TaxSubtotal": tax_subtotals,
                                }
                            ],
                            "AllowanceCharge": allowance_charges_list if allowance_charges_list else None,
                            "LegalMonetaryTotal": [
                                {
                                    "TaxExclusiveAmount": [{"_": sales_invoice_doc.net_total, "currencyID": "MYR"}],
                                    "TaxInclusiveAmount": [{"_": sales_invoice_doc.grand_total, "currencyID": "MYR"}],
                                    "ChargeTotalAmount": [{"_": charge_total_amount,"currencyID": "MYR" }],
                                    "PayableAmount": [{"_": sales_invoice_doc.rounded_total, "currencyID": "MYR"}],
                                }
                            ],
                            "InvoiceLine": item_prices,
                                "UBLExtensions": [
                                {
                                    "UBLExtension": [
                                        {
                                        "ExtensionURI": [
                                            {
                                            "_": "urn:oasis:names:specification:ubl:dsig:enveloped:xades"
                                            }
                                        ],
                                        "ExtensionContent": [
                                            {
                                            "UBLDocumentSignatures": [
                                                {
                                                "SignatureInformation": [
                                                    {
                                                    "ID": [
                                                        {
                                                        "_": "urn:oasis:names:specification:ubl:signature:1"
                                                        }
                                                    ],
                                                    "ReferencedSignatureID": [
                                                        {
                                                        "_": "urn:oasis:names:specification:ubl:signature:Invoice"
                                                        }
                                                    ],
                                                    "Signature": [
                                                        {
                                                        "Id": "signature",
                                                        "Object": [
                                                            {
                                                            "QualifyingProperties": [
                                                                {
                                                                "Target": "signature",
                                                                "SignedProperties": [
                                                                    {
                                                                    "Id": "id-xades-signed-props",
                                                                    "SignedSignatureProperties": [
                                                                        {
                                                                        "SigningTime": [
                                                                            {
                                                                            "_": utc_timestamp
                                                                            }
                                                                        ],
                                                                        "SigningCertificate": [
                                                                            {
                                                                            "Cert": [
                                                                                {
                                                                                "CertDigest": [
                                                                                    {
                                                                                    "DigestMethod": [
                                                                                        {
                                                                                        "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256"
                                                                                        }
                                                                                    ],
                                                                                    "DigestValue": [
                                                                                        {
                                                                                        "_": cert_hash_base64
                                                                                        }
                                                                                    ]
                                                                                    }
                                                                                ],
                                                                                "IssuerSerial": [
                                                                                    {
                                                                                    "X509IssuerName": [
                                                                                        {
                                                                                        "_": f"CN={issuer_name}, OU=Terms of use at http://www.posdigicert.com.my, O=LHDNM, C=MY"
                                                                                        }
                                                                                    ],
                                                                                    "X509SerialNumber": [
                                                                                        {
                                                                                        "_": serial_number
                                                                                        }
                                                                                    ]
                                                                                    }
                                                                                ]
                                                                                }
                                                                            ]
                                                                            }
                                                                        ]
                                                                        }
                                                                    ]
                                                                    }
                                                                ]
                                                                }
                                                            ]
                                                            }
                                                        ],
                                                        "KeyInfo": [
                                                            {
                                                            "X509Data": [
                                                                {
                                                                "X509Certificate": [
                                                                    {
                                                                    "_": X509Certificate
                                                                    }
                                                                ],
                                                                "X509SubjectName": [
                                                                    {
                                                                    "_": cert_subject
                                                                    }
                                                                ],
                                                                "X509IssuerSerial": [
                                                                    {
                                                                    "X509IssuerName": [
                                                                        {
                                                                        "_": f"CN={issuer_name}, OU=Terms of use at http://www.posdigicert.com.my, O=LHDNM, C=MY"
                                                                        }
                                                                    ],
                                                                    "X509SerialNumber": [
                                                                        {
                                                                        "_": serial_number
                                                                        }
                                                                    ]
                                                                    }
                                                                ]
                                                                }
                                                            ]
                                                            }
                                                        ],
                                                        "SignatureValue": [
                                                            {
                                                            "_": docdigest
                                                            }
                                                        ],
                                                        "SignedInfo": [
                                                            {
                                                            "SignatureMethod": [
                                                                {
                                                                "_": "",
                                                                "Algorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
                                                                }
                                                            ],
                                                            "Reference": [
                                                                {
                                                                "Type": "http://uri.etsi.org/01903/v1.3.2#SignedProperties",
                                                                "URI": "#id-xades-signed-props",
                                                                "DigestMethod": [
                                                                    {
                                                                    "_": "",
                                                                    "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256"
                                                                    }
                                                                ],
                                                                "DigestValue": [
                                                                    {
                                                                    "_": props_digest
                                                                    }
                                                                ]
                                                                },
                                                                {
                                                                "Type": "",
                                                                "URI": "",
                                                                "DigestMethod": [
                                                                    {
                                                                    "_": "",
                                                                    "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256"
                                                                    }
                                                                ],
                                                                "DigestValue": [
                                                                    {
                                                                    "_": base64_hash
                                                                    }
                                                                ]
                                                                }
                                                            ]
                                                            }
                                                        ]
                                                        }
                                                    ]
                                                    }
                                                ]
                                                }
                                            ]
                                            }
                                        ]
                                        }
                                    ]
                                    }
                                ],
                                "Signature": [
                                    {
                                    "ID": [
                                        {
                                        "_": "urn:oasis:names:specification:ubl:signature:Invoice"
                                        }
                                    ],
                                    "SignatureMethod": [
                                        {
                                        "_": "urn:oasis:names:specification:ubl:dsig:enveloped:xades"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            if not allowance_charges_list:
                del document_info["Invoice"][0]["AllowanceCharge"]
            run_test =document_info
            info=document_info
            json_content = json.dumps(document_info, indent=2).encode()
            base64_document = base64.b64encode(json_content).decode("utf-8")
            document_hash = hashlib.sha256(json_content).hexdigest()
            invoice_data = {
                "format": "JSON",
                "document": base64_document,
                "documentHash": document_hash,
                "invoice_id": sales_invoice_doc.name
            }
            print(f"json_content {json_content}")
            run=remove_signature_and_ublextensions(run_test)
            base64_hash = run
 
            return invoice_data,info,base64_hash,document_info
        except Exception as e:
            logger.exception("Error in build_document_info")
            frappe.throw(f"Error in build_document_info: {str(e)}")
            
    @frappe.whitelist()
    def send_einvoice(self, invoice_data):
        import re

        def json_path_to_readable(path):
            """
            Converts a JSON path like #/Invoice[0].InvoiceLine[0].Item[0].CommodityClassification
            to readable: Invoice Line 1 → Item 1 → CommodityClassification
            """
            if not path:
                return "Unknown Path"
            parts = re.findall(r'([A-Za-z_]+)\[(\d+)\]|([A-Za-z_]+)', path)
            readable_parts = []
            for part in parts:
                if part[0]:  # matched something like Invoice[0]
                    name = part[0].replace('_', ' ')
                    index = int(part[1]) + 1
                    readable_parts.append(f"{name} {index}")
                else:
                    readable_parts.append(part[2].replace('_', ' '))
            return " → ".join(readable_parts)

        def parse_nested_errors(details_list, parent_path="Invoice"):
            """
            Recursively parse nested e-invoice validation errors into user-friendly messages.
            """
            messages = []
            for item in details_list or []:
                msg = item.get("message")
                nested = item.get("details")
                prop_path = item.get("propertyPath") or parent_path

                # Extract missing fields from TooFewItems errors
                missing_fields = []
                if msg:
                    for line in msg.splitlines():
                        if "TooFewItems" in line:
                            field_name = line.split(".")[-1].strip()
                            missing_fields.append(field_name)

                if missing_fields:
                    readable_path = json_path_to_readable(prop_path)
                    messages.append(f"{readable_path}: Missing {', '.join(missing_fields)}")
                elif msg:
                    messages.append(f"{prop_path}: {msg}")

                if nested:
                    messages.extend(parse_nested_errors(nested, parent_path=prop_path))

            return messages

        try:
            api_access_token = self.api_access_token
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ERPNextPythonClient/1.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "Authorization": f"Bearer {api_access_token}",
                "Accept-Language": "en"
            }

            body = {
                "documents": [{
                    "document": invoice_data["document"],
                    "codeNumber": invoice_data["invoice_id"],
                    "format": "JSON",
                    "documentHash": invoice_data["documentHash"]
                }]
            }

            cred_doc = frappe.get_doc("API Credentials", self.api_credentials)
            api_base_url = "https://preprod-api.myinvois.hasil.gov.my" if cred_doc.environment != "PROD" else "https://api.myinvois.hasil.gov.my"
            send_document_url = f"{api_base_url}/api/v1.0/documentsubmissions"

            response = requests.post(send_document_url, headers=headers, json=body)

            # Parse JSON safely
            try:
                self.response_content = response.json()
            except ValueError:
                self.response_content = {}
                logger.error(f"Empty or invalid JSON response: {get_response_text(response)}")
                frappe.throw("No valid JSON returned from e-invoice service. Please check logs.")

            logger.info(f"E-Invoice API response status: {response.status_code}")

            accepted_documents = self.response_content.get("acceptedDocuments") or []
            rejected_documents = self.response_content.get("rejectedDocuments") or []

            if accepted_documents:
                doc_info = accepted_documents[0]
                return {
                    "submissionUid": self.response_content.get("submissionUid"),
                    "uuid": doc_info.get("uuid"),
                    "invoiceCodeNumber": doc_info.get("invoiceCodeNumber"),
                }

            elif rejected_documents:
                doc_info = rejected_documents[0]
                error_details = doc_info.get("error", {})
                details = error_details.get("details") or []

                if details:
                    readable_messages = parse_nested_errors(details)
                    final_message = "\n".join(readable_messages)
                else:
                    final_message = error_details.get("message", "Unknown validation error")

                frappe.msgprint(f"Invoice submission failed:\n{final_message}")
                logger.error(f"E-Invoice validation errors:\n{final_message}")
                return None

            else:
                logger.error(f"No accepted or rejected documents: {self.response_content}")
                frappe.throw("No document summary returned from e-invoice service. Please check logs for details.")

        except requests.RequestException as e:
            logger.error(f"E-Invoice API request failed: {str(e)}")
            frappe.throw(f"E-Invoice API request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in send_einvoice: {str(e)}")
            raise

    # --------------------------------------------------------Validation Error-------------------------------
    def handle_validation_errors(self, *args, **kwargs):
        """
        Parses response_content and raises a readable exception
        for all validation errors, including deeply nested ones.
        """
        er = getattr(self, "response_content", {}) or {}
        error = er.get("error", {})
        details = error.get("details", [])

        def parse_details(details_list, prefix=""):
            messages = ""
            for item in details_list or []:
                # Extract possible info
                code = item.get("code")
                msg = item.get("message")
                target = item.get("target") or item.get("propertyPath")
                nested = item.get("details")  # can be another list

                # Format each message line
                line = ""
                if code:
                    line += f"[Code {code}] "
                if target:
                    line += f"Target: {target} - "
                if msg:
                    line += msg

                if line:
                    messages += f"{prefix}{line}\n"

                # Recursively handle nested errors
                if isinstance(nested, list) and nested:
                    messages += parse_details(nested, prefix=prefix + "  ")

            return messages

        all_messages = parse_details(details)

        # Fallback if top-level message exists
        if not all_messages and error.get("message"):
            all_messages = error["message"]

        if all_messages:
            raise Exception(f"Validation Errors:\n{all_messages}")


    # ------------------------------------------------------------------------------------
    def recursive_search(self,data, keys):
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

    def extract_target_and_signed_properties(self,data, output_path):
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

    def extract_property(self,json_data, property_path):
        """Extracts a nested property from JSON using dot notation and handles lists properly."""
        keys = property_path.split(".")
        value = json_data

        for key in keys:
            if isinstance(value, list):
                try:
                    key = int(key)  
                    value = value[key]
                except (ValueError, IndexError):
                    raise KeyError(f"Property '{property_path}' not found in JSON (Invalid list index: {key})")
            else:
                value = value.get(key, None)

            if value is None:
                raise KeyError(f"Property '{property_path}' not found in JSON")

        return value

    def minify_json(self,json_obj):
        """Convert JSON object to a minified string"""
        return json.dumps(json_obj, separators=(',', ':'))

    def generate_sha256_base64(self,input_str):
        """Generate SHA-256 hash and encode in Base64"""
        sha256_hash = hashlib.sha256(input_str.encode('utf-8')).digest()
        return base64.b64encode(sha256_hash).decode('utf-8')

# # -----------------------------------------------QR Funcion ----------------------------------------------------------
#     def qr_code_img(self, qr_link):
#         qr = qrcode.QRCode(version=1, box_size=9, border=5)
#         qr.add_data(qr_link)
#         qr.make(fit=True)

#         img = qr.make_image(fill='black', back_color='white')
#         buffer = BytesIO()
#         img.save(buffer, format="PNG")
#         img_bytes = buffer.getvalue()
#         buffer.close()

#         return base64.b64encode(img_bytes)

#     def create_get_document_details_if_not_exists(self,sales_invoice_name):
#         """Check if submitted 'Get Document Details' exists. If not, create and submit it."""
#         qr_doc = frappe.get_all(
#             'Get Document Details',
#             filters={'sales_e_invoice': sales_invoice_name, 'docstatus': 1},
#             fields=['name', 'code'],
#             limit=1
#         )

#         if qr_doc:
#             return frappe.get_doc('Get Document Details', qr_doc[0].name)

#         # Create and submit new doc
#         doc = frappe.get_doc({
#             "doctype": "Get Document Details",
#             "sales_e_invoice": sales_invoice_name
#         })
#         doc.insert(ignore_permissions=True)
#         doc.submit()
#         frappe.msgprint("✅ Created and submitted 'Get Document Details'.")
        
#         return doc


#     @frappe.whitelist()
#     def gr_link(self):
#         # Step 1: Ensure 'Get Document Details' exists and is submitted
#         qr_doc = self.create_get_document_details_if_not_exists(self.name)

#         # Step 2: Validate 'code' field
#         if not qr_doc.code:
#             frappe.throw("❌ 'Get Document Details' is missing the 'code' field.")

#         try:
#             code_data = json.loads(qr_doc.code)
#         except json.JSONDecodeError as err:
#             frappe.throw(f"❌ Invalid JSON in 'code': {err}")

#         # Step 3: Validate JSON content
#         sales_e_invoice_status = code_data.get("status")
#         self.submission_status = sales_e_invoice_status

#         if sales_e_invoice_status != "Valid":
#             frappe.msgprint(f"⚠️ {self.name} is not valid for QR generation. Please check.")
#             return

#         uuid = code_data.get("uuid")
#         long_id = code_data.get("longId")
#         if not uuid or not long_id:
#             frappe.throw("❌ UUID or Long ID missing in QR code data.")

#         qr_link = f"https://myinvois.hasil.gov.my/{uuid}/share/{long_id}"

#         # Step 4: Generate QR image and attach it
#         try:
#             img_str = self.qr_code_img(qr_link)
#             filename = f"QR_{uuid}.png"

#             file_doc = frappe.get_doc({
#                 "doctype": "File",
#                 "file_name": filename,
#                 "is_private": 0,
#                 "content": base64.b64decode(img_str),
#                 "attached_to_doctype": "Sales E Invoice",
#                 "attached_to_name": self.name
#             })
#             file_doc.save(ignore_permissions=True)

#             # Step 5: Update document with QR file URL
#             self.validation_url = file_doc.file_url
#             self.save(ignore_permissions=True)

#             return {
#                 "qr_link": qr_link,
#                 "file_url": file_doc.file_url,
#                 "message": "✅ QR code generated and saved."
#             }

#         except Exception as e:
#             frappe.throw(f"❌ Failed to generate or save QR code: {e}")

# ---------------------------------------------------------------------------------------------------------------
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

            qr_link = f"{qr_base_url}/e-invois/preview/{self.uuid}/share/{long_id}"

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


def clean_digits(value):
    """Keep only digits from text."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))

def validate_phone(phone, label):
    """Validate phone numbers (must be 11 digits)."""
    cleaned = clean_digits(phone)
    if len(cleaned) not in (10, 11):
        frappe.throw(f"{label} must contain 10 or 11 digits. Given: {phone}")
    return cleaned

def validate_postal(postal, label):
    """Validate postal code (must be 5 digits)."""
    cleaned = clean_digits(postal)
    if len(cleaned) != 5:
        frappe.throw(f"{label} must contain exactly 5 digits. Given: {postal}")
    return cleaned

def extract_code(value):
    if not isinstance(value, str):
        return ""
    return value.split(":")[0].strip()

def get_response_text(response):
    """Return raw text if Response object, otherwise JSON dump."""
    if hasattr(response, "text"):  # real HTTP Response
        return response.text
    return frappe.as_json(response)  # dict or other type



import traceback

@frappe.whitelist()
def cancel_from_button(docname, reason):
    try:
        doc = frappe.get_doc("Sales E Invoice", docname)

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
        frappe.throw(_("Sales E Invoice {0} does not exist.".format(docname)))

    except Exception as e:
        frappe.log_error(title="Error Cancelling LHDN E-Invoice", message=traceback.format_exc())
        frappe.throw(_("Failed to cancel document in LHDN. Error: {0}").format(str(e)))





from frappe.model.mapper import get_mapped_doc
# e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/sales_e_invoice.py

import frappe
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def check_sales_invoice_used_v2(source_name):
    """
    Validates whether a Sales Invoice is already linked to any E-Invoice document.
    Returns warnings or blocks to control creation logic.
    """
    blocks = []
    warnings = []

    # Check Sales E Invoice
    existing = frappe.get_all(
        "Sales E Invoice",
        filters={"sales_invoice": source_name},
        fields=["name", "custom_lhdn_e_invoice_status"],
        limit=1
    )

    if existing:
        name = existing[0]["name"]
        status = existing[0]["custom_lhdn_e_invoice_status"] or "Unknown"
        docstatus = frappe.db.get_value("Sales E Invoice", name, "docstatus")

        if docstatus == 1:
            if status in ["Valid", "Submitted", "InProgress"]:
                blocks.append({
                    "name": source_name,
                    "source": "Sales E Invoice",
                    "existing_doc": name,
                    "status": status,
                    "error": f"Sales Invoice <b>{source_name}</b> is already linked to submitted Sales E Invoice <b>{name}</b> with status <b>{status}</b>. Cannot create again.",
                    "type": "block"
                })
            else:
                warnings.append({
                    "name": source_name,
                    "source": "Sales E Invoice",
                    "existing_doc": name,
                    "status": status,
                    "error": f"Sales Invoice <b>{source_name}</b> is linked to submitted Sales E Invoice <b>{name}</b> with status <b>{status}</b>. Please review before continuing.",
                    "type": "warning"
                })
        else:
            blocks.append({
                "name": source_name,
                "source": "Sales E Invoice",
                "existing_doc": name,
                "status": status,
                "error": f"Sales Invoice <b>{source_name}</b> is linked to draft Sales E Invoice <b>{name}</b>. Please submit or delete it first.",
                "type": "block"
            })

    # Check Consolidated E Invoice
    consolidated_invoice = frappe.db.sql("""
        SELECT parent FROM `tabConsolidated Invoice Entry`
        WHERE original_invoice = %s LIMIT 1
    """, source_name, as_dict=True)

    if consolidated_invoice:
        parent_name = consolidated_invoice[0]["parent"]
        parent_doc = frappe.get_doc("Consolidated E Invoice", parent_name)
        status = parent_doc.custom_lhdn_e_invoice_status or "Unknown"

        if parent_doc.docstatus == 1:
            if status in ["Valid", "Submitted", "InProgress"]:
                blocks.append({
                    "name": source_name,
                    "source": "Consolidated E Invoice",
                    "existing_doc": parent_name,
                    "status": status,
                    "error": f"Sales Invoice <b>{source_name}</b> is already in submitted Consolidated E Invoice <b>{parent_name}</b> with status <b>{status}</b>.",
                    "type": "block"
                })
            else:
                warnings.append({
                    "name": source_name,
                    "source": "Consolidated E Invoice",
                    "existing_doc": parent_name,
                    "status": status,
                    "error": f"Sales Invoice <b>{source_name}</b> is in Consolidated E Invoice <b>{parent_name}</b> with status <b>{status}</b>. Please review.",
                    "type": "warning"
                })
        else:
            blocks.append({
                "name": source_name,
                "source": "Consolidated E Invoice",
                "existing_doc": parent_name,
                "status": status,
                "error": f"Sales Invoice <b>{source_name}</b> is in draft Consolidated E Invoice <b>{parent_name}</b>. Please submit or delete it first.",
                "type": "block"
            })

    return {"blocks": blocks, "warnings": warnings}


@frappe.whitelist()
def make_sales_e_invoice(source_name, target_doc=None, ignore_permissions=False):
    def set_missing_values(source, target):
        target.flags.ignore_permissions = ignore_permissions
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        target.other_charges_calculation = source.other_charges_calculation
        target.sales_invoice = source.name
        # Log to Error Log in ERPNext Desk
        frappe.log_error(
            title="Debug: Target Doc Before Setting Tax Category",
            message=frappe.as_json(target)
        )

        if source.custom_tax_category:
            target.custom_tax_category = source.custom_tax_category

        # Optional: log again after assignment
            frappe.log_error(
                title="Debug: Target Doc After Setting Tax Category",
                message=frappe.as_json(target)
            )
    try:
        doclist = get_mapped_doc(
            "Sales Invoice",
            source_name,
            {
                "Sales Invoice": {
                    "doctype": "Sales E Invoice",
                    "validation": {"docstatus": ["=", 1]},
                },
                "Sales Invoice Item": {
                    "doctype": "Sales Invoice Item",
                    "field_map": {
                        "name": "si_detail",
                        "parent": "sales_invoice",
                        "custom_total_amount_before_discount": "custom_total_amount_before_discount",
                        
                    },
                    "condition": lambda doc: doc.qty > 0,
                },
                "Sales Taxes and Charges": {
                    "doctype": "Sales Taxes and Charges",
                    "field_map": {
                        # "Source Field": "Target Field"
                        "custom_is_tax": "custom_is_tax" 
                    },
                    "condition": lambda doc: doc.tax_amount != 0,
                    "reset_value": True,
                },
                "Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
            },
            target_doc,
            set_missing_values,
            ignore_permissions=ignore_permissions,
        )

        return doclist

    except Exception:
        frappe.throw("Unexpected error while creating Sales E Invoice. Please check the server logs.")




# In your validate_and_populate_party_info function

@frappe.whitelist()
def validate_and_populate_party_info(doc):
    if isinstance(doc, str):
        doc = frappe._dict(json.loads(doc))
    
    # ... (pre-checks for company and customer) ...

    try:
        # --- Step 1: Fetch master documents ---
        company_doc = frappe.get_doc("Company", doc.company)
        customer_doc = frappe.get_doc("Customer", doc.customer)

        # --- Step 2: Get Company Address ---
        # Your method for getting the company address is correct.
        company_address_name = frappe.db.get_value(
            "Dynamic Link",
            {"link_doctype": "Company", "link_name": company_doc.name, "parenttype": "Address"},
            "parent"
        )
        if not company_address_name:
            # It's better to throw an error if the company has no linked address.
            frappe.throw(_("The selected Company '{0}' does not have a linked address.").format(company_doc.name))
        
        address_doc = frappe.get_doc("Address", company_address_name)

        # --- Step 3: Get Customer's PRIMARY Address (The Simple Way) ---
        # This is the most reliable way. Trust the field on the Customer doctype.
        customer_primary_address_name = customer_doc.customer_primary_address
        
        if not customer_primary_address_name:
            # If the customer has no primary address set, it's a validation failure.
            frappe.throw(_("The selected Customer '{0}' does not have a 'Customer Primary Address' set.").format(customer_doc.name))

        # Now, fetch the full address document using the name we just got.
        address_customer_doc = frappe.get_doc("Address", customer_primary_address_name)
        
        # You can now confidently use 'address_doc' for the company and 'address_customer_doc' for the customer.
        print(f"Company Address: {address_doc.address_line1}, {address_doc.city}")
        print(f"Customer Address: {address_customer_doc.address_line1}, {address_customer_doc.city}")

    except frappe.DoesNotExistError as e:
        # This will catch errors if get_doc fails for Company, Customer, or Address
        frappe.throw(
            _("Could not find a required document: {0}").format(e),
            title=_("Invalid Document Link"),
        )
    
    # ... (rest of your validation logic for company fields, address fields, etc.) ...
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
        message = _(
            f"The selected Company <b>{doc.company}</b> is missing required information:"
        )
        message += "<ul>" + "".join(missing_company_fields) + "</ul>"
        message += _("Please update the Company record and try again.")
        frappe.throw(message, title=_("Incomplete Company Data"))

    # All company checks passed, assign values.
    doc.registration_name = company_doc.custom_taxpayer_name
    doc.registration_full_name = company_doc.custom_taxpayer_name

    msic_full_string = company_doc.custom_msic_code_
    if msic_full_string and ":" in msic_full_string:
        # Extract just the numeric part before the colon
        doc.msic_codes = msic_full_string.split(":", 1)[0].strip()
    else:
        # If the format is unexpected, assign the original value as a fallback
        doc.msic_codes = msic_full_string

    doc.supplier_brn = company_doc.custom_company__registrationicpassport_number
    doc.supplier_tin = company_doc.custom_company_tin_number
    doc.tourism_tax_registration = company_doc.custom_tourism_tax_number
    # =========================================================================
    # 3. supplier ADDRESS VALIDATION & ASSIGNMENT
    # =========================================================================
    def validate_required_fields(obj, fields_with_labels, label="Object"):
        """
        Checks that the given object has non-empty values for all fields.

        :param obj: The object (e.g. a Frappe Doc or dict) to validate.
        :param fields: A list of field names to check.
        :param label: Optional label to use in error messages.
        :return: List of missing field names.
        """
        missing_labels = []
        for fieldname, user_label in fields_with_labels.items():
            if not getattr(obj, fieldname, None):
                missing_labels.append(user_label)
        
        if missing_labels:
            # Create a nicer HTML message
            missing_html = "<ul>" + "".join(f"<li>{lbl}</li>" for lbl in missing_labels) + "</ul>"
            frappe.throw(
                _("{} is missing required fields: {}").format(label, missing_html),
                title=_("Missing Required Fields"),
            )
    def extract_code_before_colon(value):
        return value.split(":", 1)[0].strip() if value and ":" in value else value

    company_address_required_fields = {
        "name": "Name",
        "address_title": "Address Title",
        "city": "City",
        "state": "State",
        "custom_state_code": "State Code",
        "pincode": "Postal Code",
        "phone": "Phone",
        "email_id": "Email ID",
    }
    if address_doc:
        for field in company_address_required_fields:
            print(f"{field}: {getattr(address_doc, field, None)}")
        # Validate address fields using the helper
        validate_required_fields(
            address_doc,
            company_address_required_fields,
            label=f"Company Address for {doc.company}",
        )
        print(f"address_doc: {address_doc}")
        # The customer has a valid, linked primary address. Assign its details.
        doc.supplier_address_name = address_doc.name
        doc.supplier_location = address_doc.address_title
        print(doc.supplier_location)
        doc.supplier_city = address_doc.city
        doc.supplier_state = address_doc.state
        state_code = address_doc.custom_state_code
        doc.supplier_state_codes = extract_code_before_colon(address_doc.custom_state_code)

        doc.supplier_postal_code = address_doc.pincode
        doc.suplier_mobile = address_doc.phone
        doc.supplier_email_address = address_doc.email_id
        # Add any other address fields you need here, e.g.:
        # doc.supplier_address_line2 = address_doc.address_line2
    else:
        # This means the customer is valid but has no primary address set.
        # This is a validation failure for this document.

        # First, clear any stale data.
        doc.supplier_address_name = None
        doc.supplier_city = None
        doc.supplier_state = None
        doc.supplier_pincode = None
        doc.supplier_country = None

        # Then, throw a clear error.
        frappe.throw(
            _(
                f"The selected Customer <b>{doc.customer}</b> does not have a Primary Address set."
            ),
            title=_("Missing Primary Address"),
        )
    # =========================================================================
    # 4. CUSTOMER DATA VALIDATION
    # =========================================================================

    required_customer_fields = {
        "custom_customer_registrationicpassport_number": "Customer Registration/IC/Passport Number",
        "custom_customer_tin_number": "Customer TIN number",
    }

    missing_customer_fields = [
        f"<li>{label}</li>"
        for fieldname, label in required_customer_fields.items()
        if not getattr(customer_doc, fieldname, None)
    ]

    if missing_customer_fields:
        message = _(
            f"The selected customer <b>{doc.customer}</b> is missing required information:"
        )
        message += "<ul>" + "".join(missing_customer_fields) + "</ul>"
        message += _("Please update the customer record and try again.")
        frappe.throw(message, title=_("Incomplete customer Data"))

    # All customer checks passed, assign values.
    doc.customer_brn = customer_doc.custom_customer_registrationicpassport_number
    doc.customer_tin = customer_doc.custom_customer_tin_number

    # =========================================================================
    # 5. CUSTOMER ADDRESS VALIDATION & ASSIGNMENT
    # =========================================================================

    customer_address_required_fields = {
    "name": "Name",
    "address_title": "Address Title",
    "city": "City",
    "state": "State",
    "custom_state_code": "State Code",
    "pincode": "Postal Code",
    "phone": "Phone",
    "email_id": "Email ID",
    }

    if address_customer_doc:
        # Validate address fields using the helper
        validate_required_fields(
            address_customer_doc,
             customer_address_required_fields,
              label=f"Address for Customer {doc.customer}"
        )

        # Assign values if all required fields are present
        doc.customer_address = address_customer_doc.name
        doc.address_line1 = address_customer_doc.address_title
        doc.city_customer = address_customer_doc.city
        doc.state_customer = address_customer_doc.state

        state_code = address_customer_doc.custom_state_code
        doc.customer_state_code = extract_code_before_colon(address_customer_doc.custom_state_code)

        doc.customer_postal_code = address_customer_doc.pincode
        doc.customer_phone = address_customer_doc.phone
        doc.customer_email_address = address_customer_doc.email_id

    else:
        # No address found
        doc.customer_address = None
        doc.city_customer = None
        doc.state_customer = None
        doc.customer_postal_code = None
        doc.customer_state_code = None

        frappe.throw(
            _(
                "The selected Customer <b>{}</b> does not have a Primary Address set."
            ).format(doc.customer),
            title=_("Missing Primary Address"),
        )
    return {
        "registration_name": doc.registration_name,
        "registration_full_name": doc.registration_full_name,
        "msic_codes": doc.msic_codes,
        "supplier_brn": doc.supplier_brn,
        "supplier_tin": doc.supplier_tin,
        "tourism_tax_registration": doc.tourism_tax_registration,
        # supplier address fields
        "supplier_address_name": doc.supplier_address_name,
        "supplier_location": doc.supplier_location,
        "supplier_city": doc.supplier_city,
        "supplier_state": doc.supplier_state,
        "supplier_state_codes": doc.supplier_state_codes,
        "supplier_postal_code": doc.supplier_postal_code,
        "suplier_mobile": doc.suplier_mobile,
        "supplier_email_address": doc.supplier_email_address,
        # customer fields
        "customer_brn": doc.customer_brn,
        "customer_tin": doc.customer_tin,
        # customer address fields
        "customer_address": doc.customer_address,
        "address_line1": doc.address_line1,
        "city_customer": doc.city_customer,
        "state_customer": doc.state_customer,
        "customer_state_code": doc.customer_state_code,
        "customer_postal_code": doc.customer_postal_code,
        "customer_phone": doc.customer_phone,
        "customer_email_address": doc.customer_email_address,
    }

# This function MUST be called from the 'before_cancel' hook
def before_cancel_sales_e_invoice_hook(doc, method):

    sales_invoice_name = doc.name

    try:
        if not doc.sales_e_invoice_number:
            return
        
        linked_e_invoices = frappe.get_all(
            "Sales E Invoice",
            filters={"sales_invoice": sales_invoice_name},
            fields=["name"]
        )
        for sei_meta in linked_e_invoices:
            e_invoice_doc = frappe.get_doc("Sales E Invoice", sei_meta.name)
            e_invoice_doc.sales_invoice = None  # Remove the link
            e_invoice_doc.custom_lhdn_e_invoice_status = "Cancelled"
            e_invoice_doc.save(ignore_permissions=True)

        doc.sales_e_invoice_number = None
        doc.custom_lhdn_status = None
    except Exception:
        frappe.log_error(traceback.format_exc(), "Before Cancel Sales Invoice Hook")
        frappe.throw("Could not unlink the related Sales E Invoice. Cancellation aborted.")

def validate_tax_type(doc, method=None):
    TaxCategory = doc.custom_tax_category
    if TaxCategory and ":" in TaxCategory:
                # Extract just the numeric part before the colon
        TaxCategory = TaxCategory.split(":", 1)[0].strip()
    else:
        # If the format is unexpected, assign the original value as a fallback
        TaxCategory = doc.custom_tax_category
    if doc.total_taxes_and_charges == 0 and TaxCategory != "06":
        print(doc.custom_tax_category)
        frappe.throw(_("Tax Category must be '06 : Not Applicable' when there are no taxes applied."))

