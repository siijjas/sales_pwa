export interface UserSession {
  user: string;
  full_name: string;
  sid: string;
}

export interface Customer {
  name: string;
  customer_name: string;
  customer_group: string;
  territory: string;
  image?: string;
}

export interface Item {
  item_code: string;
  item_name: string;
  description: string;
  stock_uom: string;
  image?: string;
  item_group: string;
  standard_rate?: number;
  price_list_rate?: number;
  actual_qty?: number;
}

export interface CartLine {
  item: Item;
  qty: number;
}

export interface SalesOrderItem {
  item_code: string;
  item_name: string;
  qty: number;
  rate: number;
  amount: number;
  delivery_date?: string;
  stock_uom?: string;
  price_list_rate?: number;
}

export interface SalesOrder {
  name: string;
  customer: string;
  customer_name: string;
  transaction_date: string;
  modified?: string;
  grand_total: number;
  total_taxes_and_charges?: number;
  status: string;
  owner: string;
  docstatus: number;
  items: SalesOrderItem[];
  selling_price_list?: string;
  company?: string;
  delivery_date?: string;
}
