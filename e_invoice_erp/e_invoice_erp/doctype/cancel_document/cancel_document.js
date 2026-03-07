frappe.ui.form.on('Cancel Document', {
	e_invoice: function(frm) {
	    console.log("Fetched e_invoice:", frm.doc.e_invoice);
  
	    if (!frm.doc.e_invoice_model || !frm.doc.e_invoice) return;
  
	    frappe.call({
		  method: "frappe.client.get",
		  args: {
			doctype: frm.doc.e_invoice_model,
			name: frm.doc.e_invoice
		  },
		  callback: function(r) {
			if (r.message) {
			    console.log("Fetched Record:", r.message);
  
			    // Fetch UUID and API Credentials
			    const uuid = r.message.uuid ;
			    const api_credentials = r.message.api_credentials;
  
			    if (uuid) {
				  frm.set_value("uuid", uuid);
			    } else {
				  frappe.msgprint("UUID not found in the selected invoice record.");
			    }
  
			    if (api_credentials) {
				  frm.set_value("api_credentials", api_credentials);
			    } else {
				  frappe.msgprint("API Credentials not found in the selected invoice record.");
			    }
			} else {
			    frappe.msgprint("Failed to fetch the selected invoice record.");
			}
		  }
	    });
	}
  });
  