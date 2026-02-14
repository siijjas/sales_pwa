<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Header -->
    <div class="px-4 py-3 bg-white border-b flex items-center gap-2 sticky top-0 z-10 justify-between">
      <div class="flex items-center gap-2">
        <button class="text-sm text-gray-600" @click="$router.back()">Back</button>
        <h2 class="text-base font-semibold text-gray-900">New Payment</h2>
      </div>
      <div class="flex items-center gap-3">
        <button class="text-sm text-gray-600" @click="$router.push({ name: 'dashboard' })">Dashboard</button>
        <button class="text-sm text-blue-600" @click="reload">Refresh</button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-4 py-4 space-y-6 pb-24">
      <!-- Customer Section -->
      <div class="space-y-2">
        <label class="block text-xs font-semibold text-gray-600 uppercase">Customer</label>
        <div v-if="customer" class="bg-white p-3 rounded-xl border flex justify-between items-center shadow-sm">
          <div>
            <p class="font-semibold text-gray-900">{{ customer.customer_name }}</p>
            <p class="text-xs text-gray-500">{{ customer.name }}</p>
          </div>
          <button class="text-blue-600 text-sm font-medium" @click="changeCustomer">Change</button>
        </div>
        <button
          v-else
          class="w-full bg-white border-2 border-dashed border-gray-300 rounded-xl p-4 text-gray-500 font-medium hover:border-blue-500 hover:text-blue-500 transition-colors"
          @click="$router.push({ name: 'customers', query: { redirect: 'payment' } })"
        >
          + Select Customer
        </button>
      </div>

      <div v-if="customer" class="space-y-6">
        <!-- Customer Summary -->
        <div v-if="customerSummary" class="bg-blue-50 border border-blue-100 rounded-xl p-3 text-sm space-y-2">
           <div class="flex justify-between items-center">
             <span class="text-blue-800 font-medium">Outstanding Balance</span>
             <span class="font-bold text-blue-900">{{ currency }} {{ (customerSummary.outstanding_balance || 0).toFixed(2) }}</span>
           </div>
           
           <div v-if="customerSummary.last_invoice" class="flex justify-between items-center border-t border-blue-100 pt-2">
             <span class="text-blue-700">Last Invoice</span>
             <div class="text-right">
               <span class="font-medium text-blue-900 block">{{ customerSummary.last_invoice.name }}</span>
               <span class="text-xs text-blue-600 block">{{ customerSummary.last_invoice.posting_date }} • {{ currency }} {{ (customerSummary.last_invoice.grand_total || 0).toFixed(2) }}</span>
             </div>
           </div>
           
           <div v-if="customerSummary.last_payment" class="flex justify-between items-center border-t border-blue-100 pt-2">
             <span class="text-blue-700">Last Payment</span>
             <div class="text-right">
               <span class="font-medium text-blue-900 block">{{ currency }} {{ (customerSummary.last_payment.paid_amount || 0).toFixed(2) }}</span>
               <span class="text-xs text-blue-600 block">{{ customerSummary.last_payment.posting_date }}</span>
             </div>
           </div>
        </div>

        <!-- Payment Details -->
        <div class="space-y-4">
          <div>
             <label class="block text-xs font-semibold text-gray-600 uppercase mb-1">Mode of Payment</label>
             <select v-model="modeOfPayment" class="w-full bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none shadow-sm">
               <option value="" disabled>Select Mode</option>
               <option v-for="mode in paymentModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
             </select>
          </div>
          
          <div>
            <label class="block text-xs font-semibold text-gray-600 uppercase mb-1">Paid Amount ({{ currency }})</label>
            <input
              type="number"
              v-model.number="paidAmount"
              @input="onPaidAmountChange"
              class="w-full bg-white border border-gray-200 rounded-xl px-3 py-2 text-lg font-bold text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none shadow-sm"
              placeholder="0.00"
            />
          </div>
        </div>

        <!-- Allocation Mode -->
        <div class="space-y-2">
          <label class="block text-xs font-semibold text-gray-600 uppercase">Allocation Type</label>
          <div class="grid grid-cols-3 gap-2">
            <button
              @click="allocationMode = 'auto'"
              class="px-3 py-2 rounded-lg text-sm font-medium transition-all"
              :class="allocationMode === 'auto' ? 'bg-blue-600 text-white shadow-md' : 'bg-white text-gray-700 border border-gray-200'"
            >
              Auto (FIFO)
            </button>
            <button
              @click="allocationMode = 'manual'"
              class="px-3 py-2 rounded-lg text-sm font-medium transition-all"
              :class="allocationMode === 'manual' ? 'bg-blue-600 text-white shadow-md' : 'bg-white text-gray-700 border border-gray-200'"
            >
              Manual
            </button>
            <button
              @click="allocationMode = 'advance'"
              class="px-3 py-2 rounded-lg text-sm font-medium transition-all"
              :class="allocationMode === 'advance' ? 'bg-blue-600 text-white shadow-md' : 'bg-white text-gray-700 border border-gray-200'"
            >
              Advance
            </button>
          </div>
          <p class="text-xs text-gray-500 mt-1">
            <span v-if="allocationMode === 'auto'">Automatically allocate to oldest invoices first</span>
            <span v-else-if="allocationMode === 'manual'">Manually select and allocate to specific invoices</span>
            <span v-else>Record as advance payment (not allocated to invoices)</span>
          </p>
        </div>

        <!-- Outstanding Invoices (only for auto and manual modes) -->
        <div v-if="allocationMode !== 'advance'" class="space-y-2">
           <div class="flex justify-between items-center">
             <label class="block text-xs font-semibold text-gray-600 uppercase">Outstanding Invoices</label>
             <span class="text-xs font-medium text-gray-500">Unallocated: {{ currency }} {{ unallocatedAmount.toFixed(2) }}</span>
           </div>
           
           <!-- Search Input for Manual Mode -->
           <div v-if="allocationMode === 'manual' && invoices.length > 0">
             <input
               type="text"
               v-model="invoiceSearchQuery"
               placeholder="Search by invoice number..."
               class="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none shadow-sm"
             />
           </div>
           
           <div v-if="loadingInvoices" class="space-y-2">
             <div class="h-16 bg-white rounded-xl animate-pulse" />
             <div class="h-16 bg-white rounded-xl animate-pulse" />
           </div>
           
           <div v-else-if="invoices.length === 0" class="bg-gray-100 rounded-xl p-4 text-center text-sm text-gray-500">
             No outstanding invoices found.
           </div>

           <div v-else class="space-y-2">
             <div
               v-for="inv in filteredInvoices"
               :key="inv.name"
               class="bg-white p-3 rounded-xl border border-gray-200 transition-all shadow-sm"
               :class="inv.checked ? 'border-blue-500 ring-1 ring-blue-500' : ''"
               @click="allocationMode === 'manual' ? toggleInvoice(inv) : null"
             >
               <div class="flex items-start gap-3">
                 <div v-if="allocationMode === 'manual'" class="pt-1">
                   <div 
                     class="w-5 h-5 rounded border flex items-center justify-center transition-colors"
                     :class="inv.checked ? 'bg-blue-600 border-blue-600' : 'border-gray-300'"
                   >
                     <svg v-if="inv.checked" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
                   </div>
                 </div>
                 <div class="flex-1">
                    <div class="flex justify-between items-start mb-2">
                       <div>
                         <p class="font-semibold text-gray-900">{{ inv.name }}</p>
                         <p class="text-xs text-gray-500">{{ inv.posting_date }}</p>
                       </div>
                    </div>

                    <div class="flex justify-between items-center text-sm bg-gray-50 p-2 rounded-lg">
                       <div>
                         <p class="text-[10px] uppercase text-gray-500 font-semibold mb-0.5">Invoice Amt</p>
                         <p class="font-medium text-gray-900">{{ currency }} {{ inv.grand_total.toFixed(2) }}</p>
                       </div>
                       <div class="text-right">
                         <p class="text-[10px] uppercase text-gray-500 font-semibold mb-0.5">Pending</p>
                         <p class="font-bold text-blue-600">{{ currency }} {{ inv.outstanding_amount.toFixed(2) }}</p>
                       </div>
                    </div>
                   
                   <div v-if="inv.checked && inv.allocated_amount > 0" class="mt-2 pt-2 border-t">
                     <div class="flex items-center justify-between">
                       <label class="text-xs font-medium text-gray-600">Allocated</label>
                       <div class="flex items-center gap-2">
                         <input
                           v-if="allocationMode === 'manual'"
                           type="number"
                           v-model.number="inv.allocated_amount"
                           class="w-24 text-right text-sm border rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 outline-none"
                           @click.stop
                           @input="validateAllocation(inv)"
                         />
                         <span v-else class="text-sm font-semibold text-blue-600">{{ currency }} {{ inv.allocated_amount.toFixed(2) }}</span>
                       </div>
                     </div>
                   </div>
                 </div>
               </div>
             </div>
           </div>
        </div>

        <!-- Advance Payment - Sales Order Selection -->
        <div v-if="allocationMode === 'advance'" class="space-y-3">
          <div class="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <div class="text-2xl">ℹ️</div>
              <div>
                <p class="text-sm font-semibold text-blue-900">Advance Payment</p>
                <p class="text-xs text-blue-700 mt-1">Optionally link this payment to a Sales Order, or leave unlinked for general advance payment.</p>
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <label class="block text-xs font-semibold text-gray-600 uppercase">Link to Sales Order (Optional)</label>
            
            <!-- Search Input for Sales Orders -->
            <div v-if="!loadingSalesOrders && salesOrders.length > 0">
              <input
                type="text"
                v-model="salesOrderSearchQuery"
                placeholder="Search by order number..."
                class="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none shadow-sm"
              />
            </div>
            
            <div v-if="loadingSalesOrders" class="space-y-2">
              <div class="h-16 bg-white rounded-xl animate-pulse" />
              <div class="h-16 bg-white rounded-xl animate-pulse" />
            </div>
            
            <div v-else-if="salesOrders.length === 0" class="bg-gray-100 rounded-xl p-4 text-center text-sm text-gray-500">
              No sales orders found for this customer.
            </div>

            <div v-else class="space-y-2">
              <button
                @click="selectedSalesOrder = null"
                class="w-full bg-white p-3 rounded-xl border transition-all text-left"
                :class="selectedSalesOrder === null ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-200'"
              >
                <div class="flex items-center gap-3">
                  <div 
                    class="w-5 h-5 rounded-full border flex items-center justify-center transition-colors"
                    :class="selectedSalesOrder === null ? 'bg-blue-600 border-blue-600' : 'border-gray-300'"
                  >
                    <div v-if="selectedSalesOrder === null" class="w-2 h-2 bg-white rounded-full"></div>
                  </div>
                  <div class="flex-1">
                    <p class="font-semibold text-gray-900">No Sales Order</p>
                    <p class="text-xs text-gray-500">General advance payment</p>
                  </div>
                </div>
              </button>

              <div
                v-for="so in filteredSalesOrders"
                :key="so.name"
                @click="selectedSalesOrder = so.name"
                class="bg-white p-3 rounded-xl border transition-all cursor-pointer"
                :class="selectedSalesOrder === so.name ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-200'"
              >
                <div class="flex items-start gap-3">
                  <div class="pt-1">
                    <div 
                      class="w-5 h-5 rounded-full border flex items-center justify-center transition-colors"
                      :class="selectedSalesOrder === so.name ? 'bg-blue-600 border-blue-600' : 'border-gray-300'"
                    >
                      <div v-if="selectedSalesOrder === so.name" class="w-2 h-2 bg-white rounded-full"></div>
                    </div>
                  </div>
                  <div class="flex-1">
                    <div class="flex justify-between items-start mb-2">
                       <div>
                         <p class="font-semibold text-gray-900">{{ so.name }}</p>
                         <p class="text-xs text-gray-500">{{ so.transaction_date }}</p>
                       </div>
                    </div>

                    <div class="flex justify-between items-center text-sm bg-gray-50 p-2 rounded-lg">
                       <div>
                         <p class="text-[10px] uppercase text-gray-500 font-semibold mb-0.5">Order Amt</p>
                         <p class="font-medium text-gray-900">{{ currency }} {{ so.grand_total.toFixed(2) }}</p>
                       </div>
                       <div class="text-right">
                         <p class="text-[10px] uppercase text-gray-500 font-semibold mb-0.5">Pending</p>
                         <p class="font-bold text-blue-600">{{ currency }} {{ (so.grand_total - (so.advance_paid || 0)).toFixed(2) }}</p>
                       </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer Actions -->
    <div class="p-4 bg-white border-t sticky bottom-0 z-10 shadow-lg">
      <button
        class="w-full bg-blue-700 text-white rounded-lg py-3 font-semibold disabled:opacity-50 disabled:cursor-not-allowed shadow-sm active:scale-[0.99] transition-transform"
        :disabled="submitting || !isValid"
        @click="submit"
      >
        {{ submitting ? 'Submitting...' : 'Create Payment' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import * as api from '../api/frappe';
import type { OutstandingInvoice, PaymentMode, PaymentReference, SalesOrderSummary, CustomerSummary } from '../types';

const store = useSessionStore();
const route = useRoute();
const router = useRouter();

const customer = computed(() => store.customer);
const currency = computed(() => store.currencyDisplay);

const modeOfPayment = ref('');
const paidAmount = ref<number | null>(null);
const invoices = ref<OutstandingInvoice[]>([]);
const salesOrders = ref<SalesOrderSummary[]>([]);
const customerSummary = ref<CustomerSummary | null>(null);
const paymentModes = ref<PaymentMode[]>([]);
const loadingInvoices = ref(false);
const loadingSalesOrders = ref(false);
const submitting = ref(false);
const allocationMode = ref<'auto' | 'manual' | 'advance'>('auto');
const selectedSalesOrder = ref<string | null>(null);
const invoiceSearchQuery = ref('');
const salesOrderSearchQuery = ref('');

const customerParam = route.query.customer as string | undefined;
const customerNameParam = route.query.customer_name as string | undefined;

onMounted(async () => {
  if (customerParam && customerNameParam) {
    store.setCustomer({ name: customerParam, customer_name: customerNameParam, customer_group: '', territory: '' });
  }
  
  try {
    paymentModes.value = await api.getPaymentModes();
    if (paymentModes.value.length) {
      modeOfPayment.value = paymentModes.value[0].name;
    }
  } catch (e) {
    console.error('Failed to load payment modes', e);
  }
  
  if (customer.value) {
    loadInvoices();
    loadSalesOrders();
    loadCustomerSummary();
  }
});

const reload = async () => {
  if (!customer.value) return;
  await Promise.all([
    loadInvoices(),
    loadSalesOrders(),
    loadCustomerSummary()
  ]);
};

const loadInvoices = async () => {
  if (!customer.value) return;
  loadingInvoices.value = true;
  try {
    const data = await api.getOutstandingInvoices(customer.value.name);
    invoices.value = data.map(inv => ({
      ...inv,
      checked: false,
      allocated_amount: 0
    }));
  } catch (e) {
    console.error('Failed to load invoices', e);
  } finally {
    loadingInvoices.value = false;
  }
};

const loadSalesOrders = async () => {
  if (!customer.value) return;
  loadingSalesOrders.value = true;
  try {
    salesOrders.value = await api.getSalesOrders(customer.value.name);
  } catch (e) {
    console.error('Failed to load sales orders', e);
  } finally {
    loadingSalesOrders.value = false;
  }
};

const loadCustomerSummary = async () => {
  if (!customer.value) return;
  try {
    customerSummary.value = await api.getCustomerSummary(customer.value.name);
  } catch (e) {
    console.error('Failed to load customer summary', e);
  }
};

const changeCustomer = () => {
  store.setCustomer(null);
  invoices.value = [];
  salesOrders.value = [];
  customerSummary.value = null;
  paidAmount.value = null;
  selectedSalesOrder.value = null;
};

const onPaidAmountChange = () => {
  if (allocationMode.value === 'auto') {
    autoAllocate();
  }
};

const autoAllocate = () => {
  if (!paidAmount.value || paidAmount.value <= 0) {
    // Clear all allocations
    invoices.value.forEach(inv => {
      inv.checked = false;
      inv.allocated_amount = 0;
    });
    return;
  }

  let remaining = paidAmount.value;
  
  // Sort by posting date (FIFO - oldest first)
  const sortedInvoices = [...invoices.value].sort((a, b) => 
    new Date(a.posting_date).getTime() - new Date(b.posting_date).getTime()
  );

  sortedInvoices.forEach(inv => {
    if (remaining <= 0) {
      inv.checked = false;
      inv.allocated_amount = 0;
    } else {
      const toAllocate = Math.min(remaining, inv.outstanding_amount);
      inv.checked = toAllocate > 0;
      inv.allocated_amount = toAllocate;
      remaining -= toAllocate;
    }
  });
};

const toggleInvoice = (inv: OutstandingInvoice) => {
  inv.checked = !inv.checked;
  if (inv.checked) {
    if (!inv.allocated_amount) inv.allocated_amount = inv.outstanding_amount;
  } else {
    inv.allocated_amount = 0;
  }
  updatePaidAmountFromSelection();
};

const validateAllocation = (inv: OutstandingInvoice) => {
  if (inv.allocated_amount && inv.allocated_amount > inv.outstanding_amount) {
    inv.allocated_amount = inv.outstanding_amount;
  }
  if (inv.allocated_amount && inv.allocated_amount < 0) {
    inv.allocated_amount = 0;
  }
  if (inv.allocated_amount === 0) {
    inv.checked = false;
  }
  updatePaidAmountFromSelection();
};

const updatePaidAmountFromSelection = () => {
  const totalAllocated = invoices.value
    .filter(i => i.checked)
    .reduce((sum, i) => sum + (i.allocated_amount || 0), 0);
    
  paidAmount.value = totalAllocated;
};

const allocatedTotal = computed(() => {
  return invoices.value
    .filter(i => i.checked)
    .reduce((sum, i) => sum + (i.allocated_amount || 0), 0);
});

const filteredInvoices = computed(() => {
  if (!invoiceSearchQuery.value.trim()) {
    return invoices.value;
  }
  const query = invoiceSearchQuery.value.toLowerCase();
  return invoices.value.filter(inv => 
    inv.name.toLowerCase().includes(query)
  );
});

const filteredSalesOrders = computed(() => {
  if (!salesOrderSearchQuery.value.trim()) {
    return salesOrders.value;
  }
  const query = salesOrderSearchQuery.value.toLowerCase();
  return salesOrders.value.filter(so => 
    so.name.toLowerCase().includes(query)
  );
});

const unallocatedAmount = computed(() => {
  return (paidAmount.value || 0) - allocatedTotal.value;
});

const isValid = computed(() => {
  if (!customer.value || !modeOfPayment.value || (paidAmount.value || 0) <= 0) {
    return false;
  }
  
  // For advance payment, just need amount
  if (allocationMode.value === 'advance') {
    return true;
  }
  
  // For auto/manual, unallocated must be >= 0
  return unallocatedAmount.value >= 0;
});

const submit = async () => {
  if (!isValid.value || !customer.value) return;
  
  submitting.value = true;
  try {
    const references: PaymentReference[] = allocationMode.value === 'advance' 
      ? [] 
      : invoices.value
          .filter(i => i.checked && (i.allocated_amount || 0) > 0)
          .map(i => ({
            name: i.name,
            grand_total: i.grand_total,
            outstanding_amount: i.outstanding_amount,
            allocated_amount: i.allocated_amount || 0
          }));
      
    await api.createPaymentEntry(
      customer.value.name,
      modeOfPayment.value,
      paidAmount.value || 0,
      references,
      allocationMode.value === 'advance' ? selectedSalesOrder.value || undefined : undefined
    );
    
    alert('Payment created successfully!');
    router.back();
  } catch (e: any) {
    alert(e.message || 'Failed to create payment');
  } finally {
    submitting.value = false;
  }
};

// Watch allocation mode changes
watch(allocationMode, (newMode) => {
  if (newMode === 'auto' && paidAmount.value) {
    autoAllocate();
  } else if (newMode === 'advance') {
    // Clear all allocations for advance payment
    invoices.value.forEach(inv => {
      inv.checked = false;
      inv.allocated_amount = 0;
    });
  }
});
</script>
