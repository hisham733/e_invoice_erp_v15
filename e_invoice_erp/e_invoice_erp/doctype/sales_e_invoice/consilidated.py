# from __future__ import unicode_literals
# import logging
# import pdb
# import base64
# import hashlib
# import json
# from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import (
#     get_party_tax_withholding_details,
# )

# # from frappe.api import utils
# import pytz
# import requests
# from datetime import datetime, timedelta
# from bs4 import BeautifulSoup
# import frappe
# from frappe.model.document import Document
# from frappe.model.mapper import get_mapped_doc
# from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
#     APICredentials,
# )
# from e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.run_invoice import (
#     remove_signature_and_ublextensions,
# )
# import base64
# from cryptography.hazmat.primitives import hashes
# from cryptography.hazmat.primitives.asymmetric import padding, utils
# from cryptography.hazmat.primitives.serialization import pkcs12
# import os

# logger = logging.getLogger(__name__)
# url = ""
# token = ""
# import base64
# from io import BytesIO
# import qrcode
# from PIL import Image


# class SalesEInvoice(Document):

#     # def before_save(self):
#     #     try:
#     #         self.update_api_credentials_and_fetch_token()
#     #     except Exception as e:
#     #         logger.exception("Error in before_save while updating API credentials.")
#     #         frappe.throw(f"Error in before_save: {str(e)}")

#     def before_submit(self):
#         try:
#             utc_timestamp = self.get_utc_timestamp()
#             sales_invoice_doc = self.fetch_sales_invoice_details()

#             tax_subtotals, tax_category, item_prices = (
#                 self.get_sales_invoice_details_items_info(sales_invoice_doc)
#             )

#             X509Certificate, issuer_name, serial_number, cert_hash_base64 = (
#                 self.update_api_credentials_and_fetch_token()
#             )
#             formatted_posting_date, formatted_issue_time = self.fix_time_format(
#                 sales_invoice_doc
#             )
#             invoice_data, info, base64_hash, document_info = self.build_document_info(
#                 sales_invoice_doc,
#                 formatted_posting_date,
#                 formatted_issue_time,
#                 item_prices,
#                 tax_subtotals,
#                 tax_category,
#                 utc_timestamp,
#                 None,
#                 X509Certificate,
#                 issuer_name,
#                 serial_number,
#                 cert_hash_base64,
#                 None,
#                 None,
#             )

#             docdigest = self.sign_document_digest(base64_hash)
#             print("Invoice data built successfully in before_submit.")

#             invoice_data, info, base64_hash, document_info = self.build_document_info(
#                 sales_invoice_doc,
#                 formatted_posting_date,
#                 formatted_issue_time,
#                 item_prices,
#                 tax_subtotals,
#                 tax_category,
#                 utc_timestamp,
#                 base64_hash,
#                 X509Certificate,
#                 issuer_name,
#                 serial_number,
#                 cert_hash_base64,
#                 docdigest,
#                 None,
#             )

#             output_directory = "home/frappe/frappe-bench/apps/e_invoice_erp/e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/"

#             step7 = self.extract_target_and_signed_properties(
#                 document_info, output_directory
#             )

#             json_file_path = os.path.join(output_directory, "signed_properties.json")
#             with open(json_file_path, "r", encoding="utf-8") as json_file:
#                 json_data = json.load(json_file)

#             property_path = "SignedProperties.0.SignedSignatureProperties"
#             extracted_property = self.extract_property(json_data, property_path)
#             print("Extracted Property:", extracted_property)

#             minified_json = self.minify_json(json_data)
#             print("Minified JSON:", minified_json)

#             props_digest = self.generate_sha256_base64(minified_json)
#             print("Props Digest (Base64):", props_digest)

#             self.invoice_data = self.build_document_info(
#                 sales_invoice_doc,
#                 formatted_posting_date,
#                 formatted_issue_time,
#                 item_prices,
#                 tax_subtotals,
#                 tax_category,
#                 utc_timestamp,
#                 base64_hash,
#                 X509Certificate,
#                 issuer_name,
#                 serial_number,
#                 cert_hash_base64,
#                 docdigest,
#                 props_digest,
#             )

#         except Exception as e:
#             logger.exception("Error in before_submit while building invoice data.")
#             frappe.throw(f"Error in before_submit: {str(e)}")

#     def on_submit(self):
#         try:

#             if isinstance(self.invoice_data, tuple):
#                 self.invoice_data = self.invoice_data[0]

#             if not isinstance(self.invoice_data, dict):
#                 frappe.throw(
#                     f"❌ Error: invoice_data must be a dictionary but received type: {type(self.invoice_data)}"
#                 )

