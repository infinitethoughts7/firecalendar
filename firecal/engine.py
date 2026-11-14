"""FireCalendar engine: area -> harmonized (MODIS-equivalent) daily/monthly series, calendar, anomaly."""
import duckdb, json, os, numpy as np, pandas as pd
from shapely import contains_xy
from shapely.geometry import shape, box
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
P = f"{ROOT}/data/processed"
SNPP_END = pd.Timestamp("2026-11-02")      # S-NPP fire data production ceased 2 Nov 2026 (FIRMS FAQ)

class Engine:
    def __init__(self, country="India"):
        k = country.lower()
        files = [f"{P}/fires_{k}.parquet"] + ([f"{P}/fires_{k}_2026.parquet"] if os.path.exists(f"{P}/fires_{k}_2026.parquet") else [])
        self.country, self.files = country, files
        self.fires = "read_parquet([" + ",".join(f"'{f}'" for f in files) + "], union_by_name=true)"   # archive + 2026
        x = json.load(open(f"{P}/fires_{k}_2026.json")) if len(files) > 1 else {}
        self.provisional_from = min(x["provisional_from"].values()) if x.get("provisional_from") else None
        self.err = json.load(open(f"{P}/errors_{k}.json"))
        self.cell = self.err["cell_deg"]; self.stable_end = self.err["stable_end"]
        f = pd.read_parquet(f"{P}/factors_{k}.parquet")
        self.fac = {s: f[f.src == s].drop(columns="src") for s in ["terra", "snpp", "n20"]}
        self.mo = {s: pd.read_parquet(f"{P}/monthratio_{s}_{k}.parquet").drop(columns="src") for s in ["terra", "snpp", "n20"]}
        self.db = duckdb.connect(); self.db.execute("SET memory_limit='2GB'")
        ay, am = self.err["starts"]["aqua"]; self.aqua_start = pd.Timestamp(ay, am, 1)
        end, x0, y0, x1, y1 = self.db.execute(f"SELECT max(date), min(lon), min(lat), max(lon), max(lat) FROM {self.fires}").fetchone()
        self.data_end = pd.Timestamp(end)          # same time axis for every area
        me = self.data_end + pd.offsets.MonthEnd(0)
        self.partial = (self.data_end.year, self.data_end.month) if self.data_end < me else None   # last month incomplete
        self.bounds = (x0, y0, x1, y1)             # country data extent, used to reject drawn areas elsewhere

    def points(self, geom):
        """vegetation-fire points (low confidence removed) inside a shapely geometry."""
        x0, y0, x1, y1 = geom.bounds
        df = self.db.execute(f"""SELECT lat, lon, date, satellite, sensor, time_utc, frp FROM {self.fires}
            WHERE type=0 AND conf_class<>'low' AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?""", [y0, y1, x0, x1]).df()
        if not geom.equals(box(x0, y0, x1, y1)):
            df = df[contains_xy(geom, df.lon.values, df.lat.values)]
        return df

    def _weights(self, df):
        """MODIS-equivalent weight for each point, by its satellite, 0.5° cell and month."""
        df = df.copy(); c = self.cell
        df["cy"] = np.floor(df.lat / c) * c; df["cx"] = np.floor(df.lon / c) * c
        df["mo"] = pd.to_datetime(df.date).dt.month; df["w"] = np.nan
        for sat, src in [("Terra", "terra"), ("N", "snpp"), ("N20", "n20")]:
            m = df.satellite == sat
            if not m.any(): continue
            t = df.loc[m, ["cy", "cx", "mo"]].merge(self.fac[src], on=["cy", "cx", "mo"], how="left") \
                    .merge(self.mo[src], on="mo", how="left")
            df.loc[m, "w"] = t.f.fillna(t.r_mo).fillna(self.err[src]["national"]).values
        return df

    def daily(self, geom):
        df = self._weights(self.points(geom)); df["date"] = pd.to_datetime(df.date)
        sat_map = {"Terra": "terra", "Aqua": "aqua", "N": "snpp", "N20": "n20"}
        df["s"] = df.satellite.map(sat_map)
        n = df.groupby(["date", "s"]).size().unstack(fill_value=0)
        w = df[df.s.isin(["terra", "snpp", "n20"])].groupby(["date", "s"]).w.sum().unstack(fill_value=0).add_suffix("_eq")
        out = pd.concat([n, w], axis=1).fillna(0)
        for col in ["terra", "aqua", "snpp", "n20", "terra_eq", "snpp_eq", "n20_eq"]:
            if col not in out: out[col] = 0.0
        idx = pd.date_range(f"{int(self.err['starts']['terra'][0])}-{int(self.err['starts']['terra'][1]):02d}-01", self.data_end)
        return out.reindex(idx, fill_value=0), df

    def daily_value(self, d):
        """daily harmonized MODIS-equivalent value, same method switch as monthly()."""
        e = self.err
        v_mean = self._viirs_daily(d)
        stable_end = pd.Timestamp(self.stable_end, 12, 31)
        v = np.select([d.index < self.aqua_start, d.index <= stable_end], [d.terra_eq, d.terra + d.aqua], v_mean)
        return pd.Series(v, index=d.index, name="value")

    def _viirs_daily(self, d):
        """daily VIIRS->MODIS-eq: mean of S-NPP and NOAA-20 when both fly, else the one that does (NaN before VIIRS)."""
        e = self.err
        has_s = (d.index >= pd.Timestamp(*e["starts"]["snpp"], 1)) & (d.index <= SNPP_END)
        has_n = d.index >= pd.Timestamp(*e["starts"]["n20"], 1)
        return pd.Series(np.where(has_s & has_n, (d.snpp_eq + d.n20_eq) / 2,
                                  np.where(has_s, d.snpp_eq, np.where(has_n, d.n20_eq, np.nan))), index=d.index)

    def monthly(self, geom):
        d, pts = self.daily(geom)
        return self.monthly_from_daily(d), pts

    def monthly_from_daily(self, d):
        m = d.resample("MS").sum()
        e = self.err
        m["modis"] = m.terra + m.aqua
        vd = self._viirs_daily(d)                                   # summed per month: handles S-NPP ending mid-month
        v_mean = vd.resample("MS").sum(min_count=1).reindex(m.index).values
        stable_end = pd.Timestamp(self.stable_end, 12, 1)
        m["method"] = np.select([m.index < self.aqua_start, m.index <= stable_end], ["terra-adjusted", "modis-measured"], "viirs-translated")
        m["value"] = np.select([m.method == "terra-adjusted", m.method == "modis-measured"], [m.terra_eq, m.modis], v_mean)
        rel = {"terra-adjusted": e["terra"]["block_month_median_rel_err"], "modis-measured": 0.0,
               "viirs-translated": max(e["snpp"]["block_month_median_rel_err"], e["n20"]["block_month_median_rel_err"])}
        m["rel_err"] = m.method.map(rel)
        m["lo"], m["hi"] = m.value * (1 - m.rel_err), m.value * (1 + m.rel_err)
        m["viirs_eq"] = v_mean
        return m.drop(columns=[c for c in m.columns if c.endswith("_eq") and c != "viirs_eq"])

    @staticmethod
    def calendar(m):
        c = m.assign(yr=m.index.year, mo=m.index.month).pivot_table(index="yr", columns="mo", values="value", aggfunc="sum")
        return c.reindex(columns=range(1, 13))

    @staticmethod
    def anomaly(m, year, month, first_full_year=2003, partial=None):
        """partial = (year, month) of an unfinished last month: never used as history, and flagged when it is the target."""
        cal = Engine.calendar(m)
        cur = cal.loc[year, month]
        if partial and month == partial[1] and year != partial[0]: cal.loc[partial[0], month] = np.nan
        base = cal.loc[(cal.index >= first_full_year) & (cal.index != year), month].dropna()
        base = base[base.index < year] if (base.index < year).sum() >= 8 else base
        med = float(base.median())
        pct = float(((base < cur).mean() + 0.5 * (base == cur).mean()) * 100)     # ties count half
        ratio = cur / med if med > 0 else np.nan
        if partial and (year, month) == tuple(partial):
            label = "month not finished yet"
        elif med < 3 and cur < 3:
            label = "too little fire to compare"
        else:
            label = ("much higher than usual" if pct >= 90 else "higher than usual" if pct >= 75 else
                     "much lower than usual" if pct <= 10 else "lower than usual" if pct <= 25 else "normal")
        return dict(year=year, month=month, value=float(cur), median=med, ratio=float(ratio), percentile=pct,
                    label=label, n_years=int(len(base)), base_years=[int(base.index.min()), int(base.index.max())])


