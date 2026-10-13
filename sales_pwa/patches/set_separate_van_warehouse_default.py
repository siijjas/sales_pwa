import frappe


def execute():
	"""Sales Profile.separate_van_warehouse was added with every existing Van Sales
	profile already loading into its own van warehouse, so they keep doing so."""
	if not frappe.db.has_column("Sales Profile", "separate_van_warehouse"):
		return
	frappe.db.sql(
		"""
		update `tabSales Profile`
		set separate_van_warehouse = 1
		where ifnull(van_warehouse, '') != ''
		"""
	)
