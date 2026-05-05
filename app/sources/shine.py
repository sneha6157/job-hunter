import re
from bs4 import BeautifulSoup
from app.sources.http import safe_get

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.shine.com/",
}
LOCATION_MAP = {
    "hyderabad":      "hyderabad",
    "work from home": "work-from-home",
    "remote":         "work-from-home",
}


def fetch(query: str, location: str, days: int = 30) -> list[dict]:
    jobs     = []
    loc_slug = LOCATION_MAP.get(location.lower(), location.lower().replace(" ", "-"))
    q_slug   = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")

    for url in [
        f"https://www.shine.com/job-search/{q_slug}-jobs-in-{loc_slug}/",
        f"https://www.shine.com/job-search/{q_slug}-jobs/",
    ]:
        try:
            resp = safe_get(url, headers=HEADERS, timeout=14)
            if resp is None or resp.status_code != 200:
                continue
            soup  = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_=re.compile(r"jobCard|job-card|srp-tuple", re.I))
            if not cards:
                cards = soup.select("article.job, li.job-item, div.job-item")

            for card in cards[:20]:
                try:
                    title_el   = card.find(["h2","h3","a"], class_=re.compile(r"title|designation|jobTitle", re.I))
                    company_el = card.find(class_=re.compile(r"company|employer|compName", re.I))
                    loc_el     = card.find(class_=re.compile(r"location|city|loc", re.I))
                    sal_el     = card.find(class_=re.compile(r"salary|sal|ctc", re.I))
                    exp_el     = card.find(class_=re.compile(r"experience|exp", re.I))
                    link_el    = card.find("a", href=re.compile(r"shine\.com/job", re.I)) or card.find("a", href=True)

                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 4:
                        continue
                    if any(x in title.lower() for x in ["senior","lead ","manager","architect","sr."]):
                        continue

                    link = link_el["href"] if link_el else url
                    if link.startswith("/"):
                        link = "https://www.shine.com" + link

                    jobs.append({
                        "title":       title,
                        "company":     company_el.get_text(strip=True) if company_el else "Unknown",
                        "location":    loc_el.get_text(strip=True) if loc_el else location.title(),
                        "link":        link,
                        "source":      "Shine",
                        "posted_date": "",
                        "age_days":    7,
                        "summary":     "",
                        "salary":      sal_el.get_text(strip=True) if sal_el else "",
                        "experience":  exp_el.get_text(strip=True) if exp_el else "",
                    })
                except Exception:
                    continue
            if jobs:
                break
        except Exception as e:
            print(f"  [Shine] error ({query}): {e}")
    return jobs