def theil_sen(x, y, z=1.96):
    """Theil-Sen slope (median of pairwise slopes) with Sen's (1968) rank-based 95% interval."""
    x, y = np.asarray(x, float), np.asarray(y, float); n = len(x)
    i, j = np.triu_indices(n, 1); dx = x[j] - x[i]; ok = dx != 0
    sl = np.sort((y[j] - y[i])[ok] / dx[ok]); N = len(sl)
    c = z * np.sqrt(n * (n - 1) * (2 * n + 5) / 18)          # Kendall S variance, no tie correction
    lo_i, hi_i = int(np.floor((N - c) / 2)), int(np.ceil((N + c) / 2))
    return float(np.median(sl)), float(sl[max(lo_i - 1, 0)]), float(sl[min(hi_i, N - 1)])


MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def find_seasons(clim, max_seasons=2, grow=0.10, min_share=0.05):
    """burning seasons from the monthly climatology (12 values).
    core = peak month grown to neighbours with >= `grow` x that peak; window = core + 1 buffer month each side.
    A second season counts only if its peak >= 5% of the main peak and it holds >= `min_share` of annual fire."""
    c = np.nan_to_num(np.asarray(clim, float)); tot = c.sum(); free = set(range(12)); out = []
    while len(out) < max_seasons and free and tot > 0:
        pk = max(free, key=lambda i: c[i])
        if c[pk] <= 0 or (out and c[pk] < 0.05 * out[0]["peak_val"]): break
        core = [pk]
        for step in (-1, 1):
            i = (pk + step) % 12
            while i in free and i not in core and c[i] >= grow * c[pk] and len(core) < 10:
                (core.insert(0, i) if step < 0 else core.append(i)); i = (i + step) % 12
        share = c[core].sum() / tot
        if out and share < min_share: break
        lo, hi = (core[0] - 1) % 12, (core[-1] + 1) % 12
        win = ([lo] if lo in free else []) + core + ([hi] if hi in free else [])
        free -= set(win)
        out.append(dict(label=MON[core[0]] + ("–" + MON[core[-1]] if len(core) > 1 else ""),
                        core_start=core[0] + 1, crosses_year=bool(core[-1] < core[0]), start_month=win[0] + 1, n_months=len(win), share=round(float(share), 3), peak_val=float(c[pk])))
    return out


