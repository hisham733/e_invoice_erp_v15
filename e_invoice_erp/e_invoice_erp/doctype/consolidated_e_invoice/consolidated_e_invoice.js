// In your Client Script for "Sales E Invoice"

// frappe.ui.form.on('Consolidated E Invoice', {
//     refresh: function(frm) {
        
//         frm.remove_custom_button(__('Generate QR Code'));

//         // MODIFIED CONDITION: Show the button as soon as there is a submission_uid.
//         // The user's first action will be to click this button.
//         if (frm.doc.docstatus === 1 && frm.doc.submission_uid) {
            
//             // Modified Button Text
//             frm.add_custom_button(__('Generate QR Code'), function() {
//                 frappe.call({
//                     doc: frm.doc,
//                     method: 'generate_qr_code', // This method already checks the status internally
//                     freeze: true,
//                     freeze_message: __("Contacting LHDN and generating QR Code..."),

//                     callback: function(r) {
//                         // On success, the backend shows a message. We just need to reload.
//                         if (r.message) { // A good practice to check if the server returned something
//                            frm.reload_doc();
//                         }
//                     }
//                     // No error block needed, which is correct!
//                 });
//             }).addClass('btn-primary');
//         }
//     }
// });


// frappe.ui.form.on('Consolidated E Invoice', {
//     refresh: function(frm) {
//         // Remove previous button to avoid duplication
//         frm.remove_custom_button('Check LHDN Status');

//         // Only show button if document is submitted and submission_uid is present
//         if (frm.doc.docstatus === 1 && frm.doc.submission_uid) {
//             const btn = frm.add_custom_button(__('Check LHDN Status'), function() {
//                 // Hide the button immediately after click
//                 $(btn).hide();

//                 frappe.call({
//                     method: 'e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.get_invoice_status.get_lhdn_submission_status',
//                     freeze: true,
//                     freeze_message: __("Retrieving invoice status from LHDN. Please wait..."),
//                     args: {
//                         doc: frm.doc
//                     },
//                     callback: function(r) {
//                         if (r.message) {
//                             frm.reload_doc();
//                         }
//                     },
//                     always: function() {
//                         // Show the button again after 5 seconds
//                         setTimeout(() => {
//                             $(btn).show();
//                         }, 5000);
//                     }
//                 });
//             });

//             // Optional: Make the button blue
//             $(btn).addClass('btn-primary');
//         }
//     }
// });


frappe.ui.form.on('Consolidated E Invoice', {
    refresh: function(frm) {
        // Only show grouped actions if document is submitted
        if (frm.doc.docstatus === 1) {

            // --- Remove previously added buttons to prevent duplicates ---
            frm.remove_custom_button('Generate QR Code', __('E-Invoice Actions'));
            frm.remove_custom_button('Check LHDN Status', __('E-Invoice Actions'));
            frm.remove_custom_button('Cancel in LHDN', __('E-Invoice Actions'));

            // === 1. Generate QR Code ===
            if (frm.doc.submission_uid) {
                const qr_btn = frm.add_custom_button(__('Generate QR Code'), function() {
                    frappe.call({
                        doc: frm.doc,
                        method: 'generate_qr_code',
                        freeze: true,
                        freeze_message: __("Contacting LHDN and generating QR Code..."),
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();
                            }
                        }
                    });
                }, __('E-Invoice Actions'));
                $(qr_btn).addClass('btn-primary');
            }

            // === 2. Check LHDN Status ===
            if (frm.doc.submission_uid) {
                const status_btn = frm.add_custom_button(__('Check LHDN Status'), function() {
                    $(status_btn).hide();

                    frappe.call({
                        method: 'e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.get_invoice_status.get_lhdn_submission_status',
                        freeze: true,
                        freeze_message: __("Retrieving invoice status from LHDN. Please wait..."),
                        args: {
                            doc: frm.doc
                        },
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();

                                if (frm.doc.custom_lhdn_e_invoice_status === "Valid" && frm.doc.sales_invoice) {
                                    frappe.call({
                                        method: "frappe.client.set_value",
                                        args: {
                                            doctype: "Sales Invoice",
                                            name: frm.doc.sales_invoice,
                                            fieldname: {
                                                sales_e_invoice_number: frm.doc.name
                                            }
                                        },
                                        callback: function() {
                                            frappe.msgprint({
                                                message: __("Sales Invoice linked successfully to this Consolidated E Invoice."),
                                                title: __("Updated"),
                                                indicator: "green"
                                            });
                                        }
                                    });
                                }
                            }
                        },
                        always: function() {
                            setTimeout(() => {
                                $(status_btn).show();
                            }, 5000);
                        }
                    });
                }, __('E-Invoice Actions'));
                $(status_btn).addClass('btn-primary');
            }

            // === 3. Cancel in LHDN ===
            if (frm.doc.custom_lhdn_e_invoice_status !== "Cancelled") {
                const cancel_btn = frm.add_custom_button(__('Cancel in LHDN'), function() {
                    frappe.prompt(
                        {
                            label: __("Cancellation Reason"),
                            fieldname: "reason",
                            fieldtype: "Small Text",
                            reqd: 1
                        },
                        function(values) {
                            frappe.call({
                                method: "e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.consolidated_e_invoice.cancel_from_button",
                                args: {
                                    docname: frm.doc.name,
                                    reason: values.reason
                                },
                                freeze: true,
                                freeze_message: __("Cancelling document in LHDN..."),
                                callback: function(r) {
                                    if (r.message) {
                                        frappe.msgprint({
                                            title: __("LHDN Response"),
                                            message: __("Document cancelled successfully."),
                                            indicator: "green"
                                        });
                                        frm.reload_doc();
                                    }
                                },
                                error: function(err) {
                                    frappe.msgprint({
                                        title: __("LHDN Cancellation Failed"),
                                        message: __("Could not cancel the document. Please check the error log."),
                                        indicator: "red"
                                    });
                                }
                            });
                        },
                        __("Enter Reason for Cancellation"),
                        __("Cancel Document")
                    );
                }, __('E-Invoice Actions'));
                $(cancel_btn).addClass('btn-danger');
            }
        }
    }
});

  

