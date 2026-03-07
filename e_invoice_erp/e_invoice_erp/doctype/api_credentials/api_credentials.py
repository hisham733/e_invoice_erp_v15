
import hashlib
import os
import base64
from datetime import datetime, timedelta
from cryptography.hazmat.backends import default_backend
import frappe
import pytz
import requests
from frappe.model.document import Document
from frappe.utils import now_datetime
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
from cryptography.x509.oid import NameOID, ObjectIdentifier

# --- Constants ---
LHDN_API_URLS = {
    "SANDBOX": "https://preprod-api.myinvois.hasil.gov.my",
    "PROD": "https://api.myinvois.hasil.gov.my",
}
# Safety buffer to request a new token before the old one actually expires
TOKEN_EXPIRATION_BUFFER = timedelta(minutes=5)

class APICredentials(Document):
    """Manages API credentials, token fetching, and digital certificate details for LHDN e-Invoicing."""

    # --- Document Events ---

    def on_update(self):
        """
        After saving, automatically fetch an API token if credentials are new or have changed.
        This provides initial validation for the user.
        """
        if self.is_new() or self.has_value_changed("client_id") or self.has_value_changed("client_secret"):
            frappe.msgprint("New or updated credentials saved. Attempting to fetch initial API token...")
            try:
                # Call the internal logic to fetch and save the token
                self._fetch_and_save_token()
                frappe.msgprint("✅ Initial API token fetched and saved successfully.", indicator="green", title="Success")
                # Reload the form to show the new token data
                frappe.local.flags.commit = True # Ensure the save is committed before reload
                frappe.publish_realtime("form_refresh", {"doctype": self.doctype, "docname": self.name})
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "Initial Token Fetch Failed")
                frappe.throw(f"Credentials saved, but failed to fetch initial API token. Please check credentials and try again manually. Error: {e}", title="API Token Error")


    # --- The Core Logic: The Smart Token Manager ---

    def get_valid_token(self) -> str:
        """
        The main "smart" function.
        Returns a valid access token, fetching a new one only if the current one is missing or expired.
        This is the primary method that should be used by other server scripts.
        """
        # Check if the current token is still valid (with a buffer)
        if not self.token:
            print("no token")
        if self.token and self.token_expiration:
            # Ensure token_expiration is a datetime object
            token_expiration_dt = frappe.utils.get_datetime(self.token_expiration)
            if token_expiration_dt > (now_datetime() + TOKEN_EXPIRATION_BUFFER):
                # Token is still valid, return it.
                return self.token

        # If we reach here, the token is missing, invalid, or expired.
        # Fetch a new one.
        return self._fetch_and_save_token()

    def _fetch_and_save_token(self) -> str:
        """
        Private helper that contains the actual API call logic.
        It fetches, saves the token to the DB, and returns it.
        """
        if not self.client_id or not self.get_password("client_secret"):
            raise ValueError("Client ID and Client Secret must be set.")

        api_base_url = LHDN_API_URLS.get(self.environment, LHDN_API_URLS["PROD"])
        token_url = f"{api_base_url}/connect/token"

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "client_id": self.client_id,
            "client_secret": self.get_password("client_secret"),
            "grant_type": "client_credentials",
            "scope": "InvoicingAPI",
        }

        try:
            response = requests.post(token_url, headers=headers, data=payload, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            frappe.log_error(frappe.get_traceback(), "API Token Fetch")
            raise ConnectionError(f"API Connection Error: {e}") from e

        token_data = response.json()
        access_token = token_data.get("access_token")
        print(f"access_token: {access_token}")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("API did not return an access token.")

        # Calculate expiration in local server timezone
        expiration_time = now_datetime() + timedelta(seconds=expires_in)

        # Use db_set to save immediately and avoid triggering hooks again
        self.db_set("token", access_token)
        self.db_set("token_expiration", expiration_time)
        
        # This commit is crucial so that subsequent calls in the same request get the new value
        frappe.db.commit()

        return access_token
    @frappe.whitelist()
    def get_cert_info(self):
        try:
            if not self.cert:
                frappe.throw("Certificate file path is missing in API credentials.")

            P12_FILE_PATH = frappe.utils.get_site_path(self.cert.lstrip("/"))

            if not os.path.exists(P12_FILE_PATH):
                frappe.throw(f"Certificate file not found at: {P12_FILE_PATH}")

            if not self.cert_password:
                frappe.throw("Certificate password is missing in API credentials.")

            P12_PASSWORD = self.get_password("cert_password").encode()
            # P12_PASSWORD = self.cert_password.encode()
            print(P12_PASSWORD)

            try:
                with open(P12_FILE_PATH, "rb") as p12_file:
                    p12_data = p12_file.read()

                private_key, certificate, additional_certs = (
                    pkcs12.load_key_and_certificates(
                        p12_data, P12_PASSWORD, default_backend()
                    )
                )
            except ValueError:
                frappe.throw(
                    "Incorrect certificate password or invalid .p12 file format."
                )
            except Exception as e:
                frappe.throw(f"Error loading .p12 file: {str(e)}")

            if not certificate:
                frappe.throw("No certificate found in the .p12 file.")

            cert_der = certificate.public_bytes(Encoding.DER)
            cert_hash = hashlib.sha256(cert_der).digest()
            cert_hash_base64 = base64.b64encode(cert_hash).decode("utf-8")
            cert_base64 = base64.b64encode(cert_der).decode("utf-8")

            full_issuer_name = certificate.issuer.rfc4514_string()
            print(f"full_issuer_name: {full_issuer_name}")
            serial_number = certificate.serial_number
            # subject_name = certificate.subject.rfc4514_string()

            issuer_cn = ""
            for part in full_issuer_name.split(","):
                if part.strip().startswith("CN="):
                    issuer_cn = part.strip().replace("CN=", "")
                    break

            if not issuer_cn:
                frappe.throw("Failed to extract Issuer CN from certificate.")

            from cryptography.x509.oid import NameOID

            subject = certificate.subject

            email = subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)[0].value
            subject_serial_number = subject.get_attributes_for_oid(
                NameOID.SERIAL_NUMBER
            )[0].value
            common_name = subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            organization = subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[
                0
            ].value
            country = subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value

            # organizationIdentifier (OID 2.5.4.97) is not included in NameOID, so use ObjectIdentifier manually:
            from cryptography.x509.oid import ObjectIdentifier

            org_id_oid = ObjectIdentifier("2.5.4.97")
            organization_identifier = subject.get_attributes_for_oid(org_id_oid)[
                0
            ].value

            # Combine as string
            subject_name_string = f"E={email}, SERIALNUMBER={subject_serial_number}, CN={common_name}, organizationIdentifier={organization_identifier}, O={organization}, C={country}"

            print(f"----------{type(subject_name_string)}---")

            return (
                cert_base64,
                issuer_cn,
                serial_number,
                cert_hash_base64,
                subject_name_string,
            )

        except frappe.ValidationError as e:
            frappe.throw(f"Validation Error: {str(e)}")
        except FileNotFoundError as e:
            frappe.throw(f"File Not Found: {str(e)}")
        except Exception as e:
            frappe.throw(f"Error in get_cert_info: {str(e)}")

@frappe.whitelist()
def get_access_token_for_credential(credential_name: str) -> str:
    """
    Public-facing function to get a valid access token for a specific credential document.

    :param credential_name: The name (ID) of the API Credentials document to use.
    :return: A valid access token.
    """
    if not credential_name:
        frappe.throw("Credential Name must be provided to get an access token.")

    try:
        doc = frappe.get_doc("API Credentials", credential_name)
        return doc.get_valid_token()
    except frappe.DoesNotExistError:
        frappe.throw(f"API Credentials document '{credential_name}' not found.")
    except Exception as e:
        # Catch errors from get_valid_token (e.g., ConnectionError) and re-throw
        frappe.throw(f"Failed to get access token for '{credential_name}'. Error: {e}")