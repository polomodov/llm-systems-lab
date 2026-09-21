export function createFixtureApi({ cycle = false } = {}) {
  const calls = [];
  const pages = {
    start: { records: [{ invoice_id: '0007', amount_minor: 1299, currency: 'RUB' }], next_cursor: 'empty' },
    empty: { records: [], next_cursor: 'last' },
    last: { records: [{ invoice_id: '0100', amount_minor: 201, currency: 'RUB' }], next_cursor: cycle ? 'empty' : null }
  };
  return {
    calls,
    async fetchPage(cursor) {
      if (calls.length >= 8) throw new Error('Fixture call guard exceeded');
      calls.push(cursor);
      const page = pages[cursor === null ? 'start' : cursor];
      if (!page) throw new Error('Unknown cursor');
      return structuredClone(page);
    }
  };
}
