export function normalize(lines) {
  if (!Array.isArray(lines)) throw new Error('Order must be an array');
  return lines.map(line => {
    if (typeof line?.sku !== 'string' || !line.sku.trim()) throw new Error('Invalid SKU');
    if (!Number.isSafeInteger(line.quantity) || line.quantity <= 0) throw new Error('Invalid quantity');
    return { sku: line.sku.trim(), quantity: line.quantity };
  });
}
