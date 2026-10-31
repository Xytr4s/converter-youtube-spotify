# 🎧 Converter YouTube → Spotify

Copia automaticamente una playlist YouTube su Spotify (**musica, episodi di podcast e clip di podcast**)
e permette di **passare da una piattaforma all'altra allo stesso minuto**.

## Funzioni

| Comando | Cosa fa |
|---|---|
| `sync.bat` / `python converter.py sync` | Aggiunge alla playlist Spotify i nuovi video della playlist YouTube e riprova quelli non trovati |
| `riprendi.bat` | Su YouTube: tasto destro → *Copia URL del video all'ora corrente*, poi `riprendi.bat`: Spotify riparte da quel punto |
| `torna.bat` | Mette in pausa Spotify e apre il video corrispondente su YouTube allo stesso minuto |
| `python converter.py mancanti` | Elenca i video non trovati su Spotify |
| `python converter.py collega CLIP DEST [mm:ss]` | Abbina a mano una clip all'episodio intero (link YouTube con `?t=` o link Spotify) |
| `python converter.py auto` | Sync silenzioso con log in `sync.log` e notifica di Windows per i video non trovati (per l'Utilità di pianificazione) |

## Come abbina i video

- **Musica** (categoria Musica, canali "- Topic"/VEVO): pulisce il titolo (*"(Official Video)"*, *"[HD]"*…) e cerca artista + brano.
- **Episodi** (video lunghi, soglia configurabile): trova il podcast dal link Spotify nella descrizione o dal nome del canale, poi l'episodio per **numero** (`#324`, `Ep. 45`), titolo e **durata**.
- **Clip**: risale all'episodio intero tramite il link nella descrizione; se il link ha `?t=` sa anche in che punto dell'episodio inizia la clip.

## Installazione

1. `pip install -r requirements.txt`
2. Chiave API di **YouTube Data API v3** (Google Cloud Console → Credenziali → Chiave API).
3. App su **Spotify Developer Dashboard** con Redirect URI `http://127.0.0.1:8888/callback` (Web API).
4. Copia `.env.example` in `.env` e compila i valori. La playlist YouTube deve essere *Pubblica* o *Non in elenco*.
5. `sync.bat`: la prima volta si apre il browser per autorizzare Spotify.

Per far partire la riproduzione (`riprendi` / `torna`) serve Spotify **Premium** e un dispositivo Spotify aperto.

### Sync automatico ogni ora (Windows)

```powershell
$dir = (Get-Location).Path
$a = New-ScheduledTaskAction -Execute (Get-Command pythonw).Source -Argument "`"$dir\converter.py`" auto" -WorkingDirectory $dir
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "Converter YouTube-Spotify" -Action $a -Trigger $t
```

## File locali (non nel repo)

`.env` (chiavi), `.spotify_token` (accesso Spotify), `stato.json` (abbinamenti), `sync.log`.
