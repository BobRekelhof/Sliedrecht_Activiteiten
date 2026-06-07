"""
Sliedrecht Doet - Agenda Scraper
Haalt elke nacht alle activiteiten op van sliedrechtdoet.nl/agenda
en slaat ze op als activities.json met tags voor de matcher.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE_URL = "https://sliedrechtdoet.nl"
AGENDA_URL = "https://sliedrechtdoet.nl/agenda"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── SCORE MAPPING ──────────────────────────────────────────────────────────────
# Each keyword awards points (0–3) to the matching quiz answer.
# 3 = strong match, 2 = good match, 1 = loose match, 0 = no match (default).

SCORE_RULES = [
  # (keywords_in_text, scores_dict)
  # TEMPO
  (["hardlopen", "rennen", "joggen", "sprint"],
   {"snelwandelaar": 3, "etalagekijker": 0, "buurtprater": 0}),
  (["wandelen", "fietsen", "zwemmen", "sport", "fitness", "bewegen", "gym", "actief", "dans", "yoga"],
   {"snelwandelaar": 3, "etalagekijker": 1, "buurtprater": 1}),
  (["workshop", "cursus", "kunst", "cultuur", "muziek", "theater", "museum", "lezen", "creatief", "schilderen", "tekenen", "natuur", "geschiedenis"],
   {"snelwandelaar": 0, "etalagekijker": 3, "buurtprater": 1}),
  (["ontmoeten", "koffie", "gezellig", "babbel", "inloop", "buurtactiviteit", "samen", "sociaal", "vrijwillig", "maatje", "lunch", "eten"],
   {"snelwandelaar": 0, "etalagekijker": 1, "buurtprater": 3}),

  # ENERGIE
  (["tuin", "moestuin", "knutselen", "klussen", "bouwen", "repareren"],
   {"handen": 3, "hersens": 1, "bakkie": 0}),
  (["sport", "hardlopen", "zwemmen", "fietsen", "wandelen", "bewegen", "gym", "dans", "yoga", "fitness"],
   {"handen": 3, "hersens": 0, "bakkie": 0}),
  (["workshop", "cursus", "leren", "lezing", "museum", "cultuur", "kunst", "muziek", "theater", "taal", "digitaal", "computer", "schilderen", "tekenen", "geschiedenis"],
   {"handen": 0, "hersens": 3, "bakkie": 1}),
  (["koffie", "ontmoeten", "inloop", "gezellig", "samen", "lunch", "eten", "sociaal", "vrijwillig", "maatje", "spelletjes", "zingen"],
   {"handen": 0, "hersens": 1, "bakkie": 3}),

  # TIJD
  (["09:00", "10:00", "11:00", "08:00", "ochtend", "voormiddag", "morgenvroeg"],
   {"ochtend": 3, "middag": 0, "avond": 0}),
  (["12:00", "13:00", "14:00", "15:00", "16:00", "middag", "namiddag", "lunch"],
   {"ochtend": 0, "middag": 3, "avond": 0}),
  (["17:00", "18:00", "19:00", "20:00", "21:00", "avond", "nacht"],
   {"ochtend": 0, "middag": 0, "avond": 3}),
]

def compute_scores(text: str) -> dict:
  """Return a scores dict with points for each quiz answer."""
  text_lower = text.lower()
  scores = {
    "snelwandelaar": 0, "etalagekijker": 0, "buurtprater": 0,
    "handen": 0, "hersens": 0, "bakkie": 0,
    "ochtend": 0, "middag": 0, "avond": 0,
  }
  for keywords, award in SCORE_RULES:
    if any(kw in text_lower for kw in keywords):
      for key, pts in award.items():
        scores[key] = max(scores[key], pts)  # take highest matching rule
  return scores


def scrape_page(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  ⚠️  Fout bij ophalen {url}: {e}")
        return None


def parse_activities(soup: BeautifulSoup) -> list[dict]:
    activities = []

    # sliedrechtdoet.nl renders agenda items as article or list elements.
    # We try multiple selectors to be resilient against layout changes.
    items = (
        soup.select("article.agenda-item") or
        soup.select(".agenda-item") or
        soup.select(".event-item") or
        soup.select("[class*='agenda']") or
        soup.select("li.item")
    )

    if not items:
        # Fallback: grab any card-like blocks with a link and title
        items = soup.select("a[href*='/agenda/']")

    print(f"  → {len(items)} items gevonden op pagina")

    seen_urls = set()

    for item in items:
        try:
            # Title
            title_el = (
                item.select_one("h2, h3, h4, .title, .event-title, strong") or
                item
            )
            title = title_el.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # URL
            link_el = item if item.name == "a" else item.select_one("a[href]")
            url = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                url = href if href.startswith("http") else BASE_URL + href

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Only keep agenda links
            if url and "/agenda/" not in url:
                continue

            # Description
            desc_el = item.select_one("p, .description, .intro, .summary")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            # Full text for tag matching
            full_text = f"{title} {desc}"

            # Try to extract date/time info from the item text
            item_text = item.get_text(" ", strip=True)

            # Location
            loc_el = item.select_one(".location, .address, [class*='locatie']")
            location = loc_el.get_text(strip=True) if loc_el else ""

            # Derive scores
            scores = compute_scores(full_text + " " + item_text)

            activities.append({
                "title":    title,
                "desc":     desc[:300] if desc else title,
                "url":      url,
                "location": location,
                "scores":   scores,
                "raw_text": item_text[:500],
            })

        except Exception as e:
            print(f"  ⚠️  Item overgeslagen: {e}")
            continue

    return activities


def get_all_pages() -> list[dict]:
    all_activities = []
    page = 1

    while True:
        url = AGENDA_URL if page == 1 else f"{AGENDA_URL}?page={page}"
        print(f"\n📄 Pagina {page}: {url}")
        soup = scrape_page(url)
        if not soup:
            break

        activities = parse_activities(soup)
        if not activities:
            print("  → Geen activiteiten meer, stoppen.")
            break

        all_activities.extend(activities)

        # Check for a "next page" link
        next_link = soup.select_one("a[rel='next'], .pagination .next, a[href*='page=']")
        if not next_link or page >= 10:  # safety cap at 10 pages
            break

        page += 1

    return all_activities


def main():
    print("🕷️  Sliedrecht Doet scraper gestart...")
    print(f"⏰  {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")

    activities = get_all_pages()

    # Deduplicate by title
    seen = set()
    unique = []
    for a in activities:
        key = a["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    print(f"\n✅  {len(unique)} unieke activiteiten gevonden")

    output = {
        "updated_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "source": AGENDA_URL,
        "count": len(unique),
        "activities": unique,
    }

    with open("activities.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("💾  activities.json opgeslagen")


if __name__ == "__main__":
    main()
