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

# ── TAG MAPPING ──────────────────────────────────────────────────────────────
# Maps keywords found on the site to our three matcher dimensions:
# tempo (snelwandelaar / etalagekijker / buurtprater)
# energie (handen / hersens / bakkie)
# tijd (ochtend / middag / avond)

TEMPO_MAP = {
    "snelwandelaar": ["sport", "bewegen", "fitness", "hardlopen", "wandelen",
                      "zwemmen", "voetbal", "gym", "dans", "yoga", "actief"],
    "etalagekijker": ["cultuur", "kunst", "muziek", "theater", "museum",
                      "workshop", "cursus", "leren", "lezen", "natuur",
                      "creatief", "schilderen", "tekenen", "fotograferen"],
    "buurtprater":   ["ontmoeten", "gezellig", "koffie", "inloop", "babbel",
                      "sociaal", "buurt", "samen", "vrijwillig", "hulp",
                      "ouderen", "senioren", "maatje"],
}

ENERGIE_MAP = {
    "handen":  ["klussen", "tuin", "moestuin", "knutselen", "repareren",
                "bouwen", "sport", "bewegen", "fitness", "hardlopen",
                "zwemmen", "voetbal", "dans", "yoga", "actief", "schoonmaken"],
    "hersens": ["workshop", "cursus", "leren", "lezing", "museum", "cultuur",
                "kunst", "muziek", "theater", "lezen", "taal", "digitaal",
                "computer", "creatief", "schilderen", "tekenen"],
    "bakkie":  ["ontmoeten", "koffie", "inloop", "buurtactiviteit", "gezellig",
                "samen", "lunch", "eten", "drinken", "sociaal", "vrijwillig",
                "maatje", "zingen", "spel", "spelletjes"],
}

TIJD_MAP = {
    "ochtend": ["ochtend", "09:00", "10:00", "11:00", "08:00",
                "morning", "'s ochtends", "voormiddag"],
    "middag":  ["middag", "12:00", "13:00", "14:00", "15:00", "16:00",
                "'s middags", "namiddag", "lunch"],
    "avond":   ["avond", "17:00", "18:00", "19:00", "20:00", "21:00",
                "'s avonds", "nacht"],
}


def keyword_match(text: str, keyword_lists: dict) -> list:
    """Return all keys whose keywords appear in text (lowercased)."""
    text_lower = text.lower()
    matched = []
    for key, keywords in keyword_lists.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(key)
    return matched or list(keyword_lists.keys())  # fallback: all


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

            # Derive tags
            tempo  = keyword_match(full_text, TEMPO_MAP)
            energie = keyword_match(full_text, ENERGIE_MAP)
            tijd   = keyword_match(item_text, TIJD_MAP)

            activities.append({
                "title":    title,
                "desc":     desc[:300] if desc else title,
                "url":      url,
                "location": location,
                "tags": {
                    "tempo":   tempo,
                    "energie": energie,
                    "tijd":    tijd,
                },
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
