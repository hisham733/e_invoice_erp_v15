# Copyright (c) 2025, Alharazi_hisham and contributors
# For license information, please see license.txt
import logging
import pdb
import base64
import hashlib
import json
import re


# from frappe.api import utils
import pytz
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import frappe
from frappe.model.document import Document

from e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.remove_ubl import (
    remove_signature_and_ublextensions_consolidated,
)
import base64


class build_invoice:
    @frappe.whitelist()
    def get_sales_invoice_details_tax(self, sales_invoice_doc):
        try:
            TaxCategory = sales_invoice_doc.tax_category
            if TaxCategory and ":" in TaxCategory:
                # Extract just the numeric part before the colon
                TaxCategory = TaxCategory.split(":", 1)[0].strip()
            else:
                # If the format is unexpected, assign the original value as a fallback
                TaxCategory = sales_invoice_doc.tax_category

            tax_category = str(TaxCategory).strip()            # tax = sales_invoice_doc.taxes
            # print(f"tax: {tax}")
            # if not tax or len(tax) > 1:
            #     frappe.throw(
            #         f"No tax table found for Sales Invoice or Tax More Then One {sales_invoice_doc.name}"
            #     )

            # total_tax_amount = 0.0
            # total_tax_percent = 0.0
            # for row in tax:

            #     print({row})
            #     total_tax_amount = row.tax_amount
            #     print(f"total_tax_amount:{total_tax_amount}")

            #     total_tax_percent = row.rate
            #     print(f"✔ tax_percent: {total_tax_percent}")
            # ✅ Only one tax_subtotal now
            tax_subtotals = []

            tax_subtotal_dict = {
                "TaxableAmount": [
                    {"_": round(sales_invoice_doc.total, 2), "currencyID": "MYR"}
                ],
                "TaxAmount": [
                    {"_": round(sales_invoice_doc.total_taxes_and_charges, 2), "currencyID": "MYR"}
                ],
                "TaxCategory": [
                    {
                        "ID": [{"_": tax_category}],
                        "TaxScheme": [
                            {
                                "ID": [
                                    {
                                        "_": "OTH",
                                        "schemeID": "UN/ECE 5153",
                                        "schemeAgencyID": "6",
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }

            tax_subtotals.append(tax_subtotal_dict)
            return tax_subtotals, tax_category

        except Exception as e:
            frappe.throw(f"❌ Error in get_sales_invoice_details: {e}")

    def get_sales_invoice_details_items_info(self, invoice):
        try:
            item_prices = []
            for index, item in enumerate(invoice.invoices):
                tax_subtotals, tax_category = (
                    self.get_sales_invoice_details_tax(invoice)
                )
                print(tax_subtotals)
                item_tax_subtotal = (
                    tax_subtotals[index] if index < len(tax_subtotals) else {}
                )
                print(item_tax_subtotal)
                description = item.original_invoice
                net_amount = item.total
                tax_rate = item.tax_rate
                total_taxes = item.total_taxes
                total_additional = item.total_additional


                # total_amount_before_discount = item.total_amount_before_discount

                invoice_item = {
                    "ID": [{"_": str(index + 1)}],
                    "InvoicedQuantity": [{"_": 1, "unitCode": "XUN"}],
                    "LineExtensionAmount": (
                        [{"_": total_additional or 0.0, "currencyID": "MYR"}]
                    ),
                    "TaxTotal": [
                        {
                            "TaxAmount": [
                                {
                                    "_": total_taxes,
                                    "currencyID": "MYR",
                                }
                            ],
                            "TaxSubtotal": [
                                {
                                    "TaxableAmount": [
                                        {"_": net_amount, "currencyID": "MYR"}
                                    ],
                                    "TaxAmount": [
                                        {
                                            "_": total_taxes,
                                            "currencyID": "MYR",
                                        }
                                    ],
                                    "TaxCategory": [
                                        {
                                            "ID": [{"_": tax_category}],
                                            "Percent": ([{"_": tax_rate}]),
                                            "TaxScheme": [
                                                {
                                                    "ID": [
                                                        {
                                                            "_": "OTH",
                                                            "schemeID": "UN/ECE 5153",
                                                            "schemeAgencyID": "6",
                                                        }
                                                    ]
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                    "Item": [
                        {
                            "CommodityClassification": (
                                [
                                    {
                                        "ItemClassificationCode": [
                                            {
                                                "_": "004",
                                                "listID": "CLASS",
                                            }
                                        ]
                                    }
                                ]
                            ),
                            "Description": [{"_": description}] if description else [],
                        }
                    ],
                    "Price": (
                        [{"PriceAmount": [{"_": net_amount or 0.0, "currencyID": "MYR"}]}]
                    ),
                    "ItemPriceExtension": [
                        {"Amount": [{"_": net_amount or 0.0, "currencyID": "MYR"}]}
                    ],
                }
                item_prices.append(invoice_item)

                print(f"and item_prices: {item_prices}")
            return tax_subtotals, tax_category, item_prices

        except Exception as e:
            print(f"Error in get_sales_invoice_details: {str(e)}")
            return []

    def fix_time_format(self, sales_invoice_doc):
        try:
            posting_date = sales_invoice_doc.posting_date
            posting_time = sales_invoice_doc.posting_time
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")
            if isinstance(posting_time, str):
                hours, minutes, seconds = map(int, posting_time.split(":"))
                posting_time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            posting_time_str = (
                (datetime.min + posting_time).time().strftime("%H:%M:%S")
                if isinstance(posting_time, timedelta)
                else posting_time.strftime("%H:%M:%S")
            )
            combined_datetime = datetime.combine(
                posting_date, datetime.strptime(posting_time_str, "%H:%M:%S").time()
            )
            local_timezone = pytz.timezone("Asia/Kuala_Lumpur")
            local_datetime = local_timezone.localize(combined_datetime, is_dst=None)
            utc_datetime = local_datetime.astimezone(pytz.utc)
            formatted_posting_date = utc_datetime.strftime("%Y-%m-%d")
            formatted_issue_time = utc_datetime.strftime("%H:%M:%SZ")
            return formatted_posting_date, formatted_issue_time
        except Exception as e:
            print(f"Error in fix_time_format: {str(e)}")
            return None

    def get_utc_timestamp(self):
        utc_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return utc_timestamp

    def build_document_info(
        self,
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
    ):
        try:
            document_info = {
                "_D": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
                "_A": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
                "_B": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
                "Invoice": [
                    {
                        "ID": [{"_": sales_invoice_doc.name}],
                        "IssueDate": [{"_": formatted_posting_date}],
                        "IssueTime": [{"_": formatted_issue_time}],
                        "InvoiceTypeCode": [{"_": "01", "listVersionID": "1.1"}],
                        "DocumentCurrencyCode": [{"_": "MYR"}],
                        "TaxCurrencyCode": [{"_": "MYR"}],
                        "AccountingSupplierParty": [
                            {
                                "Party": [
                                    {
                                        "IndustryClassificationCode": [
                                            {
                                                "_": sales_invoice_doc.msic_codes,
                                                "name": sales_invoice_doc.company,
                                            }
                                        ],
                                        "PartyIdentification": [
                                            {
                                                "ID": [
                                                    {
                                                        "_": sales_invoice_doc.supplier_tin,
                                                        "schemeID": "TIN",
                                                    }
                                                ]
                                            },
                                            {
                                                "ID": [
                                                    {
                                                        "_": sales_invoice_doc.supplier_brn,
                                                        "schemeID": "BRN",
                                                    }
                                                ]
                                            },
                                            {
                                                "ID": [
                                                    {
                                                        "_": "NA",
                                                        "schemeID": "SST",
                                                    }
                                                ]
                                            },
                                        ],
                                        "PostalAddress": [
                                            {
                                                "CityName": [
                                                    {
                                                        "_": sales_invoice_doc.supplier_city
                                                    }
                                                ],
                                                "PostalZone": [
                                                    {
                                                        "_": sales_invoice_doc.supplier_postal_code
                                                    }
                                                ],
                                                "CountrySubentityCode": [
                                                    {
                                                        "_": sales_invoice_doc.supplier_state_codes
                                                    }
                                                ],
                                                "AddressLine": [
                                                    {
                                                        "Line": [
                                                            {
                                                                "_": sales_invoice_doc.supplier_location
                                                            }
                                                        ]
                                                    }
                                                ],
                                                "Country": [
                                                    {
                                                        "IdentificationCode": [
                                                            {
                                                                "_": "MYS",
                                                                "listID": "ISO3166-1",
                                                                "listAgencyID": "6",
                                                            }
                                                        ]
                                                    }
                                                ],
                                            }
                                        ],
                                        "PartyLegalEntity": [
                                            {
                                                "RegistrationName": [
                                                    {
                                                        "_": sales_invoice_doc.registration_name
                                                    }
                                                ]
                                            }
                                        ],
                                        "Contact": [
                                            {
                                                "Telephone": [
                                                    {
                                                        "_": sales_invoice_doc.suplier_mobile
                                                    }
                                                ],
                                                "ElectronicMail": [
                                                    {
                                                        "_": sales_invoice_doc.supplier_email_address
                                                    }
                                                ],
                                            }
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
                                                "CityName": [{"_": ""}],
                                                "PostalZone": [{"_": ""}],
                                                "CountrySubentityCode": [{"_": ""}],
                                                "AddressLine": [
                                                    {"Line": [{"_": "NA"}]}
                                                ],
                                                "Country": [
                                                    {
                                                        "IdentificationCode": [
                                                            {
                                                                "_": "MYS",
                                                                "listID": "ISO3166-1",
                                                                "listAgencyID": "6",
                                                            }
                                                        ]
                                                    }
                                                ],
                                            }
                                        ],
                                        "PartyLegalEntity": [
                                            {
                                                "RegistrationName": [
                                                    {
                                                        "_": sales_invoice_doc.customer_name
                                                    }
                                                ]
                                            }
                                        ],
                                        "PartyIdentification": [
                                            {
                                                "ID": [
                                                    {
                                                        "_": "EI00000000010",
                                                        "schemeID": "TIN",
                                                    }
                                                ]
                                            },
                                            {
                                                "ID": [
                                                    {
                                                        "_": "NA",
                                                        "schemeID": "NRIC",
                                                    }
                                                ]
                                            },
                                        ],
                                        "Contact": [
                                            {
                                                "Telephone": [{"_": "NA"}],
                                                "ElectronicMail": [{"_": "NA"}],
                                            }
                                        ],
                                    }
                                ]
                            }
                        ],
                        "TaxTotal": [
                            {
                                "TaxAmount": [
                                    {
                                        "_": sales_invoice_doc.total_taxes_and_charges,
                                        "currencyID": "MYR",
                                    }
                                ],
                                "TaxSubtotal": tax_subtotals,
                            }
                        ],
                        "LegalMonetaryTotal": [
                            {
                                "ChargeTotalAmount": [
                                    {
                                        "_": sales_invoice_doc.total_charge,
                                        "currencyID": "MYR",
                                    }
                                ],
                                "TaxExclusiveAmount": [
                                    {
                                        "_": sales_invoice_doc.total_charge + sales_invoice_doc.total,
                                        "currencyID": "MYR",
                                    }
                                ],
                                "TaxInclusiveAmount": [
                                    {
                                        "_": sales_invoice_doc.grand_total,
                                        "currencyID": "MYR",
                                    }
                                ],
                                "PayableAmount": [
                                    {
                                        "_": sales_invoice_doc.grand_total,
                                        "currencyID": "MYR",
                                    }
                                ],
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
                                                                                                                                ],
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
                                                                                                                                ],
                                                                                                                            }
                                                                                                                        ],
                                                                                                                    }
                                                                                                                ]
                                                                                                            }
                                                                                                        ],
                                                                                                    }
                                                                                                ],
                                                                                            }
                                                                                        ],
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
                                                                                                "_": subject_name_string
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
                                                                                                ],
                                                                                            }
                                                                                        ],
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
                                                                                        "Algorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
                                                                                    }
                                                                                ],
                                                                                "Reference": [
                                                                                    {
                                                                                        "Type": "http://uri.etsi.org/01903/v1.3.2#SignedProperties",
                                                                                        "URI": "#id-xades-signed-props",
                                                                                        "DigestMethod": [
                                                                                            {
                                                                                                "_": "",
                                                                                                "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
                                                                                            }
                                                                                        ],
                                                                                        "DigestValue": [
                                                                                            {
                                                                                                "_": props_digest
                                                                                            }
                                                                                        ],
                                                                                    },
                                                                                    {
                                                                                        "Type": "",
                                                                                        "URI": "",
                                                                                        "DigestMethod": [
                                                                                            {
                                                                                                "_": "",
                                                                                                "Algorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
                                                                                            }
                                                                                        ],
                                                                                        "DigestValue": [
                                                                                            {
                                                                                                "_": base64_hash
                                                                                            }
                                                                                        ],
                                                                                    },
                                                                                ],
                                                                            }
                                                                        ],
                                                                    }
                                                                ],
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ],
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
                                ],
                            }
                        ],
                    }
                ],
            }

            run_test = document_info
            info = document_info
            json_content = json.dumps(document_info, indent=2).encode()
            base64_document = base64.b64encode(json_content).decode("utf-8")
            print(base64_document)
            document_hash = hashlib.sha256(json_content).hexdigest()
            invoice_data = {
                "format": "JSON",
                "document": base64_document,
                "documentHash": document_hash,
                "invoice_id": sales_invoice_doc.name,
            }
            # print(f"json_content {invoice_data}")
            run = remove_signature_and_ublextensions_consolidated(run_test)
            base64_hash = run

            return invoice_data, info, base64_hash, document_info
        except Exception as e:
            frappe.throw(f"Error in build_document_info: {str(e)}")
