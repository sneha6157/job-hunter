import requests, re
from bs4 import BeautifulSoup
from app.scorer import parse_age
from app.sources.http import safe_get

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

GEO_IDS = {
    "hyderabad":      "105556991",
    "work from home": "92000000",
    "remote":         "92000000",
}


def fetch(query: str, location: str, days: int = 30) -> list[dict]:
    jobs   = []
    geo_id = GEO_IDS.get(location.lower(), "105556991")
    time_f = f"r{min(days, 30) * 86400}"

    urls = [
        (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
            f"keywords={requests.utils.quote(query)}"
            f"&geoId={geo_id}&f_TPR={time_f}&f_E=1%2C2&start=0"
        ),
        (
            f"https://www.linkedin.com/jobs/search/?"
            f"keywords={requests.utils.quote(query)}"
            f"&geoId={geo_id}&f_TPR={time_f}&f_E=1%2C2"
        ),
    ]

    for url in urls:
        try:
            resp = safe_get(url, headers=HEADERS, timeout=14)
            if resp is None or resp.status_code != 200:
                continue
            soup  = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            for card in cards[:20]:
                try:
                    title_el   = card.find("h3")
                    company_el = card.find("h4")
                    loc_el     = card.find("span", class_=re.compile(r"location", re.I))
                    link_el    = card.find("a", href=re.compile(r"linkedin\.com/jobs"))
                    time_el    = card.find("time")

                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue

                    date_str = time_el.get("datetime", "") if time_el else ""
                    age      = parse_age(date_str + "T00:00:00Z") if date_str else 15

                    link = link_el["href"].split("?")[0] if link_el else ""

                    jobs.append({
                        "title":       title,
                        "company":     company_el.get_text(strip=True) if company_el else "Unknown",
                        "location":    loc_el.get_text(strip=True) if loc_el else location.title(),
                        "link":        link,
                        "source":      "LinkedIn",
                        "posted_date": date_str,
                        "age_days":    age,
                        "summary":     "",
                        "salary":      "",
                        "experience":  "",
                    })
                except Exception:
                    continue

            if jobs:
                break
        except Exception as e:
            print(f"  [LinkedIn] error ({query}/{location}): {e}")
            continue

    return jobs
