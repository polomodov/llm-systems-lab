export function reserve(items, stock) {
  for (const { sku, quantity } of items) {
    if (!Object.hasOwn(stock, sku) || stock[sku] < quantity) throw new Error('Insufficient stock');
    stock[sku] -= quantity;
  }
}
