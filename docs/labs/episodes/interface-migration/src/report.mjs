export async function buildReport(loadInvoices, fetchPage) {
  const invoices = await loadInvoices(fetchPage);
  return {
    invoiceIds: invoices.map(invoice => Number(invoice.id)),
    count: invoices.length,
    totalMinor: invoices.reduce((sum, invoice) => sum + invoice.amount, 0),
    currency: 'RUB'
  };
}
