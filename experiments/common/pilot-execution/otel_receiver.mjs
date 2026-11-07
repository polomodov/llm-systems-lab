// Per-Trial loopback-only OTLP JSON sink. No forwarding, headers or credentials.
import http from 'node:http';
import fs from 'node:fs';
const file = '/logs/agent/hn-o01-otel.jsonl';
http.createServer(async (req, res) => {
  if (req.method !== 'POST' || req.url !== '/v1/logs' || !String(req.headers['content-type']).startsWith('application/json')) {
    res.writeHead(400); res.end(); return;
  }
  let bytes = 0; const chunks = [];
  for await (const chunk of req) {
    bytes += chunk.length;
    if (bytes > 4 * 1024 * 1024) { res.writeHead(413); res.end(); return; }
    chunks.push(chunk);
  }
  try {
    const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!Array.isArray(body.resourceLogs)) throw new Error('Expected OTLP logs');
    fs.appendFileSync(file, JSON.stringify({ received_at: new Date().toISOString(), body }) + '\n', { mode: 0o600 });
    res.writeHead(200, { 'content-type': 'application/json' }); res.end('{}');
  } catch {
    res.writeHead(400); res.end();
  }
}).listen(8769, '127.0.0.1', () => fs.writeFileSync('/logs/agent/hn-o01-otel-ready', 'ready\n'));
