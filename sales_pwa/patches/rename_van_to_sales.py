import frappe

# The app was cloned from van_sale. Its module, DocTypes, role and print formats carried a
# "Van" prefix; they are now named after the Sales App. Rename the records in place before
# the model sync so the sync updates the renamed rows instead of creating duplicates.

MODULE = ("Van Sale", "Sales App")
ROLE = ("Van Sales Driver", "Sales App User")
DOCTYPES = [
	"Profile Customer Group",
	"Profile Driver",
	"Profile Expense Account",
	"Profile Payment Mode",
	"Shift Closing Tax",
	"Shift Transaction",
	"Shift Balance Detail",
	"Shift Payment Reconciliation",
	"Profile",
	"Shift Opening",
	"Shift Closing",
	"Cash Movement",
	"EOD Report",
	"Expense Log",
]
PRINT_FORMATS = ["Shift Summary", "Shift Closing Report"]


def _rename(doctype, old, new):
	if not frappe.db.exists(doctype, old):
		return
	if frappe.db.exists(doctype, new):
		frappe.delete_doc(doctype, old, force=True, ignore_permissions=True)
		return
	frappe.rename_doc(doctype, old, new, force=True, show_alert=False, rebuild_search=False)


def execute():
	frappe.flags.in_patch = True
	_rename("Module Def", *MODULE)
	for name in DOCTYPES:
		_rename("DocType", f"Van {name}", f"Sales {name}")
	_rename("Role", *ROLE)
	for name in PRINT_FORMATS:
		_rename("Print Format", f"Van {name}", f"Sales {name}")
	# Renaming the Module Def does not touch every record that links to it.
	for doctype in ("DocType", "Print Format", "Report", "Page", "Workspace"):
		frappe.db.set_value(doctype, {"module": MODULE[0]}, "module", MODULE[1], update_modified=False)
	frappe.clear_cache()
