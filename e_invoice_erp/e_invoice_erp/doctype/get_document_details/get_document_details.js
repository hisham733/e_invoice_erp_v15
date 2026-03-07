frappe.ui.form.on('Get Document Details', {
    refresh: function(frm) {
        // Check if the document is already submitted
        if (frm.doc.docstatus === 1) {
            // Add custom buttons only if the document is submitted
            frm.add_custom_button(__("Fetch Document Details"), function() {
                frappe.call({
                    doc: frm.doc,
                    method: "resubmit",
                    callback: function(response) {
                        console.log('✅ Server response:', response.message); // 👈 prints to browser console
                        frappe.msgprint(__('✅ Document details fetched and saved successfully.'));

                        if (response.message) {
                            const [code, validation_url] = response.message;

                            frm.set_value("code", code);
                            // frm.set_value("validation_url", validation_url);

                            frm.refresh_field("code");
                            // frm.refresh_field("validation_url");
                        }
                    },
                    error: function(error) {
                        console.error('❌ Error fetching document details:', error); // 👈 error log
                        frappe.msgprint(__('❌ An error occurred: ' + error.message));
                    }
                });
            });

            frm.add_custom_button("Generate Invoice QR", function() {
                frappe.call({
                    doc: frm.doc,
                    method: 'generate_invoice_qr',
                    callback: function(r) {
                        if (r.message && r.message.file_url) {
                            frm.set_value("validation_url", r.message.file_url);
                            frm.refresh_field("validation_url");
                            frappe.msgprint("QR Code saved to file: " + r.message.file_url);
                        }
                    }
                });
            });
        }
    }
});
