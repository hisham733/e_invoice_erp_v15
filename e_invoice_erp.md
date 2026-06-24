# E Invoice Erp — v12 → v15 Migration

**Source:** https://github.com/hisham733/E_invoice_erp

## Changes Made

### 1. Module Page → Workspace JSON

**Before:** `config/desktop.py` with `get_data()` returning a module entry using old octicon format.

```python
from frappe import _
def get_data():
    return [
        {
            "module_name": "E Invoice Erp",
            "color": "grey",
            "icon": "octicon octicon-file-directory",
            "type": "module",
            "label": _("E Invoice Erp")
        }
    ]
```

**After:** `e_invoice_erp/workspace/e_invoice_erp/e_invoice_erp.json` with cards (Sales, Consolidation, Settings & Status), 4 shortcuts, and Lucide icon.

```json
{
 "doctype": "Workspace",
 "icon": "money-coins-1",
 "label": "E Invoice Erp",
 "links": [...],
 "shortcuts": [...]
}
```

The `config/desktop.py` file is kept (harmless, ignored in v15).

### 2. Fixed Icon

**Before:** `app_icon = "octicon octicon-file-directory"` (old octicon, doesn't render in v15)

**After:** `app_icon = "file-invoice"` (Lucide icon, renders correctly in v15)

### 3. Removed `from __future__ import unicode_literals` and `# -*- coding: utf-8 -*-`

**Before:** Top of every Python file:
```python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
```

**After:** Lines removed from all 21 Python files (12 coding lines, 19 unicode_literals imports).

### Files Modified

| File | Change |
|---|---|
| `setup.py` | Removed Python 2 boilerplate |
| `e_invoice_erp/__init__.py` | Removed Python 2 boilerplate |
| `e_invoice_erp/hooks.py` | Removed boilerplate + fixed icon to `file-invoice` |
| `e_invoice_erp/config/desktop.py` | Removed boilerplate |
| `e_invoice_erp/config/e_invoice_erp.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/api_credentials/api_credentials.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/api_credentials/test_api_credentials.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/cancel_document/cancel_document.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/cancel_document/test_cancel_document.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/consolidated_e_invoice/build_invoice.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/consolidated_e_invoice/consolidated_e_invoice.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/consolidated_e_invoice/consolidated_e_invoice_dashboard.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/consolidated_invoice_entry/consolidated_invoice_entry.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/get_document_details/get_document_details.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/get_document_details/test_get_document_details.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/get_document_info/get_document_info.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/get_document_info/test_get_document_info.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/new_sales_editt.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/sales_e_invoice.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/sales_e_invoice_dashboard.py` | Removed boilerplate |
| `e_invoice_erp/e_invoice_erp/doctype/sales_e_invoice/test_sales_e_invoice.py` | Removed boilerplate |
| **New: workspace JSON** | `e_invoice_erp/workspace/e_invoice_erp/e_invoice_erp.json` |
