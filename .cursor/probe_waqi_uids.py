"""Probe live freshness of selected Valencia WAQI UIDs."""

import json
import re
import urllib.request


def load_token():
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("WAQI_TOKEN="):
                m = re.match(r'WAQI_TOKEN\s*=\s*"?([^"\s#]+)"?', line.strip())
                if m:
                    return m.group(1)
    raise RuntimeError("token missing")


def main() -> None:
    token = load_token()
    uids = [(6637, "Pista de Silla"), (6638, "Molí del Sol"), (6639, "Avd. Francia"), (6640, "Politècnic")]
    for uid, label in uids:
        url = f"https://api.waqi.info/feed/@{uid}/?token={token}"
        try:
            body = json.loads(urllib.request.urlopen(url, timeout=15).read().decode())
        except Exception as e:
            print(uid, label, "ERR", e)
            continue
        if body.get("status") != "ok":
            print(uid, label, "status", body.get("status"), body.get("data"))
            continue
        data = body["data"]
        t = data.get("time", {})
        iaqi = data.get("iaqi", {})
        print(
            f"uid={uid:<5} {label:<22} aqi={data.get('aqi'):>3} "
            f"time_s={t.get('s')} tz={t.get('tz')} "
            f"pm25={iaqi.get('pm25',{}).get('v')} "
            f"no2={iaqi.get('no2',{}).get('v')} "
            f"o3={iaqi.get('o3',{}).get('v')}"
        )


if __name__ == "__main__":
    main()
