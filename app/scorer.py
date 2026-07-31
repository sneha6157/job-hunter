import hashlib, re
from datetime import datetime, timezone

SKILL_KEYWORDS = [
    "java", "spring", "spring boot", "hibernate", "maven", "gradle",
    "react", "reactjs", "javascript", "typescript", "html", "css",
    "python", "django", "flask", "fastapi",
    "mysql", "postgresql", "mongodb", "sql", "redis",
    "aws", "azure", "gcp", "docker", "kubernetes", "git",
    "rest api", "microservices", "graphql", "node.js", "nodejs",
]


def job_id(title: str, company: str, link: str) -> str:
    key = f"{company.lower().strip()}{title.lower().strip()}{link.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()


def extract_skills(text: str) -> list[str]:
    text_l = text.lower()
    return [kw for kw in SKILL_KEYWORDS if kw in text_l]


def detect_remote(location: str, summary: str) -> bool:
    combined = f"{location} {summary}".lower()
    return any(x in combined for x in ["remote", "work from home", "wfh", "anywhere in india"])


def score_job(job: dict, config: dict) -> dict:
    score  = 0
    flags  = []
    title  = job.get("title",    "").lower()
    body   = job.get("summary",  "").lower()
    loc    = job.get("location", "").lower()

    for kw, pts in config.get("score_title", {}).items():
        if kw in title:
            score += pts

    for kw, pts in config.get("score_body", {}).items():
        if kw in body:
            score += pts

    for kw, pts in config.get("score_location", {}).items():
        if kw in loc or kw in body:
            score += pts
            break

    # ── Company reputation ────────────────────────────────────────────────────
    # Reward named, verifiable employers; penalise placeholder / ghost listings.
    company = job.get("company", "").lower().strip()
    source  = job.get("source",  "").lower().strip()

    for name, pts in config.get("score_company", {}).items():
        if name in company:
            score += pts
            flags.append("known_company")
            break

    ghost_penalty = config.get("ghost_penalty", -6)
    is_ghost = False
    for pat in config.get("ghost_patterns", []):
        if pat in company:
            is_ghost = True
            break
    # Company name that just echoes the job board itself = placeholder listing
    if company and source and (company == source
                               or company == f"client of {source}"
                               or company == f"a client of {source}"):
        is_ghost = True
    if is_ghost:
        score += ghost_penalty
        flags.append("ghost")

    full = f"{title} {body} {loc}"
    for flag in config.get("bond_flags", []):
        if flag in full:
            flags.append("bond")
            break

    for flag in config.get("suspicious_keywords", []):
        if flag in full:
            flags.append("suspicious")
            break

    job["score"]       = max(score, 0)
    job["flags"]       = list(set(flags))
    job["skills_found"]= extract_skills(f"{title} {body}")
    job["is_remote"]   = detect_remote(job.get("location",""), body)
    return job


def should_reject(job: dict, config: dict) -> tuple[bool, str]:
    full = f"{job.get('title','')} {job.get('company','')} {job.get('location','')} {job.get('summary','')}".lower()
    company = job.get("company", "").lower()
    source  = job.get("source",  "").lower()

    for phrase in config.get("hard_reject_roles", []):
        if phrase in full:
            return True, "role"

    for phrase in config.get("hard_reject_bond", []):
        if phrase in full:
            return True, "bond"

    text = f"{job.get('title','')} {job.get('summary','')}".lower()
    for phrase in config.get("hard_reject_exp", []):
        if phrase in text:
            return True, "exp"

    for b in config.get("blacklist_companies", []):
        if b in company:
            return True, "blacklist"

    for b in config.get("blacklist_sources", []):
        if b in source:
            return True, "blacklist"

    return False, ""


def parse_age(date_str: str) -> int:
    if not date_str:
        return 99
    d = date_str.lower()
    if any(x in d for x in ["today", "just now", "hour", "minute"]): return 0
    if any(x in d for x in ["1 day", "yesterday"]): return 1
    m = re.search(r"(\d+)\s*day", d)
    if m: return int(m.group(1))
    m = re.search(r"(\d+)\s*month", d)
    if m: return int(m.group(1)) * 30

    formats = [
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt  = datetime.strptime(date_str.strip(), fmt)
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max((now - dt).days, 0)
        except ValueError:
            continue
    return 15