#             print("self.invoice_data", self.invoice_data)
#             if self.invoice_data:
#                 response = self.send_einvoice(
#                     self.invoice_data,
#                 )
#                 if response:
#                     self.submission_uid = response.get("submissionUid")
#                     self.uuid = response.get("uuid")
#                     self.invoicecodenumber = response.get("invoiceCodeNumber")
#                     logger.info(
#                         f"Invoice submission successful: UID: {self.submission_uid}, UUID: {self.uuid}"
#                     )
#                     frappe.msgprint("Invoice submitted successfully.")
#                     self.save()
#                 else:
#                     frappe.throw(
#                         "No data returned from e-invoice service. Please check logs for details."
#                     )
#             else:
#                 print("cannot print")

#         except Exception as e:
#             frappe.throw(f"Failed to send e-invoice: {str(e)}")

#     def sign_document_digest(self, docdigest: str) -> str:
#         try:

#             if not self.api_credentials:
#                 frappe.throw("❌ API Credentials are missing.")

#             api_key_open = frappe.get_doc("API Credentials", self.api_credentials)
#             if not api_key_open.cert or not api_key_open.cert_password:
#                 frappe.throw(
#                     "❌ Certificate or password is missing in API Credentials."
#                 )

#             cert_path = frappe.utils.get_site_path(api_key_open.cert.lstrip("/"))
#             cert_password = api_key_open.cert_password.encode()
#             if not os.path.exists(cert_path):
#                 frappe.throw(f"❌ Certificate file not found at: {cert_path}")

#             with open(cert_path, "rb") as f:
#                 p12_data = f.read()

#             private_key, certificate, additional_certs = (
#                 pkcs12.load_key_and_certificates(p12_data, cert_password)
#             )

#             if not private_key:
#                 frappe.throw("❌ Private key is missing in the certificate!")

#             try:
#                 hash_bytes = base64.b64decode(docdigest)
#             except Exception:
#                 frappe.throw("❌ Invalid Base64 hash format for document digest.")

#             public_numbers = private_key.public_key().public_numbers()
#             modulus_hex = (
#                 public_numbers.n.to_bytes(
#                     (public_numbers.n.bit_length() + 7) // 8, byteorder="big"
#                 )
#                 .hex()
#                 .upper()
#             )
#             exponent = public_numbers.e

#             signature_bytes = private_key.sign(
#                 hash_bytes, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256())
#             )

#             signature_base64 = base64.b64encode(signature_bytes).decode()
#             logger.info(
#                 f"✅ Document successfully signed. Signature (Base64): {signature_base64}"
#             )

#             return signature_base64

#         except FileNotFoundError as e:
#             frappe.throw(f"❌ Certificate file not found: {str(e)}")
#         except ValueError as e:
#             frappe.throw(f"❌ Invalid certificate format: {str(e)}")
#         except KeyError as e:
#             frappe.throw(f"❌ Missing key in API credentials: {str(e)}")
#         except Exception as e:
#             frappe.throw(f"❌ Error while signing document: {str(e)}")

#     @frappe.whitelist()
#     def update_api_credentials_and_fetch_token(self):
#         try:

#             if not self.api_credentials or self.api_credentials:
#                 latest_record = frappe.db.get_value(
#                     "API Credentials", {}, "name", order_by="creation desc"
#                 )
#                 if not latest_record:
#                     frappe.throw(
#                         "⚠️ No records found in 'API Credentials'. Please configure API credentials."
#                     )

#                 self.api_credentials = latest_record
#                 frappe.db.commit()

#             api_credentials_doc = frappe.get_doc(
#                 "API Credentials", self.api_credentials
#             )

#             if (
#                 not api_credentials_doc.client_id
#                 or not api_credentials_doc.client_secret
#             ):
#                 frappe.throw(
#                     "⚠️ Client ID or Client Secret is missing in API Credentials."
#                 )

#             try:
#                 token, api_url = APICredentials.fetch_api_token(api_credentials_doc)
#             except Exception as e:
#                 frappe.throw(f"❌ Failed to retrieve API token: {str(e)}")

#             if not token:
#                 frappe.throw(
#                     "⚠️ API token retrieval failed. Please check API Credentials configuration."
#                 )

#             self.api_access_token = token
#             logger.info(f"Successfully obtained API access token.")

#             try:
#                 cert_info = APICredentials.get_cert_info(api_credentials_doc)
#             except Exception as e:
#                 frappe.throw(f"❌ Failed to retrieve certificate information: {str(e)}")

#             if not cert_info or len(cert_info) != 4:
#                 frappe.throw("⚠️ Certificate information is incomplete or missing.")

#             logger.info("Successfully fetched certificate information.")

#             return cert_info  # (X509Certificate, issuer_name, serial_number, cert_hash_base64)

#         except frappe.ValidationError as e:
#             logger.exception("Validation error in API credentials update.")
#             frappe.throw(f"Validation Error: {str(e)}")
#         except Exception as e:
#             logger.exception(
#                 "Unexpected error updating API credentials and fetching token."
#             )
#             frappe.throw(
#                 f"❌ Error updating API credentials and fetching token: {str(e)}"
#             )

