// "Ask FireCalendar": Claude answers questions using only FireCalendar's own numbers (tool use over the static JSON).
// Vercel Node function. Secrets/config (Vercel env vars, never sent to the browser):
//   ANTHROPIC_API_KEY  required
//   ASK_ENABLED        "0" = kill switch (feature off)
//   ASK_MODEL          default claude-opus-5-5
//   ASK_DAILY_CAP      max questions per day per function instance (default 300)
// Limits below are per instance (best effort). The hard money cap is the spend limit on the API key's workspace.
const Anthropic = require('@anthropic-ai/sdk');
const FC = require('../firecal-data.js');

const SITE = process.env.SITE_URL || 'https://firecalendar-ten.vercel.app';   // fixed: never fetch from the Host header
const MODEL = process.env.ASK_MODEL || 'claude-opus-5-5';
const DAILY_CAP = +(process.env.ASK_DAILY_CAP || 300);
const PER_IP_MIN = 4, PER_IP_DAY = 30, MAX_Q = 500, MAX_STEPS = 6;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// ---------- data (cached per instance) ----------
const cache = new Map();
async function getJSON(path) {
  if (cache.has(path)) return cache.get(path);
  const r = await fetch(`${SITE}/data/${path}`);
  if (!r.ok) throw new Error(`no data for ${path}`);
  const j = await r.json(); cache.set(path, j); return j;
}
const meta = () => getJSON('meta.json');
const areas = () => getJSON('india/areas.json');
async function area(id) {
  if (!/^(state|district)-\d+$/.test(id || '')) throw new Error('unknown area_id; use find_area first');
  return getJSON(`india/areas/${id}.json`);
}
const r1 = x => x == null ? null : Math.round(x * 10) / 10;

// ---------- tools ----------
const TOOLS = [
  {
    name: 'find_area', description: 'Find Indian states or districts by name. Returns up to 8 matches with area_id.',
    input_schema: { type: 'object', properties: { query: { type: 'string', description: 'Place name, e.g. "Sangrur" or "Odisha"' } }, required: ['query'], additionalProperties: false },
  },
  {
    name: 'get_area_overview',
    description: 'Overview of one area: yearly fire totals with uncertainty, the normal (median 2003-2021) for each calendar month, fire seasons with onset trend, blind-spot test, 4-week outlook from history, data dates.',
    input_schema: { type: 'object', properties: { area_id: { type: 'string' } }, required: ['area_id'], additionalProperties: false },
  },
  {
    name: 'get_month',
    description: 'One month in one area compared with the same month in other years: value, likely range, median, average, percentile, label, how it was measured.',
    input_schema: { type: 'object', properties: { area_id: { type: 'string' }, year: { type: 'integer' }, month: { type: 'integer', description: '1-12' } }, required: ['area_id', 'year', 'month'], additionalProperties: false },
  },
  {
    name: 'get_monthly_series',
    description: 'Monthly values for one area between two months (inclusive, max 72 months), with raw counts per satellite.',
    input_schema: { type: 'object', properties: { area_id: { type: 'string' }, from: { type: 'string', description: 'YYYY-MM' }, to: { type: 'string', description: 'YYYY-MM' } }, required: ['area_id', 'from', 'to'], additionalProperties: false },
  },
];

