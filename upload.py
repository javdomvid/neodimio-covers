#!/usr/bin/env python3
"""Sube una portada JPEG a una playlist de Spotify.

Credenciales (nunca en el repo), por variables de entorno
  SPOTIFY_CID, SPOTIFY_CSEC, SPOTIFY_RTOK  (refresh token con scope ugc-image-upload)
o leidas de un script que tenga lineas CID="..", CSEC="..", RTOK=".." (--creds-from).
Uso:
  python3 upload.py --file out/november_c0.jpg --playlist <id> --creds-from /tmp/sync.py
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request

def call(url, method="GET", data=None, hdr=None):
    for a in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdr or {}, method=method), timeout=60) as r:
                raw = r.read(); return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(int(e.headers.get("Retry-After", "3")) + 1); continue
            if e.code in (500, 502, 503, 504) and a != 5: time.sleep(2 ** a); continue
            raise RuntimeError("HTTP %d %s %s :: %s" % (e.code, method, url, e.read().decode()[:400]))
        except urllib.error.URLError as e:
            if a != 5: time.sleep(2 ** a); continue
            raise RuntimeError("RED %s :: %s" % (url, e))
    raise RuntimeError("reintentos agotados " + url)

def creds(path=None):
    if path:
        import re
        txt = open(path).read()
        get = lambda k: re.search(r'^%s\s*=\s*"([^"]+)"' % k, txt, re.M).group(1)
        return get("CID"), get("CSEC"), get("RTOK")
    return tuple(os.environ[k] for k in ("SPOTIFY_CID", "SPOTIFY_CSEC", "SPOTIFY_RTOK"))

def token(path=None):
    cid, csec, rt = creds(path)
    _, t = call("https://accounts.spotify.com/api/token", "POST",
                urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": rt}).encode(),
                {"Authorization": "Basic " + base64.b64encode(f"{cid}:{csec}".encode()).decode(),
                 "Content-Type": "application/x-www-form-urlencoded"})
    if "ugc-image-upload" not in t.get("scope", ""):
        raise RuntimeError("SCOPE: el token no tiene ugc-image-upload; hay que reautorizar la app")
    return t["access_token"]

MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
          "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
TITLE = 'YOU CAN\'T MISS "{month}" - javdomvid'

def set_title(playlist, H, month="auto"):
    """Pone el titulo del mes (hora de Madrid) y verifica que quedo guardado."""
    import datetime, zoneinfo
    if month == "auto":
        month = MONTHS[datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Madrid")).month - 1]
    name = TITLE.format(month=month.upper())
    url = f"https://api.spotify.com/v1/playlists/{playlist}"
    _, old = call(url + "?fields=name", hdr=H)
    st, _ = call(url, "PUT", json.dumps({"name": name}).encode(), dict(H, **{"Content-Type": "application/json"}))
    _, new = call(url + "?fields=name", hdr=H)
    return {"titulo_antes": old.get("name"), "titulo": new.get("name"), "status": st, "ok": new.get("name") == name}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--file"); ap.add_argument("--playlist", required=True)
    ap.add_argument("--creds-from", default=None)
    ap.add_argument("--set-title", action="store_true", help='titulo: YOU CAN\'T MISS "MES" - javdomvid')
    ap.add_argument("--month", default="auto")
    a = ap.parse_args()
    if a.set_title:
        H = {"Authorization": "Bearer " + token(a.creds_from)}
        r = set_title(a.playlist, H, a.month); print(json.dumps(r, ensure_ascii=False))
        if not a.file: sys.exit(0 if r["ok"] else 1)
    if not a.file: sys.exit("Falta --file (o usa --set-title)")
    body = base64.b64encode(open(a.file, "rb").read())
    if len(body) > 256 * 1024: sys.exit("La imagen supera 256 KB en base64")
    H = {"Authorization": "Bearer " + token(a.creds_from)}
    _, before = call(f"https://api.spotify.com/v1/playlists/{a.playlist}/images", hdr=H)
    st, _ = call(f"https://api.spotify.com/v1/playlists/{a.playlist}/images", "PUT", body, dict(H, **{"Content-Type": "image/jpeg"}))
    url_before = before[0]["url"] if before else None
    for _ in range(10):                      # Spotify procesa la imagen de forma asincrona
        time.sleep(3)
        _, after = call(f"https://api.spotify.com/v1/playlists/{a.playlist}/images", hdr=H)
        if after and after[0]["url"] != url_before: break
    changed = bool(after) and after[0]["url"] != url_before
    print(json.dumps({"status": st, "cambiada": changed, "url": after[0]["url"] if after else None}))
    sys.exit(0 if st in (200, 202) else 1)