#     @frappe.whitelist()
#     def fetch_sales_invoice_details(self):
#         try:
#             sales_name = self.name
#             sales_invoice_doc = frappe.get_doc("Sales E Invoice", sales_name)
#             return sales_invoice_doc
#         except Exception as e:
#             frappe.throw(f"Error fetching Sales E Invoice details: {str(e)}")

#     @frappe.whitelist()
#     def get_sales_invoice_details_tax(self, sales_invoice_doc):
#         try:
#             tax_category = str(sales_invoice_doc.tax_category).strip()
#             other_charges_html = sales_invoice_doc.other_charges_calculation or ""

#             soup = BeautifulSoup(other_charges_html, "html.parser")
#             tax_table = soup.find(
#                 "table", {"class": "table table-bordered table-hover"}
#             )

#             if not tax_table:
#                 frappe.throw(
#                     f"No tax table found for Sales Invoice {sales_invoice_doc.name}"
#                 )

#             total_tax_amount = 0.0

#             for row in tax_table.find_all("tr")[1:]:
#                 cells = row.find_all("td")
#                 if len(cells) > 2:
#                     tax_rate_text = cells[2].text.strip().split()[-1]
#                     try:
#                         tax_rate_value = float(
#                             tax_rate_text.replace("RM", "").replace(",", "")
#                         )
#                         total_tax_amount += tax_rate_value
#                     except ValueError:
#                         pass  # Ignore invalid entries

#             # ✅ Only one tax_subtotal now
#             tax_subtotals = []

#             tax_subtotal_dict = {
#                 "TaxableAmount": [
#                     {"_": round(sales_invoice_doc.net_total, 2), "currencyID": "MYR"}
#                 ],
#                 "TaxAmount": [{"_": round(total_tax_amount, 2), "currencyID": "MYR"}],
#                 "TaxCategory": [
#                     {
#                         "ID": [{"_": tax_category}],
#                         "TaxScheme": [
#                             {
#                                 "ID": [
#                                     {
#                                         "_": "OTH",
#                                         "schemeID": "UN/ECE 5153",
#                                         "schemeAgencyID": "6",
#                                     }
#                                 ]
#                             }
#                         ],
#                     }
#                 ],
#             }

#             tax_subtotals.append(tax_subtotal_dict)
#             return tax_subtotals

#         except Exception as e:
#             frappe.throw(f"❌ Error in get_sales_invoice_details: {e}")

#     def get_sales_invoice_details_items_info(self, invoice):
#         try:
#             item_prices = []
#             for index, item in enumerate(invoice.get("items", [])):
#                 tax_subtotals, tax_category = self.get_sales_invoice_details_tax_info(
#                     invoice
#                 )
#                 item_tax_subtotal = (
#                     tax_subtotals[index] if index < len(tax_subtotals) else {}
#                 )
#                 # print(f"item_tax_subtotal: {item_tax_subtotal}")
#                 description = item.get("Description")
#                 net_amount = item.get("LineExtensionAmount")
#                 price_list_rate = item.get("Price")
#                 amount = item.get("amount")
#                 # total_taxes_and_charges = item.get("total_taxes_and_charges")
#                 total_amount_before_discount = item.get("total_amount_before_discount")
#                 invoice_item = {
#                     "ID": [{"_": str(index + 1)}],
#                     "LineExtensionAmount": (
#                         [{"_": net_amount, "currencyID": "MYR"}] if net_amount else []
#                     ),
#                     "TaxTotal": [
#                         {
#                             "TaxAmount": [
#                                 {
#                                     "_": invoice.get("total_taxes_and_charges"),
#                                     "currencyID": "MYR",
#                                 }
#                             ],
#                             "TaxSubtotal": [
#                                 {
#                                     "TaxAmount": [
#                                         {
#                                             "_": item_tax_subtotal.get(
#                                                 "TaxAmount", [{}]
#                                             )[0].get("_", 0),
#                                             "currencyID": "MYR",
#                                         }
#                                     ],
#                                     "TaxCategory": [
#                                         {
#                                             "ID": [{"_": tax_category}],
#                                             "Percent": (
#                                                 [
#                                                     {
#                                                         "_": (
#                                                             item_tax_subtotal.get(
#                                                                 "TaxAmount", [{}]
#                                                             )[0].get("_", 0)
#                                                             / amount
#                                                             * 100
#                                                         )
#                                                     }
#                                                 ]
#                                                 if amount
#                                                 else []
#                                             ),
#                                             "TaxScheme": [
#                                                 {
#                                                     "ID": [
#                                                         {
#                                                             "_": "OTH",
#                                                             "schemeID": "UN/ECE 5153",
#                                                             "schemeAgencyID": "6",
#                                                         }
#                                                     ]
#                                                 }
#                                             ],
#                                         }
#                                     ],
#                                 }
#                             ],
#                         }
#                     ],
#                     "Item": [
#                         {
#                             "CommodityClassification": (
#                                 [
#                                     {
#                                         "ItemClassificationCode": [
#                                             {
#                                                 "_": "004",
#                                                 "listID": "CLASS",
#                                             }
#                                         ]
#                                     }
#                                 ]
#                             ),
#                             "Description": [{"_": description}] if description else [],
#                         }
#                     ],
#                     "Price": (
#                         [{"PriceAmount": [{"_": price_list_rate, "currencyID": "MYR"}]}]
#                         if price_list_rate
#                         else []
#                     ),
#                     "ItemPriceExtension": [
#                         {
#                             "Amount": [
#                                 {"_": total_amount_before_discount, "currencyID": "MYR"}
#                             ]
#                         }
#                     ],
#                 }
#                 item_prices.append(invoice_item)