async function runTool(name, input) {
  if (name === 'find_area') {
    const q = String(input.query || '').toLowerCase().trim();
    const all = await areas();
    const rank = a => (a.name.toLowerCase() === q ? 0 : 2) + (a.kind === 'state' ? 0 : 1);
    const hits = all.filter(a => `${a.name}, ${a.state}`.toLowerCase().includes(q)).sort((a, b) => rank(a) - rank(b));
    return { matches: hits.slice(0, 8).map(a => ({ area_id: a.id, name: a.name, state: a.state, kind: a.kind })) };
  }
  const M = await meta(), A = await area(input.area_id);
  const d = FC.buildResponse(A, M, null, null);
  const base = { area: d.name, data_through: d.data_end, provisional_from: d.provisional_from,
    unfinished_month: d.partial ? `${d.partial[0]}-${String(d.partial[1]).padStart(2, '0')}` : null };
  if (name === 'get_area_overview') {
    const bs = d.blind_spot;
    return { ...base, unit: 'MODIS-equivalent fire detections', total_detections_all_satellites_since_2000: d.n_points,
      yearly: d.yearly.map(y => ({ year: y.year, value: r1(y.value), lo: r1(y.lo), hi: r1(y.hi) })),
      normal_by_month_median_2003_2021: Object.fromEntries(d.climatology.median.map((v, i) => [MONTHS[i], r1(v)])),
      seasons: (d.season?.seasons || []).map(s => ({ label: s.label, share_of_year: s.share, typical_day_of_season: s.typical,
        onset_trend_days_per_decade: s.onset_trend })),
      blind_spot: bs && { peak_months: bs.peak_months, warning: !!bs.flag,
        note: 'In the peak months: relative = Aqua MODIS detections per S-NPP VIIRS detection, divided by the 2012-19 normal. VIIRS passes ~13:30 IST every year; Aqua has drifted later (aqua_time_ist). relative > 1 means the LATER Aqua pass now sees MORE fires than usual compared with the 13:30 pass, i.e. the 13:30 pass misses a growing share of burning (consistent with burning moving later in the afternoon). warning=true when a year since 2023 has relative >= 1.5.',
        years: (bs.years || []).slice(-8) },
      outlook_next_4_weeks_from_history: d.outlook };
  }
  if (name === 'get_month') {
    const y = +input.year, m = +input.month;
    const dd = FC.buildResponse(A, M, y, m);
    const row = dd.monthly.find(r => r.date === `${y}-${String(m).padStart(2, '0')}`);
    const a = dd.anomaly;
    return { ...base, month: `${MONTHS[m - 1]} ${y}`, value: r1(a.value), likely_range: row && [r1(row.lo), r1(row.hi)],
      median_same_month: r1(a.median), average_same_month: r1(a.mean), ratio_to_median: a.ratio == null ? null : Math.round(a.ratio * 100) / 100,
      percentile: a.percentile, label: a.label, years_compared: a.n_years, method: row?.method,
      raw: row && { terra: row.terra, aqua: row.aqua, snpp_viirs: row.snpp, noaa20_viirs: row.n20 } };
  }
  if (name === 'get_monthly_series') {
    const rows = d.monthly.filter(r => r.date >= input.from && r.date <= input.to).slice(0, 72);
    return { ...base, months: rows.map(r => ({ month: r.date, value: r1(r.value), lo: r1(r.lo), hi: r1(r.hi), method: r.method,
      terra: r.terra, aqua: r.aqua, snpp: r.snpp, n20: r.n20 })) };
  }
  throw new Error('unknown tool');
}

const SYSTEM = `You are "Ask FireCalendar", the assistant inside FireCalendar, a web app that harmonizes NASA MODIS and VIIRS satellite fire detections for India (Dec 2000 to the data_through date) into one unit: MODIS-equivalent fire detections.

Rules:
- Use ONLY numbers returned by your tools. Never invent or estimate numbers, places, causes or dates. If the tools can't answer, say so plainly.
- A "fire" here means a satellite-flagged pixel per pass, not a fire on the ground. Say this when it matters.
- Mention uncertainty (likely range) when you give a value from VIIRS-translated or Terra-adjusted months.
- Months from provisional_from onward are near-real-time (provisional). The unfinished month is incomplete; never compare it with history as if complete.
- Blind-spot results are "consistent with" fires being lit after the satellites pass (ISRO and iFOREST reports for Punjab/Haryana); never say they prove it.
- Only answer questions about fire activity in India from this data. Politely decline anything else.
- Reply in the language of the question (English, Hindi, Telugu, ...). Be brief: at most 120 words, plain text, no tables, no markdown headings.`;

