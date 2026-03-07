# -*- coding: utf-8 -*-
# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import frappe
from frappe.model.document import Document
import requests
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import APICredentials

token =""
url=""
class GetDocumentInfo(Document):

    def on_update(self):
        uuid = self.submission_uid
        print("submission_uid:", uuid)

    def before_save(self):
        if not self.api_credentials:
            frappe.throw("Please select API Credentials before saving.")
        
        # Fetch the API Credentials document
        api_credentials_doc = frappe.get_doc("API Credentials", self.api_credentials)
        print(f"Fetched API Credentials: {api_credentials_doc}")

        # Ensure client_id and client_secret are available
        if not api_credentials_doc.client_id or not api_credentials_doc.client_secret:
            frappe.throw("Client ID or Client Secret is missing in the selected API Credentials.")
        
        # Generate the API token by calling the fetch_api_token method
        token,_ = APICredentials.fetch_api_token(api_credentials_doc)
        if token:
            # Set the fetched token in the api_access_token field
            self.api_access_token = token  # Ensure this matches the actual fieldname
            # frappe.msgprint(f"API Token fetched and saved successfully.")
        else:
            frappe.throw("Failed to fetch the API token.")

    def on_submit(self):
        uuid = self.submission_uid
        print("submission_uid:", self.submission_uid)
        
        response_data = self.get_document_status(uuid, self.api_access_token)
        
        if response_data:
            try:
                # Store the data from response
                self.overall_status = response_data.get("overallStatus")
                self.document_count = response_data.get('documentCount')
                self.date_time_received = self.parse_datetime(response_data.get('dateTimeReceived'))
                
                document_summary = response_data.get('documentSummary', [])[0]
                self.uuid = document_summary.get('uuid')
                self.submission_uid_summary = document_summary.get('submissionUid')
                self.long_id = document_summary.get('longId')
                self.internal_id = document_summary.get('internalId')
                self.type_name = document_summary.get('typeName')
                self.type_version_name = document_summary.get('typeVersionName')
                self.issuer_tin = document_summary.get('issuerTin')
                self.issuer_name = document_summary.get('issuerName')
                self.receiver_id = document_summary.get('receiverId')
                self.receiver_name = document_summary.get('receiverName')
                self.date_time_issued = self.parse_datetime(document_summary.get('dateTimeIssued'))
                self.date_time_received_summary = self.parse_datetime(document_summary.get('dateTimeReceived'))
                self.date_time_validated = self.parse_datetime(document_summary.get('dateTimeValidated'))
                self.total_payable_amount = document_summary.get('totalPayableAmount')
                self.total_excluding_tax = document_summary.get('totalExcludingTax')
                self.total_discount = document_summary.get('totalDiscount')
                self.total_net_amount = document_summary.get('totalNetAmount')
                self.status = document_summary.get('status')
                self.cancel_date_time = self.parse_datetime(document_summary.get('cancelDateTime'))
                self.reject_request_date_time = self.parse_datetime(document_summary.get('rejectRequestDateTime'))
                self.document_status_reason = document_summary.get('documentStatusReason')
                self.created_by_user_id = document_summary.get('createdByUserId')

            except Exception as e:
                frappe.log_error(message=str(e), title="E-Invoice Response Error")
        else:
            frappe.throw("No data returned from e-invoice service. Please check logs for details.")

    def get_document_status(self,uuid, api_access_token):
        try:
            # Ensure the access token is passed correctly
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ERPNextPythonClient/1.0",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Authorization": f"Bearer {api_access_token}",
                "Accept": "application/json",
                "Accept-Language": "en",
            }
            api_credentials_doc = frappe.get_doc("API Credentials", self.api_credentials)

            _,url = APICredentials.fetch_api_token(api_credentials_doc)
           
            send_api_base_url=url
            get_document_url = f"{send_api_base_url}/api/v1.0/documentsubmissions/{uuid}"

            # Making the API request
            response = requests.get(get_document_url, headers=headers)

            # Log and print for debugging
            print(f"API Request URL: {get_document_url}")
            print(f"API Response Status Code: {response.status_code}")
            print(f"API Response Content: {response.text}")

            if response.status_code == 200:
                response_data = response.json()
                if not response_data:
                    raise Exception("Empty response from e-invoice service.")
                
                return response_data
            else:
                raise Exception(f"Request failed with status code {response.status_code}\n{response.text}")

        except Exception as e:
            print(f"Error occurred: {e}")
            frappe.log_error(message=str(e), title="E-Invoice API Error")
            return None  # Ensure function returns None on failure


    def parse_datetime(datetime_str):
        if datetime_str:
            try:
                # Parse ISO format datetime string to datetime object
                dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")
                # Format datetime object as ERPNext datetime string
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError as e:
                print(f"Error parsing datetime: {e}")
        return None