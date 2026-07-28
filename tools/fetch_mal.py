# -*- coding: utf-8 -*-
import csv, json, time, urllib.request, urllib.parse, urllib.error, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "r_anime's Favorite Anime.csv")
CACHE = os.path.join(HERE, "mal_cache.json")

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
    q = urllib.parse.quote(title)
    url = f"https://api.jikan.moe/v4/anime?q={q}&limit=5"
    delay = 2.0
    last_success_data = None  # None = never got a valid response; [] = confirmed no match
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "anime-classifier-script/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
            if "data" in data:
                if data["data"]:
                    return data["data"]
                last_success_data = []
        except Exception:
            pass
        time.sleep(delay)
        delay *= 1.8
    return last_success_data

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
                time.sleep(1.3)
            else:
                print(f"skip (fetch failed) {title}", flush=True)
                time.sleep(0.4)
        if got_any:
            pass_delay = 20
        else:
            pass_delay = min(pass_delay * 1.5, max_pass_delay)
            print(f"nothing succeeded this pass, API likely still down; sleeping {pass_delay:.0f}s", flush=True)
            time.sleep(pass_delay)

if __name__ == "__main__":
    main()
