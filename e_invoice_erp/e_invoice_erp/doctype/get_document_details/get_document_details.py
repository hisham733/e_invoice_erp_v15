# Copyright (c) 2024, Alharazi_hisham and contributors
# For license information, please see license.txt
import pdb
import frappe
from frappe.model.document import Document
import requests
import json
from datetime import datetime
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import APICredentials
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import (
    get_access_token_for_credential,
)
import base64
from io import BytesIO
import qrcode
from PIL import Image
class GetDocumentDetails(Document):
	
    
    def before_save(self):
        if not self.api_credentials or not self.uuid:
            frappe.throw("Please select API Credentials before saving.")
        
        token = get_access_token_for_credential(self.api_credentials)
        if token:
            self.api_access_token = token  # Set the fetched token in the api_access_token field
        else:
            frappe.throw("Failed to fetch the API token.")
    def before_submit(self):
        # pdb.set_trace()
        
        uuid = self.uuid
        response_data = self.get_document_details(uuid, self.api_access_token)
        if response_data:
            try:
                # Save the raw response JSON in the `code` field
                self.code = json.dumps(response_data, indent=4)
                # frappe.msgprint(f"Document details fetched and saved for UUID: {uuid}")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error Saving Document Details")
                frappe.throw(f"Error while saving document details: {str(e)}")
        else:
            frappe.throw("No data returned from the e-invoice service. Please check logs for details.")
        self.show_validation_errors()
    


    @frappe.whitelist()      
    def resubmit(self):  
        self.before_submit()  
        return self.code,self.validation_url 


    @frappe.whitelist()
    def generate_invoice_qr(self):
        try:
            # Fetch document
            doc = frappe.get_doc("Get Document Details", self.name)

            # Ensure code field has JSON string with uuid and longId
            if not doc.code:
                frappe.throw("Field 'code' is empty.")

            try:
                code_data = json.loads(doc.code)
                uuid = code_data.get("uuid")
                long_id = code_data.get("longId")
            except Exception as e:
                frappe.throw(f"Invalid JSON in 'code': {str(e)}")

            if not uuid or not long_id:
                frappe.throw("Missing 'uuid' or 'longId' in code field.")

            # Construct the invoice link
            invoice_link = f"https://myinvois.hasil.gov.my/{uuid}/share/{long_id}"

            # Generate QR image
            img_str = self.qr_code_img(invoice_link)

            # Save QR image to File
            filename = f"QR_{uuid}.png"
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "is_private": 0,
                "content": base64.b64decode(img_str),
                "attached_to_doctype": "Get Document Details",
                "attached_to_name": self.name
            })
            file_doc.save(ignore_permissions=True)

            # Save the file URL back to the document
            doc.validation_url = file_doc.file_url
            doc.save(ignore_permissions=True)

            return {
                "file_url": file_doc.file_url,
                "message": "QR code successfully generated and saved."
            }

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "QR Code Generation Failed")
            frappe.throw(f"QR Code generation failed: {str(e)}")


    def qr_code_img(self,full_url):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=4,
            border=4
        )
        qr.add_data(full_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        buffered.seek(0)
        img_str = base64.b64encode(buffered.read())

        return img_str



    def get_document_details(self,uuid, api_access_token):
        # pdb.set_trace()
        """
        Fetch document details from the Get Document Details API
        :param uuid: The UUID of the document
        :param api_access_token: The access token for authentication
        :return: JSON response from the API
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_access_token}",
                "Accept": "application/json"
            }
            cred_doc = frappe.get_doc("API Credentials", self.api_credentials)
            api_base_url = "https://preprod-api.myinvois.hasil.gov.my"
            if cred_doc.environment == "PROD":
                api_base_url = "https://api.myinvois.hasil.gov.my"

            get_document_details_url = f"{api_base_url}/api/v1.0/documents/{uuid}/details"
            print(get_document_details_url)

            # Make the GET request
            response = requests.get(get_document_details_url, headers=headers)

            if response.status_code == 200:
                # Parse and return the JSON response
                return response.json()
            else:
                frappe.log_error(f"Failed to fetch document details for UUID {uuid}. Status Code: {response.status_code}, Error: {response.text}")
                return None

        except Exception as e:
            frappe.log_error(f"Error fetching document details for UUID {uuid}: {str(e)}", "E-Invoice API Error")
            return None


    def parse_datetime(datetime_str):
        """
        Helper function to parse and format datetime strings.
        """
        if datetime_str:
            try:
                dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError as e:
                frappe.log_error(f"Error parsing datetime: {e}")
        return None


    def show_validation_errors(self):
        if self.code:
            response_data = json.loads(self.code)
            if response_data.get("status") == "Invalid":
                validation_steps = response_data.get("validationResults", {}).get("validationSteps", [])
                
                for step in validation_steps:
                    if step.get("status") == "Invalid" and step.get("error"):
                        error = step["error"]
                        
                        # Top-level error message
                        # if error.get("error"):
                        #     frappe.msgprint(error["error"])

                        # Loop through inner errors
                        inner_errors = error.get("innerError", [])
                        for inner in inner_errors:
                            if inner.get("error"):
                                frappe.msgprint(f"❌ Error: {inner['error']}")