frappe.ui.form.on('Consolidated E Invoice', {
    refresh(frm) {
        // Ensure totals are correct whenever the form is loaded/refreshed
        frm.trigger('recalculate_totals_from_invoices');
    },

    invoices_add(frm) {
        frm.trigger('recalculate_totals_from_invoices');
    },

    invoices_remove(frm) {
        frm.trigger('recalculate_totals_from_invoices');
    },

    recalculate_totals_from_invoices(frm) {
        let total = 0.0;
        let total_taxes = 0.0;
        let total_charge = 0.0;
        let first_tax_category = null;

        (frm.doc.invoices || []).forEach(row => {
            total += flt(row.total || 0);
            total_taxes += flt(row.total_taxes || 0);
            total_charge += flt(row.total_additional || 0);

            if (!first_tax_category && row.tax_catagory) {
                first_tax_category = row.tax_catagory;
            }
        });

        frm.set_value('total', total);
        frm.set_value('total_taxes_and_charges', total_taxes);
        frm.set_value('total_charge', total_charge);
        // Keep consistent with server-side calculation: total + taxes + additional charges
        frm.set_value('grand_total', total + total_taxes + total_charge);

        if (first_tax_category) {
            const raw = String(first_tax_category).trim();
            const code = raw.includes(':') ? raw.split(':')[0].trim() : raw;
            const opts_raw = frm.fields_dict.tax_category?.df?.options || '';
            const opts = String(opts_raw).split('\n').map(o => o.trim()).filter(Boolean);
            const match = opts.find(o => {
                const o_code = o.includes(':') ? o.split(':')[0].trim() : o.trim();
                return o_code === code;
            });
            frm.set_value('tax_category', match || raw);
        }
    }
});

frappe.ui.form.on('Consolidated Invoice Entry', {
    total(frm) {
        frm.trigger('recalculate_totals_from_invoices');
    },
    total_taxes(frm) {
        frm.trigger('recalculate_totals_from_invoices');
    },
    tax_catagory(frm) {
        frm.trigger('recalculate_totals_from_invoices');
    }
});

// frappe.ui.form.on('Consolidated E Invoice', {
//       refresh: function(frm) {
//           // Show button only if document is submitted
//           if (frm.doc.docstatus === 1) {
//               frm.add_custom_button('Generate QR Code', function() {
//                   frappe.call({
//                       doc: frm.doc,
//                       method: 'gr_link',
//                       callback: function(r) {
//                           if (r.message) {
//                               const qr_link = r.message.qr_link;
//                               const file_url = r.message.file_url;
  
//                               // Prefer dynamic QR link if available
//                               let qr_url = qr_link
//                                   ? `https://api.qrserver.com/v1/create-qr-code/?data=${encodeURIComponent(qr_link)}&size=150x150`
//                                   : file_url;
  
//                               if (qr_url) {
//                                   frm.set_value('validation_url', qr_url);
//                                   frm.refresh_field('validation_url');
//                                   frm.refresh_field('qr');
//                                   frappe.msgprint(__('✅ QR Code generated successfully.'));
//                               } else {
//                                   frappe.msgprint(__('⚠️ QR Code generated, but no link available.'));
//                               }
//                           } else {
//                               frappe.msgprint(__('❌ Failed to generate QR code. Server returned no message.'));
//                           }
//                       },
//                       error: function(err) {
//                           frappe.msgprint(__('❌ Error during QR code generation: ') + err.message);
//                       }
//                   });
//               });
//           }
//       }
//   });
  




