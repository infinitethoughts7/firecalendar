"""Pull only one country's CSV out of FIRMS yearly global zips using HTTP Range requests.
Usage: python3 scripts/download_firms.py India
"""
import io, sys, zipfile, urllib.request, urllib.error, os, time, concurrent.futures as cf

BASE = "https://firms.modaps.eosdis.nasa.gov/data/country/zips/{src}_{yr}_all_countries.zip"
SOURCES = {"modis": range(2000, 2027), "viirs-snpp": range(2012, 2027),
           "viirs-jpss1": range(2018, 2027), "viirs-jpss2": range(2023, 2027)}
COUNTRY = sys.argv[1] if len(sys.argv) > 1 else "India"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

class HttpFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0: return 0
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{self.pos+n-1}"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as r: data = r.read()
                break
            except Exception as e:
                if attempt == 3: raise
                time.sleep(2)
        b[:len(data)] = data; self.pos += len(data); return len(data)

def job(src, yr):
    dest = os.path.join(OUT, f"{src}_{yr}_{COUNTRY}.csv")
    if os.path.exists(dest) and os.path.getsize(dest) > 0: return f"skip {dest}"
    url = BASE.format(src=src, yr=yr)
    try:
        f = io.BufferedReader(HttpFile(url), buffer_size=1 << 20)
    except urllib.error.HTTPError as e:
        return f"missing {src} {yr} ({e.code})"
    z = zipfile.ZipFile(f)
    names = [n for n in z.namelist() if n.lower().endswith(f"_{COUNTRY.lower()}.csv")]
    if not names: return f"no {COUNTRY} in {src} {yr}"
    with z.open(names[0]) as src_f, open(dest + ".part", "wb") as out: out.write(src_f.read())
    os.replace(dest + ".part", dest)
    return f"ok {src} {yr} {os.path.getsize(dest)/1e6:.1f}MB"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    jobs = [(s, y) for s, yrs in SOURCES.items() for y in yrs]
    with cf.ThreadPoolExecutor(8) as ex:
        for msg in ex.map(lambda a: job(*a), jobs): print(msg, flush=True)
    print("DONE", flush=True)
