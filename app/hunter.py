import asyncio, uuid, threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import AsyncGenerator

from app.db import jobs_col, runs_col, config_col
from app.scorer import job_id, score_job, should_reject
from app.defaults import DEFAULT_CONFIG
from app.sources import indeed, linkedin, naukri, freshersworld, shine, timesjobs, instahyre, cutshort

# SSE progress queue per run_id
_progress: dict[str, asyncio.Queue] = {}


async def get_config() -> dict:
    doc = await config_col().find_one({"_id": "hunt_config"})
    if not doc:
        await config_col().insert_one(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    doc.pop("_id", None)
    return doc


async def stream_progress(run_id: str) -> AsyncGenerator[str, None]:
    q = asyncio.Queue()
    _progress[run_id] = q
    try:
        while True:
            msg = await asyncio.wait_for(q.get(), timeout=120)
            if msg is None:
                break
            yield f"data: {msg}\n\n"
    except asyncio.TimeoutError:
        pass
    finally:
        _progress.pop(run_id, None)


def _push(run_id: str, msg: str):
    if run_id in _progress:
        try:
            _progress[run_id].put_nowait(msg)
        except Exception:
            pass


def _fetch_all(queries: list, days: int, run_id: str) -> list[dict]:
    raw    = []
    capped = queries[:6]

    # ── Naukri (optional, disabled by default) ───────────────────────────────
    # Naukri's job search API requires recaptcha even with valid session cookies.
    # The workaround is a one-time Playwright browser login (naukri_auth.py) that
    # saves a session to naukri_session.json, then a subprocess scrapes search pages.
    # Disabled here so the project runs out of the box without extra setup.
    # To enable: run `python naukri_auth.py` once, then uncomment the block below.
    #
    # naukri_results: list = []
    # naukri_done = threading.Event()
    # def _run_naukri():
    #     try:
    #         jobs = naukri.fetch_all(queries[:4], days)
    #         naukri_results.extend(jobs)
    #     except Exception as e:
    #         print(f"  [Naukri] thread error: {e}")
    #     finally:
    #         naukri_done.set()
    # naukri_thread = threading.Thread(target=_run_naukri, daemon=True)
    # naukri_thread.start()
    naukri_results: list = []
    naukri_done = threading.Event()
    naukri_done.set()  # mark done immediately (Naukri disabled)

    # All other sources run in parallel with per-future timeouts
    tasks = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for q, loc in queries:
            tasks.append(("Indeed",    pool.submit(indeed.fetch,    q, loc, days)))
            tasks.append(("LinkedIn",  pool.submit(linkedin.fetch,  q, loc, days)))
            tasks.append(("TimesJobs", pool.submit(timesjobs.fetch, q, loc, days)))
        for q, loc in capped:
            tasks.append(("Freshersworld", pool.submit(freshersworld.fetch, q, loc, days)))
            tasks.append(("Shine",         pool.submit(shine.fetch,         q, loc, days)))
            tasks.append(("Instahyre",     pool.submit(instahyre.fetch,     q, loc, days)))
            tasks.append(("Cutshort",      pool.submit(cutshort.fetch,      q, loc, days)))

        done  = 0
        total = len(tasks) + 1  # +1 for Naukri
        for source, future in tasks:
            try:
                result = future.result(timeout=25)  # per-source hard cap
                raw.extend(result)
            except Exception as e:
                print(f"  [{source}] error: {e}")
            done += 1
            _push(run_id, f'{{"type":"progress","done":{done},"total":{total},"raw":{len(raw)}}}')

    # Wait for Naukri — max 60s (it started when other sources did, so mostly done by now)
    naukri_done.wait(timeout=60)
    raw.extend(naukri_results)
    done += 1
    _push(run_id, f'{{"type":"progress","done":{done},"total":{total},"raw":{len(raw)}}}')

    return raw


def _dedup_raw(jobs: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for j in jobs:
        key = f"{j.get('company','').lower().strip()}-{j.get('title','').lower().strip()[:40]}"
        if key not in seen:
            seen.add(key)
            unique.append(j)
    return unique


async def run_hunt() -> str:
    run_id = str(uuid.uuid4())
    run_doc = {
        "_id":        run_id,
        "started_at": datetime.now(timezone.utc),
        "status":     "running",
        "stats":      {},
        "error":      None,
    }
    await runs_col().insert_one(run_doc)
    asyncio.create_task(_hunt_task(run_id))
    return run_id


async def _hunt_task(run_id: str):
    config = await get_config()
    queries  = config.get("queries", [])
    days     = config.get("days_back", 30)
    threshold = config.get("score_threshold", 3)
    stats    = {}

    try:
        _push(run_id, '{"type":"status","msg":"Fetching jobs from all sources..."}')

        loop = asyncio.get_event_loop()
        raw  = await loop.run_in_executor(None, _fetch_all, queries, days, run_id)
        stats["raw_fetched"] = len(raw)

        raw = _dedup_raw(raw)
        stats["after_dedup"] = len(raw)
        _push(run_id, f'{{"type":"status","msg":"Deduped to {len(raw)} jobs. Scoring and filtering..."}}')

        # Score all jobs
        raw = [score_job(j, config) for j in raw]

        # Filter
        rej_role = rej_bond = rej_exp = rej_bl = 0
        filtered = []
        for j in raw:
            reject, reason = should_reject(j, config)
            if reject:
                if reason == "role":   rej_role += 1
                elif reason == "bond": rej_bond += 1
                elif reason == "exp":  rej_exp  += 1
                else:                  rej_bl   += 1
                continue
            if j["score"] < threshold:
                continue
            filtered.append(j)

        stats["rejected_roles"]     = rej_role
        stats["rejected_bond"]      = rej_bond
        stats["rejected_exp"]       = rej_exp
        stats["rejected_blacklist"] = rej_bl
        stats["after_filter"]       = len(filtered)

        # Upsert into MongoDB
        now = datetime.now(timezone.utc)
        new_count = 0
        for j in filtered:
            jid = job_id(j.get("title",""), j.get("company",""), j.get("link",""))
            j["run_id"] = run_id
            existing = await jobs_col().find_one({"_id": jid})
            if existing:
                await jobs_col().update_one(
                    {"_id": jid},
                    {"$set": {"last_seen": now, "score": j["score"],
                              "skills_found": j.get("skills_found", []),
                              "flags": j.get("flags", [])}}
                )
            else:
                new_count += 1
                doc = {**j, "_id": jid, "first_seen": now, "last_seen": now,
                       "applied": False, "applied_at": None}
                await jobs_col().insert_one(doc)

        stats["new_jobs"] = new_count
        stats["total_in_db"] = await jobs_col().count_documents({})

        _push(run_id, f'{{"type":"done","stats":{__import__("json").dumps(stats)}}}')
        _push(run_id, None)  # close stream

        await runs_col().update_one(
            {"_id": run_id},
            {"$set": {"status": "done", "completed_at": now, "stats": stats}}
        )

    except Exception as e:
        await runs_col().update_one(
            {"_id": run_id},
            {"$set": {"status": "error", "error": str(e),
                      "completed_at": datetime.now(timezone.utc)}}
        )
        _push(run_id, f'{{"type":"error","msg":"{str(e)}"}}')
        _push(run_id, None)
