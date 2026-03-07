// File: e_invoice_erp/public/js/sales_e_invoice_list.js

frappe.listview_settings["Consolidated E Invoice"] = {
	add_fields: ["custom_lhdn_e_invoice_status", "customer", "grand_total", "posting_date"],
	get_indicator: function (doc) {
		const status_colors = {
			"Valid": "green",
			"Invalid": "red",
			"Submitted": "blue",
			"Cancelled": "gray",
			"Processing": "orange",
			"Replaced": "purple"
		};

		let color = status_colors[doc.custom_lhdn_e_invoice_status] || "darkgrey";
		return [__(doc.custom_lhdn_e_invoice_status || "Unknown"), color, `custom_lhdn_e_invoice_status,=,${doc.custom_lhdn_e_invoice_status}`];
	},
	right_column: "grand_total"
};
