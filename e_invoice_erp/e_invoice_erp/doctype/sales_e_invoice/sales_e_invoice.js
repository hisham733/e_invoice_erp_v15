
// =================================================================================
// Main Event Handler for Sales E Invoice Doctype
// =================================================================================
frappe.ui.form.on("Sales E Invoice", {
    /**
     * The main refresh event handler. It controls what the user sees and can do
     * based on the document's status (Draft vs. Submitted).
     */
    refresh: function (frm) {
        // --- Actions for DRAFT documents (docstatus: 0) ---
        if (frm.doc.docstatus === 0) {
            frm.clear_custom_buttons(); // Clear old buttons before adding new ones

            // 1. Add "Get Items From Sales Invoice" button
            frm.add_custom_button(__("Get Items From"), function () {
                show_get_items_dialog(frm);
            }).addClass("btn-primary");

            // 2. Add "Fetch Party Info" button
            if (frm.doc.customer && frm.doc.company) {
                frm.add_custom_button(__('Fetch Party Information'), function () {
                    fetch_supplier_customer_info(frm);
                });
            }
        }

        // --- Actions for SUBMITTED documents (docstatus: 1) ---
        if (frm.doc.docstatus === 1) {
            frm.clear_custom_buttons(); // Clear draft buttons

            // 1. Add LHDN Action buttons under a group
            if (frm.doc.submission_uid) {
                // Generate QR Code button
                frm.add_custom_button(__('Generate QR Code'), function () {
                    call_generate_qr_code(frm);
                }, __('E-Invoice Actions'));

                // Check LHDN Status button
                frm.add_custom_button(__('Check LHDN Status'), function () {
                    call_get_lhdn_status(frm);
                }, __('E-Invoice Actions'));
            }

            // Cancel in LHDN button
            if (frm.doc.custom_lhdn_e_invoice_status !== "Cancelled") {
                const cancel_btn = frm.add_custom_button(__('Cancel in LHDN'), function () {
                    prompt_for_cancellation(frm);
                }, __('E-Invoice Actions'));
                $(cancel_btn).addClass('btn-danger'); // Make it stand out
            }
        }

        // --- Always run this on refresh, regardless of status ---
        calculate_all_item_totals(frm);
    },

    /**
     * This event runs after the form and its fields have been rendered.
     * Good for initial calculations.
     */
    onload_post_render: function (frm) {
        calculate_all_item_totals(frm);
    }
});





// =================================================================================
// Helper Functions (Organized for better readability)
// =================================================================================

/**
 * Shows the dialog to select a Sales Invoice to pull items from.
 */
function show_get_items_dialog(frm) {
    new frappe.ui.form.MultiSelectDialog({
        doctype: "Sales Invoice",
        target: frm,
        setters: {
            customer: frm.doc.customer,
            company: frm.doc.company,
        },
        get_query: function () {
            return {
                filters: { docstatus: 1, status: ["!=", "Lost"], company: frm.doc.company }
            };
        },
        action: function (selections) {
            if (selections.length !== 1) {
                frappe.msgprint(__("Please select exactly one Sales Invoice."));
                return;
            }
            const invoice_name = selections[0];
            this.dialog.hide();

            frappe.call({
                method: "e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.sales_e_invoice.check_sales_invoice_used_v2",
                args: { source_name: invoice_name },
                callback: function (r) {
                    const { warnings = [], blocks = [] } = r.message || {};

                    if (blocks.length > 0) {
                        const msg = blocks.map(i => i.error).join("<hr>");
                        frappe.msgprint({ title: __("Blocked Invoice"), message: msg, indicator: "red" });
                        return;
                    }

                    if (warnings.length > 0) {
                        const msg = warnings.map(i => i.error).join("<hr>");
                        frappe.confirm(
                            `The selected invoice has issues:<br><br>${msg}<br><br>Do you want to proceed anyway?`,
                            () => map_invoice_to_e_invoice(invoice_name)
                        );
                    } else {
                        map_invoice_to_e_invoice(invoice_name);
                    }
                }
            });
        }
    });
}

/**
 * Calls the server to map a Sales Invoice to the current Sales E Invoice form.
 */
function map_invoice_to_e_invoice(invoice_name) {
    frappe.call({
        method: "e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.sales_e_invoice.make_sales_e_invoice",
        args: { source_name: invoice_name },
        callback: function (r) {
            if (r.message) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", r.message.doctype, r.message.name);
            } else {
                frappe.msgprint(__("Failed to map Sales Invoice to Sales E Invoice."), "red");
            }
        }
    });
}

/**
 * Fetches and populates information from Company and Customer masters.
 */
function fetch_supplier_customer_info(frm) {
    frappe.call({
        method: "e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.sales_e_invoice.validate_and_populate_party_info",
        args: { doc: frm.doc },
        callback: function (r) {
            if (r.message) {
                // A more concise way to set multiple values
                frm.set_value(r.message);
                frappe.show_alert({ message: __("Party details populated."), indicator: "green" });
            }
        }
    });
}





/**
 * Calls the server to generate the LHDN QR code.
 */
function call_generate_qr_code(frm) {
    frappe.call({
        doc: frm.doc,
        method: 'generate_qr_code',
        freeze: true,
        freeze_message: __("Contacting LHDN and generating QR Code..."),
        callback: function (r) {
            if (r.message) {
                frm.reload_doc();
            }
        }
    });
}

/**
 * Calls the server to get the latest status from LHDN.
 */
function call_get_lhdn_status(frm) {
    frappe.call({
        method: 'e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.get_invoice_status.get_lhdn_submission_status',
        freeze: true,
        freeze_message: __("Retrieving invoice status from LHDN..."),
        args: { doc: frm.doc },
        callback: function (r) {
            if (r.message) {
                frm.reload_doc();
                // Link to original Sales Invoice if status is now Valid
                if (frm.doc.custom_lhdn_e_invoice_status === "Valid" && frm.doc.sales_invoice) {
                    frappe.db.set_value("Sales Invoice", frm.doc.sales_invoice, "sales_e_invoice_number", frm.doc.name)
                        .then(() => {
                            frappe.show_alert({ message: __("Sales Invoice linked successfully."), indicator: "green" });
                        });
                }
            }
        }
    });
}

/**
 * Prompts the user for a cancellation reason and calls the server to cancel.
 */
function prompt_for_cancellation(frm) {
    frappe.prompt(
        {
            label: __("Cancellation Reason"),
            fieldname: "reason",
            fieldtype: "Small Text",
            reqd: 1
        },
        function (values) {
            frappe.call({
                method: "e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.sales_e_invoice.cancel_from_button",
                args: { docname: frm.doc.name, reason: values.reason },
                freeze: true,
                freeze_message: __("Cancelling document in LHDN..."),
                callback: function (r) {
                    if (r.message && r.message.status === "success") {
                        frappe.msgprint({
                            title: __("Success"),
                            message: __("<b>LHDN Response:</b><br>") + r.message.message,
                            indicator: "green"
                        });
                        frm.reload_doc();
                    }
                }
            });
        },
        __("Enter Reason for Cancellation"),
        __("Cancel Document")
    );
}