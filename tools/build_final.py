# -*- coding: utf-8 -*-
import csv, json, re, difflib

SRC = "r_anime's Favorite Anime.csv"
CACHE = "mal_cache.json"

DEMO_MAP = {
    "Shounen": "Shonen",
    "Shoujo": "Shojo",
    "Seinen": "Seinen",
    "Josei": "Josei",
    "Kids": "Kodomomuke",
}

DEMO_DESC = {
    "Shonen": "Made for young teen boys (ages 12 to 18), focusing on action, friendship, and growing strong. Famous examples: Naruto and One Piece.",
    "Shojo": "Made for young teen girls (ages 12 to 18), focusing on romance, school life, and big emotions. Famous examples: Sailor Moon and Fruits Basket.",
    "Seinen": "Made for adult men (ages 18+), featuring darker plots, deep psychology, or heavy violence. Famous examples: Berserk and Vinland Saga.",
    "Josei": "Made for adult women (ages 18+), showing realistic romance and everyday life issues. Famous examples: Paradise Kiss.",
    "Kodomomuke": "Made for young children, with bright, fun, and easy lessons. Famous examples: Pokémon and Doraemon.",
}
GENRE_DESC = {
    "Isekai": "Stories where a normal person gets sent or reborn into a fantasy world. Example: Sword Art Online.",
    "Mecha": "Shows featuring battles with giant robots. Example: Mobile Suit Gundam.",
    "Slice of Life": "Relaxing shows about everyday life and normal moments. Example: K-On!.",
    "Fantasy / Action": "Worlds filled with magic, monsters, and heavy fights. Example: Demon Slayer.",
    "Other": "Doesn't clearly fit the four genre buckets above (e.g. sports, mystery, historical, sci-fi drama, crime).",
}

def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def best_match(query, results):
    if not results:
        return None, 0.0
    qn = norm(query)
    best, best_score = None, -1.0
    for r in results:
        cands = [r.get("title", "")]
        if r.get("title_english"):
            cands.append(r["title_english"])
        for syn in r.get("title_synonyms", []) or []:
            cands.append(syn)
        titles_obj = r.get("titles", []) or []
        for t in titles_obj:
            if t.get("title"):
                cands.append(t["title"])
        score = 0.0
        for c in cands:
            cn = norm(c)
            if not cn:
                continue
            ratio = difflib.SequenceMatcher(None, qn, cn).ratio()
            if qn == cn:
                ratio = 1.0
            elif qn in cn or cn in qn:
                ratio = max(ratio, 0.85)
            score = max(score, ratio)
        if score > best_score:
            best_score = score
            best = r
    return best, best_score

with open(CACHE, encoding="utf-8") as f:
    cache = json.load(f)

with open(SRC, encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    rows = list(reader)
header = rows[0][:9]

low_confidence = []
no_result = []
demo_from_mal = 0
demo_fallback = 0
genre_other = []

out_rows = []
match_report = []

for row in rows[1:]:
    core = row[:9] if len(row) >= 9 else row + [""] * (9 - len(row))
    if not (len(core) > 1 and core[1].strip()):
        continue
    title = core[1]
    results = cache.get(title, [])
    match, score = best_match(title, results)

    genres, themes, demographics = set(), set(), []
    matched_title = ""
    if match and score >= 0.45:
        genres = {g["name"] for g in match.get("genres", [])} | {g["name"] for g in match.get("explicit_genres", [])}
        themes = {g["name"] for g in match.get("themes", [])}
        demographics = [g["name"] for g in match.get("demographics", [])]
        matched_title = match.get("title", "")
    else:
        no_result.append(title)

    # ---- Demographic ----
    if demographics:
        demo = DEMO_MAP.get(demographics[0], "")
        demo_from_mal += 1
    else:
        demo = ""
        demo_fallback += 1

    # ---- Genre ----
    if "Isekai" in genres or "Isekai" in themes:
        genre = "Isekai"
    elif "Mecha" in genres:
        genre = "Mecha"
    elif "Slice of Life" in genres:
        genre = "Slice of Life"
    elif ("Fantasy" in genres or "Supernatural" in genres) and ("Action" in genres or "Adventure" in genres):
        genre = "Fantasy / Action"
    else:
        genre = "Other"
        genre_other.append((title, matched_title, sorted(genres), sorted(themes), round(score,2)))

    match_report.append((title, matched_title, round(score, 2), sorted(genres), sorted(themes), demographics))

    core.append(demo)
    core.append(genre)
    out_rows.append(core)

print("demo_from_mal:", demo_from_mal, "demo_fallback:", demo_fallback)
print("no_result (low/no confidence match):", len(no_result))
print("genre Other count:", len(genre_other))

with open("match_report.json", "w", encoding="utf-8") as f:
    json.dump({
        "no_result": no_result,
        "genre_other": genre_other,
        "full_report": match_report,
    }, f, ensure_ascii=False, indent=1)

print("done")
