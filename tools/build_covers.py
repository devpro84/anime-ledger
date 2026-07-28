# -*- coding: utf-8 -*-
"""
Match each anime in data/anime.json against the AniList cache, then (with
--commit) write image/synopsis fields into data/anime.json and download +
resize cover art into data/covers/.

Dry-run (default): writes tools/cover_match_report.json for review, touches
nothing else. Review it, add any corrections to OVERRIDES below, then re-run
with --commit.
"""
import argparse, html, json, os, re, subprocess, sys, tempfile, time
import urllib.request, urllib.error
import difflib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ANIME_JSON = os.path.join(ROOT, "data", "anime.json")
CACHE_PATH = os.path.join(HERE, "anilist_cache.json")
REPORT_PATH = os.path.join(HERE, "cover_match_report.json")
COVERS_DIR = os.path.join(ROOT, "data", "covers")

THRESHOLD = 0.45
MAX_SYNOPSIS_CHARS = 360

# title (exact CSV/anime.json string) -> AniList id to force, or None to force "no match".
# Needed for titles whose search query (typo, curly quote, parenthetical year, etc.) returned
# zero candidates from AniList at fetch time, so there's nothing cached to re-rank among.
OVERRIDES = {
    "Jojos Bizarre Adventure": 14719,
    "A Place Furter than the Universe": 99426,
    "Bang Dream! It’s MyGO!!!!!": 163571,
    "Vivy: Flourite eyes song": 128546,
    "Tomorrow’s Joe": 2402,
    "Fullmetal Alchemist (2003)": 121,
    "Kino's Journey (2003)": 486,
    "Nausicaä of the Valley of the Wind": 572,
    "Evangelion Rebuilds": 2759,
    "Love, Chuunibyo, and Other Delusions": 14741,
    "SSSS.Girdman + SSSS.Dynazenon": 99424,
    "The Daily Life of High School Boys": 11843,
    "WorldEnd/SukaSuka": 21860,
    "Nodame Cantabille": 1698,
    "The iDOLM@STER (2011)": 10278,
    "Scum’s Wish": 21701,
    "Akiba Maid Wars": 151379,
    "Kiki’s Delivery Service": 512,
    "Interspecies Reviewers": 110270,
    "Sleepy Princess in the Demon’s Castle": 111428,
    "Urusei Yatsura (1981)": 1293,
    # AniList's exact-title match is the 2001 original (id 120, popularity ~98k);
    # the 2019 remake (popularity ~306k) is almost certainly what poll voters meant.
    "Fruits Basket": 105334,
}

