from frappe import _

def get_data():
	return [
		{
			"label": _("Core Entities"),
			"items": [

				{
					"type": "doctype",
					"name": "Item",
					"onboard": 1,

				},
				{
					"type": "doctype",
					"name": "Customer",
					"onboard": 1,

				},
				{
					"type": "doctype",
					"name": "Supplier",
					"onboard": 1,

				},
				{
					"type": "doctype",
					"name": "Address",
					"onboard": 1,

				},

			]
		},

		{
			"label": _("Sales Workflow"),
			"items": [

				{
					"type": "doctype",
					"name": "Quotation",
					"onboard": 1,

				},
				{
					"type": "doctype",
					"name": "Sales Order",
					"onboard": 1,

				},
				{
					"type": "doctype",
					"name": "Sales Invoice",
					"onboard": 1,


				},

			]
		},
				{
			"label": _("E-Invoice Operations"),
			"items": [
				{
					"type": "doctype",
					"name": "API Credentials",
					"onboard": 1,


				},
				{
					"type": "doctype",
					"name": "Sales E Invoice",
					"onboard": 1,
					"dependencies": ["Sales Invoice","API Credentials","Address"]


				},
               {
                    "type": "doctype",
                    "name": "Consolidated E Invoice",
                    "onboard": 1,
    				"dependencies": ["Sales Invoice","API Credentials","Address"]
               },
				{
					"type": "doctype",
					"name": "Get Document Info",
					"onboard": 1,
					"dependencies": ["Sales E Invoice"]

				},
				{
					"type": "doctype",
					"name": "Get Document Details",
					"onboard": 1,
					"dependencies": ["Sales E Invoice"]

				},
				{
					"type": "doctype",
					"name": "Cancel Document",
					"onboard": 1,
					"dependencies": ["Sales E Invoice"]


				},

			]
		},
		
		
	]
	
	