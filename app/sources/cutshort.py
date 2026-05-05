import re
from app.sources.http import safe_get

HEADERS = {
    "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept":      "application/json",
    "Referer":     "https://cutshort.io/",
}

ROLE_SLUG_MAP = {
    "java developer":                    "java-developer",
    "java developer fresher":            "java-developer",
    "java developer 0 1 year":           "java-developer",
    "junior java developer":             "java-developer",
    "full stack developer":              "full-stack-developer",
    "full stack developer fresher java": "full-stack-developer",
    "react developer":                   "react-developer",
    "react developer fresher":           "react-developer",
    "junior web developer react":        "web-developer",
    "software engineer":                 "software-engineer",
    "software engineer fresher java":    "software-engineer",
    "software developer fresher":        "software-developer",
    "associate engineer fresher":        "software-engineer",
    "associate software engineer java":  "software-engineer",
}

LOCATION_MAP = {
    "hyderabad":      "hyderabad",
    "work from home": "remote",
    "remote":         "remote",
}


def fetch(query: str, location: str, days: int = 30) -> list[dict]:  # noqa: ARG001
    jobs     = []
    role     = ROLE_SLUG_MAP.get(query.lower(), re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-"))
    loc_slug = LOCATION_MAP.get(location.lower(), location.lower().replace(" ", "-"))

    try:
        resp = safe_get(
            "https://cutshort.io/api/web/v1/jobs",
            headers=HEADERS,
            params={
                "skill":          role,
                "location":       loc_slug,
                "min_experience": 0,
                "max_experience": 2,
                "size":           20,
                "from":           0,
            },
            timeout=14,
        )

        if resp is None or resp.status_code != 200:
            return []

        results = resp.json().get("data", resp.json().get("jobs", []))

        for j in results:
            title = j.get("title", j.get("role", ""))
            if not title:
                continue
            if any(x in title.lower() for x in ["senior", "lead", "manager", "architect"]):
                continue

            company = j.get("company", {})
            company = company.get("name", "Unknown") if isinstance(company, dict) else str(company or "Unknown")

            loc_val = j.get("location", location.title())
            if isinstance(loc_val, list):
                loc_val = ", ".join(loc_val)

            jid  = j.get("id", j.get("slug", ""))
            link = j.get("url", f"https://cutshort.io/job/{jid}" if jid else "https://cutshort.io/jobs")

            sal = j.get("salary_range", j.get("ctc", ""))
            exp = j.get("experience_range", j.get("experience", "0-2 years"))

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    str(loc_val),
                "link":        link,
                "source":      "Cutshort",
                "posted_date": j.get("created_at", ""),
                "age_days":    7,
                "summary":     (j.get("description", j.get("job_description", "")) or "")[:500],
                "salary":      str(sal),
                "experience":  str(exp),
            })

    except Exception as e:
        print(f"  [Cutshort] error ({query}): {e}")

    return jobs
