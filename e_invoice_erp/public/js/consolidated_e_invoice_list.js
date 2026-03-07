// File: e_invoice_erp/public/js/sales_e_invoice_list.js

frappe.listview_settings["Consolidated E Invoice"] = {
	add_fields: ["custom_lhdn_e_invoice_status", "customer", "grand_total", "posting_date"],

	get_indicator: function (doc) {
		const status_colors = {
			"Valid": "green",
			"Invalid": "pink",
			"Submitted": "blue",
			"Cancelled": "gray",
			"Processing": "orange",
			"Replaced": "purple"
		};

		// Custom display labels for each status
		const status_labels = {
			"Valid": "Valid EInvoice",
			"Invalid": "Invalid EInvoice",
			"Submitted": "Submitted to LHDN",
			"Cancelled": "Cancelled EInvoice",
			"Processing": "Processing EInvoice",
			"Replaced": "Replaced EInvoice"
		};

		let status = doc.custom_lhdn_e_invoice_status || "Unknown";
		let color = status_colors[status] || "darkgrey";
		let label = status_labels[status] || status;

		return [__(label), color, `custom_lhdn_e_invoice_status,=,${status}`];
	},

	right_column: "grand_total"
};
