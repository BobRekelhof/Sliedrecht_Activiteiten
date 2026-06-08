"""
Sliedrecht Doet - Agenda Scraper v2
Haalt elke nacht activiteiten op van sliedrechtdoet.nl/agenda.
Bezoekt elke individuele activiteitspagina voor de volledige beschrijving,
en categoriseert op vier profielen: buitenmens, ontdekker, buurtgenoot, inpakker.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime

BASE_URL   = "https://sliedrechtdoet.nl"
AGENDA_URL = "https://sliedrechtdoet.nl/agenda"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://sliedrechtdoet.nl/",
}

# Datum-patroon — tekst die ALLEEN een datum is wordt nooit als beschrijving gebruikt
DATE_ONLY = re.compile(
    r"^\d{1,2}\s+\w+\s+\d{4}\s+van\s+\d{2}:\d{2}",
)

# ── PROFIEL SCORE REGELS ────────────────────────────────────────────────────
# (trefwoorden, {profiel: score})
# Scores: 3=sterke match, 2=goede match, 1=lichte match
# Regels zijn EXCLUSIEF: een "koffie"-activiteit scoort NIET op buitenmens

SCORE_RULES = [

    # ── BUITENMENS ──
    (["hardlopen", "joggen", "rennen", "marathon", "trailrun"],
     {"buitenmens": 3}),

    (["wandelen", "wandeltocht", "wandelgroep", "nordic walking", "wandelclub"],
     {"buitenmens": 3, "buurtgenoot": 1}),

    (["fietsen", "fiets", "wielrennen", "mountainbike", "e-bike"],
     {"buitenmens": 3}),

    (["zwemmen", "zwembad", "watersporten", "roeien", "kanoën", "sup"],
     {"buitenmens": 3}),

    (["sport", "fitness", "gym", "bootcamp", "voetbal", "tennis",
      "badminton", "volleyball", "basketball", "hockey"],
     {"buitenmens": 3}),

    (["yoga", "dans", "zumba", "pilates", "tai chi"],
     {"buitenmens": 2, "ontdekker": 1}),

    (["natuur", "buiten", "buitenactiviteit", "park", "bos",
      "biesbosch", "rivier", "vogels", "dieren", "planten"],
     {"buitenmens": 3, "ontdekker": 1}),

    # moestuin scoort op inpakker (klussen) én buurtgenoot, NIET op buitenmens
    (["moestuin", "tuinieren", "kweken", "zaaien", "oogsten"],
     {"inpakker": 2, "buurtgenoot": 1, "ontdekker": 1}),

    # ── ONTDEKKER ──
    (["museum", "tentoonstelling", "expositie", "galerie", "erfgoed"],
     {"ontdekker": 3}),

    (["kunst", "kunstwerk", "schilderen", "tekenen", "aquarel",
      "beeldhouwen", "fotografie", "kleuren", "creatief"],
     {"ontdekker": 3, "buurtgenoot": 1}),

    (["muziek", "concert", "koor", "zingen", "instrument",
      "gitaar", "piano", "drummen"],
     {"ontdekker": 3, "buurtgenoot": 1}),

    (["theater", "toneel", "voorstelling", "cabaret", "film",
      "bioscoop", "optreden"],
     {"ontdekker": 3, "buurtgenoot": 1}),

    (["cursus", "workshop", "training", "opleiding"],
     {"ontdekker": 3}),

    (["lezing", "presentatie", "spreker", "thema-avond", "debat"],
     {"ontdekker": 3, "buurtgenoot": 1}),

    (["geschiedenis", "historisch", "monument", "archeologie", "erfgoed",
      "onderhuis", "baggermuseum"],
     {"ontdekker": 3}),

    (["breien", "haken", "naaien", "borduren", "handwerk", "knutselen",
      "pottenbakken", "aangehaakt"],
     {"ontdekker": 3, "buurtgenoot": 1, "inpakker": 1}),

    (["digitaal", "computer", "internet", "smartphone", "tablet", "ict"],
     {"ontdekker": 3}),

    (["taal", "taalles", "nederlands leren", "inburgering", "nt2"],
     {"ontdekker": 3}),

    (["lezen", "boek", "bibliotheek", "leesclub", "voorlezen"],
     {"ontdekker": 3, "buurtgenoot": 1}),

    (["huiswerk", "huiswerkbegeleiding", "bijles", "rekenen", "leren"],
     {"ontdekker": 2, "inpakker": 1}),

    # ── BUURTGENOOT ──
    (["koffie", "thee", "bakkie", "koffieochtend"],
     {"buurtgenoot": 3}),

    (["ontmoeten", "ontmoeting", "inloop", "inloopmorgen", "inloopavond",
      "ontmoet", "ontmoetingsplek"],
     {"buurtgenoot": 3}),

    (["gezellig", "gezelligheid", "saamhorigheid", "samen"],
     {"buurtgenoot": 2}),

    (["lunch", "lunchen", "maaltijd", "eten", "diner", "borrel"],
     {"buurtgenoot": 3}),

    (["weekmarkt", "markt", "braderie", "evenement", "festival", "feest"],
     {"buurtgenoot": 3, "buitenmens": 1}),

    (["babbelen", "praten", "gesprek", "praatgroep"],
     {"buurtgenoot": 3}),

    (["ouders", "opvoeding", "baby", "peuter", "gezin"],
     {"buurtgenoot": 3}),

    (["senioren", "ouderen", "55+", "65+", "grijsaards"],
     {"buurtgenoot": 2}),

    (["spelletjes", "spel", "kaarten", "bingo", "schaken", "dammen"],
     {"buurtgenoot": 3, "ontdekker": 1}),

    # ── INPAKKER ──
    (["vrijwillig", "vrijwilliger", "vrijwilligerswerk"],
     {"inpakker": 3}),

    (["helpen", "hulp", "ondersteuning", "assisteren", "begeleiden",
      "begeleiding"],
     {"inpakker": 3}),

    (["maatje", "maatjesproject", "buddy", "mentor"],
     {"inpakker": 3, "buurtgenoot": 1}),

    (["klussen", "repareren", "bouwen", "timmeren", "onderhoud",
      "opknappen", "schoonmaken"],
     {"inpakker": 3}),

    (["voedselbank", "kledingbank", "inzameling", "donatie"],
     {"inpakker": 3}),

    (["inpakken", "sorteren", "uitdelen", "organiseren"],
     {"inpakker": 3}),

    (["zorg", "mantelzorg", "thuiszorg"],
     {"inpakker": 3, "buurtgenoot": 1}),
]

# Nulscores — startpunt
PROFILEN = ["buitenmens", "ontdekker", "buurtgenoot", "inpakker"]


def compute_scores(text: str) -> dict:
    """
    Bereken profielscores EXCLUSIEF:
    elke regel kent alleen punten toe aan de profielen die erin staan.
    Profielen die niet in de regel staan krijgen 0 (niet verhoogd).
    """
    text_lower = text.lower()
    scores = {p: 0 for p in PROFILEN}

    for keywords, award in SCORE_RULES:
        if any(kw in text_lower for kw in keywords):
            for profiel, pts in award.items():
                # Neem de hoogste score als meerdere regels matchen
                scores[profiel] = max(scores[profiel], pts)

    return scores


def is_date_only(text: str) -> bool:
    """Geeft True als de tekst alleen een datum/tijdstip bevat."""
    return bool(DATE_ONLY.match(text.strip()))


def fetch(url: str, delay: float = 0.5):
    """Haal een pagina op met een kleine pauze om de server te ontzien."""
    time.sleep(delay)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  ⚠️  Fout bij ophalen {url}: {e}")
        return None


def fetch_activity_detail(url: str) -> dict:
    """
    Bezoek de individuele activiteitspagina en extraheer:
    - volledige beschrijving
    - locatie
    - organisator
    - tijdstip
    """
    soup = fetch(url, delay=0.8)
    if not soup:
        return {}

    result = {}

    # Beschrijving: zoek de langste <p> buiten navigatie/footer
    paragraphs = soup.select("main p, article p, .content p, .description p, .body p")
    if not paragraphs:
        paragraphs = soup.find_all("p")

    best_desc = ""
    for p in paragraphs:
        text = p.get_text(strip=True)
        # Sla datum-only en te korte teksten over
        if len(text) > len(best_desc) and not is_date_only(text) and len(text) > 30:
            best_desc = text
    if best_desc:
        result["desc"] = best_desc[:400]

    # Locatie
    loc_candidates = soup.select(
        "[class*='locatie'], [class*='location'], [class*='place'], "
        "[class*='adres'], [class*='address'], [itemprop='location']"
    )
    for el in loc_candidates:
        t = el.get_text(strip=True)
        if t and len(t) < 100:
            result["location"] = t
            break

    # Organisator
    org_candidates = soup.select(
        "[class*='organis'], [class*='auteur'], [class*='org'], "
        "[class*='aanbieder'], [class*='provider']"
    )
    for el in org_candidates:
        t = el.get_text(strip=True)
        if t and len(t) < 80:
            result["organizer"] = t
            break

    # Tijdstip — zoek volledige tijdstip-tekst op de detailpagina
    full_text = soup.get_text(" ", strip=True)
    time_match = re.search(
        r"\d{1,2}\s+\w+\s+\d{4}\s+van\s+\d{2}:\d{2}\s+tot\s+\d{2}:\d{2}\s+uur",
        full_text
    )
    if time_match:
        result["time"] = time_match.group(0)

    return result


def parse_agenda_page(soup: BeautifulSoup) -> list:
    """Extraheer activiteitslinks van de agendapagina."""
    links = [
        a for a in soup.select("a[href*='/agenda/']")
        if re.search(r"/agenda/\d+/\d{4}-\d{2}-\d{2}/", a.get("href", ""))
    ]
    print(f"  → {len(links)} activiteitslinks gevonden")

    seen = set()
    results = []

    for link in links:
        href = link["href"]
        url  = href if href.startswith("http") else BASE_URL + href
        if url in seen:
            continue
        seen.add(url)

        # Titel van de link-tekst of omliggende heading
        container = link.parent
        for _ in range(5):
            if container and len(container.get_text(strip=True)) > 40:
                break
            container = container.parent if container else None

        title_el = (container or link).select_one("h2,h3,h4,strong") if container != link else None
        title    = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # Frequentie uit omliggende tekst
        item_text = (container or link).get_text(" ", strip=True) if container else ""
        freq = ""
        for word in ["wekelijks", "maandelijks", "meerdaags", "dagelijks", "jaarlijks"]:
            if word in item_text.lower():
                freq = word
                break

        results.append({"title": title, "url": url, "frequency": freq})

    return results


def get_all_agenda_links() -> list:
    """Doorloop alle agendapagina's en verzamel activiteitslinks."""
    all_items = []
    page = 1

    while True:
        url  = AGENDA_URL if page == 1 else f"{AGENDA_URL}?page={page}"
        print(f"\n📄 Agendapagina {page}: {url}")
        soup = fetch(url)
        if not soup:
            break

        items = parse_agenda_page(soup)
        if not items:
            print("  → Geen activiteiten meer, stoppen.")
            break

        all_items.extend(items)

        next_link = soup.select_one("a[rel='next'], .pagination .next")
        if not next_link or page >= 10:
            break
        page += 1

    return all_items