#             return tax_subtotals, tax_category, item_prices
#         except Exception as e:
#             print(f"Error in get_sales_invoice_details: {str(e)}")
#             return []

#     def fix_time_format(self, sales_invoice_doc):
#         try:
#             posting_date = sales_invoice_doc.posting_date
#             posting_time = sales_invoice_doc.posting_time
#             if isinstance(posting_date, str):
#                 posting_date = datetime.strptime(posting_date, "%Y-%m-%d")
#             if isinstance(posting_time, str):
#                 hours, minutes, seconds = map(int, posting_time.split(":"))
#                 posting_time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
#             posting_time_str = (
#                 (datetime.min + posting_time).time().strftime("%H:%M:%S")
#                 if isinstance(posting_time, timedelta)
#                 else posting_time.strftime("%H:%M:%S")
#             )
#             combined_datetime = datetime.combine(
#                 posting_date, datetime.strptime(posting_time_str, "%H:%M:%S").time()
#             )
#             local_timezone = pytz.timezone("Asia/Kuala_Lumpur")
#             local_datetime = local_timezone.localize(combined_datetime, is_dst=None)
#             utc_datetime = local_datetime.astimezone(pytz.utc)
#             formatted_posting_date = utc_datetime.strftime("%Y-%m-%d")
#             formatted_issue_time = utc_datetime.strftime("%H:%M:%SZ")
#             return formatted_posting_date, formatted_issue_time
#         except Exception as e:
#             print(f"Error in fix_time_format: {str(e)}")
#             return None

#     def get_utc_timestamp(self):
#         utc_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
#         return utc_timestamp

