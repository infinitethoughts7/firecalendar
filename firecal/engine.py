"""FireCalendar engine: area -> harmonized (MODIS-equivalent) daily/monthly series, calendar, anomaly."""
import duckdb, json, os, numpy as np, pandas as pd
from shapely import contains_xy
from shapely.geometry import shape, box
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
P = f"{ROOT}/data/processed"

class Engine:
    def __init__(self, country="India"):
        k = country.lower()
        self.country, self.fires = country, f"{P}/fires_{k}.parquet"
        self.err = json.load(open(f"{P}/errors_{k}.json"))
        self.cell = self.err["cell_deg"]; self.stable_end = self.err["stable_end"]
        f = pd.read_parquet(f"{P}/factors_{k}.parquet")
        self.fac = {s: f[f.src == s].drop(columns="src") for s in ["terra", "snpp", "n20"]}
        self.mo = {s: pd.read_parquet(f"{P}/monthratio_{s}_{k}.parquet").drop(columns="src") for s in ["terra", "snpp", "n20"]}
        self.db = duckdb.connect(); self.db.execute("SET memory_limit='2GB'")
        ay, am = self.err["starts"]["aqua"]; self.aqua_start = pd.Timestamp(ay, am, 1)
        self.data_end = pd.Timestamp(self.db.execute(f"SELECT max(date) FROM '{self.fires}'").fetchone()[0])  # same time axis for every area

    def points(self, geom):
        """vegetation-fire points (low confidence removed) inside a shapely geometry."""
        x0, y0, x1, y1 = geom.bounds
        df = self.db.execute(f"""SELECT lat, lon, date, satellite, sensor, time_utc, frp FROM '{self.fires}'
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

    def monthly(self, geom):
        d, pts = self.daily(geom)
        m = d.resample("MS").sum()
        e = self.err
        m["modis"] = m.terra + m.aqua
        viirs = m[["snpp_eq", "n20_eq"]].where((m[["snpp", "n20"]].values > 0) | (m.index.year.values[:, None] >= 2000))
        has_s = m.index >= pd.Timestamp(*e["starts"]["snpp"], 1); has_n = m.index >= pd.Timestamp(*e["starts"]["n20"], 1)
        v_mean = np.where(has_s & has_n, (m.snpp_eq + m.n20_eq) / 2, np.where(has_s, m.snpp_eq, m.n20_eq))
        stable_end = pd.Timestamp(self.stable_end, 12, 1)
        m["method"] = np.select([m.index < self.aqua_start, m.index <= stable_end], ["terra-adjusted", "modis-measured"], "viirs-translated")
        m["value"] = np.select([m.method == "terra-adjusted", m.method == "modis-measured"], [m.terra_eq, m.modis], v_mean)
        rel = {"terra-adjusted": e["terra"]["block_month_median_rel_err"], "modis-measured": 0.0,
               "viirs-translated": max(e["snpp"]["block_month_median_rel_err"], e["n20"]["block_month_median_rel_err"])}
        m["rel_err"] = m.method.map(rel)
        m["lo"], m["hi"] = m.value * (1 - m.rel_err), m.value * (1 + m.rel_err)
        m["viirs_eq"] = np.where(has_s | has_n, v_mean, np.nan)
        return m.drop(columns=[c for c in m.columns if c.endswith("_eq") and c != "viirs_eq"]), pts

    @staticmethod
    def calendar(m):
        c = m.assign(yr=m.index.year, mo=m.index.month).pivot_table(index="yr", columns="mo", values="value", aggfunc="sum")
        return c.reindex(columns=range(1, 13))

    @staticmethod
    def anomaly(m, year, month, first_full_year=2003):
        cal = Engine.calendar(m)
        cur = cal.loc[year, month]
        base = cal.loc[(cal.index >= first_full_year) & (cal.index != year), month].dropna()
        base = base[base.index < year] if (base.index < year).sum() >= 8 else base
        med = float(base.median())
        pct = float(((base < cur).mean() + 0.5 * (base == cur).mean()) * 100)     # ties count half
        ratio = cur / med if med > 0 else np.nan
        if med < 3 and cur < 3:
            label = "too little fire to compare"
        else:
            label = ("much higher than usual" if pct >= 90 else "higher than usual" if pct >= 75 else
                     "much lower than usual" if pct <= 10 else "lower than usual" if pct <= 25 else "normal")
        return dict(year=year, month=month, value=float(cur), median=med, ratio=float(ratio), percentile=pct,
                    label=label, n_years=int(len(base)), base_years=[int(base.index.min()), int(base.index.max())])