def main():
    print("🕷️  Sliedrecht Doet scraper v2 gestart...")
    print(f"⏰  {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")

    # Stap 1: verzamel alle links van de agendapagina's
    agenda_items = get_all_agenda_links()

    # Dedupliceer op URL
    seen_urls = set()
    unique_items = []
    for item in agenda_items:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique_items.append(item)

    print(f"\n🔗  {len(unique_items)} unieke activiteiten gevonden")
    print("📖  Detailpagina's ophalen voor beschrijvingen...\n")

    activities = []

    for i, item in enumerate(unique_items):
        print(f"  [{i+1}/{len(unique_items)}] {item['title'][:60]}")

        # Stap 2: haal de detailpagina op voor volledige info
        detail = fetch_activity_detail(item["url"])

        title     = item["title"]
        desc      = detail.get("desc", "")
        location  = detail.get("location", "")
        organizer = detail.get("organizer", "")
        time_str  = detail.get("time", "")
        freq      = item["frequency"]

        # Stap 3: scores berekenen op titel + beschrijving
        # NOOIT op alleen de datum/tijd-tekst
        score_text = f"{title} {desc}".strip()
        scores     = compute_scores(score_text)

        # Dominant profiel
        dominant       = max(scores, key=scores.get)
        dominant_score = scores[dominant]

        activities.append({
            "title":            title,
            "organizer":        organizer,
            "desc":             desc,
            "url":              item["url"],
            "location":         location,
            "time":             time_str,
            "frequency":        freq,
            "scores":           scores,
            "dominant_profile": dominant if dominant_score > 0 else "buurtgenoot",
        })

    # Verdeling loggen
    print(f"\n✅  {len(activities)} activiteiten verwerkt")
    for p in PROFILEN:
        count = sum(1 for a in activities if a["dominant_profile"] == p)
        print(f"   {p}: {count}")

    output = {
        "updated_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "source":     AGENDA_URL,
        "count":      len(activities),
        "activities": activities,
    }

    with open("activities.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("💾  activities.json opgeslagen")


if __name__ == "__main__":
    main()