#     def build_document_info(
#         self,
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
#         cert_hash_base64,
#         docdigest,
#         props_digest,
#     ):
#         try:
#             document_info = {
#                 "_D": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
#                 "_A": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
#                 "_B": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
#                 "Invoice": [
#                     {
#                         "ID": [{"_": sales_invoice_doc.name}],
#                         "IssueDate": [{"_": formatted_posting_date}],
#                         "IssueTime": [{"_": formatted_issue_time}],
#                         "InvoiceTypeCode": [{"_": "01", "listVersionID": "1.1"}],
#                         "DocumentCurrencyCode": [{"_": "MYR"}],
#                         "TaxCurrencyCode": [{"_": "MYR"}],
#                         "AccountingSupplierParty": [
#                             {
#                                 "Party": [
#                                     {
#                                         "IndustryClassificationCode": [
#                                             {
#                                                 "_": sales_invoice_doc.msic_codes,
#                                                 "name": sales_invoice_doc.company,
#                                             }
#                                         ],
#                                         "PartyIdentification": [
#                                             {
#                                                 "ID": [
#                                                     {
#                                                         "_": sales_invoice_doc.supplier_tin,
#                                                         "schemeID": "TIN",
#                                                     }
#                                                 ]
#                                             },
#                                             {
#                                                 "ID": [
#                                                     {
#                                                         "_": sales_invoice_doc.supplier_brn,
#                                                         "schemeID": "BRN",
#                                                     }
#                                                 ]
#                                             },
#                                             {
#                                                 "ID": [
#                                                     {
#                                                         "_": sales_invoice_doc.tourism_tax_registration,
#                                                         "schemeID": "SST",
#                                                     }
#                                                 ]
#                                             },
#                                         ],
#                                         "PostalAddress": [
#                                             {
#                                                 "CityName": [
#                                                     {
#                                                         "_": sales_invoice_doc.supplier_city
#                                                     }
#                                                 ],
#                                                 "PostalZone": [
#                                                     {
#                                                         "_": sales_invoice_doc.supplier_postal_code
#                                                     }
#                                                 ],
#                                                 "CountrySubentityCode": [
#                                                     {
#                                                         "_": sales_invoice_doc.supplier_state_codes
#                                                     }
#                                                 ],
#                                                 "AddressLine": [
#                                                     {
#                                                         "Line": [
#                                                             {
#                                                                 "_": sales_invoice_doc.supplier_location
#                                                             }
#                                                         ]
#                                                     }
#                                                 ],
#                                                 "Country": [
#                                                     {
#                                                         "IdentificationCode": [
#                                                             {
#                                                                 "_": "MYS",
#                                                                 "listID": "ISO3166-1",
#                                                                 "listAgencyID": "6",
#                                                             }
#                                                         ]
#                                                     }
#                                                 ],
#                                             }
#                                         ],
#                                         "PartyLegalEntity": [
#                                             {
#                                                 "RegistrationName": [
#                                                     {
#                                                         "_": sales_invoice_doc.registration_name
#                                                     }
#                                                 ]
#                                             }
#                                         ],
#                                         "Contact": [
#                                             {
#                                                 "Telephone": [
#                                                     {
#                                                         "_": sales_invoice_doc.suplier_mobile
#                                                     }
#                                                 ],
#                                                 "ElectronicMail": [
#                                                     {
#                                                         "_": sales_invoice_doc.supplier_email_address
#                                                     }
#                                                 ],
#                                             }
#                                         ],
#                                     }
#                                 ]
#                             }
#                         ],
#                         "AccountingCustomerParty": [
#                             {
#                                 "Party": [
#                                     {
#                                         "PostalAddress": [
#                                             {
#                                                 "CityName": [{"_": ""}],
#                                                 "PostalZone": [{"_": ""}],
#                                                 "CountrySubentityCode": [{"_": ""}],
#                                                 "AddressLine": [
#                                                     {"Line": [{"_": "NA"}]}
#                                                 ],
#                                                 "Country": [
#                                                     {
#                                                         "IdentificationCode": [
#                                                             {
#                                                                 "_": "MYS",
#                                                                 "listID": "ISO3166-1",
#                                                                 "listAgencyID": "6",
#                                                             }
#                                                         ]
#                                                     }
#                                                 ],
#                                             }
#                                         ],
#                                         "PartyLegalEntity": [
#                                             {
#                                                 "RegistrationName": [
#                                                     {"_": "Consolidated Buyer's"}
#                                                 ]
#                                             }
#                                         ],
#                                         "PartyIdentification": [
#                                             {
#                                                 "ID": [
#                                                     {
#                                                         "_": "EI00000000010",
#                                                         "schemeID": "TIN",
#                                                     }
#                                                 ]
#                                             },
#                                             {
#                                                 "ID": [
#                                                     {
#                                                         "_": "NA",
#                                                         "schemeID": "BRN",
#                                                     }
#                                                 ]
#                                             },
#                                         ],
#                                         "Contact": [
#                                             {
#                                                 "Telephone": [{"_": "NA"}],
#                                                 "ElectronicMail": [{"_": "NA"}],
#                                             }
#                                         ],
#                                     }
#                                 ]
#                             }
#                         ],
#                         "TaxTotal": [
#                             {
#                                 "TaxAmount": [
#                                     {
#                                         "_": sales_invoice_doc.total_taxes_and_charges,
#                                         "currencyID": "MYR",
#                                     }
#                                 ],
#                                 "TaxSubtotal": tax_subtotals,
#                             }
#                         ],
#                         "LegalMonetaryTotal": [
#                             {
#                                 "TaxExclusiveAmount": [
#                                     {
#                                         "_": sales_invoice_doc.net_total,
#                                         "currencyID": "MYR",
#                                     }
#                                 ],
#                                 "TaxInclusiveAmount": [
#                                     {
#                                         "_": sales_invoice_doc.grand_total,
#                                         "currencyID": "MYR",
#                                     }
#                                 ],
#                                 "PayableAmount": [
#                                     {
#                                         "_": sales_invoice_doc.rounded_total,
#                                         "currencyID": "MYR",
#                                     }
#                                 ],
#                             }
#                         ],
#                         "InvoiceLine": item_prices,
#                         "UBLExtensions": [
#                             {
#                                 "UBLExtension": [
#                                     {
#                                         "ExtensionURI": [
#                                             {
#                                                 "_": "urn:oasis:names:specification:ubl:dsig:enveloped:xades"
#                                             }
#                                         ],
#                                         "ExtensionContent": [
#                                             {
#                                                 "UBLDocumentSignatures": [
#                                                     {
#                                                         "SignatureInformation": [
#                                                             {
#                                                                 "ID": [
#                                                                     {
#                                                                         "_": "urn:oasis:names:specification:ubl:signature:1"
#                                                                     }
#                                                                 ],
#                                                                 "ReferencedSignatureID": [
#                                                                     {
#                                                                         "_": "urn:oasis:names:specification:ubl:signature:Invoice"
#                                                                     }
#                                                                 ],
#                                                                 "Signature": [
#                                                                     {
#                                                                         "Id": "signature",
#                                                                         "Object": [
#                                                                             {
#                                                                                 "QualifyingProperties": [
#                                                                                     {
#                                                                                         "Target": "signature",
#                                                                                         "SignedProperties": [
#                                                                                             {
#                                                                                                 "Id": "id-xades-signed-props",
#                                                                                                 "SignedSignatureProperties": [
#                                                                                                     {
#                                                                                                         "SigningTime": [
#                                                                                                             {
#                                                                                                                 "_": utc_timestamp
#                                                                                                             }
#                                                                                                         ],
#                                                                                                         "SigningCertificate": [
#                                                                                                             {
#                                                                                                                 "Cert": [
#                                                                                                                     {
#                                                                                                                         "CertDigest": [
#                                                                                                                             {
#                                                                                                                                 "DigestMethod": [
#                                                                                                                                     {
#                                                                                                                                         "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256"
#                                                                                                                                     }
#                                                                                                                                 ],
#                                                                                                                                 "DigestValue": [
#                                                                                                                                     {
#                                                                                                                                         "_": cert_hash_base64
#                                                                                                                                     }
#                                                                                                                                 ],
#                                                                                                                             }
#                                                                                                                         ],
#                                                                                                                         "IssuerSerial": [
#                                                                                                                             {
#                                                                                                                                 "X509IssuerName": [
#                                                                                                                                     {
#                                                                                                                                         "_": f"CN={issuer_name}, OU=Terms of use at http://www.posdigicert.com.my, O=LHDNM, C=MY"
#                                                                                                                                     }
#                                                                                                                                 ],
#                                                                                                                                 "X509SerialNumber": [
#                                                                                                                                     {
#                                                                                                                                         "_": serial_number
#                                                                                                                                     }
#                                                                                                                                 ],
#                                                                                                                             }
#                                                                                                                         ],
#                                                                                                                     }
#                                                                                                                 ]
#                                                                                                             }
#                                                                                                         ],
#                                                                                                     }
#                                                                                                 ],
#                                                                                             }
#                                                                                         ],
#                                                                                     }
#                                                                                 ]
#                                                                             }
#                                                                         ],
#                                                                         "KeyInfo": [
#                                                                             {
#                                                                                 "X509Data": [
#                                                                                     {
#                                                                                         "X509Certificate": [
#                                                                                             {
#                                                                                                 "_": X509Certificate
#                                                                                             }
#                                                                                         ],
#                                                                                         "X509SubjectName": [
#                                                                                             {
#                                                                                                 "_": "E=td.hq.acc@gmail.com, SERIALNUMBER=200201014135, CN=TIAN DI TRADING SDN BHD, organizationIdentifier=C10915062070, O=TIAN DI TRADING SDN BHD, C=MY"
#                                                                                             }
#                                                                                         ],
#                                                                                         "X509IssuerSerial": [
#                                                                                             {
#                                                                                                 "X509IssuerName": [
#                                                                                                     {
#                                                                                                         "_": f"CN={issuer_name}, OU=Terms of use at http://www.posdigicert.com.my, O=LHDNM, C=MY"
#                                                                                                     }
#                                                                                                 ],
#                                                                                                 "X509SerialNumber": [
#                                                                                                     {
#                                                                                                         "_": serial_number
#                                                                                                     }
#                                                                                                 ],
#                                                                                             }
#                                                                                         ],
#                                                                                     }
#                                                                                 ]
#                                                                             }
#                                                                         ],
#                                                                         "SignatureValue": [
#                                                                             {
#                                                                                 "_": docdigest
#                                                                             }
#                                                                         ],
#                                                                         "SignedInfo": [
#                                                                             {
#                                                                                 "SignatureMethod": [
#                                                                                     {
#                                                                                         "_": "",
#                                                                                         "Algorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
#                                                                                     }
#                                                                                 ],
#                                                                                 "Reference": [
#                                                                                     {
#                                                                                         "Type": "http://uri.etsi.org/01903/v1.3.2#SignedProperties",
#                                                                                         "URI": "#id-xades-signed-props",
#                                                                                         "DigestMethod": [
#                                                                                             {
#                                                                                                 "_": "",
#                                                                                                 "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
#                                                                                             }
#                                                                                         ],
#                                                                                         "DigestValue": [
#                                                                                             {
#                                                                                                 "_": props_digest
#                                                                                             }
#                                                                                         ],
#                                                                                     },
#                                                                                     {
#                                                                                         "Type": "",
#                                                                                         "URI": "",
#                                                                                         "DigestMethod": [
#                                                                                             {
#                                                                                                 "_": "",
#                                                                                                 "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
#                                                                                             }
#                                                                                         ],
#                                                                                         "DigestValue": [
#                                                                                             {
#                                                                                                 "_": base64_hash
#                                                                                             }
#                                                                                         ],
#                                                                                     },
#                                                                                 ],
#                                                                             }
#                                                                         ],
#                                                                     }
#                                                                 ],
#                                                             }
#                                                         ]
#                                                     }
#                                                 ]
#                                             }
#                                         ],
#                                     }
#                                 ]
#                             }
#                         ],
#                         "Signature": [
#                             {
#                                 "ID": [
#                                     {
#                                         "_": "urn:oasis:names:specification:ubl:signature:Invoice"
#                                     }
#                                 ],
#                                 "SignatureMethod": [
#                                     {
#                                         "_": "urn:oasis:names:specification:ubl:dsig:enveloped:xades"
#                                     }
#                                 ],
#                             }
#                         ],
#                     }
#                 ],
#             }

