#!/usr/bin/env python3
"""
Naukri scraper — uses saved session cookies with requests + BeautifulSoup.
Parses job data embedded in the page HTML (Naukri inlines job JSON in <script> tags).
Called as a subprocess so it runs in its own process, away from FastAPI's event loop.
"""
import sys, json, re, requests, urllib3
from pathlib import Path
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SESSION_FILE = Path(__file__).parent.parent.parent / "naukri_session.json"

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.naukri.com/",
    "DNT":             "1",
}

LOCATION_SLUG = {
    "hyderabad":      "hyderabad",
    "work from home": "work-from-home",
    "remote":         "work-from-home",
}


def _query_to_slug(q: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")


def _extract_jobs_from_html(html: str, location: str) -> list[dict]:
    """Try multiple strategies to extract job listings from Naukri HTML."""
    jobs = []

    # Strategy 1: Parse embedded JSON from <script> tags
    # Naukri inlines job data as window.__INITIAL_DATA__ or similar
    for pattern in [
        r'window\.__INITIAL_DATA__\s*=\s*({.*?});\s*</script>',
        r'window\._cr\s*=\s*({.*?});\s*</script>',
        r'"jobDetails"\s*:\s*(\[.*?\])',
        r'"jobs"\s*:\s*(\[.*?\])',
    ]:
        try:
            m = re.search(pattern, html, re.DOTALL)
            if not m:
                continue
            data = json.loads(m.group(1))
            # Handle both object and array
            if isinstance(data, list):
                job_list = data
            else:
                job_list = (data.get("jobDetails") or data.get("jobs") or
                            data.get("data", {}).get("jobDetails") or [])
            for j in job_list[:20]:
                title = j.get("title", j.get("jobTitle", ""))
                if not title or len(title) < 4:
                    continue
                if any(x in title.lower() for x in ["senior","lead ","manager","architect","sr."]):
                    continue
                company  = j.get("companyName", j.get("company", "Unknown"))
                link     = j.get("jdURL", j.get("jobUrl", ""))
                if link and not link.startswith("http"):
                    link = "https://www.naukri.com" + link
                salary = exp = loc_str = ""
                for p in j.get("placeholders", []):
                    t = p.get("type",""); lbl = p.get("label","")
                    if t == "salary":     salary  = lbl
                    if t == "experience": exp     = lbl
                    if t == "location":   loc_str = lbl
                jobs.append({
                    "title": title, "company": company,
                    "location": loc_str or location.title(),
                    "link": link, "source": "Naukri",
                    "posted_date": j.get("footerPlaceholderLabel",""),
                    "age_days": 7, "summary": j.get("jobDescription",""),
                    "salary": salary, "experience": exp,
                })
            if jobs:
                return jobs
        except Exception:
            continue

    # Strategy 2: BeautifulSoup HTML card parsing
    soup  = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("article", class_=re.compile(r"jobTuple", re.I))
    if not cards:
        cards = soup.find_all("div", class_=re.compile(r"srp-jobtuple|jobTupleHeader", re.I))
    if not cards:
        # Generic fallback — any element with a job link
        cards = soup.find_all("li", attrs={"data-job-id": True})

    for card in cards[:20]:
        try:
            title_el = card.find("a", class_=re.compile(r"title|jobTitle", re.I))
            if not title_el:
                title_el = card.find("a", href=re.compile(r"naukri\.com.*job"))
            comp_el  = card.find("a", class_=re.compile(r"subTitle|compName", re.I))
            loc_el   = card.find(class_=re.compile(r"locW|location", re.I))
            exp_el   = card.find(class_=re.compile(r"expW|experience", re.I))
            sal_el   = card.find(class_=re.compile(r"salary|sal", re.I))

            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 4:
                continue
            if any(x in title.lower() for x in ["senior","lead ","manager","architect","sr."]):
                continue

            link = title_el.get("href","") if title_el else ""
            if link and not link.startswith("http"):
                link = "https://www.naukri.com" + link

            jobs.append({
                "title":    title,
                "company":  comp_el.get_text(strip=True) if comp_el else "Unknown",
                "location": loc_el.get_text(strip=True)  if loc_el  else location.title(),
                "link":     link, "source": "Naukri",
                "posted_date": "", "age_days": 7, "summary": "",
                "salary":    sal_el.get_text(strip=True) if sal_el else "",
                "experience": exp_el.get_text(strip=True) if exp_el else "",
            })
        except Exception:
            continue

    return jobs


def main():
    data    = json.loads(sys.stdin.read())
    queries = data["queries"]

    if not SESSION_FILE.exists():
        print("[]")
        print("[Naukri-worker] No session file — run: python naukri_auth.py", file=sys.stderr)
        return

    # Load cookies into requests session
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        for c in json.loads(SESSION_FILE.read_text()):
            session.cookies.set(c["name"], c["value"], domain=c.get("domain", ".naukri.com"))
    except Exception as e:
        print("[]")
        print(f"[Naukri-worker] Cookie load error: {e}", file=sys.stderr)
        return

    all_jobs  = []
    seen_urls = set()

    for query, location in queries:
        q_slug   = _query_to_slug(query)
        loc_slug = LOCATION_SLUG.get(location.lower(), location.lower().replace(" ", "-"))

        for url in [
            f"https://www.naukri.com/{q_slug}-jobs-in-{loc_slug}?experience=0",
            f"https://www.naukri.com/{q_slug}-jobs?experience=0",
        ]:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                resp = session.get(url, timeout=14, verify=False)
                if resp.status_code != 200:
                    print(f"[Naukri-worker] {resp.status_code} {url}", file=sys.stderr)
                    continue
                jobs = _extract_jobs_from_html(resp.text, location)
                print(f"[Naukri-worker] {url.split('?')[0].split('naukri.com/')[1]} → {len(jobs)} jobs", file=sys.stderr)
                all_jobs.extend(jobs)
                if jobs:
                    break
            except Exception as e:
                print(f"[Naukri-worker] error {url}: {e}", file=sys.stderr)

    print(json.dumps(all_jobs))
    print(f"[Naukri-worker] Done: {len(all_jobs)} jobs total.", file=sys.stderr)


if __name__ == "__main__":
    main()
