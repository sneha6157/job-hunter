from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Job(BaseModel):
    id: str                             # md5 of company+title+link
    title: str
    company: str
    location: str
    link: str
    source: str
    salary: str = ""
    experience: str = ""
    summary: str = ""
    skills_found: list[str] = []        # tech keywords extracted from summary
    is_remote: bool = False
    age_days: int = 99
    posted_date: str = ""
    score: int = 0
    flags: list[str] = []               # bond, suspicious
    applied: bool = False
    applied_at: Optional[datetime] = None
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    run_id: str = ""


class Profile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    experience_years: str = "0-1"
    skills: list[str] = []
    notice_period: str = "30 days"
    target_roles: list[str] = []
    target_locations: list[str] = []
    summary: str = ""


class HuntConfig(BaseModel):
    queries: list[list[str]] = []       # [[query, location], ...]
    days_back: int = 30
    score_threshold: int = 3
    hard_reject_roles: list[str] = []
    hard_reject_exp: list[str] = []
    hard_reject_bond: list[str] = []
    blacklist_companies: list[str] = []
    blacklist_sources: list[str] = []
    score_title: dict[str, int] = {}
    score_body: dict[str, int] = {}
    score_location: dict[str, int] = {}
    bond_flags: list[str] = []
    suspicious_keywords: list[str] = []


class HuntRun(BaseModel):
    id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"             # running | done | error
    stats: dict = {}
    error: Optional[str] = None
