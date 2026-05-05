import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import ensure_indexes, jobs_col, config_col, profile_col, runs_col
from app.hunter import run_hunt, stream_progress, get_config
from app.defaults import DEFAULT_CONFIG, DEFAULT_PROFILE, build_default_config

load_dotenv()

app = FastAPI(title="Job Hunter V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

FRONTEND = Path(__file__).parent.parent / "frontend"


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    # Seed defaults if not present
    if not await config_col().find_one({"_id": "hunt_config"}):
        await config_col().insert_one(DEFAULT_CONFIG.copy())
    if not await profile_col().find_one({"_id": "profile"}):
        await profile_col().insert_one(DEFAULT_PROFILE.copy())


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = FRONTEND / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
async def list_jobs(
    source:   str  = Query(default=""),
    location: str  = Query(default=""),
    applied:  str  = Query(default=""),   # "true" | "false" | ""
    remote:   str  = Query(default=""),
    min_score:int  = Query(default=0),
    search:   str  = Query(default=""),
    sort:     str  = Query(default="score"),  # score | date | new
    limit:    int  = Query(default=100),
    skip:     int  = Query(default=0),
):
    filt: dict = {}
    if source:   filt["source"]    = source
    if applied == "true":  filt["applied"] = True
    if applied == "false": filt["applied"] = False
    if remote  == "true":  filt["is_remote"] = True
    if min_score > 0:      filt["score"] = {"$gte": min_score}
    if location:
        filt["location"] = {"$regex": location, "$options": "i"}
    if search:
        filt["$or"] = [
            {"title":   {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
        ]

    sort_key = {"score": [("score", -1), ("first_seen", -1)],
                "date":  [("first_seen", -1)],
                "new":   [("first_seen", -1), ("score", -1)]}.get(sort, [("score", -1)])

    cursor = jobs_col().find(filt, {"_id": 1, "title": 1, "company": 1, "location": 1,
                                     "link": 1, "source": 1, "salary": 1, "experience": 1,
                                     "summary": 1, "score": 1, "flags": 1, "skills_found": 1,
                                     "is_remote": 1, "age_days": 1, "posted_date": 1,
                                     "applied": 1, "applied_at": 1, "first_seen": 1}) \
                        .sort(sort_key).skip(skip).limit(limit)

    jobs = []
    async for doc in cursor:
        doc["id"] = doc.pop("_id")
        if doc.get("first_seen"):
            doc["first_seen"] = doc["first_seen"].isoformat()
        if doc.get("applied_at"):
            doc["applied_at"] = doc["applied_at"].isoformat()
        jobs.append(doc)

    total = await jobs_col().count_documents(filt)
    return {"jobs": jobs, "total": total, "skip": skip, "limit": limit}


@app.post("/api/jobs/{job_id}/apply")
async def mark_applied(job_id: str):
    res = await jobs_col().update_one(
        {"_id": job_id},
        {"$set": {"applied": True, "applied_at": datetime.now(timezone.utc)}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Job not found")
    return {"ok": True}


@app.delete("/api/jobs/{job_id}/apply")
async def unmark_applied(job_id: str):
    await jobs_col().update_one(
        {"_id": job_id},
        {"$set": {"applied": False, "applied_at": None}}
    )
    return {"ok": True}


# ── Hunt ──────────────────────────────────────────────────────────────────────

@app.post("/api/hunt")
async def start_hunt():
    run_id = await run_hunt()
    return {"run_id": run_id}


@app.get("/api/hunt/{run_id}/progress")
async def hunt_progress(run_id: str):
    return StreamingResponse(
        stream_progress(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/hunt/runs")
async def list_runs(limit: int = Query(default=20)):
    runs = []
    async for doc in runs_col().find({}, {"error": 0}).sort("started_at", -1).limit(limit):
        doc["id"] = str(doc.pop("_id"))
        if doc.get("started_at"):   doc["started_at"]   = doc["started_at"].isoformat()
        if doc.get("completed_at"): doc["completed_at"] = doc["completed_at"].isoformat()
        runs.append(doc)
    return runs


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def stats():
    total    = await jobs_col().count_documents({})
    applied  = await jobs_col().count_documents({"applied": True})
    remote   = await jobs_col().count_documents({"is_remote": True})
    new_today = await jobs_col().count_documents({
        "first_seen": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)}
    })

    # Score buckets
    excellent = await jobs_col().count_documents({"score": {"$gte": 10}})
    good      = await jobs_col().count_documents({"score": {"$gte": 6, "$lt": 10}})
    maybe     = await jobs_col().count_documents({"score": {"$gte": 3, "$lt": 6}})

    # By source
    by_source = []
    async for doc in jobs_col().aggregate([
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]):
        by_source.append({"source": doc["_id"], "count": doc["count"]})

    # By location (top 5)
    by_location = []
    async for doc in jobs_col().aggregate([
        {"$group": {"_id": "$location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 8}
    ]):
        by_location.append({"location": doc["_id"], "count": doc["count"]})

    # Top skills found
    top_skills = []
    async for doc in jobs_col().aggregate([
        {"$unwind": "$skills_found"},
        {"$group": {"_id": "$skills_found", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 12}
    ]):
        top_skills.append({"skill": doc["_id"], "count": doc["count"]})

    last_run = await runs_col().find_one({}, sort=[("started_at", -1)])
    last_run_at = last_run["started_at"].isoformat() if last_run else None

    return {
        "total": total, "applied": applied, "remote": remote,
        "new_today": new_today, "excellent": excellent,
        "good": good, "maybe": maybe,
        "by_source": by_source, "by_location": by_location,
        "top_skills": top_skills, "last_run_at": last_run_at,
    }


# ── Profile ───────────────────────────────────────────────────────────────────

@app.get("/api/profile")
async def get_profile():
    doc = await profile_col().find_one({"_id": "profile"})
    if not doc:
        return DEFAULT_PROFILE
    doc.pop("_id", None)
    return doc


@app.put("/api/profile")
async def update_profile(body: dict):
    body.pop("_id", None)
    await profile_col().update_one(
        {"_id": "profile"}, {"$set": body}, upsert=True
    )
    # Auto-rebuild scoring + queries whenever profile skills/roles/locations change
    if any(k in body for k in ("target_roles", "target_locations", "skills", "experience_years")):
        full_profile = await profile_col().find_one({"_id": "profile"}) or body
        full_profile.pop("_id", None)
        new_cfg = build_default_config(full_profile)
        new_cfg.pop("_id", None)
        # Preserve any manual edits to thresholds and blacklists — only update scoring+queries
        update_keys = ("queries", "score_title", "score_body", "score_location")
        await config_col().update_one(
            {"_id": "hunt_config"},
            {"$set": {k: new_cfg[k] for k in update_keys}},
            upsert=True
        )
    return {"ok": True}


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_hunt_config():
    return await get_config()


@app.put("/api/config")
async def update_hunt_config(body: dict):
    body.pop("_id", None)
    await config_col().update_one(
        {"_id": "hunt_config"}, {"$set": body}, upsert=True
    )
    return {"ok": True}


@app.post("/api/config/reset")
async def reset_config():
    """Rebuild config from current profile — wipes and regenerates scoring + queries."""
    profile = await profile_col().find_one({"_id": "profile"}) or DEFAULT_PROFILE
    profile.pop("_id", None)
    new_cfg = build_default_config(profile)
    await config_col().replace_one({"_id": "hunt_config"}, new_cfg, upsert=True)
    new_cfg.pop("_id", None)
    return new_cfg