#             run_test = document_info
#             info = document_info
#             json_content = json.dumps(document_info, indent=2).encode()
#             base64_document = base64.b64encode(json_content).decode("utf-8")
#             document_hash = hashlib.sha256(json_content).hexdigest()
#             invoice_data = {
#                 "format": "JSON",
#                 "document": base64_document,
#                 "documentHash": document_hash,
#                 "invoice_id": sales_invoice_doc.name,
#             }
#             # print(f"json_content {invoice_data}")
#             run = remove_signature_and_ublextensions(run_test)
#             base64_hash = run

#             return invoice_data, info, base64_hash, document_info
#         except Exception as e:
#             logger.exception("Error in build_document_info")
#             frappe.throw(f"Error in build_document_info: {str(e)}")

#     print("url", url)

#     @frappe.whitelist()
#     def send_einvoice(self, invoice_data):
#         try:
#             api_access_token = self.api_access_token
#             headers = {
#                 "Content-Type": "application/json",
#                 "User-Agent": "ERPNextPythonClient/1.0",
#                 "Accept": "application/json",
#                 "Accept-Encoding": "gzip, deflate, br",
#                 "Authorization": f"Bearer {api_access_token}",
#                 "Accept-Language": "en",
#             }
#             body = {
#                 "documents": [
#                     {
#                         "document": invoice_data["document"],
#                         "codeNumber": invoice_data["invoice_id"],
#                         "format": "JSON",
#                         "documentHash": invoice_data["documentHash"],
#                     }
#                 ]
#             }
#             api_credentials_doc = frappe.get_doc(
#                 "API Credentials", self.api_credentials
#             )

