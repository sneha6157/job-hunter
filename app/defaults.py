# Default config and profile — seeded into MongoDB on first run.
# Fill in your details via the Profile tab in the dashboard after first run.

DEFAULT_PROFILE = {
    "_id":              "profile",
    "name":             "",
    "email":            "",
    "phone":            "",
    "location":         "",
    "linkedin":         "",
    "github":           "",
    "experience_years": "0-1",
    "notice_period":    "30 days",
    "skills":           ["Java", "ReactJS", "JavaScript", "MySQL", "MongoDB", "Python", "HTML5", "CSS3"],
    "target_roles":     ["Java Developer", "Full Stack Developer", "Software Engineer"],
    "target_locations": ["Hyderabad", "Remote"],
    "summary":          "",
}


def generate_queries(profile: dict) -> list:
    """Auto-generate hunt queries from target_roles × target_locations."""
    roles     = profile.get("target_roles", [])
    locations = profile.get("target_locations", [])
    exp       = profile.get("experience_years", "0-1")

    if exp in ("0-1", "fresher", "0"):
        suffixes = ["fresher", "0 1 year", "junior"]
    elif exp in ("1-2", "1-3"):
        suffixes = ["junior", "1 year experience"]
    else:
        suffixes = [""]

    queries, seen = [], set()
    for role in roles:
        role_lower = role.lower()
        for loc in locations:
            loc_lower = "work from home" if loc.lower() == "remote" else loc.lower()
            for suffix in suffixes:
                q   = f"{role_lower} {suffix}".strip()
                key = f"{q}|{loc_lower}"
                if key not in seen:
                    seen.add(key)
                    queries.append([q, loc_lower])
    return queries[:20]


def generate_scoring(profile: dict) -> dict:
    """
    Build score_title, score_body, score_location from profile.
    Positive weights come from user's own skills + roles.
    Negative weights (seniority, hard tech rejects) are universal — user can tune in Config tab.
    """
    skills  = [s.lower() for s in profile.get("skills", [])]
    roles   = [r.lower() for r in profile.get("target_roles", [])]
    locs    = [l.lower() for l in profile.get("target_locations", [])]

    # ── score_title ───────────────────────────────────────────────────────────
    title_scores = {}

    # Role keywords — main signal
    for role in roles:
        words = role.split()
        for w in words:
            if w in ("developer", "engineer", "software", "full", "stack"):
                title_scores[w] = max(title_scores.get(w, 0), 1)
            else:
                title_scores[w] = max(title_scores.get(w, 0), 3)
        if "full stack" in role or "fullstack" in role:
            title_scores["full stack"] = 2
            title_scores["fullstack"]  = 2

    # Seniority boosts
    title_scores.update({"fresher": 3, "junior": 2, "associate": 2, "trainee": 2,
                          "developer": max(title_scores.get("developer", 0), 1),
                          "engineer":  max(title_scores.get("engineer",  0), 1)})

    # Universal seniority negatives
    title_scores.update({"senior": -4, "lead": -4, "manager": -5, "architect": -4,
                          "principal": -4, "staff": -3, "head": -5, "director": -5,
                          "vp": -5, "data scientist": -2, "devops": -2})

    # ── score_body ────────────────────────────────────────────────────────────
    body_scores = {}

    # Skill keywords — positive
    SKILL_WEIGHTS = {
        "java": 2, "python": 2, "react": 1, "reactjs": 1, "javascript": 1,
        "typescript": 1, "html": 1, "css": 1, "sql": 1, "mysql": 1,
        "mongodb": 1, "spring": 1, "spring boot": 1, "node": 1, "nodejs": 1,
        "django": 1, "flask": 1, "fastapi": 1, "postgresql": 1, "redis": 1,
        "aws": 1, "docker": 1, "git": 1,
    }
    for skill in skills:
        if skill in SKILL_WEIGHTS:
            body_scores[skill] = SKILL_WEIGHTS[skill]

    # Experience level boosts
    body_scores.update({"0-2 years": 2, "0-1 year": 3, "fresher": 3, "entry level": 2})

    # Universal negatives — shift, experience, irrelevant tech (not in user skills)
    body_scores.update({
        "night shift": -8, "us shift": -8, "us time zone": -8,
        "5:30 pm": -8, "2:30 am": -8,
        "2+ years": -5, "2 years": -4, "3+ years": -7, "3 years": -6,
        "4 years": -7, "5 years": -8,
        "minimum 2": -5, "minimum 3": -7, "at least 2": -5, "at least 3": -7,
    })

    # Penalise tech stacks NOT in user's skills (only well-known distractors)
    DISTRACTORS = {
        "angular": -4, "angularjs": -4, "dot net": -4, ".net framework": -4,
        "salesforce": -5, "sap": -5, "cobol": -5, "mainframe": -5,
        "oracle forms": -4, "power apps": -3,
    }
    for tech, penalty in DISTRACTORS.items():
        if not any(tech in s for s in skills):
            body_scores[tech] = penalty

    # ── score_location ────────────────────────────────────────────────────────
    loc_scores = {}
    for loc in locs:
        key = "work from home" if loc == "remote" else loc
        loc_scores[key] = 3
        if loc == "remote":
            loc_scores["remote"] = 3
            loc_scores["wfh"]    = 3

    # Generic positive
    loc_scores.update({"pan india": 2, "anywhere": 2})

    return {
        "score_title":    title_scores,
        "score_body":     body_scores,
        "score_location": loc_scores,
    }


