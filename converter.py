"""Converter YouTube -> Spotify (musica, episodi di podcast, clip di podcast).
Lingua dei messaggi: LINGUA=it|en nel file .env. Vedi MESSAGGI qui sotto.
"""

import json
import os
import re
import sys
import webbrowser
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import requests
import spotipy
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "stato.json"
load_dotenv(BASE / ".env")

# ================================================================ lingua

LINGUA = (os.getenv("LINGUA") or "it").lower()[:2]

MESSAGGI = {
    "it": {
        "aiuto": """Converter YouTube -> Spotify

Comandi:
  python converter.py sync           Copia i nuovi video della playlist YouTube nella playlist Spotify
  python converter.py riprendi [URL] Continua su Spotify il video YouTube (URL o appunti, con ?t=)
  python converter.py torna          Passa da Spotify al video YouTube corrispondente
  python converter.py mancanti       Elenca i video non trovati su Spotify
  python converter.py collega CLIP DEST [mm:ss]
                                     Abbina a mano: DEST = link YouTube dell'episodio intero
                                     (con ?t= dove inizia la clip) o link Spotify dell'episodio
  python converter.py auto           Sync silenzioso con log in sync.log (per l'Utilità di pianificazione)""",
        "manca_env": "Manca {name} nel file .env (vedi .env.example).",
        "notifica_ko": "(notifica non riuscita: {e})",
        "errore_yt": "Errore YouTube ({code}): {testo}",
        "tipo_musica": "musica", "tipo_episodio": "episodio", "tipo_clip": "clip",
        "et_episodio": "[episodio] {nome}", "et_clip_a": "[clip @ {t}] {nome}", "et_clip_ignoto": "[clip, punto ignoto] {nome}",
        "playlist_nome": "Da YouTube", "playlist_descr": "Sincronizzata da YouTube con converter.py",
        "nessun_dispositivo": "Nessun dispositivo Spotify trovato: apri Spotify (PC o telefono) e riprova.",
        "playlist_creata": "Creata playlist Spotify '{nome}'.",
        "ok": "  OK  {titolo}\n      -> {trovato}",
        "non_trovato": "  ??  {titolo}  ({tipo}, non trovato)",
        "fatto": "Fatto: {n} elementi aggiunti alla playlist Spotify.",
        "notifica_1": "1 video non trovato su Spotify", "notifica_n": "{n} video non trovati su Spotify",
        "e_altri": "\n…e altri {n}", "usa_collega": "\nUsa 'collega' per abbinarli a mano.",
        "no_link_appunti": "Negli appunti non c'è un link YouTube.\nSu YouTube: tasto destro sul video -> 'Copia URL del video all'ora corrente'.",
        "video_non_trovato": "Video non trovato su YouTube.",
        "non_trovo": "Non trovo su Spotify: {titolo}",
        "clip_inizio_ignoto": "Non so in che punto dell'episodio sta questa clip: parto dall'inizio dell'episodio.",
        "su_spotify": "Su Spotify ({tipo}) da {t}.",
        "niente_in_ascolto": "Su Spotify non sta suonando niente.",
        "aperto_youtube": "Aperto YouTube da {t}.",
        "arg1": "Il primo argomento deve essere il link YouTube del video da collegare.",
        "arg2": "Il secondo argomento deve essere un link YouTube o Spotify valido.",
        "non_trovo_episodio": "Non trovo su Spotify l'episodio: {titolo}",
        "collegato": "Collegato: {titolo}\n  -> {uri}", "clip_inizia": " (la clip inizia a {t})",
        "mancanti": "{n} video non trovati su Spotify.",
    },
    "en": {
        "aiuto": """YouTube -> Spotify Converter

Commands:
  python converter.py sync           Copy new videos from the YouTube playlist to the Spotify playlist
  python converter.py riprendi [URL] Resume the YouTube video on Spotify (URL or clipboard, with ?t=)
  python converter.py torna          Switch from Spotify to the matching YouTube video
  python converter.py mancanti       List videos not found on Spotify
  python converter.py collega CLIP DEST [mm:ss]
                                     Link by hand: DEST = YouTube link of the full episode
                                     (with ?t= where the clip starts) or Spotify episode link
  python converter.py auto           Silent sync logging to sync.log (for Task Scheduler)""",
        "manca_env": "{name} is missing from the .env file (see .env.example).",
        "notifica_ko": "(notification failed: {e})",
        "errore_yt": "YouTube error ({code}): {testo}",
        "tipo_musica": "music", "tipo_episodio": "episode", "tipo_clip": "clip",
        "et_episodio": "[episode] {nome}", "et_clip_a": "[clip @ {t}] {nome}", "et_clip_ignoto": "[clip, start unknown] {nome}",
        "playlist_nome": "From YouTube", "playlist_descr": "Synced from YouTube with converter.py",
        "nessun_dispositivo": "No Spotify device found: open Spotify (PC or phone) and try again.",
        "playlist_creata": "Created Spotify playlist '{nome}'.",
        "ok": "  OK  {titolo}\n      -> {trovato}",
        "non_trovato": "  ??  {titolo}  ({tipo}, not found)",
        "fatto": "Done: {n} items added to the Spotify playlist.",
        "notifica_1": "1 video not found on Spotify", "notifica_n": "{n} videos not found on Spotify",
        "e_altri": "\n…and {n} more", "usa_collega": "\nUse 'collega' to link them by hand.",
        "no_link_appunti": "There's no YouTube link in the clipboard.\nOn YouTube: right-click the video -> 'Copy video URL at current time'.",
        "video_non_trovato": "Video not found on YouTube.",
        "non_trovo": "Can't find on Spotify: {titolo}",
        "clip_inizio_ignoto": "I don't know where in the episode this clip is: starting from the beginning of the episode.",
        "su_spotify": "On Spotify ({tipo}) from {t}.",
        "niente_in_ascolto": "Nothing is playing on Spotify.",
        "aperto_youtube": "Opened YouTube at {t}.",
        "arg1": "The first argument must be the YouTube link of the video to link.",
        "arg2": "The second argument must be a valid YouTube or Spotify link.",
        "non_trovo_episodio": "Can't find the episode on Spotify: {titolo}",
        "collegato": "Linked: {titolo}\n  -> {uri}", "clip_inizia": " (the clip starts at {t})",
        "mancanti": "{n} videos not found on Spotify.",
    },
}


