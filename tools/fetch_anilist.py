# -*- coding: utf-8 -*-
import csv, json, time, urllib.request, urllib.error, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "r_anime's Favorite Anime.csv")
CACHE = os.path.join(HERE, "anilist_cache.json")

API_URL = "https://graphql.anilist.co"

QUERY = """
query ($q: String, $page: Int) {
  Page(page: $page, perPage: 5) {
    media(search: $q, type: ANIME) {
      id
      title { romaji english native }
      synonyms
      format
      seasonYear
      isAdult
      coverImage { extraLarge large medium color }
      description(asHtml: false)
      siteUrl
    }
  }
}
"""

def load_titles():
    with open(SRC, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        titles = []
        for row in reader:
            if len(row) > 1 and row[1].strip():
                titles.append(row[1])
    return titles

def load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)
    os.replace(tmp, CACHE)

def fetch(title, retries=3):
    """Returns a list of candidate media dicts on success (possibly empty
    if AniList genuinely found nothing), or None if we never got a valid
    response (caller must NOT cache this — retry in a later pass)."""
    body = json.dumps({"query": QUERY, "variables": {"q": title, "page": 1}}).encode("utf-8")
    delay = 3.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                API_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "anime-ledger-cover-fetcher/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                remaining = resp.headers.get("X-RateLimit-Remaining")
                data = json.load(resp)
            if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
                time.sleep(3)
            if "data" in data and data["data"] and data["data"].get("Page"):
                return data["data"]["Page"]["media"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = e.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 60.0
                print(f"  429 rate limited, sleeping {wait:.0f}s", flush=True)
                time.sleep(wait)
                continue
        except Exception:
            pass
        time.sleep(delay)
        delay *= 1.8
    return None

def main():
    titles = load_titles()
    cache = load_cache()
    total = len(titles)
    pass_delay = 20
    max_pass_delay = 180
    while True:
        remaining = [t for t in titles if t not in cache]
        if not remaining:
            print("ALL DONE", len(cache), "/", total, flush=True)
            return
        print(f"--- pass start: {len(remaining)} remaining ---", flush=True)
        got_any = False
        for title in remaining:
            results = fetch(title)
            if results is not None:
                cache[title] = results
                save_cache(cache)
                got_any = True
                print(f"[{len(cache)}/{total}] OK {title} -> {len(results)} results", flush=True)
                time.sleep(2.1)  # ~30/min budget, leave headroom
            else:
                print(f"skip (fetch failed) {title}", flush=True)
                time.sleep(0.5)
        if got_any:
            pass_delay = 20
        else:
            pass_delay = min(pass_delay * 1.5, max_pass_delay)
            print(f"nothing succeeded this pass; sleeping {pass_delay:.0f}s", flush=True)
            time.sleep(pass_delay)

if __name__ == "__main__":
    main()
