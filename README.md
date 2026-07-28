# The Anime Ledger

A small installable web app for browsing, filtering, searching, and starring r/anime's
community-voted top 500 favorite anime — tagged by demographic (Shonen/Shojo/Seinen/Josei/
Kodomomuke) and story genre (Isekai/Mecha/Slice of Life/Fantasy-Action/Other).

No backend, no build step, no framework. Static HTML/CSS/JS + a JSON dataset, installable
as a PWA on iOS and Android via "Add to Home Screen."

## Structure

```
index.html              app shell
styles.css               all styling (light + dark theme via CSS custom properties)
app.js                    filtering / sorting / starring / PWA install logic
manifest.webmanifest      PWA manifest
sw.js                     service worker (offline cache)
icons/                    app icons (generated from icons/icon.svg)
data/anime.json           the dataset — 500 self-contained records
data/covers/              cover art thumbnails (rank.jpg), sourced from AniList
tools/                    data-sourcing scripts (see below) + raw CSV inputs
```

## Data

`data/anime.json` is an array of records, each fully self-contained (no join needed):

```json
{
  "rank": 2,
  "title": "Steins;Gate",
  "votes": { "first_place": 97, "second_place": 74, "...": "..." },
  "total_points": 1715,
  "demographic": { "tag": "Seinen", "description": "..." },
  "genre": { "tag": "Other", "description": "..." },
  "image": "data/covers/2.jpg",
  "synopsis": "Self-proclaimed mad scientist Okabe Rintarou..."
}
```

`image`/`synopsis` are `null` for the handful of titles that couldn't be confidently matched.

Source: the r/anime community favorites poll (`tools/r_anime's Favorite Anime.csv`).

- **Demographic/genre tags**: cross-referenced against MyAnimeList (via the Jikan API)
  where a confident match exists; `tools/fetch_mal.py` fetches and caches that data
  (`tools/mal_cache.json`), and `tools/build_final.py` merges it into the dataset, falling
  back to a manually-reasoned tag when MAL has no match or no demographic listed.
- **Cover art/synopsis**: sourced from [AniList](https://anilist.co)'s GraphQL API (chosen
  over MyAnimeList/Jikan for this pass — more reliable rate limiting, no API key). Covers
  are downloaded once and stored locally under `data/covers/{rank}.jpg` (resized to ~220px
  wide via macOS `sips`) so the app stays fully self-contained and works offline through the
  existing service worker — nothing is hotlinked at runtime.

To refresh the dataset:

1. `python3 tools/fetch_anilist.py` — resumable, safe to re-run, caches to `tools/anilist_cache.json`.
2. `python3 tools/build_covers.py` — dry run, writes `tools/cover_match_report.json` for review
   (fuzzy-matches titles against the AniList cache; anything scoring under ~0.6 is worth a look).
   Fix any bad matches via the `OVERRIDES` dict at the top of the script, then:
3. `python3 tools/build_covers.py --commit` — writes `image`/`synopsis` into `data/anime.json`
   and downloads + resizes the matched covers into `data/covers/`.

The equivalent MAL-side refresh: `python3 tools/fetch_mal.py`, then `python3 tools/build_final.py`
(demographic/genre tags — currently a manual copy into `data/anime.json`, unlike the covers script).

## Running locally

```
python3 -m http.server 8000
```

then open `http://localhost:8000`.

## Deploying (GitHub Pages)

Push to a GitHub repo, then in **Settings → Pages** set source to "Deploy from a branch",
branch `main`, folder `/ (root)`. The site becomes installable at the resulting
`github.io` URL.