def m(chiave, **kw):
    testo = MESSAGGI.get(LINGUA, MESSAGGI["it"]).get(chiave) or MESSAGGI["it"][chiave]
    return testo.format(**kw)

SCOPES = " ".join([
    "playlist-read-private",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-playback-position",
])

YT_API = "https://www.googleapis.com/youtube/v3"
DURATA_MIN_EPISODIO = int(os.getenv("DURATA_MIN_EPISODIO_MIN", "20")) * 60
CATEGORIA_MUSICA = "10"


# ================================================================ utilità

def env(name, default=None):
    value = os.getenv(name) or default
    if not value:
        sys.exit(m("manca_env", name=name))
    return value


def mercato():
    return os.getenv("SPOTIFY_MARKET") or "IT"


def load_state():
    state = {"spotify_playlist_id": None, "video": {}, "show": {}}
    if STATE_FILE.exists():
        state.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return state


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def playlist_id_youtube():
    raw = env("YOUTUBE_PLAYLIST")
    if "list=" in raw:
        return parse_qs(urlparse(raw).query)["list"][0]
    return raw


def parse_tempo(t):
    """'123', '123s', '1m23s', '1h2m3s' -> secondi."""
    if not t:
        return 0
    if t.isdigit():
        return int(t)
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", t)
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def parse_durata_iso(d):
    """'PT1H2M3S' -> secondi."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    g, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return g * 86400 + h * 3600 + mi * 60 + s


def parse_url_youtube(url):
    """Restituisce (video_id, secondi) da un link YouTube, oppure (None, 0)."""
    u = urlparse(url.strip())
    q = parse_qs(u.query)
    vid = None
    if "youtu.be" in u.netloc:
        vid = u.path.lstrip("/").split("/")[0]
    elif u.path.startswith(("/shorts/", "/live/")):
        vid = u.path.split("/")[2]
    elif "youtube.com" in u.netloc:
        vid = q.get("v", [None])[0]
    return vid, parse_tempo(q.get("t", [""])[0])


def mmss(secondi):
    h, resto = divmod(int(secondi), 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def leggi_appunti():
    import tkinter
    root = tkinter.Tk()
    root.withdraw()
    try:
        return root.clipboard_get()
    except tkinter.TclError:
        return ""
    finally:
        root.destroy()


def notifica(titolo, testo):
    """Notifica di Windows (quelle in basso a destra), senza librerie extra."""
    from xml.sax.saxutils import escape
    import subprocess
    xml = (f"<toast><visual><binding template='ToastGeneric'><text>{escape(titolo)}</text>"
           f"<text>{escape(testo)}</text></binding></visual></toast>").replace("'", "''")
    app_id = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] > $null;"
        f"$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml('{xml}');"
        "$t = [Windows.UI.Notifications.ToastNotification]::new($x);"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($t)"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=30)
    except Exception as e:
        print(m("notifica_ko", e=e))


def simile(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ================================================================ YouTube

def yt_get(endpoint, **params):
    params["key"] = env("YOUTUBE_API_KEY")
    r = requests.get(f"{YT_API}/{endpoint}", params=params, timeout=30)
    if r.status_code != 200:
        sys.exit(m("errore_yt", code=r.status_code, testo=r.text[:300]))
    return r.json()


def id_playlist_youtube():
    pid = playlist_id_youtube()
    token = None
    while True:
        data = yt_get("playlistItems", part="contentDetails", playlistId=pid,
                      maxResults=50, pageToken=token)
        for item in data["items"]:
            yield item["contentDetails"]["videoId"]
        token = data.get("nextPageToken")
        if not token:
            break


def dettagli_video(ids):
    """Titolo, canale, categoria, durata e descrizione per una lista di ID (a blocchi di 50)."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 50):
        data = yt_get("videos", part="snippet,contentDetails", id=",".join(ids[i:i + 50]))
        for it in data["items"]:
            sn = it["snippet"]
            out[it["id"]] = {
                "id": it["id"],
                "titolo": sn["title"],
                "canale": sn["channelTitle"],
                "categoria": sn.get("categoryId", ""),
                "descrizione": sn.get("description", ""),
                "durata": parse_durata_iso(it["contentDetails"].get("duration")),
            }
    return out