#             token, url = APICredentials.fetch_api_token(api_credentials_doc)
#             print("url", url)
#             send_api_base_url = url
#             send_document_url = f"{send_api_base_url}/api/v1.0/documentsubmissions"
#             response = requests.post(send_document_url, headers=headers, json=body)
#             self.response_content = response.json()
#             print(f"response_content: {response.status_code}")
#             self.handle_validation_errors()
#             # frappe.msgprint(f"Response content: {self.response_content}")
#             if response.status_code in [200, 202]:
#                 accepted_documents = self.response_content.get("acceptedDocuments", [])
#                 #  ms = accepted_documents[0].get('message')
#                 #  frappe.msgprint(f"message: {ms}")
#                 rejected_documents = self.response_content.get("rejectedDocuments", [])
#                 if accepted_documents:
#                     uuid = accepted_documents[0].get("uuid")
#                     invoice_code_number = accepted_documents[0].get("invoiceCodeNumber")
#                     return {
#                         "submissionUid": self.response_content.get("submissionUid"),
#                         "uuid": uuid,
#                         "invoiceCodeNumber": invoice_code_number,
#                     }
#                 elif rejected_documents:
#                     error_details = rejected_documents[0].get("error", {})
#                     error_message = error_details.get("message", "Unknown error")
#                     frappe.msgprint(
#                         f"Invoice submission failed. Reason: {error_message}"
#                     )
#                     return None
#                 else:
#                     error_message = "No accepted or rejected documents in the response."
#                     logger.error(error_message)
#                     frappe.throw(
#                         "No document summary returned from e-invoice service. Please check Error logs list for details."
#                     )
#             else:
#                 raise Exception(
#                     f"Request failed with status code {response.status_code}: Please check document validation"
#                 )
#         except Exception as e:
#             raise

#     # --------------------------------------------------------Validation Error-------------------------------
#     def handle_validation_errors(self, *args, **kwargs):
#         er = self.response_content
#         error = er.get("error", {})
#         details = error.get("details", [])

#         messages = ""
#         if details:
#             for item in details:
#                 messages += item.get("message") + "\n"
#             raise Exception(f"{messages}")

#     # ------------------------------------------------------------------------------------

#     def recursive_search(self, data, keys):
#         """Recursively searches for specific keys in a nested dictionary."""
#         if isinstance(data, dict):
#             extracted = {key: data[key] for key in keys if key in data}
#             if extracted:
#                 return extracted  # Stop searching once we find the keys
#             for value in data.values():
#                 result = self.recursive_search(value, keys)
#                 if result:
#                     return result
#         elif isinstance(data, list):
#             for item in data:
#                 result = self.recursive_search(item, keys)
#                 if result:
#                     return result
#         return None

#     def extract_target_and_signed_properties(self, data, output_path):
#         """Extracts Target and SignedProperties from a nested dictionary and saves to a specified path."""
#         try:
#             if not isinstance(data, dict):
#                 print("❌ Error: Expected a dictionary but got something else.")
#                 return None

#             extracted_data = self.recursive_search(data, ["Target", "SignedProperties"])

#             if not extracted_data:
#                 print("❌ Target and SignedProperties section not found.")
#                 return None

#             os.makedirs(output_path, exist_ok=True)

#             output_file = os.path.join(output_path, "signed_properties.json")

#             with open(output_file, "w", encoding="utf-8") as file:
#                 json.dump(extracted_data, file, indent=2)

