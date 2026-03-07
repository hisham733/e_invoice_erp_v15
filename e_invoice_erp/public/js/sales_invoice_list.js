frappe.listview_settings["Sales Invoice"] = {
	add_fields: [
		"customer",
		"customer_name",
		"base_grand_total",
		"outstanding_amount",
		"due_date",
		"company",
		"currency",
		"is_return",
		"custom_lhdn_status"
	],

	get_indicator: function (doc) {
		const erp_status_colors = {
			Draft: "red",
			Unpaid: "orange",
			Paid: "green",
			Return: "gray",
			"Credit Note Issued": "gray",
			"Unpaid and Discounted": "orange",
			"Partly Paid and Discounted": "yellow",
			"Overdue and Discounted": "red",
			Overdue: "red",
			"Partly Paid": "yellow",
			"Internal Transfer": "darkgrey",
		};

		const lhdn_status_colors = {
			"Valid": "green",
			"Invalid": "red",
			"Submitted": "blue",
			"InProgress": "orange",
			"Cancelled": "gray",
			"Processing": "yellow",
			"Replaced": "purple"
		};

		// 🎨 Merge both in one label for visibility
		let erp_status = doc.status || "Unknown";
		let lhdn_status = doc.custom_lhdn_status || "Not Linked";

		// Choose color based on LHDN status if available, fallback to ERP status
		let color = lhdn_status_colors[lhdn_status] || erp_status_colors[erp_status] || "gray";

		// Combined label
		let label = `${erp_status} (LHDN: ${lhdn_status})`;

		// Filter by ERP status
		let filter = `status,=,${erp_status}`;

		return [__(label), color, filter];
	},

	right_column: "grand_total",

	onload: function (listview) {
		if (frappe.model.can_create("Delivery Note")) {
			listview.page.add_action_item(__("Delivery Note"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Invoice", "Delivery Note");
			});
		}

		if (frappe.model.can_create("Payment Entry")) {
			listview.page.add_action_item(__("Payment"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Invoice", "Payment Entry");
			});
		}
	},
};


function show_loading_overlay() {
	if (!$('#custom-loading-overlay').length) {
		$('body').append(`
			<div id="custom-loading-overlay" style="
				position: fixed;
				top: 0; left: 0; right: 0; bottom: 0;
				background: rgba(255, 255, 255, 0.8);
				z-index: 9999;
				display: flex;
				align-items: center;
				justify-content: center;
			">
				<img src="/assets/e_invoice_erp/js/invoice.gif" style="width: 200px; height: 200px;" />
			</div>
		`);
	}
}

function hide_loading_overlay() {
	$('#custom-loading-overlay').remove();
}

function extend_listview_event(doctype, event, callback) {
	if (!frappe.listview_settings[doctype]) {
		frappe.listview_settings[doctype] = {};
	}
	const old_event = frappe.listview_settings[doctype][event];
	frappe.listview_settings[doctype][event] = function (listview) {
		if (old_event) old_event(listview);
		callback(listview);
	};
}

extend_listview_event("Sales Invoice", "onload", function (listview) {
	listview.page.add_action_item(__("Create Consolidated E Invoice"), () => {
		const selected = listview.get_checked_items();
		if (selected.length < 2) {
			frappe.msgprint(__('Please select at least two Sales Invoices.'));
			return;
		}

		const invoiceNames = selected.map(invoice => invoice.name);
		show_loading_overlay();

		frappe.call({
			method: "e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.marge_invoices.validate_invoice_statuses",
			args: { invoice_numbers: invoiceNames },
			callback: function (r) {
				hide_loading_overlay();
				console.log("Validation response:", r);
				const { warnings = [], blocks = [] } = r.message || {};

				// Handle blocking errors
				if (blocks.length > 0) {
					const errors = blocks.map(inv => inv.error).join("<hr>");
					frappe.msgprint({
						title: __("Blocked Invoices"),
						message: errors,
						indicator: "red"
					});
					return;
				}

				// If there are warnings, ask for confirmation
				if (warnings.length > 0) {
					const warningMsg = warnings.map(inv => inv.error).join("<hr>");
					frappe.confirm(
						`Some invoices have issues:<br><br>${warningMsg}<br><br>Do you want to proceed anyway?`,
						() => {
							create_consolidated_invoice(invoiceNames, true, listview);
						},
						() => {
							frappe.msgprint(__('Consolidated E Invoice creation cancelled.'));
						}
					);
				} else {
					// All good, no warnings or blocks
					create_consolidated_invoice(invoiceNames, false, listview);
				}
			},
			error: function () {
				hide_loading_overlay();
				frappe.msgprint({
					title: __("Error"),
					message: __("Failed to validate invoices."),
					indicator: "red"
				});
			}
		});
	});
});

function create_consolidated_invoice(invoiceNames, force, listview) {
	show_loading_overlay();
	frappe.call({
		method: "e_invoice_erp.e_invoice_erp.doctype.consolidated_e_invoice.marge_invoices.create_consolidated_invoice",
		args: {
			invoice_numbers: invoiceNames,
			force: force
		},
		callback: function (response) {
			hide_loading_overlay();
			if (response.message) {
				frappe.msgprint({
					title: __("Success"),
					message: __('Consolidated E Invoice created: ') +
						`<a href="/app/consolidated-e-invoice/${response.message}" target="_blank">${response.message}</a>`,
					indicator: "green"
				});
				listview.refresh();
				listview.check_all(false);
			} else {
				frappe.msgprint({
					title: __("Failed"),
					message: __("No Consolidated E Invoice was created."),
					indicator: "red"
				});
			}
		},
		error: function () {
			hide_loading_overlay();
			frappe.msgprint({
				title: __("Error"),
				message: __("An error occurred while creating the Consolidated E Invoice."),
				indicator: "red"
			});
		}
	});
}

frappe.ui.form.on('Sales Invoice', {
	refresh(frm) {
		// Only show the button if submitted
		if (frm.doc.docstatus === 1 && !frm.doc.sales_e_invoice_number) {
			frm.add_custom_button('Make Sales E Invoice', () => {
				frappe.call({
					method: 'e_invoice_erp.e_invoice_erp.doctype.sales_e_invoice.sales_e_invoice.make_sales_e_invoice',
					args: {
						source_name: frm.doc.name
					},
					callback(r) {
						if (r.message) {
							frappe.model.sync(r.message);
							frappe.set_route('Form', r.message.doctype, r.message.name);
						}
					}
				});
			}, 'Create');
		}
	}
});
