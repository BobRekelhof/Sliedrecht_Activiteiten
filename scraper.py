"""
Sliedrecht Doet - Agenda Scraper
Haalt elke nacht alle activiteiten op van sliedrechtdoet.nl/agenda
en categoriseert ze naar vier profielen: buitenmens, ontdekker, buurtgenoot, inpakker.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE_URL  = "https://sliedrechtdoet.nl"
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

# ── PROFIEL SCORE REGELS ────────────────────────────────────────────────────
# Elke regel: (lijst van trefwoorden, scores per profiel)
# Scores: 3 = sterke match, 2 = goede match, 1 = lichte match, 0 = geen match
# Profielen: buitenmens | ontdekker | buurtgenoot | inpakker

SCORE_RULES = [

    # ── BUITENMENS: actief, natuur, bewegen, buiten ──
    (["hardlopen", "joggen", "rennen", "sprint", "marathon"],
     {"buitenmens": 3, "ontdekker": 0, "buurtgenoot": 0, "inpakker": 1}),

    (["wandelen", "wandeltocht", "wandelgroep", "nordic walking"],
     {"buitenmens": 3, "ontdekker": 0, "buurtgenoot": 1, "inpakker": 0}),

    (["fietsen", "fiets", "wielrennen", "mountainbike"],
     {"buitenmens": 3, "ontdekker": 1, "buurtgenoot": 0, "inpakker": 0}),

    (["zwemmen", "zwembad", "watersporten", "roeien", "kanoën"],
     {"buitenmens": 3, "ontdekker": 0, "buurtgenoot": 0, "inpakker": 1}),

    (["sport", "fitness", "gym", "bewegen", "actief", "bootcamp", "yoga", "dans", "voetbal", "tennis", "badminton"],
     {"buitenmens": 3, "ontdekker": 0, "buurtgenoot": 0, "inpakker": 1}),

    (["natuur", "buiten", "groen", "park", "bos", "dieren", "planten", "vogels", "biesbosch", "rivier"],
     {"buitenmens": 3, "ontdekker": 2, "buurtgenoot": 0, "inpakker": 1}),

    (["moestuin", "tuin", "tuinieren", "kweken", "zaaien"],
     {"buitenmens": 2, "ontdekker": 1, "buurtgenoot": 1, "inpakker": 3}),

    # ── ONTDEKKER: cultuur, leren, creatief, inspiratie ──
    (["museum", "tentoonstelling", "expositie", "galerie"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 1, "inpakker": 0}),

    (["kunst", "kunstwerk", "schilderen", "tekenen", "aquarel", "beeldhouwen"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 1, "inpakker": 1}),

    (["muziek", "concert", "koor", "zingen", "instrument", "gitaar", "piano"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 2, "inpakker": 0}),

    (["theater", "toneel", "voorstelling", "cabaret", "film", "bioscoop"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 2, "inpakker": 0}),

    (["cursus", "workshop", "training", "les", "leren", "studeren", "opleiding"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 1, "inpakker": 1}),

    (["lezing", "presentatie", "debat", "spreker", "thema-avond", "informatie"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 2, "inpakker": 0}),

    (["geschiedenis", "historisch", "erfgoed", "monument", "archeologie"],
     {"buitenmens": 1, "ontdekker": 3, "buurtgenoot": 1, "inpakker": 0}),

    (["creatief", "knutselen", "handwerk", "breien", "haken", "naaien", "pottenbakken"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 1, "inpakker": 2}),

    (["digitaal", "computer", "internet", "smartphone", "tablet"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 1, "inpakker": 0}),

    (["taal", "taalles", "nederlands", "inburgering"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 2, "inpakker": 0}),

    (["lezen", "boek", "bibliotheek", "leesclub"],
     {"buitenmens": 0, "ontdekker": 3, "buurtgenoot": 1, "inpakker": 0}),

    # ── BUURTGENOOT: gezelligheid, ontmoeten, sociaal, koffie ──
    (["koffie", "thee", "bakkie", "koffieochtend", "koffiedrinken"],
     {"buitenmens": 0, "ontdekker": 1, "buurtgenoot": 3, "inpakker": 1}),

    (["ontmoeten", "ontmoeting", "inloop", "inloopavond", "inloopmorgen"],
     {"buitenmens": 0, "ontdekker": 1, "buurtgenoot": 3, "inpakker": 1}),

    (["gezellig", "gezelligheid", "saamhorigheid", "samen", "sociale"],
     {"buitenmens": 1, "ontdekker": 1, "buurtgenoot": 3, "inpakker": 1}),

    (["lunch", "eten", "maaltijd", "diner", "borrel", "feest"],
     {"buitenmens": 0, "ontdekker": 0, "buurtgenoot": 3, "inpakker": 0}),

    (["babbelen", "praten", "gesprek", "praatgroep", "discussie"],
     {"buitenmens": 0, "ontdekker": 2, "buurtgenoot": 3, "inpakker": 0}),

    (["buurt", "buurtactiviteit", "buurtfeest", "buurtgenoten", "wijk", "buren"],
     {"buitenmens": 1, "ontdekker": 0, "buurtgenoot": 3, "inpakker": 2}),

    (["ouderen", "senioren", "65+", "55+", "volwassenen"],
     {"buitenmens": 1, "ontdekker": 1, "buurtgenoot": 3, "inpakker": 1}),

    (["jongeren", "jeugd", "kinderen", "jongvolwassenen"],
     {"buitenmens": 2, "ontdekker": 1, "buurtgenoot": 2, "inpakker": 1}),

    (["spelletjes", "spel", "kaarten", "bingo", "schaken", "dammen"],
     {"buitenmens": 0, "ontdekker": 1, "buurtgenoot": 3, "inpakker": 0}),

    # ── INPAKKER: vrijwillig, helpen, klussen, doen ──
    (["vrijwillig", "vrijwilliger", "vrijwilligerswerk"],
     {"buitenmens": 0, "ontdekker": 0, "buurtgenoot": 1, "inpakker": 3}),

    (["helpen", "hulp", "ondersteuning", "assisteren", "begeleiden"],
     {"buitenmens": 0, "ontdekker": 0, "buurtgenoot": 1, "inpakker": 3}),

    (["maatje", "maatjesproject", "buddy", "mentor"],
     {"buitenmens": 0, "ontdekker": 0, "buurtgenoot": 2, "inpakker": 3}),

    (["klussen", "repareren", "bouwen", "timmeren", "schilderen", "onderhoud"],
     {"buitenmens": 1, "ontdekker": 0, "buurtgenoot": 0, "inpakker": 3}),

    (["voedselbank", "kledingbank", "inzameling", "donatie"],
     {"buitenmens": 0, "ontdekker": 0, "buurtgenoot": 1, "inpakker": 3}),

    (["inpakken", "sorteren", "uitdelen", "organiseren", "coördineren"],
     {"buitenmens": 0, "ontdekker": 0, "buurtgenoot": 1, "inpakker": 3}),

    (["zorg", "mantelzorg", "thuiszorg", "begeleiding"],
     {"buitenmens": 0, "ontdekker": 0, "buurtgenoot": 2, "inpakker": 3}),

    # ── TIJDSTIP (voor informatieve display, niet voor profiel) ──
    (["09:00", "10:00", "11:00", "08:00", "ochtend", "voormiddag"],
     {"tijd_ochtend": 1}),
    (["12:00", "13:00", "14:00", "15:00", "16:00", "middag", "namiddag"],
     {"tijd_middag": 1}),
    (["17:00", "18:00", "19:00", "20:00", "21:00", "avond"],
     {"tijd_avond": 1}),
]


def compute_scores(text: str) -> dict:
    """Bereken profielscores op basis van trefwoorden in de tekst."""
    text_lower = text.lower()
    scores = {
        "buitenmens": 0,
        "ontdekker":  0,
        "buurtgenoot": 0,
        "inpakker":   0,
    }
    for keywords, award in SCORE_RULES:
        if any(kw in text_lower for kw in keywords):
            for key, pts in award.items():
                if key in scores:
                    scores[key] = max(scores[key], pts)
    return scores


def scrape_page(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  ⚠️  Fout bij ophalen {url}: {e}")
        return None


def extract_agenda_url(item) -> str:
    """Haal de specifieke activiteits-URL op uit een agenda-item."""
    links = item.find_all("a", href=True) if item.name != "a" else [item]
    for a in links:
        href = a["href"]
        if re.search(r"/agenda/\d+/\d{4}-\d{2}-\d{2}/", href):
            return href if href.startswith("http") else BASE_URL + href
    for a in links:
        href = a["href"]
        if "/agenda/" in href and href.rstrip("/") not in ["/agenda", AGENDA_URL]:
            return href if href.startswith("http") else BASE_URL + href
    return AGENDA_URL


def parse_activities(soup: BeautifulSoup) -> list:
    activities = []

    # Zoek specifieke activiteitslinks op de pagina
    specific_links = [
        a for a in soup.select("a[href*='/agenda/']")
        if re.search(r"/agenda/\d+/\d{4}-\d{2}-\d{2}/", a.get("href", ""))
    ]

    print(f"  → {len(specific_links)} activiteitslinks gevonden")

    seen_urls = set()

    for link in specific_links:
        try:
            href = link["href"]
            url = href if href.startswith("http") else BASE_URL + href

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Zoek de omliggende container
            container = link.parent
            for _ in range(5):
                if container and len(container.get_text(strip=True)) > 80:
                    break
                container = container.parent if container else None
            item = container or link

            # Titel
            title_el = item.select_one("h2, h3, h4, strong") if item != link else None
            title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # Volledige tekst voor scoring
            item_text = item.get_text(" ", strip=True)

            # Beschrijving
            desc_el = item.select_one("p")
            desc = desc_el.get_text(strip=True)[:300] if desc_el else ""

            # Locatie
            loc_el = item.select_one(".location, [class*='locatie'], [class*='place'], [class*='adres']")
            location = loc_el.get_text(strip=True) if loc_el else ""

            # Tijdstip
            time_match = re.search(r"\d{1,2}\s+\w+\s+\d{4}\s+van\s+\d{2}:\d{2}", item_text)
            time_str = time_match.group(0) if time_match else ""

            # Frequentie
            freq = ""
            for word in ["wekelijks", "maandelijks", "meerdaags", "dagelijks", "jaarlijks"]:
                if word in item_text.lower():
                    freq = word
                    break

            # Organisator
            org_el = item.select_one("[class*='organis'], [class*='auteur'], [class*='org']")
            organizer = org_el.get_text(strip=True) if org_el else ""

            # Profielscores berekenen
            full_text = f"{title} {desc} {item_text}"
            scores = compute_scores(full_text)

            # Dominant profiel bepalen (voor snelle filtering)
            dominant = max(scores, key=scores.get)
            dominant_score = scores[dominant]

            activities.append({
                "title":     title,
                "organizer": organizer,
                "desc":      desc,
                "url":       url,
                "location":  location,
                "time":      time_str,
                "frequency": freq,
                "scores":    scores,
                "dominant_profile": dominant if dominant_score > 0 else "buurtgenoot",
            })

        except Exception as e:
            print(f"  ⚠️  Item overgeslagen: {e}")
            continue

    return activities


def get_all_pages() -> list:
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

        next_link = soup.select_one("a[rel='next'], .pagination .next")
        if not next_link or page >= 10:
            break
        page += 1

    return all_activities


def main():
    print("🕷️  Sliedrecht Doet scraper gestart...")
    print(f"⏰  {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")

    activities = get_all_pages()

    # Dedupliceer op URL
    seen = set()
    unique = []
    for a in activities:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)

    print(f"\n✅  {len(unique)} unieke activiteiten gevonden")

    # Verdeling over profielen loggen
    for p in ["buitenmens", "ontdekker", "buurtgenoot", "inpakker"]:
        count = sum(1 for a in unique if a.get("dominant_profile") == p)
        print(f"   {p}: {count} activiteiten")

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