def season_clock(v, start_month, n_months, data_end, first_year=2003, min_total=10.0, core_start=None):
    """per year: onset = day 10% of the window's fire is reached, end = 90%, peak = centre of busiest 15 days.
    `year` = calendar year in which the season's core starts (window may begin with a buffer month in the year before)."""
    shift = int(core_start is not None and core_start < start_month); years = []
    for y in range(first_year, data_end.year + 1):
        a = pd.Timestamp(y, start_month, 1); b = a + pd.DateOffset(months=n_months) - pd.Timedelta(days=1)
        if b > data_end: break
        x = v.loc[a:b].values; tot = float(x.sum())
        row = dict(year=y + shift, start=a.strftime("%Y-%m-%d"), total=round(tot, 1), onset=None, peak=None, end=None)
        if tot >= min_total:
            cum = np.cumsum(x) / tot; r = np.convolve(x, np.ones(15), "valid")
            row.update(onset=int(np.argmax(cum >= 0.10)), end=int(np.argmax(cum >= 0.90)), peak=int(np.argmax(r)) + 7)
        years.append(row)
    ok = [r for r in years if r["onset"] is not None]
    out = dict(years=years, n_years=len(ok))
    if len(ok) >= 5:
        out["typical"] = {k: int(np.median([r[k] for r in ok])) for k in ["onset", "peak", "end"]}
    if len(ok) >= 8:
        sl, lo, hi = theil_sen([r["year"] for r in ok], [r["onset"] for r in ok])
        out["onset_trend"] = dict(days_per_decade=round(sl * 10, 1), lo=round(lo * 10, 1), hi=round(hi * 10, 1),
                                  significant=bool(lo > 0 or hi < 0), years=[ok[0]["year"], ok[-1]["year"]])
    return out


