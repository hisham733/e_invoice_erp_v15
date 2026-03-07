import json
import frappe
import os
import hashlib
import base64
from e_invoice_erp.e_invoice_erp.doctype.api_credentials.api_credentials import APICredentials  
@frappe.whitelist()
def remove_signature_and_ublextensions(document_info):
    try:
        # Ensure we are working on a copy
        modified_document_info = json.loads(json.dumps(document_info))  # Deep copy

        # Define keys to remove
        keys_to_remove = {"UBLExtensions", "Signature"}

        # Remove unwanted keys using remove_keys function
        cleaned_data = remove_keys(modified_document_info, keys_to_remove)

        # Define correct file path
        file_path = "home/frappe/frappe-bench/apps/e_invoice_erp/e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/out_invoice.json"
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Convert cleaned JSON to string (ensuring consistent formatting)
        cleaned_json_str = json.dumps(cleaned_data, separators=(",", ":"), ensure_ascii=False)

        # Compute SHA-256 hash
        sha256_hash = hashlib.sha256(cleaned_json_str.encode("utf-8")).digest()

        # Encode hash in Base64
        base64_hash = base64.b64encode(sha256_hash).decode("utf-8")

        # Save the cleaned JSON to a new file
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(cleaned_data, json_file, indent=2, ensure_ascii=False)

        # Print and return the Base64-encoded hash
        print(f"✅ Base64 SHA-256 Hash: {base64_hash}")
        return base64_hash

    except Exception as e:
        frappe.throw(f"❌ Error in remove_signature_and_ublextensions: {str(e)}")

# Function to recursively remove specific keys
def remove_keys(obj, keys_to_remove):
    """Recursively removes specified keys from a dictionary or list."""
    if isinstance(obj, dict):
        return {k: remove_keys(v, keys_to_remove) for k, v in obj.items() if k not in keys_to_remove}
    elif isinstance(obj, list):
        return [remove_keys(item, keys_to_remove) for item in obj]
    else:
        return obj


from datetime import datetime

def get_utc_timestamp():
    utc_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Current Sign UTC Timestamp: {utc_timestamp}")
    return utc_timestamp
zone_time = get_utc_timestamp()