def classifica(v):
    """'musica', 'episodio' o 'clip'."""
    canale = v["canale"]
    if v["categoria"] == CATEGORIA_MUSICA or canale.endswith(" - Topic") or "VEVO" in canale:
        return "musica"
    if v["durata"] >= DURATA_MIN_EPISODIO:
        return "episodio"
    return "clip"


def episodio_da_clip(v):
    """Cerca nella descrizione della clip il link all'episodio completo.
    Restituisce (dettagli_video_completo, secondo_di_inizio) oppure (None, 0)."""
    link = re.findall(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/\S+", v["descrizione"])
    candidati = {}
    for url in link:
        vid, t = parse_url_youtube(url.rstrip(").,]"))
        if vid and vid != v["id"] and vid not in candidati:
            candidati[vid] = t
    if not candidati:
        return None, 0
    info = dettagli_video(list(candidati)[:50])
    lunghi = [info[k] for k in candidati if k in info and info[k]["durata"] >= DURATA_MIN_EPISODIO]
    if not lunghi:
        return None, 0
    # Preferisco un link con minutaggio, poi quello più simile per canale.
    lunghi.sort(key=lambda x: (candidati[x["id"]] > 0, simile(x["canale"], v["canale"])), reverse=True)
    completo = lunghi[0]
    return completo, candidati[completo["id"]]


# ================================================================ pulizia titoli

RUMORE = re.compile(
    r"[\(\[][^\)\]]*(official|video|audio|lyric|testo|hd|4k|remaster|visuali[sz]er|clip|mv)[^\)\]]*[\)\]]",
    re.I,
)


def pulisci_musica(titolo, canale):
    """Ricava (artista, brano) da titolo e canale YouTube."""
    t = RUMORE.sub("", titolo)
    t = re.sub(r"\b(official (music )?video|official audio|lyrics?|videoclip)\b", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -|–—")
    for sep in (" - ", " – ", " — ", " | "):
        if sep in t:
            artista, brano = t.split(sep, 1)
            return artista.strip(), brano.strip()
    artista = re.sub(r"(VEVO| - Topic|Official)$", "", canale, flags=re.I).strip()
    return artista, t


def pulisci_episodio(titolo, canale):
    """Toglie dal titolo il nome del canale e i fronzoli tipici ('| Podcast', '[FULL EPISODE]')."""
    t = re.sub(r"[\(\[][^\)\]]*(full|episod|puntata|video|podcast)[^\)\]]*[\)\]]", "", titolo, flags=re.I)
    pezzi = [p.strip() for p in re.split(r"\s[|–—-]\s", t) if p.strip()]
    pezzi = [p for p in pezzi if simile(p, canale) < 0.6] or pezzi
    return max(pezzi, key=len) if pezzi else titolo


# ================================================================ Spotify

def client_spotify():
    auth = spotipy.SpotifyOAuth(
        client_id=env("SPOTIFY_CLIENT_ID"),
        client_secret=env("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=env("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPES,
        cache_path=str(BASE / ".spotify_token"),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def cerca_brano(sp, artista, brano):
    for q in (f'track:"{brano}" artist:"{artista}"', f"{artista} {brano}"):
        res = sp.search(q=q, type="track", limit=5, market=mercato())["tracks"]["items"]
        migliore, punteggio = None, 0
        for tr in filter(None, res):
            artisti = " ".join(a["name"] for a in tr["artists"])
            p = simile(brano, tr["name"]) * 0.6 + simile(artista, artisti) * 0.4
            if p > punteggio:
                migliore, punteggio = tr, p
        if migliore and punteggio >= 0.55:
            return migliore["uri"], f'{migliore["artists"][0]["name"]} - {migliore["name"]}'
    return None, None


def numero_episodio(titolo):
    m = re.search(r"(?:#|\bep\.?\s*|\bepisod[ei]o?\s*|\bpuntata\s*|\bn\.\s*)(\d{1,4})\b", titolo, re.I)
    return int(m.group(1)) if m else None


def punteggio_episodio(titolo, durata_yt, ep, dello_show=False):
    p_nome = max(simile(titolo, ep["name"]),
                 # titoli lunghi: conta anche se uno contiene l'altro
                 0.9 if titolo.lower() in ep["name"].lower() or ep["name"].lower() in titolo.lower() else 0)
    dur_sp = ep.get("duration_ms", 0) / 1000
    if durata_yt and dur_sp:
        scarto = abs(dur_sp - durata_yt) / max(durata_yt, dur_sp)
        p_dur = 1.0 if scarto < 0.1 else max(0.0, 1 - scarto * 3)
    else:
        scarto, p_dur = 1, 0.5
    if dello_show:
        # Nello stesso podcast una durata quasi identica è un indizio fortissimo
        # (i titoli su YouTube sono spesso riscritti "acchiappa-clic").
        p_dur = 1.0 if scarto < 0.005 else 0.7 if scarto < 0.02 else p_dur * 0.5
        return p_nome * 0.5 + p_dur * 0.5
    return p_nome * 0.7 + p_dur * 0.3


_cache_episodi = {}


def episodi_show(sp, show_id, massimo=300):
    if show_id not in _cache_episodi:
        eps, offset = [], 0
        while offset < massimo:
            page = sp.show_episodes(show_id, limit=50, offset=offset, market=mercato())
            eps += [e for e in page["items"] if e]
            if not page.get("next"):
                break
            offset += 50
        _cache_episodi[show_id] = eps
    return _cache_episodi[show_id]


def trova_show(sp, canale, state):
    if canale in state["show"]:
        return state["show"][canale]
    res = sp.search(q=canale, type="show", limit=5, market=mercato())["shows"]["items"]
    migliori = sorted(filter(None, res), key=lambda s: simile(canale, s["name"]), reverse=True)
    show_id = migliori[0]["id"] if migliori and simile(canale, migliori[0]["name"]) >= 0.6 else None
    state["show"][canale] = show_id
    return show_id


def cerca_episodio(sp, v, state):
    """Restituisce (uri, descrizione) dell'episodio Spotify corrispondente al video completo v."""
    titolo = pulisci_episodio(v["titolo"], v["canale"])
    trovato = lambda e: (e["uri"], e["name"])

    # 1) Il podcast: dal link Spotify nella descrizione, altrimenti dal nome del canale.
    m = re.search(r"open\.spotify\.com/show/([A-Za-z0-9]{22})", v.get("descrizione", ""))
    if m:
        show_id = state["show"][v["canale"]] = m.group(1)
    else:
        show_id = trova_show(sp, v["canale"], state)

    if show_id:
        eps = episodi_show(sp, show_id)
        # 1a) Stesso numero di episodio = abbinamento sicuro.
        n = numero_episodio(v["titolo"])
        if n is not None:
            stesso_n = [e for e in eps if numero_episodio(e["name"]) == n]
            if len(stesso_n) == 1:
                return trovato(stesso_n[0])
        # 1b) Titolo + durata, dentro il podcast.
        if eps:
            migliore = max(eps, key=lambda e: punteggio_episodio(titolo, v["durata"], e, True))
            if punteggio_episodio(titolo, v["durata"], migliore, True) >= 0.6:
                return trovato(migliore)

    # 2) Ricerca libera tra tutti gli episodi di Spotify.
    candidati = []
    for q in (f"{v['canale']} {titolo}", titolo):
        candidati += [e for e in sp.search(q=q, type="episode", limit=10,
                                           market=mercato())["episodes"]["items"] if e]
    if candidati:
        migliore = max(candidati, key=lambda e: punteggio_episodio(titolo, v["durata"], e))
        if punteggio_episodio(titolo, v["durata"], migliore) >= 0.6:
            return trovato(migliore)
    return None, None


def abbina(sp, v, state):
    """Abbina un video YouTube a un contenuto Spotify. Restituisce il record da salvare."""
    tipo = classifica(v)
    rec = {"titolo": v["titolo"], "tipo": tipo, "spotify": None, "inizio": 0}
    trovato = None

    if tipo == "musica":
        rec["spotify"], trovato = cerca_brano(sp, *pulisci_musica(v["titolo"], v["canale"]))
    elif tipo == "episodio":
        rec["spotify"], trovato = cerca_episodio(sp, v, state)
    else:  # clip
        completo, inizio = episodio_da_clip(v)
        if completo:
            rec["video_completo"] = completo["id"]
            rec["inizio"] = inizio
            rec["inizio_noto"] = inizio > 0
            rec["spotify"], trovato = cerca_episodio(sp, completo, state)
        if not rec["spotify"]:
            # Senza link all'episodio: forse non è una clip ma una canzone breve.
            rec["spotify"], trovato = cerca_brano(sp, *pulisci_musica(v["titolo"], v["canale"]))
            if rec["spotify"]:
                rec["tipo"] = "musica"
        elif trovato:
            trovato = m("et_clip_a", t=mmss(inizio), nome=trovato) if inizio else m("et_clip_ignoto", nome=trovato)
            return rec, trovato
    if rec["tipo"] == "episodio" and trovato:
        trovato = m("et_episodio", nome=trovato)
    return rec, trovato


def crea_playlist(sp, nome):
    body = {"name": nome, "public": False,
            "description": m("playlist_descr")}
    try:
        return sp._post("me/playlists", payload=body)["id"]
    except spotipy.SpotifyException:
        return sp._post(f"users/{sp.me()['id']}/playlists", payload=body)["id"]


def aggiungi_alla_playlist(sp, playlist_id, uris):
    for i in range(0, len(uris), 100):
        blocco = {"uris": uris[i:i + 100]}
        try:
            sp._post(f"playlists/{playlist_id}/items", payload=blocco)
        except spotipy.SpotifyException:
            sp._post(f"playlists/{playlist_id}/tracks", payload=blocco)


def dispositivo_attivo(sp):
    devs = sp.devices()["devices"]
    if not devs:
        sys.exit(m("nessun_dispositivo"))
    return next((d for d in devs if d["is_active"]), devs[0])["id"]


# ================================================================ comandi

def cmd_sync():
    state = load_state()
    sp = client_spotify()
    if not state["spotify_playlist_id"]:
        nome = os.getenv("SPOTIFY_PLAYLIST_NAME") or m("playlist_nome")
        state["spotify_playlist_id"] = crea_playlist(sp, nome)
        save_state(state)
        print(m("playlist_creata", nome=nome))

    gia_presenti = {r["spotify"] for r in state["video"].values() if r.get("spotify")}
    # Nuovi video + quelli non trovati le volte scorse (magari ora sono su Spotify).
    nuovi_id = [i for i in dict.fromkeys(id_playlist_youtube())  # senza doppioni
                if i not in state["video"] or not state["video"][i].get("spotify")]
    dettagli = dettagli_video(nuovi_id)  # i video privati/eliminati non compaiono

    da_aggiungere, da_avvisare = [], []
    for vid in nuovi_id:
        if vid not in dettagli:
            continue
        rec, trovato = abbina(sp, dettagli[vid], state)
        # Avviso una sola volta per video, non a ogni giro orario.
        rec["avvisato"] = state["video"].get(vid, {}).get("avvisato", False)
        if not rec["spotify"] and not rec["avvisato"]:
            da_avvisare.append(rec["titolo"])
            rec["avvisato"] = True
        state["video"][vid] = rec
        uri = rec["spotify"]
        if uri:
            print(m("ok", titolo=rec["titolo"], trovato=trovato))
            if uri not in gia_presenti:  # due clip dello stesso episodio = un solo episodio
                da_aggiungere.append(uri)
                gia_presenti.add(uri)
        else:
            print(m("non_trovato", titolo=rec["titolo"], tipo=m("tipo_" + rec["tipo"])))
        save_state(state)

    if da_aggiungere:
        aggiungi_alla_playlist(sp, state["spotify_playlist_id"], da_aggiungere)
    print(m("fatto", n=len(da_aggiungere)))
    if da_avvisare:
        n = len(da_avvisare)
        titolo = m("notifica_1") if n == 1 else m("notifica_n", n=n)
        elenco = "\n".join(f"• {t[:70]}" for t in da_avvisare[:3]) + (m("e_altri", n=n - 3) if n > 3 else "")
        notifica(titolo, elenco + m("usa_collega"))


def cmd_riprendi(url=None):
    url = url or leggi_appunti()
    vid, secondi = parse_url_youtube(url) if "youtu" in url else (None, 0)
    if not vid:
        sys.exit(m("no_link_appunti"))
    state = load_state()
    sp = client_spotify()

    rec = state["video"].get(vid)
    in_playlist = bool(rec and rec.get("spotify") and state["spotify_playlist_id"])
    if not rec or not rec.get("spotify"):
        dettagli = dettagli_video([vid])
        if vid not in dettagli:
            sys.exit(m("video_non_trovato"))
        rec, _ = abbina(sp, dettagli[vid], state)
        save_state(state)  # salva la cache dei podcast trovati
        if not rec["spotify"]:
            sys.exit(m("non_trovo", titolo=rec["titolo"]))

    posizione = secondi
    if rec["tipo"] == "clip":
        if rec.get("inizio_noto"):
            posizione = rec["inizio"] + secondi
        else:
            posizione = 0
            print(m("clip_inizio_ignoto"))

    device = dispositivo_attivo(sp)
    if in_playlist:
        # Dentro la playlist, così poi prosegue con gli elementi successivi.
        sp.start_playback(device_id=device, context_uri=f"spotify:playlist:{state['spotify_playlist_id']}",
                          offset={"uri": rec["spotify"]}, position_ms=posizione * 1000)
    else:
        sp.start_playback(device_id=device, uris=[rec["spotify"]], position_ms=posizione * 1000)
    print(m("su_spotify", tipo=m("tipo_" + rec["tipo"]), t=mmss(posizione)))


def cmd_torna():
    state = load_state()
    sp = client_spotify()
    pb = sp.current_playback(additional_types="episode")
    if not pb or not pb.get("item"):
        sys.exit(m("niente_in_ascolto"))
    item = pb["item"]
    uri, secondi = item["uri"], pb["progress_ms"] // 1000
    if pb["is_playing"]:
        sp.pause_playback()

    lista = playlist_id_youtube()
    collegati = [(k, r) for k, r in state["video"].items() if r.get("spotify") == uri]
    episodio = next(((k, r) for k, r in collegati if r["tipo"] in ("episodio", "musica")), None)
    clip = [(k, r) for k, r in collegati if r["tipo"] == "clip"]

    if episodio:
        url = f"https://www.youtube.com/watch?v={episodio[0]}&list={lista}&t={secondi}s"
    elif clip:
        # Meglio l'episodio intero su YouTube (stesso minutaggio); altrimenti la clip.
        k, r = clip[0]
        if r.get("video_completo"):
            url = f"https://www.youtube.com/watch?v={r['video_completo']}&t={secondi}s"
        elif r.get("inizio_noto") and secondi >= r["inizio"]:
            url = f"https://www.youtube.com/watch?v={k}&list={lista}&t={secondi - r['inizio']}s"
        else:
            url = f"https://www.youtube.com/watch?v={k}&list={lista}"
    else:
        autore = item["show"]["name"] if item["type"] == "episode" else item["artists"][0]["name"]
        url = "https://www.youtube.com/results?search_query=" + quote(f"{autore} {item['name']}")
    webbrowser.open(url)
    print(m("aperto_youtube", t=mmss(secondi)))


def secondi_da_testo(t):
    """'1:02:03', '45:10', '90' -> secondi."""
    parti = [int(x) for x in t.split(":")]
    s = 0
    for p in parti:
        s = s * 60 + p
    return s


def cmd_collega(video_url, destinazione, inizio=None):
    """Abbina a mano un video (tipicamente una clip senza link) a:
       - il link YouTube dell'episodio intero (con ?t= dove inizia la clip), oppure
       - il link Spotify dell'episodio/brano (+ eventuale minuto di inizio mm:ss)."""
    vid, _ = parse_url_youtube(video_url)
    if not vid:
        sys.exit(m("arg1"))
    state = load_state()
    sp = client_spotify()
    info = dettagli_video([vid]).get(vid)
    if not info:
        sys.exit(m("video_non_trovato"))
    rec = {"titolo": info["titolo"], "tipo": classifica(info), "spotify": None,
           "inizio": 0, "manuale": True}

    link_sp = re.search(r"open\.spotify\.com/(episode|track)/([A-Za-z0-9]{22})", destinazione)
    if link_sp:
        rec["spotify"] = f"spotify:{link_sp.group(1)}:{link_sp.group(2)}"
        if link_sp.group(1) == "track":
            rec["tipo"] = "musica"
        if inizio:
            rec["inizio"] = secondi_da_testo(inizio)
    else:
        completo_id, t = parse_url_youtube(destinazione)
        completo = dettagli_video([completo_id]).get(completo_id) if completo_id else None
        if not completo:
            sys.exit(m("arg2"))
        rec["spotify"], _ = cerca_episodio(sp, completo, state)
        if not rec["spotify"]:
            sys.exit(m("non_trovo_episodio", titolo=completo["titolo"]))
        rec["video_completo"] = completo_id
        rec["inizio"] = secondi_da_testo(inizio) if inizio else t

    if rec["tipo"] != "musica" and rec["spotify"].startswith("spotify:episode:"):
        rec["tipo"] = "clip" if info["durata"] < DURATA_MIN_EPISODIO else "episodio"
    rec["inizio_noto"] = rec["tipo"] == "clip" and rec["inizio"] > 0

    gia = {r["spotify"] for k, r in state["video"].items() if r.get("spotify") and k != vid}
    state["video"][vid] = rec
    if rec["spotify"] not in gia and state["spotify_playlist_id"]:
        aggiungi_alla_playlist(sp, state["spotify_playlist_id"], [rec["spotify"]])
    save_state(state)
    print(m("collegato", titolo=rec["titolo"], uri=rec["spotify"])
          + (m("clip_inizia", t=mmss(rec["inizio"])) if rec["inizio_noto"] else ""))


def cmd_mancanti():
    state = load_state()
    mancanti = [(k, r) for k, r in state["video"].items() if not r.get("spotify")]
    for k, r in mancanti:
        print(f"https://youtu.be/{k}  [{m('tipo_' + r['tipo']) if r.get('tipo') else '?'}]  {r['titolo']}")
    print(m("mancanti", n=len(mancanti)))


if __name__ == "__main__":
    args = sys.argv[1:]
    comando = args[0] if args else "sync"
    if comando == "auto":
        # Sync senza finestra (Utilità di pianificazione): l'output va in sync.log.
        import datetime, traceback
        log = BASE / "sync.log"
        if log.exists() and log.stat().st_size > 1_000_000:
            log.replace(BASE / "sync.old.log")
        with open(log, "a", encoding="utf-8") as f:
            sys.stdout = sys.stderr = f
            print(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M} ===")
            try:
                cmd_sync()
            except SystemExit as e:
                print(e)
            except Exception:
                traceback.print_exc()
    elif comando == "sync":
        cmd_sync()
    elif comando == "riprendi":
        cmd_riprendi(args[1] if len(args) > 1 else None)
    elif comando == "torna":
        cmd_torna()
    elif comando == "mancanti":
        cmd_mancanti()
    elif comando == "collega" and len(args) >= 3:
        cmd_collega(args[1], args[2], args[3] if len(args) > 3 else None)
    else:
        print(m("aiuto"))
