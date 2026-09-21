import { normalize } from './basket.mjs';
import { reserve } from './inventory.mjs';

export function checkout(lines, stock) {
  const items = normalize(lines);
  reserve(items, stock);
  return { items };
}
