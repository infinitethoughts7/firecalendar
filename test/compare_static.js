// node test/compare_static.js  — static adapter (web/firecal-data.js + web/data) must match the live API (port 8765)
const FC = require('../web/firecal-data.js'), fs = require('fs');
const meta = JSON.parse(fs.readFileSync('web/data/meta.json'));
const ids = process.argv.slice(2).length ? process.argv.slice(2) : ['state-8', 'district-499', 'district-296', 'state-20', 'district-231', 'state-19'];
const cases = [[null, null], [2024, 11], [2010, 4], [2025, 3], [2003, 1]];
let bad = 0, n = 0;
const near = (a, b, tol) => (a == null && b == null) || (a != null && b != null && Math.abs(a - b) <= tol);
(async () => {
  for (const id of ids) {
    const A = JSON.parse(fs.readFileSync(`web/data/india/areas/${id}.json`));
    for (const [y, m] of cases) {
      const body = { id }; if (y) { body.year = y; body.month = m; }
      const api = await (await fetch('http://127.0.0.1:8765/api/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json();
      const st = FC.buildResponse(A, meta, y, m); n++;
      const errs = [];
      const aa = api.anomaly, sa = st.anomaly;
      if (aa.year !== sa.year || aa.month !== sa.month) errs.push(`default ${aa.year}-${aa.month} vs ${sa.year}-${sa.month}`);
      if (aa.label !== sa.label) errs.push(`label ${aa.label} vs ${sa.label}`);
      if (!near(aa.value, sa.value, 0.06) || !near(aa.median, sa.median, 0.06) || !near(aa.percentile, sa.percentile, 0.01)) errs.push(`anomaly ${JSON.stringify([aa.value, aa.median, aa.percentile])} vs ${JSON.stringify([sa.value, sa.median, sa.percentile])}`);
      if (api.monthly.length !== st.monthly.length) errs.push('monthly length');
      api.monthly.forEach((r, i) => { const s = st.monthly[i]; if (r.date !== s.date || r.method !== s.method || !near(r.value, s.value, 0.06) || !near(r.lo, s.lo, 0.11) || r.terra !== s.terra || r.n20 !== s.n20 || !near(r.viirs_eq, s.viirs_eq, 0.06)) errs.push(`month ${r.date}`); });
      api.yearly.forEach((r, i) => { if (!near(r.value, st.yearly[i].value, 1)) errs.push(`year ${r.year} ${r.value} vs ${st.yearly[i].value}`); });
      if (JSON.stringify(api.blind_spot) !== JSON.stringify(st.blind_spot)) errs.push('blind_spot');
      if (JSON.stringify(api.season) !== JSON.stringify(st.season)) errs.push('season');
      if (JSON.stringify(api.outlook.weeks.map(w => [w.start, w.median, w.p10, w.p90, w.recent])) !== JSON.stringify(st.outlook.weeks.map(w => [w.start, w.median, w.p10, w.p90, w.recent]))) errs.push('outlook');
      if (errs.length) { bad++; console.log('FAIL', id, y, m, errs.slice(0, 4).join(' | ')); }
    }
  }
  console.log(`${n - bad}/${n} cases match`); process.exit(bad ? 1 : 0);
})();