#             print(f"✅ Extracted Target & SignedProperties saved to {output_file}")

#             return extracted_data

#         except Exception as e:
#             print(f"❌ Unexpected error: {e}")

#     def extract_property(self, json_data, property_path):
#         """Extracts a nested property from JSON using dot notation and handles lists properly."""
#         keys = property_path.split(".")
#         value = json_data

#         for key in keys:
#             if isinstance(value, list):
#                 try:
#                     key = int(key)
#                     value = value[key]
#                 except (ValueError, IndexError):
#                     raise KeyError(
#                         f"Property '{property_path}' not found in JSON (Invalid list index: {key})"
#                     )
#             else:
#                 value = value.get(key, None)

#             if value is None:
#                 raise KeyError(f"Property '{property_path}' not found in JSON")

#         return value

#     def minify_json(self, json_obj):
#         """Convert JSON object to a minified string"""
#         return json.dumps(json_obj, separators=(",", ":"))

#     def generate_sha256_base64(self, input_str):
#         """Generate SHA-256 hash and encode in Base64"""
#         sha256_hash = hashlib.sha256(input_str.encode("utf-8")).digest()
#         return base64.b64encode(sha256_hash).decode("utf-8")

#     # -----------------------------------------------QR Funcion ----------------------------------------------------------
#     def qr_code_img(self, qr_link):
#         qr = qrcode.QRCode(version=1, box_size=9, border=5)
#         qr.add_data(qr_link)
#         qr.make(fit=True)

#         img = qr.make_image(fill="black", back_color="white")
#         buffer = BytesIO()
#         img.save(buffer, format="PNG")
#         img_bytes = buffer.getvalue()
#         buffer.close()

#         return base64.b64encode(img_bytes)

#     def create_get_document_details_if_not_exists(self, sales_invoice_name):
#         """Check if submitted 'Get Document Details' exists. If not, create and submit it."""
#         qr_doc = frappe.get_all(
#             "Get Document Details",
#             filters={"sales_e_invoice": sales_invoice_name, "docstatus": 1},
#             fields=["name", "code"],
#             limit=1,
#         )

#         if qr_doc:
#             return frappe.get_doc("Get Document Details", qr_doc[0].name)

#         # Create and submit new doc
#         doc = frappe.get_doc(
#             {"doctype": "Get Document Details", "sales_e_invoice": sales_invoice_name}
#         )
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
#             frappe.msgprint(
#                 f"⚠️ {self.name} is not valid for QR generation. Please check."
#             )
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

#             file_doc = frappe.get_doc(
#                 {
#                     "doctype": "File",
#                     "file_name": filename,
#                     "is_private": 0,
#                     "content": base64.b64decode(img_str),
#                     "attached_to_doctype": "Sales E Invoice",
#                     "attached_to_name": self.name,
#                 }
#             )
#             file_doc.save(ignore_permissions=True)

#             # Step 5: Update document with QR file URL
#             self.validation_url = file_doc.file_url
#             self.save(ignore_permissions=True)

#             return {
#                 "qr_link": qr_link,
#                 "file_url": file_doc.file_url,
#                 "message": "✅ QR code generated and saved.",
#             }

#         except Exception as e:
#             frappe.throw(f"❌ Failed to generate or save QR code: {e}")


# # ---------------------------------------------------------------------------------------------------------------


# @frappe.whitelist()
# def make_sales_e_invoice(source_name, target_doc=None, ignore_permissions=False):

#     def set_missing_values(source, target):
#         target.flags.ignore_permissions = ignore_permissions
#         target.run_method("set_missing_values")
#         target.run_method("calculate_taxes_and_totals")
#         target.other_charges_calculation = source.other_charges_calculation

#         # Get target as a dictionary
#         data = target.as_dict()
#         non_empty_data = {k: v for k, v in data.items() if v not in [None, "", 0, []]}

#     try:
#         doclist = get_mapped_doc(
#             "Sales Invoice",
#             source_name,
#             {
#                 "Sales Invoice": {
#                     "doctype": "Sales E Invoice",
#                     "validation": {"docstatus": ["=", 1]},
#                 },
#                 "Sales Invoice Item": {
#                     "doctype": "Sales Invoice Item",
#                     "field_map": {
#                         "name": "si_detail",
#                         "parent": "sales_invoice",
#                     },
#                     "condition": lambda doc: doc.qty > 0,
#                 },
#                 "Sales Taxes and Charges": {
#                     "doctype": "Sales Taxes and Charges",
#                     "reset_value": True,
#                 },
#                 "Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
#             },
#             target_doc,
#             set_missing_values,
#             ignore_permissions=ignore_permissions,
#         )
#         print(
#             "Mapping successful. New Sales E Invoice created with name (ID):",
#             doclist.name,
#         )
#         return doclist
#     except Exception as e:
#         print("Error in make_sales_e_invoice:", e)
#         frappe.throw("An error occurred while creating Sales E Invoice: {}".format(e))
