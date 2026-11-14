import duckdb, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
c=duckdb.connect(); c.execute("SET memory_limit='2GB'")
c.execute("CREATE VIEW f AS SELECT * FROM 'data/processed/fires_india.parquet' WHERE type=0 AND conf_class<>'low'")
fig,ax=plt.subplots(2,2,figsize=(15,11)); fig.suptitle("FIRMS active fires over India (type 0 = vegetation fire, low-confidence dropped)",fontsize=14,weight="bold")
# (a) yearly counts per sensor
y=c.sql("SELECT year(date) yr, sensor, count(*) n FROM f WHERE year(date)>=2001 GROUP BY 1,2 ORDER BY 1").df()
for s,col in [("modis","#1f4e79"),("viirs-snpp","#d9822b"),("viirs-jpss1","#7f7f7f")]:
    d=y[y.sensor==s]; ax[0,0].plot(d.yr,d.n/1e3,"o-",label=s,color=col)
ax[0,0].axvspan(2000.5,2002.5,color="red",alpha=.08); ax[0,0].text(2001,520,"Terra only\n(Aqua starts\nmid-2002)",fontsize=8,color="red")
ax[0,0].set_title("A. Same fires, different sensors: VIIRS counts ~5.5x MODIS"); ax[0,0].set_ylabel("detections / year (thousands)"); ax[0,0].legend()
# (b) ratio map on 1-degree grid, 2013-2025
r=c.sql("""SELECT floor(lat) la, floor(lon) lo, sum((sensor='viirs-snpp')::int)::DOUBLE/nullif(sum((sensor='modis')::int),0) ratio, sum((sensor='modis')::int) m
 FROM f WHERE year(date) BETWEEN 2013 AND 2025 GROUP BY 1,2 HAVING m>=200""").df()
sc=ax[0,1].scatter(r.lo+.5,r.la+.5,c=r.ratio,s=38,marker="s",cmap="viridis",vmin=2,vmax=12)
plt.colorbar(sc,ax=ax[0,1],label="VIIRS-SNPP / MODIS detections"); ax[0,1].set_title("B. The ratio is NOT constant: varies by region (1° cells)"); ax[0,1].set_aspect("equal")
# (c) Punjab-Haryana calendar (MODIS only)
p=c.sql("""SELECT year(date) yr, month(date) mo, count(*) n FROM f WHERE sensor='modis' AND lat BETWEEN 29 AND 32.5 AND lon BETWEEN 73.8 AND 77.5 AND year(date)>=2003 GROUP BY 1,2""").df()
yrs=sorted(p.yr.unique()); M=np.zeros((len(yrs),12))
for _,row in p.iterrows(): M[yrs.index(row.yr),row.mo-1]=row.n
im=ax[1,0].imshow(np.log10(M+1),aspect="auto",cmap="inferno"); ax[1,0].set_yticks(range(len(yrs)),yrs,fontsize=7)
ax[1,0].set_xticks(range(12),list("JFMAMJJASOND")); plt.colorbar(im,ax=ax[1,0],label="log10(MODIS detections)")
ax[1,0].set_title("C. Burning calendar, Punjab-Haryana (MODIS): Apr wheat + Oct-Nov paddy")
# (d) overpass time Punjab Oct-Nov
t=c.sql("""SELECT sensor, (cast(substr(time_utc,1,2) AS INT)*60+cast(substr(time_utc,3,2) AS INT)+330)/60.0 ist FROM f
 WHERE month(date) IN (10,11) AND lat BETWEEN 29 AND 32.5 AND lon BETWEEN 73.8 AND 77.5 AND year(date)>=2020""").df()
for s,col in [("modis","#1f4e79"),("viirs-snpp","#d9822b"),("viirs-jpss1","#7f7f7f")]:
    ax[1,1].hist(t[t.sensor==s].ist%24,bins=96,range=(0,24),alpha=.6,label=s,color=col)
ax[1,1].axvspan(15,19,color="red",alpha=.1); ax[1,1].text(15.2,ax[1,1].get_ylim()[1]*.8,"peak burning 2024\n(~17:00 IST, per ISRO)\n= NO polar pass",fontsize=8,color="red")
ax[1,1].set_xlabel("detection time (IST)"); ax[1,1].set_title("D. Satellites only look at ~10:30-14:00 & ~01:30 IST"); ax[1,1].legend()
plt.tight_layout(); plt.savefig("figures/01_data_overview.png",dpi=110); print("saved")