def build_default_config(profile: dict) -> dict:
    """Build a full DEFAULT_CONFIG from a profile dict."""
    scoring = generate_scoring(profile)
    return {
        "_id":            "hunt_config",
        "queries":        generate_queries(profile),
        "days_back":      30,
        "score_threshold": 3,
        **scoring,
        # ── Company reputation ────────────────────────────────────────────────
        # +points when the employer is a known, verifiable company. Substring
        # match on the company name, lowercase. Tune freely in the Config tab.
        "score_company": {
            # Global product / banking / consulting majors
            "jpmorgan": 5, "jp morgan": 5, "j.p. morgan": 5, "morgan stanley": 5,
            "goldman": 5, "wells fargo": 5, "bank of america": 5, "citi": 5,
            "bnp paribas": 5, "barclays": 5, "hsbc": 5, "standard chartered": 5,
            "natwest": 5, "deutsche": 5, "state street": 5, "fidelity": 5,
            "blackrock": 5, "amazon": 5, "apple": 5, "microsoft": 5, "google": 5,
            "meta": 5, "nvidia": 5, "adobe": 5, "salesforce": 5, "oracle": 5,
            "vmware": 5, "ibm": 4, "cisco": 4, "qualcomm": 4, "paypal": 4,
            "servicenow": 4, "notion": 4, "electronic arts": 4, "honeywell": 4,
            "ss&c": 4, "franklin templeton": 5, "thomson reuters": 4, "sap": 4,
            "gap inc": 4, "hitachi": 4, "optum": 4, "unitedhealth": 4, "ea": 3,
            # India IT services / GCC majors
            "infosys": 4, "tcs": 4, "tata consultancy": 4, "wipro": 4,
            "cognizant": 4, "accenture": 4, "capgemini": 4, "tech mahindra": 4,
            "hcl": 4, "ltimindtree": 4, "mindtree": 3, "mphasis": 3,
            "persistent": 3, "dxc": 3, "value labs": 3, "valuelabs": 3,
            "deloitte": 4, "kpmg": 4, "pwc": 4, "ernst": 4, "ey ": 4,
        },
        # Listings whose "company" is a placeholder, staffing echo, or the job
        # board itself. Heavy penalty + 'ghost' flag so they sink to the bottom.
        "ghost_patterns": [
            "client of", "a client of", "confidential", "hiring for",
            "talent solution", "talent acquisition", "consultancy hiring",
            "staffing", "manpower", "placements", "recruiter", "hr solutions",
            "undisclosed", "stealth", "testhiring", "test hiring",
        ],
        "ghost_penalty": -6,
        "hard_reject_roles": [
            "internship", "intern ", "trainee intern", "apprentice",
            "early career program", "graduate program", "training program",
            "decp", "campus program", "entry program", "bootcamp",
            "part time", "part-time", "contract only", "freelance",
            "volunteer", "unpaid", "stipend only", "allowance only",
            "night shift", "us shift", "us time zone", "us timezone",
            "5:30 pm - 2:30 am", "2:30 am ist", "rotational shift",
            "vietnam", "singapore", "malaysia", "philippines", "manila",
            "dubai", "uae", "gulf", "saudi", "qatar", "bahrain", "abu dhabi",
            "australia", "canada", "uk only", "united kingdom", "london",
            "germany", "netherlands", "europe only",
            "new york", "new jersey", "california", "united states",
        ],
        "hard_reject_exp": [
            "2+ years", "2+ yrs", "minimum 2 years", "minimum 2 yrs",
            "at least 2 years", "at least 2 yrs",
            "2 years of experience", "2 years experience",
            "2-3 years", "2-4 years", "2-5 years", "2 to 3 years", "2 to 4 years",
            "3+ years", "3+ yrs", "minimum 3 years", "at least 3 years",
            "3 years of experience", "3 years experience",
            "3-5 years", "3-6 years", "3 to 5 years",
            "4+ years", "4-6 years", "5+ years", "5-8 years",
            "1-3 years", "1 to 3 years",
        ],
        "hard_reject_bond": [
            "24 months commitment", "commit to work for",
            "service bond", "service agreement", "training bond",
            "bond period", "bond amount", "training cost recovery",
            "2 lakh", "two lakh", "1 lakh", "one lakh",
            "repay", "pay back", "deduct from salary", "training fee",
        ],
        "blacklist_companies": [
            "disha consultant", "people prime worldwide",
            "important company of the sector", "lettfaktura", "globee software",
        ],
        "blacklist_sources": [
            "jobrapido", "jooble", "trabajo.org", "talent.com",
            "jobleads", "placement india", "apna jobs",
        ],
        "bond_flags": [
            "service bond", "service agreement", "training bond",
            "training fee", "training cost", "recovery",
            "2 lakh", "two lakh", "1 lakh", "one lakh",
            "bond period", "bond amount", "repay", "pay back", "deduct from salary",
        ],
        "suspicious_keywords": [
            "no salary", "stipend only", "unpaid", "commission only",
            "placement guarantee", "we train you", "100% placement",
        ],
    }


DEFAULT_CONFIG = build_default_config(DEFAULT_PROFILE)
