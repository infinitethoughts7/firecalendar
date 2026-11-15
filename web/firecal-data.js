/* FireCalendar static data layer.
   Turns precomputed JSON (web/data/, built by firecal/export_static.py) into the same object the
   FastAPI /api/query endpoint returns, so the page needs no server.  Mirrors firecal/engine.py + firecal/app.py;
   test/compare_static.js checks the two agree. */
(function (root) {
  const METHOD = { t: 'terra-adjusted', m: 'modis-measured', v: 'viirs-translated' };
  const r1 = x => x == null || !isFinite(x) ? null : Math.round(x * 10) / 10;
  const ym = (y, m) => `${y}-${String(m).padStart(2, '0')}`;
  const addMonths = (start, k) => { const [y, m] = start.split('-').map(Number); const t = y * 12 + (m - 1) + k; return [Math.floor(t / 12), t % 12 + 1]; };
  const median = a => { if (!a.length) return NaN; const s = [...a].sort((x, y) => x - y), h = s.length >> 1; return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2; };
  const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN;

  // ---- monthly table from columnar arrays -------------------------------------------------------------
  function monthlyRows(M, meta) {
    const rows = [];
    for (let i = 0; i < M.value.length; i++) {
      const [y, m] = addMonths(M.start, i), code = M.method[i], v = M.value[i], rel = meta.rel_err[code];
      rows.push({ date: ym(y, m), y, m, value: v, lo: r1(v * (1 - rel)), hi: r1(v * (1 + rel)), method: METHOD[code],
        terra: M.terra[i], aqua: M.aqua[i], snpp: M.snpp[i], n20: M.n20[i], modis: M.terra[i] + M.aqua[i], viirs_eq: M.viirs_eq[i] });
    }
    return rows;
  }

  function calendarOf(rows) {
    const y0 = rows[0].y, y1 = rows[rows.length - 1].y, years = [], values = [];
    for (let y = y0; y <= y1; y++) { years.push(y); values.push(new Array(12).fill(null)); }
    rows.forEach(r => { values[r.y - y0][r.m - 1] = (values[r.y - y0][r.m - 1] || 0) + r.value; });
    return { years, values };
  }

  function climatology(cal, a = 2003, b = 2021) {
    return Array.from({ length: 12 }, (_, j) => {
      const v = cal.years.map((y, i) => [y, cal.values[i][j]]).filter(([y, x]) => y >= a && y <= b && x != null).map(([, x]) => x);
      return v.length ? r1(median(v)) : null;
    });
  }

  // same rules as Engine.anomaly
  // partial = [year, month] of an unfinished last month: never used as history, flagged when it is the target
  function anomaly(cal, year, month, firstFull = 2003, partial = null) {
    const yi = cal.years.indexOf(year), cur = cal.values[yi][month - 1];
    const isPartial = (y, m) => partial && y === partial[0] && m === partial[1];
    let base = cal.years.map((y, i) => [y, cal.values[i][month - 1]]).filter(([y, v]) => y >= firstFull && y !== year && v != null && !isPartial(y, month));
    const earlier = base.filter(([y]) => y < year);
    if (earlier.length >= 8) base = earlier;
    const vals = base.map(([, v]) => v), med = median(vals);
    const pct = (vals.filter(v => v < cur).length / vals.length + 0.5 * vals.filter(v => v === cur).length / vals.length) * 100;
    const ratio = med > 0 ? cur / med : null;
    let label;
    if (isPartial(year, month)) label = 'month not finished yet';
    else if (med < 3 && cur < 3) label = 'too little fire to compare';
    else label = pct >= 90 ? 'much higher than usual' : pct >= 75 ? 'higher than usual' : pct <= 10 ? 'much lower than usual' : pct <= 25 ? 'lower than usual' : 'normal';
    return { year, month, value: cur, median: med, mean: mean(vals), ratio, percentile: pct, label, n_years: vals.length,
      base_years: [Math.min(...base.map(b => b[0])), Math.max(...base.map(b => b[0]))] };
  }

  // default = peak month of the latest full calendar year (as app.py)
  function defaultMonth(rows) {
    const end = rows[rows.length - 1], full = end.m === 12 ? end.y : end.y - 1;
    const yr = rows.filter(r => r.y === full);
    if (!yr.length || Math.max(...yr.map(r => r.value)) <= 0) return [end.y, end.m];
    const p = yr.reduce((a, b) => b.value > a.value ? b : a);
    return [p.y, p.m];
  }

  function yearly(rows) {
    const out = new Map();
    rows.forEach(r => {
      const o = out.get(r.y) || { year: r.y, value: 0, lo: 0, hi: 0, modis: 0, viirs_eq: 0 };
      o.value += r.value; o.lo += r.lo; o.hi += r.hi; o.modis += r.modis; o.viirs_eq += r.viirs_eq || 0; out.set(r.y, o);
    });
    return [...out.values()].map(o => ({ year: o.year, value: r1(o.value), lo: r1(o.lo), hi: r1(o.hi), modis: r1(o.modis), viirs_eq: r1(o.viirs_eq) }));
  }

  // next `weeks` weeks from `today` (IST) using the 366-row MM-DD table (Feb 29 frame = 2024)
  function outlookFrom(T, today, weeks = 4) {
    if (!T) return null;
    const d0 = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()), iso = t => new Date(t).toISOString().slice(0, 10);
    const rows = [];
    for (let w = 0; w < weeks; w++) {
      const a = d0 + 7 * w * 864e5, da = new Date(a);
      const idx = Math.round((Date.UTC(2024, da.getUTCMonth(), da.getUTCDate()) - Date.UTC(2024, 0, 1)) / 864e5);
      const [p10, med, p90, recent] = T.rows[idx];
      rows.push({ start: iso(a), end: iso(a + 6 * 864e5), p10, median: med, p90, recent });
    }
    return { from_date: iso(d0), weeks: rows, base_years: T.base_years };
  }
  const todayIST = () => new Date(Date.now() + 5.5 * 3600e3);

  function buildResponse(A, meta, year, month) {
    const rows = monthlyRows(A.monthly, meta), cal = calendarOf(rows);
    let [y, m] = defaultMonth(rows);
    if (year) { y = year; m = month; }
    if (!cal.years.includes(y)) throw new Error('year out of range');
    return {
      name: A.label || A.name, country: A.country, n_points: A.n_points, approx: !!A.approx,
      monthly: rows.map(({ y, m, ...r }) => r), calendar: cal, climatology: { median: climatology(cal) },
      anomaly: anomaly(cal, y, m, 2003, meta.partial), yearly: yearly(rows), blind_spot: A.blind_spot, season: A.season,
      outlook: outlookFrom(A.outlook_table, todayIST()), sensors: meta.sensors, data_end: meta.data_end,
      provisional_from: meta.provisional_from, partial: meta.partial,
    };
  }

  // ---- drawn areas: sum 0.5 deg grid cells whose centre is inside the polygon (approximate) ---------------
  function inRing(x, y, ring) {
    let c = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
    }
    return c;
  }
  function inGeom(x, y, g) {
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
    return polys.some(p => inRing(x, y, p[0]) && !p.slice(1).some(h => inRing(x, y, h)));
  }

  // grid cells whose centre is inside the shape; a shape smaller than a cell gets the cell under its centre
  function cellsOf(G, geom) {
    const h = G.cell / 2, cells = new Set();
    for (let i = 0; i < G.n; i++) if (inGeom(G.cx[i] + h, G.cy[i] + h, geom)) cells.add(G.cy[i] + ',' + G.cx[i]);
    if (!cells.size) {
      const pts = (geom.type === 'Polygon' ? geom.coordinates[0] : geom.coordinates[0][0]);
      const cx = mean(pts.map(p => p[0])), cy = mean(pts.map(p => p[1]));
      cells.add(Math.floor(cy / G.cell) * G.cell + ',' + Math.floor(cx / G.cell) * G.cell);
    }
    return cells;
  }

  function drawnArea(G, meta, geom) {
    const cells = cellsOf(G, geom);
    const [ey, em] = meta.data_end.split('-').map(Number), [y0, m0] = G.month0.split('-').map(Number);
    const N = (ey - y0) * 12 + (em - m0) + 1;
    const Z = () => new Float64Array(N);
    const S = { terra: Z(), aqua: Z(), snpp: Z(), n20: Z(), terra_eq: Z(), snpp_eq: Z(), n20_eq: Z(), aqua_day: Z(), snpp_day: Z(), aqua_ist_sum: Z() };
    let npts = 0;
    for (let i = 0; i < G.n; i++) {
      if (!cells.has(G.cy[i] + ',' + G.cx[i]) || G.t[i] >= N) continue;
      for (const k in S) S[k][G.t[i]] += G[k][i];
      npts += G.terra[i] + G.aqua[i] + G.snpp[i] + G.n20[i];
    }
    const st = meta.sensors.starts, mi = (y, m) => (y - y0) * 12 + (m - m0);
    const iA = mi(...st.aqua), iS = mi(...st.snpp), iN = mi(...st.n20), iStable = mi(meta.sensors.modis_stable_end, 12);
    const [sy, sm] = meta.sensors.snpp_end.split('-').map(Number), iSend = mi(sy, sm);   // S-NPP ended 2 Nov 2026: from that month use NOAA-20 only (approx.)
    const M = { start: G.month0, value: [], method: '', terra: [], aqua: [], snpp: [], n20: [], viirs_eq: [] };
    for (let t = 0; t < N; t++) {
      const hs = t >= iS && t < iSend, hn = t >= iN;
      const v = hs && hn ? (S.snpp_eq[t] + S.n20_eq[t]) / 2 : hs ? S.snpp_eq[t] : S.n20_eq[t];
      const code = t < iA ? 't' : t <= iStable ? 'm' : 'v';
      M.value.push(r1(code === 't' ? S.terra_eq[t] : code === 'm' ? S.terra[t] + S.aqua[t] : v)); M.method += code;
      ['terra', 'aqua', 'snpp', 'n20'].forEach(k => M[k].push(S[k][t]));
      M.viirs_eq.push(hs || hn ? r1(v) : null);
    }
    const A = { name: 'Drawn area', label: 'Your drawn area', country: meta.countries[0], n_points: npts, monthly: M, approx: true,
      n_cells: cells.size, season: { seasons: [], drawn: true }, outlook_table: null };
    A.blind_spot = blindSpot(S, monthlyRows(M, meta), y0, m0);
    return A;
  }

  // port of app.blind_spot on grid sums (Aqua pass time = mean, not median, of daytime detections)
  function blindSpot(S, rows, y0, m0) {
    const clim = climatology(calendarOf(rows));
    const peak = clim.map((v, j) => [v == null ? -Infinity : v, j + 1]).sort((a, b) => b[0] - a[0]).slice(0, 2).map(x => x[1]);
    const by = new Map();
    for (let t = 0; t < S.aqua_day.length; t++) {
      const y = y0 + Math.floor((m0 - 1 + t) / 12), m = (m0 - 1 + t) % 12 + 1;
      if (y < 2012 || !peak.includes(m)) continue;
      const o = by.get(y) || { aqua: 0, snpp: 0, ist: 0 };
      o.aqua += S.aqua_day[t]; o.snpp += S.snpp_day[t]; o.ist += S.aqua_ist_sum[t]; by.set(y, o);
    }
    const ys = [...by.entries()].filter(([, o]) => o.aqua + o.snpp > 0).sort((a, b) => a[0] - b[0]);
    if (!ys.length || !ys.some(([, o]) => o.aqua > 0) || !ys.some(([, o]) => o.snpp > 0)) return null;
    const r = new Map(ys.map(([y, o]) => [y, o.snpp > 0 ? o.aqua / o.snpp : NaN]));
    const base = mean([...r.entries()].filter(([y, v]) => y >= 2012 && y <= 2019 && isFinite(v)).map(([, v]) => v));
    const years = ys.map(([y, o]) => ({ year: y, aqua: o.aqua, snpp: o.snpp, aqua_time_ist: o.aqua ? Math.round(o.ist / o.aqua * 100) / 100 : null,
      relative: base && isFinite(r.get(y)) ? Math.round(r.get(y) / base * 100) / 100 : null }));
    const recent = years.filter(x => x.year >= 2023 && x.aqua >= 50);
    return { peak_months: peak.sort((a, b) => a - b), years, flag: recent.length > 0 && Math.max(...recent.map(x => x.relative || 0)) >= 1.5 };
  }

  // ---- CSV (same columns as /api/csv); optional month range 'YYYY-MM' (inclusive) ---------------------------
  const inRange = (date, from, to) => (!from || date >= from) && (!to || date <= to);
  const q = s => /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s, f1 = v => v == null ? '' : String(Math.round(v * 10) / 10);
  function toCsv(d, meta, from, to) {
    const rel = { 'terra-adjusted': meta.rel_err.t, 'modis-measured': 0, 'viirs-translated': meta.rel_err.v };
    const f = f1;
    const head = 'area,month,raw_terra_modis,raw_aqua_modis,raw_snpp_viirs,raw_noaa20_viirs,raw_modis_total,method,fires_modis_equivalent,rel_err,low_estimate,high_estimate,viirs_translated_modis_eq';
    return [head, ...d.monthly.filter(r => inRange(r.date, from, to)).map(r => [q(d.name), r.date, r.terra, r.aqua, r.snpp, r.n20, r.modis, r.method, f(r.value), f(rel[r.method]), f(r.lo), f(r.hi), f(r.viirs_eq)].join(','))].join('\n') + '\n';
  }

  // yearly totals within the range; n_months says how many months of that year are included
  function yearlyCsv(d, from, to) {
    const by = new Map();
    d.monthly.filter(r => inRange(r.date, from, to)).forEach(r => {
      const y = +r.date.slice(0, 4), o = by.get(y) || { n: 0, value: 0, lo: 0, hi: 0, terra: 0, aqua: 0, snpp: 0, n20: 0, methods: new Set() };
      o.n++; o.value += r.value; o.lo += r.lo; o.hi += r.hi; o.terra += r.terra; o.aqua += r.aqua; o.snpp += r.snpp; o.n20 += r.n20; o.methods.add(r.method); by.set(y, o);
    });
    const head = 'area,year,n_months,fires_modis_equivalent,low_estimate,high_estimate,raw_terra_modis,raw_aqua_modis,raw_snpp_viirs,raw_noaa20_viirs,methods';
    return [head, ...[...by].map(([y, o]) => [q(d.name), y, o.n, f1(o.value), f1(o.lo), f1(o.hi), o.terra, o.aqua, o.snpp, o.n20, [...o.methods].join('|')].join(','))].join('\n') + '\n';
  }

  // hotspot counts per 0.5 deg grid cell x month x satellite for the cells covering the area (approximate)
  function cellsCsv(G, geom, name, from, to) {
    const cells = cellsOf(G, geom), [y0, m0] = G.month0.split('-').map(Number), out = [];
    const head = 'area,cell_lat_min,cell_lon_min,cell_size_deg,month,raw_terra_modis,raw_aqua_modis,raw_snpp_viirs,raw_noaa20_viirs,modis_eq_from_terra,modis_eq_from_snpp,modis_eq_from_noaa20';
    for (let i = 0; i < G.n; i++) {
      if (!cells.has(G.cy[i] + ',' + G.cx[i])) continue;
      const t = y0 * 12 + (m0 - 1) + G.t[i], date = ym(Math.floor(t / 12), t % 12 + 1);
      if (!inRange(date, from, to)) continue;
      out.push([q(name), G.cy[i], G.cx[i], G.cell, date, G.terra[i], G.aqua[i], G.snpp[i], G.n20[i], G.terra_eq[i], G.snpp_eq[i], G.n20_eq[i]].join(','));
    }
    return [head, ...out].join('\n') + '\n';
  }

  // raw hotspot points: 1 deg tile x year gzipped CSVs (GitHub Pages), filtered to the shape and month range
  async function pointsCsv(index, base, geom, name, from, to, onProgress, limit = 2000000) {
    const xy = [];
    (geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates).forEach(p => p[0].forEach(c => xy.push(c)));
    const lo = [Math.min(...xy.map(c => c[0])), Math.min(...xy.map(c => c[1]))], hi = [Math.max(...xy.map(c => c[0])), Math.max(...xy.map(c => c[1]))];
    const y0 = from ? +from.slice(0, 4) : 0, y1 = to ? +to.slice(0, 4) : 9999, keys = [];
    for (const k of Object.keys(index.tiles)) {
      const [yr, t] = k.split('/'), [ty, tx] = t.split('_').map(Number);
      if (+yr >= y0 && +yr <= y1 && ty >= Math.floor(lo[1]) && ty <= Math.floor(hi[1]) && tx >= Math.floor(lo[0]) && tx <= Math.floor(hi[0])) keys.push(k);
    }
    const est = keys.reduce((s, k) => s + index.tiles[k], 0);
    if (est > limit) throw new Error(`about ${Math.round(est / 1e3).toLocaleString()} thousand points in the tiles covering this area and range; please narrow the date range (limit ${(limit / 1e6)} million)`);
    const rows = []; let done = 0;
    const one = async k => {
      const r = await fetch(`${base}/${k}.csv.gz`); if (!r.ok) throw new Error(`could not load points ${k} (${r.status})`);
      const txt = await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text();
      const lines = txt.split('\n');
      for (let i = 1; i < lines.length; i++) {
        const L = lines[i]; if (!L) continue;
        const c = L.split(','), m = c[2].slice(0, 7);
        if ((from && m < from) || (to && m > to)) continue;
        if (inGeom(+c[1], +c[0], geom)) rows.push(L);
      }
      onProgress && onProgress(++done, keys.length);
    };
    for (let i = 0; i < keys.length; i += 8) await Promise.all(keys.slice(i, i + 8).map(one));
    rows.sort((a, b) => { const A = a.split(','), B = b.split(','); return (A[2] + A[3]).localeCompare(B[2] + B[3]); });
    return { n: rows.length, csv: 'area,' + index.columns.join(',') + '\n' + rows.map(L => q(name) + ',' + L).join('\n') + '\n' };
  }

  const api = { buildResponse, drawnArea, toCsv, yearlyCsv, cellsCsv, pointsCsv, cellsOf, anomaly, calendarOf, monthlyRows, outlookFrom, inGeom };
  if (typeof module !== 'undefined') module.exports = api; else root.FC = api;
})(this);
