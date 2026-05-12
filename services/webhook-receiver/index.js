const express = require('express');
const app = express();

const requests = [];

// Parse raw body regardless of content-type
app.use((req, res, next) => {
  let raw = '';
  req.on('data', (chunk) => { raw += chunk.toString(); });
  req.on('end', () => {
    try {
      req.body = JSON.parse(raw);
      req.rawBody = raw;
    } catch {
      req.body = raw;
      req.rawBody = raw;
    }
    next();
  });
});

app.post('/hook', (req, res) => {
  const entry = {
    id: requests.length + 1,
    timestamp: new Date().toISOString(),
    method: req.method,
    headers: req.headers,
    body: req.body,
    rawBody: req.rawBody,
  };
  requests.push(entry);
  console.log(`[${entry.timestamp}] POST /hook — request #${entry.id}`);
  res.status(200).json({ received: true, id: entry.id });
});

app.get('/', (_req, res) => {
  const rows = requests
    .slice()
    .reverse()
    .map(
      (r) => `
    <tr>
      <td class="num">${r.id}</td>
      <td>${r.timestamp}</td>
      <td><pre>${esc(JSON.stringify(r.headers, null, 2))}</pre></td>
      <td><pre>${esc(typeof r.body === 'string' ? r.body : JSON.stringify(r.body, null, 2))}</pre></td>
    </tr>`
    )
    .join('');

  const count = requests.length;
  res.send(`<!DOCTYPE html>
<html>
<head>
  <title>Webhook Receiver</title>
  <meta http-equiv="refresh" content="5">
  <style>
    * { box-sizing: border-box; }
    body { font-family: monospace; padding: 1.5rem 2rem; background: #0f172a; color: #e2e8f0; margin: 0; }
    h1 { color: #38bdf8; margin: 0 0 0.25rem; }
    p  { color: #94a3b8; margin: 0 0 1.5rem; font-size: 0.85rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    th { text-align: left; padding: 0.5rem 0.75rem; background: #1e293b; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.7rem; }
    td { padding: 0.5rem 0.75rem; border-top: 1px solid #1e293b; vertical-align: top; }
    td.num { color: #475569; width: 2.5rem; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 8rem; overflow-y: auto; color: #cbd5e1; }
    .empty { color: #475569; text-align: center; padding: 3rem; }
    code { background: #1e293b; padding: 0 0.3rem; border-radius: 3px; }
  </style>
</head>
<body>
  <h1>Webhook Receiver</h1>
  <p>${count} request(s) captured &mdash; page refreshes every 5 s &mdash; send requests to <code>POST /hook</code></p>
  <table>
    <thead><tr><th>#</th><th>Timestamp</th><th>Headers</th><th>Body</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="4" class="empty">No requests yet. Try: curl -X POST http://localhost:8027/hook -H \'Content-Type: application/json\' -d \'{"event":"test"}\'</td></tr>'}</tbody>
  </table>
</body>
</html>`);
});

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const PORT = process.env.PORT || 8027;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Webhook receiver on http://0.0.0.0:${PORT}`);
});
