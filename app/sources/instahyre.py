import requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept":          "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer":         "https://www.instahyre.com/",
}

LOCATION_MAP = {
    "hyderabad":      "Hyderabad",
    "work from home": "Remote",
    "remote":         "Remote",
}


def fetch(query: str, location: str, days: int = 30) -> list[dict]:  # noqa: ARG001
    jobs = []
    loc  = LOCATION_MAP.get(location.lower(), location.title())

    try:
        resp = requests.get(
            "https://www.instahyre.com/api/v2/opportunity/",
            params={
                "format":         "json",
                "q":              query,
                "location":       loc,
                "experience_min": 0,
                "experience_max": 2,
                "limit":          20,
                "offset":         0,
            },
            headers=HEADERS,
            timeout=14, verify=False,
        )

        if resp.status_code != 200:
            return []

        data    = resp.json()
        results = data.get("results", data.get("opportunities", []))

        for j in results:
            title = j.get("role", j.get("title", ""))
            if not title:
                continue
            if any(x in title.lower() for x in ["senior", "lead", "manager", "architect"]):
                continue

            company = j.get("employer", {})
            company = company.get("name", "Unknown") if isinstance(company, dict) else str(company)

            loc_str = j.get("location", loc)
            if isinstance(loc_str, list):
                loc_str = ", ".join(loc_str)

            jid  = j.get("id", "")
            link = j.get("url", f"https://www.instahyre.com/jobs/{jid}" if jid else "https://www.instahyre.com/")

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    str(loc_str),
                "link":        link,
                "source":      "Instahyre",
                "posted_date": j.get("created_at", ""),
                "age_days":    7,
                "summary":     (j.get("description", "") or "")[:500],
                "salary":      str(j.get("ctc_range", j.get("salary", ""))),
                "experience":  str(j.get("experience_range", j.get("experience", ""))),
            })

    except Exception as e:
        print(f"  [Instahyre] error ({query}): {e}")

    return jobs
