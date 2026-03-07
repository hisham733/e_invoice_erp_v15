


// frappe.ui.form.on("Sales Invoice", {
//     refresh: function(frm) {
//         if (frm.doc.docstatus === 1) {
//             frm.add_custom_button("Check LHDN Status", function () {
//                 frappe.call({
//                     method: "e_invoice_erp.e_invoice_erp.search_taxpayer.update_lhdn_status_on_invoice",
//                     args: { invoice_name: frm.doc.name },
//                     callback: function(r) {
//                         if (r.message) {
//                             frm.set_value("custom_lhdn_status", r.message);
//                             frappe.show_alert({
//                                 message: __('LHDN Status updated to: {0}', [r.message]),
//                                 indicator: 'green'
//                             });
//                         } else {
//                             frm.set_value("custom_lhdn_status", "");
//                             frappe.show_alert({
//                                 message: __('LHDN Status cleared (not linked)'),
//                                 indicator: 'orange'
//                             });
//                         }
//                     }
//                 });
//             }).addClass("btn-primary");
//         }
//     }
// });



// extend_listview_event("Sales Invoice", "onload", function (listview) {
// 	listview.page.add_action_item(__("Create Consolidated E Invoice"), () => {
// 		const selected = listview.get_checked_items();

// 		if (selected.length < 2) {
// 			frappe.msgprint(__('Please select at least two Sales Invoices.'));
// 			return;
// 		}

// 		frappe.confirm(
// 			`Are you sure you want to create a Consolidated E Invoice for <b>${selected.length}</b> invoices?`,
// 			() => {
// 				show_loading_overlay();

// 				frappe.call({
// 					method: "e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.marge_invoices.create_consolidated_invoice",
// 					args: {
// 						invoice_numbers: selected.map(invoice => invoice.name)
// 					},
// 					callback: function (response) {
// 						hide_loading_overlay();

// 						if (response.message) {
// 							frappe.msgprint({
// 								title: __("Success"),
// 								message: __('Consolidated E Invoice created: ') + `<a href="/app/consolidated-e-invoice/${response.message}" target="_blank">${response.message}</a>`,
// 								indicator: "green"
// 							});
// 							listview.refresh();
// 							listview.check_all(false);
// 						} else {
// 							frappe.msgprint({
// 								title: __("Failed"),
// 								message: __("No Consolidated E Invoice was created."),
// 								indicator: "red"
// 							});
// 						}
// 					},
// 					error: function () {
// 						hide_loading_overlay();
// 						frappe.msgprint({
// 							title: __("Error"),
// 							message: __("An error occurred while creating the Consolidated E Invoice."),
// 							indicator: "red"
// 						});
// 					}
// 				});
// 			},
// 			() => {
// 				frappe.msgprint(__('Consolidated E Invoice creation was cancelled.'));
// 			}
// 		);
// 	});
// });



frappe.ui.form.on('Sales Invoice Item', {
	qty: function(frm, cdt, cdn) {
            console.log("Normalized dropdown value:");
	    calculate_item_total_before_discount(frm, cdt, cdn);
	},
	price_list_rate: function(frm, cdt, cdn) {
	    calculate_item_total_before_discount(frm, cdt, cdn);
	}
  });
  
  frappe.ui.form.on('Sales Invoice', {
	refresh: function(frm) {
	    frm.doc.items.forEach(item => {
		  calculate_item_total_before_discount(frm, item.doctype, item.name);
	    });
	},
	onload_post_render: function(frm) {
	    frm.doc.items.forEach(item => {
		  calculate_item_total_before_discount(frm, item.doctype, item.name);
	    });
	}
  });
  
  function calculate_item_total_before_discount(frm, cdt, cdn) {
	let item = locals[cdt][cdn];
	if (item.price_list_rate && item.qty) {
	    let total_amount_before_discount = item.price_list_rate * item.qty;
	    frappe.model.set_value(cdt, cdn, 'custom_total_amount_before_discount', total_amount_before_discount);
	}
  }
  




