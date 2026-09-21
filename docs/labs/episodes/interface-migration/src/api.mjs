export async function loadInvoices(fetchPage) {
  const payload = await fetchPage(null);
  return payload.items ?? [];
}
