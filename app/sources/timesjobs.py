import requests, re, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.timesjobs.com/",
}


def fetch(query: str, location: str, days: int = 30) -> list[dict]:  # noqa: ARG001
    jobs = []
    q   = query.replace(" ", "%20")
    loc = location.replace(" ", "%20")

    url = (
        f"https://www.timesjobs.com/candidate/job-search.html"
        f"?searchType=personalizedSearch&from=submit"
        f"&txtKeywords={q}&txtLocation={loc}&pDate=I&sequence=1&startPage=1"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=14, verify=False)
        if resp.status_code != 200:
            return []

        soup  = BeautifulSoup(resp.text, "html.parser")
        # TimesJobs job cards — each is a <li> with both h2 (title) and h3 (company)
        cards = [
            li for li in soup.find_all("li", class_=re.compile(r"job-bx|wht-shd-bx"))
            if li.find("h2") and li.find("h3")
        ]

        for card in cards[:20]:
            try:
                title_el   = card.find("h2")
                company_el = card.find("h3", class_=re.compile(r"joblist-comp-name|comp-name", re.I))
                link_el    = title_el.find("a") if title_el else None

                if not title_el or not link_el:
                    continue

                title = title_el.get_text(strip=True)
                if not title or len(title) < 4:
                    continue
                if any(x in title.lower() for x in ["senior", "lead ", "manager", "architect", "sr."]):
                    continue

                link    = link_el.get("href", url)
                company = company_el.get_text(strip=True) if company_el else "Unknown"

                # Extract exp / salary / location from detail list
                exp = sal = loc_txt = ""
                for item in card.select("ul.top-jd-dtl li, ul.jd-desc li"):
                    text = item.get_text(strip=True)
                    if re.search(r"\d+\s*[-–]\s*\d+\s*(yrs?|years?)", text, re.I):
                        exp = text
                    elif re.search(r"lakh|lpa|₹|salary|ctc", text, re.I):
                        sal = text
                    elif re.search(r"hyderabad|bangalore|mumbai|delhi|pune|remote|chennai|anywhere", text, re.I):
                        loc_txt = text

                posted_el = card.find(class_=re.compile(r"sim-posted|posted-date", re.I))
                posted    = posted_el.get_text(strip=True) if posted_el else ""

                jobs.append({
                    "title":       title,
                    "company":     company.strip(),
                    "location":    loc_txt or location.title(),
                    "link":        link,
                    "source":      "TimesJobs",
                    "posted_date": posted,
                    "age_days":    7,
                    "summary":     "",
                    "salary":      sal,
                    "experience":  exp,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"  [TimesJobs] error ({query}): {e}")

    return jobs