// ---------- abuse limits (per instance) ----------
const hits = new Map(); let day = '', dayCount = 0;
function allowed(ip) {
  const now = Date.now(), today = new Date().toISOString().slice(0, 10);
  if (today !== day) { day = today; dayCount = 0; hits.clear(); }
  if (dayCount >= DAILY_CAP) return 'FireCalendar has answered its daily limit of questions. Please try again tomorrow.';
  const h = (hits.get(ip) || []).filter(t => now - t < 864e5);
  if (h.length >= PER_IP_DAY) return 'You have reached today\'s question limit.';
  if (h.filter(t => now - t < 6e4).length >= PER_IP_MIN) return 'Too many questions in a minute. Please wait a moment.';
  h.push(now); hits.set(ip, h); dayCount++; return null;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  if (process.env.ASK_ENABLED === '0' || !process.env.ANTHROPIC_API_KEY) return res.status(503).json({ error: 'Ask FireCalendar is switched off right now.' });
  const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
  const question = String(body.question || '').trim().slice(0, MAX_Q);
  if (!question) return res.status(400).json({ error: 'Empty question.' });
  const ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'unknown';
  const block = allowed(ip); if (block) return res.status(429).json({ error: block });

  // what the user is looking at (optional): helps "here" / "this month"
  const ctx = body.context || {};
  const where = /^(state|district)-\d+$/.test(ctx.area_id || '') ? `The user is viewing area_id ${ctx.area_id} (${String(ctx.name || '').slice(0, 80)})` : 'The user has not selected a state or district (a drawn area cannot be queried; ask them to pick a state or district)';
  const when = Number.isInteger(ctx.year) && Number.isInteger(ctx.month) ? `, month ${ctx.year}-${String(ctx.month).padStart(2, '0')}.` : '.';
  const history = (Array.isArray(body.history) ? body.history : []).slice(-4)
    .filter(t => t && (t.role === 'user' || t.role === 'assistant') && typeof t.text === 'string')
    .map(t => ({ role: t.role, content: t.text.slice(0, 1200) }));
  if (history.length && history[0].role !== 'user') history.shift();
  const messages = [...history, { role: 'user', content: `${where}${when}\n\nQuestion: ${question}` }];

  const client = new Anthropic();
  const used = [];
  try {
    for (let step = 0; step < MAX_STEPS; step++) {
      const r = await client.beta.messages.create({
        model: MODEL, max_tokens: 2000, system: SYSTEM, tools: TOOLS, messages,
        output_config: { effort: 'low' },
        betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default',
      });
      if (r.stop_reason === 'refusal') return res.status(200).json({ answer: 'Sorry, I can\'t help with that. Ask me about fire activity in an Indian state or district.', tools: used });
      if (r.stop_reason !== 'tool_use') {
        const answer = r.content.filter(b => b.type === 'text').map(b => b.text).join('\n').trim();
        return res.status(200).json({ answer: answer || 'Sorry, I could not find an answer in FireCalendar\'s data.', tools: used, model: r.model });
      }
      messages.push({ role: 'assistant', content: r.content });
      const results = [];
      for (const b of r.content.filter(b => b.type === 'tool_use')) {
        used.push({ name: b.name, input: b.input });
        try { results.push({ type: 'tool_result', tool_use_id: b.id, content: JSON.stringify(await runTool(b.name, b.input)) }); }
        catch (e) { results.push({ type: 'tool_result', tool_use_id: b.id, content: String(e.message || e), is_error: true }); }
      }
      messages.push({ role: 'user', content: results });
    }
    return res.status(200).json({ answer: 'Sorry, that question needed too many steps. Try asking about one area and one month.', tools: used });
  } catch (e) {
    console.error('ask failed', e?.status, e?.message);
    const busy = e instanceof Anthropic.RateLimitError || (e?.status >= 500);
    return res.status(busy ? 503 : 500).json({ error: busy ? 'Claude is busy right now. Please try again in a minute.' : 'Something went wrong answering that.' });
  }
};