_ID_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
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
"""


def fetch_by_id(anilist_id):
    body = json.dumps({"query": _ID_QUERY, "variables": {"id": anilist_id}}).encode("utf-8")
    req = urllib.request.Request(
        "https://graphql.anilist.co",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "anime-ledger-cover-fetcher/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    return data.get("data", {}).get("Media")


def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def best_match(query, candidates):
    """candidates: list of AniList media dicts (already isAdult-filtered)."""
    if not candidates:
        return None, 0.0
    qn = norm(query)
    best, best_score = None, -1.0
    for c in candidates:
        cands = []
        t = c.get("title") or {}
        for key in ("romaji", "english", "native"):
            if t.get(key):
                cands.append(t[key])
        for syn in c.get("synonyms") or []:
            cands.append(syn)

        score = 0.0
        for cand in cands:
            cn = norm(cand)
            if not cn:
                continue
            ratio = difflib.SequenceMatcher(None, qn, cn).ratio()
            if qn == cn:
                ratio = 1.0
            elif qn in cn or cn in qn:
                ratio = max(ratio, 0.85)
            score = max(score, ratio)

        fmt = (c.get("format") or "").upper()
        if fmt not in ("TV", "TV_SHORT"):
            score -= 0.05

        if score > best_score:
            best_score = score
            best = c
    return best, best_score


def clean_synopsis(text):
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s*[\(\[]\s*(Source|Note)\s*:.*?[\)\]]\s*$", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    if len(text) > MAX_SYNOPSIS_CHARS:
        cut = text[:MAX_SYNOPSIS_CHARS]
        m = list(re.finditer(r"[.!?]\s", cut))
        if m and m[-1].end() > MAX_SYNOPSIS_CHARS * 0.5:
            text = cut[: m[-1].end()].rstrip() + "…"
        else:
            text = cut.rstrip() + "…"
    return text


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def download_and_resize(url, rank, force=False):
    out_path = os.path.join(COVERS_DIR, f"{rank}.jpg")
    if os.path.exists(out_path) and not force:
        return True, "exists"
    os.makedirs(COVERS_DIR, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".img")
    os.close(tmp_fd)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "anime-ledger-cover-fetcher/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp, open(tmp_path, "wb") as f:
            f.write(resp.read())
        result = subprocess.run(
            [
                "sips",
                "-s", "format", "jpeg",
                "-s", "formatOptions", "78",
                "--resampleWidth", "220",
                tmp_path,
                "--out", out_path,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return False, f"sips failed: {result.stderr.strip()}"
        return True, "downloaded"
    except Exception as e:
        return False, str(e)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true", help="write anime.json fields + download covers")
    parser.add_argument("--force", action="store_true", help="re-download covers even if the file already exists")
    args = parser.parse_args()

    anime = load_json(ANIME_JSON, [])
    cache = load_json(CACHE_PATH, {})

    report = []
    matched = 0
    unmatched = 0
    downloaded = 0
    download_failed = []

    for item in anime:
        title = item["title"]
        rank = item["rank"]
        raw_candidates = cache.get(title, [])
        candidates = [c for c in raw_candidates if not c.get("isAdult")]

        override = OVERRIDES.get(title, "unset")
        chosen, score = None, 0.0
        if override is None:
            chosen, score = None, 0.0
        elif override != "unset":
            chosen = next((c for c in raw_candidates if c.get("id") == override), None)
            if chosen is None:
                # Not among this title's cached search candidates (the search query itself
                # returned nothing useful) — fetch the overridden entry directly by id.
                chosen = fetch_by_id(override)
                time.sleep(1.0)
            score = 1.0 if chosen else 0.0
        else:
            chosen, score = best_match(title, candidates)

        entry = {
            "rank": rank,
            "title": title,
            "score": round(score, 3),
            "matched_title": None,
            "anilist_id": None,
            "format": None,
            "site_url": None,
            "has_image": False,
            "has_synopsis": False,
        }

        image_url = None
        synopsis = None
        if chosen and score >= THRESHOLD:
            matched += 1
            t = chosen.get("title") or {}
            entry["matched_title"] = t.get("english") or t.get("romaji")
            entry["anilist_id"] = chosen.get("id")
            entry["format"] = chosen.get("format")
            entry["site_url"] = chosen.get("siteUrl")
            cover = chosen.get("coverImage") or {}
            image_url = cover.get("extraLarge") or cover.get("large") or cover.get("medium")
            synopsis = clean_synopsis(chosen.get("description"))
            entry["has_image"] = bool(image_url)
            entry["has_synopsis"] = bool(synopsis)
        else:
            unmatched += 1

        report.append(entry)

        if args.commit:
            if image_url:
                ok, msg = download_and_resize(image_url, rank, force=args.force)
                if ok:
                    item["image"] = f"data/covers/{rank}.jpg"
                    if msg == "downloaded":
                        downloaded += 1
                        time.sleep(0.35)
                else:
                    item["image"] = None
                    download_failed.append((title, msg))
            else:
                item["image"] = None
            item["synopsis"] = synopsis

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(f"matched: {matched}  unmatched: {unmatched}  (threshold {THRESHOLD})")
    low_conf = [e for e in report if e["anilist_id"] and e["score"] < 0.6]
    print(f"low-confidence matches (score < 0.6, worth eyeballing): {len(low_conf)}")

    if args.commit:
        with open(ANIME_JSON, "w", encoding="utf-8") as f:
            json.dump(anime, f, ensure_ascii=False, indent=2)
        print(f"downloaded this run: {downloaded}")
        if download_failed:
            print(f"download failures: {len(download_failed)}")
            for t, m in download_failed[:20]:
                print("  ", t, "->", m)
        print(f"wrote {ANIME_JSON}")
    else:
        print(f"dry run only — review {REPORT_PATH}, then re-run with --commit")


if __name__ == "__main__":
    main()