def season(v, m, data_end):
    """fire-season clock for each burning season of the area (most areas: one; Punjab-type: two)."""
    clim = Engine.calendar(m).loc[2003:2021].median().reindex(range(1, 13)).values
    seasons = find_seasons(clim)
    for s in seasons:
        s.update(season_clock(v, s["start_month"], s["n_months"], data_end, core_start=s["core_start"])); s.pop("peak_val")
    return dict(seasons=seasons, base_years=[2003, 2021])


def outlook(v, today, weeks=4, first_year=2003):
    """what the next `weeks` weeks looked like in past years (climatology, NOT a forecast)."""
    today = pd.Timestamp(today).normalize(); data_end = v.index.max(); rows = []
    for w in range(weeks):
        a = today + pd.Timedelta(days=7 * w); vals = []
        for y in range(first_year, data_end.year + 1):
            try: ay = a.replace(year=y)
            except ValueError: ay = a.replace(year=y, day=28)  # 29 Feb
            by = ay + pd.Timedelta(days=6)
            if by <= data_end: vals.append(float(v.loc[ay:by].sum()))
        q = np.percentile(vals, [10, 50, 90]) if vals else [np.nan] * 3
        rows.append(dict(start=a.strftime("%Y-%m-%d"), end=(a + pd.Timedelta(days=6)).strftime("%Y-%m-%d"),
                         p10=round(float(q[0]), 1), median=round(float(q[1]), 1), p90=round(float(q[2]), 1),
                         recent=round(float(np.median(vals[-5:])), 1) if vals else None, n_years=len(vals)))
    return dict(from_date=today.strftime("%Y-%m-%d"), weeks=rows,
                base_years=[first_year, int(data_end.year)])


def outlook_table(v, first_year=2003, recent=5):
    """7-day fire totals starting on each calendar day (366 rows, MM-DD) across years -> p10/median/p90/recent median.
    Lets a static site show the 4-week climatology from any date (row i, i+7, i+14, i+21). Feb 29 uses Feb 28 in non-leap years."""
    data_end = v.index.max()
    fwd = v[::-1].rolling(7, min_periods=7).sum()[::-1]          # fwd[t] = v[t..t+6]
    days = pd.date_range("2024-01-01", "2024-12-31")             # leap year = all 366 MM-DD
    rows = []
    for dd in days:
        vals = []
        for y in range(first_year, data_end.year + 1):
            try: t = dd.replace(year=y)
            except ValueError: t = dd.replace(year=y, day=28)
            if t + pd.Timedelta(days=6) <= data_end: vals.append(float(fwd.loc[t]))
        q = np.percentile(vals, [10, 50, 90]) if vals else [np.nan] * 3
        rows.append([round(float(q[0]), 1), round(float(q[1]), 1), round(float(q[2]), 1),
                     round(float(np.median(vals[-recent:])), 1) if vals else None])
    return dict(first_day="01-01", cols=["p10", "median", "p90", "recent"], rows=rows,
                base_years=[first_year, int(data_end.year)])
