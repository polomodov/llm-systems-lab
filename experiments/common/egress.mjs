// Trusted coordinator: the agent has no external route except this gateway.
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import { lookup } from 'node:dns/promises';
import { readFileSync, appendFileSync, existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
export function publicAddress(ip) {
  const family = net.isIP(ip);
  if (family === 6) {
    const value = ip.toLowerCase();
    // Only global unicast; disallow documentation and transition/tunnelling ranges.
    return /^[23]/.test(value) && !/^2001:(0{0,3}:|db8:)/.test(value) && !value.startsWith('2002:');
  }
  if (family !== 4) return false;
  const [a,b,c] = ip.split('.').map(Number);
  return a !== 0 && a !== 10 && a !== 127 && a < 224 && !(a === 169 && b === 254) && !(a === 172 && b >= 16 && b <= 31) && !(a === 192 && b === 168) && !(a === 100 && b >= 64 && b <= 127) && !(a === 198 && [18,19].includes(b)) && !(a === 192 && b === 0 && [0,2].includes(c)) && !(a === 192 && b === 88 && c === 99) && !(a === 198 && b === 51 && c === 100) && !(a === 203 && b === 0 && c === 113);
}
async function address(host) {
  const found = await lookup(host, { all: true });
  if (!found.length || found.some(x => !publicAddress(x.address))) throw new Error('Private/reserved destination denied');
  return found[0];
}
export function normalizeUrl(raw) {
  const url = new URL(raw);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || (url.port && !['80','443'].includes(url.port))) throw new Error('Only public HTTP(S) URLs are accepted');
  url.hash = '';
  return url.href;
}
export function replayFetcher(text) {
  const records = new Map();
  for (const line of text.split('\n').filter(line => line.trim())) {
    const row = JSON.parse(line);
    if (row?.type !== 'source' || typeof row.requested_url !== 'string' || typeof row.url !== 'string' || typeof row.body !== 'string' || typeof row.content_type !== 'string' || !Number.isInteger(row.status) || row.status < 100 || row.status > 599) throw new Error('Invalid source archive record');
    const url = normalizeUrl(row.requested_url); normalizeUrl(row.url);
    if (records.has(url)) throw new Error('Duplicate source URL in replay archive');
    records.set(url, row);
  }
  if (!records.size) throw new Error('Source archive is empty');
  return async url => {
    const row = records.get(normalizeUrl(url));
    if (!row) throw new Error('Source missing from frozen replay archive');
    return row;
  };
}
export function fetchPublic(raw, redirects = 0) {
  return new Promise(async (resolve, reject) => {
    try {
      const url = new URL(normalizeUrl(raw)), ip = await address(url.hostname);
      const req = (url.protocol === 'https:' ? https : http).get(url, { lookup: (_host, _opts, cb) => cb(null, ip.address, ip.family), timeout: 20000, headers: { 'user-agent': 'harness-lab-source-snapshot/1', accept: 'text/html,text/plain,application/json' } }, res => {
        if ([301,302,303,307,308].includes(res.statusCode) && res.headers.location) {
          res.resume();
          if (redirects >= 5) return reject(new Error('Too many redirects'));
          return resolve(fetchPublic(new URL(res.headers.location, url).href, redirects + 1));
        }
        const type = res.headers['content-type'] ?? '';
        if (!/^(text\/|application\/(json|xml|xhtml\+xml))/.test(type)) { res.resume(); return reject(new Error('Only text source documents are accepted')); }
        let bytes = 0; const chunks = [];
        res.on('data', chunk => { bytes += chunk.length; if (bytes > 4 * 1024 * 1024) res.destroy(new Error('Source exceeds 4 MiB')); else chunks.push(chunk); });
        res.on('error', reject);
        res.on('end', () => resolve({ url: url.href, status: res.statusCode, content_type: type, body: Buffer.concat(chunks).toString('utf8') }));
      });
      req.on('timeout', () => req.destroy(new Error('Source timeout'))); req.on('error', reject);
    } catch (e) { reject(e); }
  });
}
export function createGateway(policy, { fetcher = fetchPublic, resolver = address, audit = () => {} } = {}) {
  const initial = new Set((policy.sources ?? []).map(normalizeUrl)), allowed = new Set(initial), cache = new Map();
  const domains = new Set(policy.connect_domains ?? []);
  const server = http.createServer(async (req, res) => {
    try {
      const endpoint = new URL(req.url, 'http://egress');
      if (req.method === 'GET' && endpoint.pathname === '/health') { res.end('ok'); return; }
      if (req.method !== 'GET' || endpoint.pathname !== '/fetch') { res.writeHead(403); res.end('GET /fetch only'); return; }
      const target = normalizeUrl(endpoint.searchParams.get('url'));
      if (!allowed.has(target)) { res.writeHead(403); res.end('URL is outside sources and depth-1 links'); return; }
      if (!cache.has(target)) {
        const pending = (async () => {
          const result = await fetcher(target);
          if (initial.has(target)) for (const match of result.body.matchAll(/href\s*=\s*["']([^"']+)["']/gi)) {
            try { allowed.add(normalizeUrl(new URL(match[1].replaceAll('&amp;', '&'), result.url).href)); } catch {}
          }
          audit({ type: 'source', requested_url: target, fetched_at: new Date().toISOString(), ...result });
          return result;
        })();
        cache.set(target, pending);
        pending.catch(() => cache.delete(target));
      }
      const result = await cache.get(target);
      res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(result));
    } catch (error) { res.writeHead(502); res.end(JSON.stringify({ error: error.message })); }
  });
  server.on('connect', async (req, client, head) => {
    let upstream;
    try {
      const match = /^([a-z0-9.-]+):443$/i.exec(req.url);
      if (!match || !domains.has(match[1].toLowerCase())) throw new Error('CONNECT domain denied');
      const ip = await resolver(match[1]);
      upstream = net.connect({ host: ip.address, port: 443 });
      upstream.once('connect', () => { client.write('HTTP/1.1 200 Connection Established\r\n\r\n'); if (head.length) upstream.write(head); upstream.pipe(client); client.pipe(upstream); });
      upstream.on('error', () => client.destroy()); client.on('error', () => upstream.destroy()); client.on('close', () => upstream.destroy());
      upstream.setTimeout(120000, () => upstream.destroy());
    } catch { upstream?.destroy(); client.end('HTTP/1.1 403 Forbidden\r\n\r\n'); }
  });
  return server;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const policy = JSON.parse(readFileSync('/control/network.json', 'utf8'));
  let auditBytes = 0;
  const replay = existsSync('/control/sources.replay.jsonl') ? replayFetcher(readFileSync('/control/sources.replay.jsonl', 'utf8')) : null;
  createGateway(policy, { ...(replay ? { fetcher: replay } : {}), audit: row => { const line = JSON.stringify(row) + '\n'; auditBytes += Buffer.byteLength(line); if (auditBytes > 64 * 1024 * 1024) throw new Error('Source archive limit exceeded'); appendFileSync('/audit/sources.jsonl', line); } }).listen(8080, '0.0.0.0');
}
