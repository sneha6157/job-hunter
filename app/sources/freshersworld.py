import requests, re, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.freshersworld.com/",
}
LOCATION_MAP = {
    "hyderabad":      "hyderabad",
    "work from home": "work-from-home",
    "remote":         "work-from-home",
}
QUERY_SLUG_MAP = {
    "java developer fresher":           "java-developer",
    "java developer 0 1 year":          "java-developer",
    "junior java developer":            "java-developer",
    "associate software engineer java": "software-engineer",
    "full stack developer fresher java":"full-stack-developer",
    "react developer fresher":          "reactjs-developer",
    "junior web developer react":       "web-developer",
    "software engineer fresher java":   "software-engineer",
    "software developer fresher":       "software-developer",
    "associate engineer fresher":       "software-engineer",
}


def fetch(query: str, location: str, days: int = 30) -> list[dict]:
    jobs     = []
    kw_slug  = QUERY_SLUG_MAP.get(query.lower(), re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-"))
    loc_slug = LOCATION_MAP.get(location.lower(), re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-"))

    for url in [
        f"https://www.freshersworld.com/jobs/jobsearch/{kw_slug}-jobs-in-{loc_slug}",
        f"https://www.freshersworld.com/jobs/jobsearch/{kw_slug}-jobs",
    ]:
        try:
            resp  = requests.get(url, headers=HEADERS, timeout=14, verify=False)
            if resp.status_code != 200:
                continue
            soup  = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_=re.compile(r"job[-_]container|job[-_]card|jobcontainer", re.I))
            if not cards:
                cards = soup.select("ul.job-list li, div.job-bx, div.job_listing")

            for card in cards[:20]:
                try:
                    title_el   = card.find(["h3","h2","a"], class_=re.compile(r"title|heading", re.I))
                    if not title_el:
                        title_el = card.find("a", href=re.compile(r"freshersworld\.com/jobs/"))
                    company_el = card.find(class_=re.compile(r"company|employer", re.I))
                    loc_el     = card.find(class_=re.compile(r"location|city", re.I))
                    exp_el     = card.find(class_=re.compile(r"experience|exp", re.I))
                    sal_el     = card.find(class_=re.compile(r"salary|sal|ctc", re.I))
                    link_el    = card.find("a", href=re.compile(r"freshersworld\.com/jobs/"))

                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 4:
                        continue
                    if any(x in title.lower() for x in ["senior","lead ","manager","architect","sr."]):
                        continue

                    link = link_el["href"] if link_el else url
                    if link.startswith("/"):
                        link = "https://www.freshersworld.com" + link

                    jobs.append({
                        "title":       title,
                        "company":     company_el.get_text(strip=True) if company_el else "Unknown",
                        "location":    loc_el.get_text(strip=True) if loc_el else location.title(),
                        "link":        link,
                        "source":      "Freshersworld",
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
            print(f"  [Freshersworld] error ({query}): {e}")
    return jobs
