# import requests
# import frappe
# from frappe import _
# from myinvois_erpgulf.myinvois_erpgulf.taxpayerlogin import get_access_token
# from urllib.parse import quote
# from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
#     APICredentials,
# )


# @frappe.whitelist(allow_guest=True)
# def search_company_tin(company_name):
#     company = frappe.get_doc("Company", company_name)
#     company_abbr = company.abbr
#     api_credential = company.custom_api_credentials
#     print(f"company.docstatus: {company.docstatus}")
#     if not api_credential:
#         frappe.throw("Please select API Credentials before saving.")
#     id_type = (
#         company.custom_company_registrationicpassport_type
#         or company.custom_company_registration_for_self_einvoicing
#     )
#     id_value = company.custom_company__registrationicpassport_number
#     taxpayer_name = company.custom_taxpayer_name

#     # Determine API endpoint and construct query URL
#     if id_type and id_value:
#         endpoint = f"api/v1.0/taxpayer/search/tin?idType={quote(id_type)}&idValue={quote(id_value)}"
#     elif taxpayer_name:
#         endpoint = f"api/v1.0/taxpayer/search/tin?taxpayerName={quote(taxpayer_name)}"
#     else:
#         frappe.throw(
#             _(
#                 "As per LHDN Regulations,Either ID Type and Value or Taxpayer Name must be present in the Company document."
#             )
#         )
#     api_credentials_doc = frappe.get_doc("API Credentials", api_credential)
#     print(f"Fetched API Credentials: {api_credentials_doc}")

#     # Ensure client_id and client_secret are available
#     if not api_credentials_doc.client_id or not api_credentials_doc.client_secret:
#         frappe.throw(
#                 "Client ID or Client Secret is missing in the selected API Credentials."
#             )

#         # Generate the API token by calling the fetch_api_token method
#     token, url = APICredentials.fetch_api_token(api_credentials_doc)
#     if not token:
#         frappe.throw("Failed to fetch the API token.")

#     try:
#         # Ensure the access token is passed correctly
#         headers = {
#                 "Content-Type": "application/json",
#                 "User-Agent": "ERPNextPythonClient/1.0",
#                 "Accept": "*/*",
#                 "Accept-Encoding": "gzip, deflate, br",
#                 "Authorization": f"Bearer {token}",
#                 "Accept": "application/json",
#                 "Accept-Language": "en",
#             }
#         if not url:
#             frappe.throw("Failed to fetch the API token.")

#         send_api_base_url = url
#         get_document_url = f"{send_api_base_url}/{endpoint}"

#         # Making the API request
#         response = requests.get(get_document_url, headers=headers, timeout=10)
#         frappe.msgprint(f"Response body: {response.text}")

#         if response.status_code != 200:
#             frappe.throw(_("API request failed: {0}").format(response.text))
#         try:
#             data = response.json()
#         except ValueError:
#             frappe.throw(_("Failed to parse API response."))
#         # Extract TIN
#         tin = data.get("tin") or data.get("data", {}).get("tin")
#         if not tin:
#             frappe.throw(_("TIN not found in API response."))

#         # Save TIN to Company doc
#         company.custom_company_tin_number = tin
#         company.save()
#         return data
#     except Exception as e:
#         print(f"Error occurred: {e}")
#         frappe.log_error(message=str(e), title="E-Invoice API Error")
#         return None         


# # @frappe.whitelist()
# # def update_lhdn_status_on_invoice(invoice_name):
# #     status = None

# #     sei = frappe.get_all(
# #         "Sales E Invoice",
# #         filters={"sales_invoice": invoice_name},
# #         fields=["name", "custom_lhdn_e_invoice_status"],
# #         limit=1
# #     )

# #     if sei:
# #         status = sei[0]["custom_lhdn_e_invoice_status"] or "Linked (SEI)"
# #     else:
# #         entry = frappe.get_value("Consolidated Invoice Entry", {"original_invoice": invoice_name}, "parent")
# #         if entry:
# #             status = frappe.db.get_value("Consolidated E Invoice", entry, "custom_lhdn_e_invoice_status") or "Linked (CEI)"
# #         else:
# #             status = ""  # 👉 return empty if not linked

# #     frappe.db.set_value("Sales Invoice", invoice_name, "custom_lhdn_status", status)
# #     return status
