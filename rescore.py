"""
One-time re-score: pushes the new company-reputation + ghost-detection keys
into the existing DB config (non-destructive), then re-ranks every stored job.

Run from job_hunter_v2/ with the venv active:
    python rescore.py
"""
import asyncio
from app.db import jobs_col, config_col, profile_col
from app.defaults import build_default_config, DEFAULT_PROFILE
from app.scorer import score_job


async def main():
    # 1. Merge the new reputation keys into existing config (keeps queries/tuning)
    profile = await profile_col().find_one({"_id": "profile"}) or DEFAULT_PROFILE
    profile.pop("_id", None)
    fresh = build_default_config(profile)
    patch = {
        "score_company":  fresh["score_company"],
        "ghost_patterns": fresh["ghost_patterns"],
        "ghost_penalty":  fresh["ghost_penalty"],
    }
    await config_col().update_one({"_id": "hunt_config"}, {"$set": patch}, upsert=True)
    cfg = await config_col().find_one({"_id": "hunt_config"})
    print("Config patched with reputation scoring.")

    # 2. Re-score every stored job
    changed, total = 0, 0
    promoted, demoted = [], []
    async for job in jobs_col().find({}):
        total += 1
        old = job.get("score", 0)
        rescored = score_job(dict(job), cfg)
        new = rescored["score"]
        await jobs_col().update_one(
            {"_id": job["_id"]},
            {"$set": {"score": new, "flags": rescored.get("flags", [])}},
        )
        if new != old:
            changed += 1
            label = f'{job.get("company","?")[:28]:28} {old:>3} -> {new:<3}'
            if new > old:   promoted.append(label)
            else:           demoted.append(label)

    print(f"\nRe-scored {total} jobs | {changed} changed\n")
    if promoted:
        print("PROMOTED (real companies surfaced):")
        for p in sorted(promoted, key=lambda x: x.split('->')[-1], reverse=True):
            print("  +", p)
    if demoted:
        print("\nDEMOTED (ghost / placeholder listings sunk):")
        for d in demoted:
            print("  -", d)


if __name__ == "__main__":
    asyncio.run(main())
