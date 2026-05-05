import requests, feedparser
from bs4 import BeautifulSoup
from app.scorer import parse_age

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}


def fetch(query: str, location: str, days: int = 30) -> list[dict]:
    jobs = []
    try:
        url = (
            f"https://in.indeed.com/rss?"
            f"q={requests.utils.quote(query)}"
            f"&l={requests.utils.quote(location)}"
            f"&sort=date&fromage={days}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=12)
        feed = feedparser.parse(resp.text)

        for entry in feed.entries:
            title   = entry.get("title", "")
            company = ""
            if " - " in title:
                parts   = title.split(" - ", 1)
                title   = parts[0].strip()
                company = parts[1].strip()

            date_str = entry.get("published", "")
            age      = parse_age(date_str)
            if age > days:
                continue

            summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)[:500]

            jobs.append({
                "title":       title,
                "company":     company or entry.get("author", "Unknown"),
                "location":    location.title(),
                "link":        entry.get("link", ""),
                "source":      "Indeed",
                "posted_date": date_str,
                "age_days":    age,
                "summary":     summary,
                "salary":      "",
                "experience":  "",
            })
    except Exception as e:
        print(f"  [Indeed] error ({query}/{location}): {e}")
    return jobs
