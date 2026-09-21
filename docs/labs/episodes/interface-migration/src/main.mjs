import { createFixtureApi } from '../fixture-api.mjs';
import { loadInvoices } from './api.mjs';
import { buildReport } from './report.mjs';

const fixture = createFixtureApi();
console.log(JSON.stringify(await buildReport(loadInvoices, fixture.fetchPage)));
