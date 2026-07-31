"""Quick check: is the Gokul Infocare job in the DB, and is it marked applied?"""
import asyncio
from app.db import jobs_col


async def main():
    found = False
    async for j in jobs_col().find({}):
        blob = f'{j.get("company","")} {j.get("title","")}'.lower()
        if "gokul" in blob or ("ai/ml" in blob and "wfh" in blob) or "infocare" in blob:
            found = True
            print(f'MATCH: {j.get("company")} | {j.get("title")}')
            print(f'   source={j.get("source")} applied={j.get("applied")} '
                  f'applied_at={j.get("applied_at")} score={j.get("score")}')
            print(f'   link={j.get("link")}')
    if not found:
        print("No Gokul Infocare / AI-ML-WFH job found in the job hunter DB.")
        n = await jobs_col().count_documents({})
        a = await jobs_col().count_documents({"applied": True})
        print(f"(DB has {n} jobs, {a} marked applied.)")


if __name__ == "__main__":
    asyncio.run(main())
