import os, re, json, urllib.request
TOKEN=None
with open('.env','r',encoding='utf-8') as f:
    for line in f:
        if line.strip().startswith('WAQI_TOKEN='):
            m=re.match(r'WAQI_TOKEN\s*=\s*"?([^"\s#]+)"?', line.strip())
            if m: TOKEN=m.group(1); break

stations=[
 ("Francia",39.4578,-0.343),
 ("Moli del Sol",39.4811,-0.4088),
 ("Pista de Silla",39.4581,-0.3766),
 ("Politecnica",39.4796,-0.3374),
 ("Puerto Valencia",39.4484,-0.3172),
 ("Puerto llit antic Turia",39.4661,-0.3306),
 ("Puerto Moll Trans. Ponent",39.4536,-0.3137),
]
for name,lat,lon in stations:
    url="https://api.waqi.info/feed/geo:%s;%s/?token=%s" % (lat,lon,TOKEN)
    try:
        r=urllib.request.urlopen(url, timeout=15).read().decode()
        d=json.loads(r)
        if d.get("status")!="ok":
            print(name,"->",d.get("status"),d.get("data")); continue
        data=d["data"]; t=data.get("time",{}); iaqi=data.get("iaqi",{})
        city=(data.get("city") or {}).get("name","")[:50]
        print("%-30s idx=%s aqi=%s city='%s' time_s='%s' tz='%s' pm25=%s no2=%s o3=%s" % (
            name, data.get("idx"), data.get("aqi"), city, t.get("s"), t.get("tz"),
            iaqi.get("pm25",{}).get("v"), iaqi.get("no2",{}).get("v"), iaqi.get("o3",{}).get("v"),
        ))
    except Exception as e:
        print(name,"ERR",e)