//   frappe.ui.form.on('Consolidated E Invoice', {
//     refresh(frm) {
//         frm.add_custom_button(__('Import Sales Invoices'), () => {
//             const dialog = new frappe.ui.form.MultiSelectDialog({
//                 doctype: "Sales Invoice",
//                 target: frm,
//                 setters: {
//                     customer: frm.doc.customer || undefined
//                 },
//                 add_filters_group: 1,
//                 get_query() {
//                     return {
//                         filters: {
//                             docstatus: 1
//                         }
//                     };
//                 },
//                 action(selections) {
//                     if (!selections.length) {
//                         frappe.msgprint("Please select at least one Sales Invoice.");
//                         return;
//                     }

//                     frappe.call({
//                         method: "e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.consolidated_e_invoice.get_sales_invoice_items",
//                         args: {
//                             sales_invoices: selections,
//                             consolidated_invoice_name: frm.doc.name
//                         },
//                         callback: function(r) {
//                             if (r.message) {
//                                 // Clear existing data
//                                 frm.clear_table("items");
//                                 frm.clear_table("taxes");
//                                 frm.clear_table("sales_team");

//                                 // Add new data
//                                 r.message.items.forEach(item => {
//                                     frm.add_child("items", item);
//                                 });

//                                 r.message.taxes.forEach(tax => {
//                                     frm.add_child("taxes", tax);
//                                 });

//                                 r.message.sales_team.forEach(team => {
//                                     frm.add_child("sales_team", team);
//                                 });

//                                 frm.refresh_field("items");
//                                 frm.refresh_field("taxes");
//                                 frm.refresh_field("sales_team");

//                                 frappe.msgprint("Sales Invoices successfully added.");
//                                 dialog.dialog.hide();
//                             }
//                         }
//                     });
//                 }
//             });
//         }, __("Actions"));
//     }
// });








// function show_loading_overlay() {
// 	if (!$('#custom-loading-overlay').length) {
// 		$('body').append(`
// 			<div id="custom-loading-overlay" style="
// 				position: fixed;
// 				top: 0; left: 0; right: 0; bottom: 0;
// 				background: rgba(255, 255, 255, 0.8);
// 				z-index: 9999;
// 				display: flex;
// 				align-items: center;
// 				justify-content: center;
// 			">
// 				<img src="/caf/caf/e_invoice_erp/public/js/invoice.gif" style="width: 200px; height: 200px;" />
// 			</div>
// 		`);
// 	}
// }
//   // Helper to hide loading overlay
//   function hide_loading_overlay() {
//       $('#custom-loading-overlay').remove();
//   }
  
//   // Function to extend ListView events
//   function extend_listview_event(doctype, event, callback) {
//       if (!frappe.listview_settings[doctype]) {
//           frappe.listview_settings[doctype] = {};
//       }
  
//       const old_event = frappe.listview_settings[doctype][event];
//       frappe.listview_settings[doctype][event] = function (listview) {
//           if (old_event) {
//               old_event(listview);
//           }
//           callback(listview);
//       };
//   }
  
//   // Extend "onload" event for Sales Invoice
//   extend_listview_event("Sales Invoice", "onload", function (listview) {
//       listview.page.add_action_item(__("Create Consolidate E_Invoices"), () => {
//           const selected = listview.get_checked_items();
//           if (selected.length < 2) {
//               frappe.msgprint(__('Please select at least two Consolidated E Invoice.'));
//               return;
//           }
  
//           frappe.confirm(
//               `Are you sure you want to create Consolidated E_Invoice for ${selected.length} invoices ?`,
//               () => {
//                   // Show loading GIF
//                   show_loading_overlay();
  
//                   frappe.call({
//                       method: "e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.marge_invoices.create_consolidated_invoice",
//                       args: {
//                           invoice_numbers: selected.map(invoice => invoice.name)
//                       },
//                       callback: function (response) {
//                           // Hide loading GIF
//                           hide_loading_overlay();
  
//                           if (response.message) {
//                               frappe.msgprint(__('Invoices successfully created in Consolidated E_Invoice: ') + response.message);
//                               listview.refresh();
//                               listview.check_all(false);
//                           } else {
//                               frappe.msgprint(__('Failed to create invoices.'));
//                           }
//                       },
//                       error: function () {
//                           hide_loading_overlay();
//                           frappe.msgprint(__('An error occurred during invoice Create.'));
//                       }
//                   });
//               },
//               () => {
//                   frappe.msgprint(__('Invoice Create operation cancelled.'));
//               }
//           );
//       });
  
//   });
  