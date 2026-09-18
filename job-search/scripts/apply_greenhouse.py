#!/usr/bin/env python3
"""Greenhouse job-board apply helper for Revanth Mallol.

Reads materials/applicant_profile.json. Will NOT submit if work_authorization
or needs_sponsorship is unknown when the form asks those questions.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / "materials" / "applicant_profile.json").read_text())
RESUME = Path(PROFILE["resume_path"])
LOG_DIR = ROOT / "logs"
TRACKER = ROOT / "applications" / "tracker.csv"
QUEUE = ROOT / "applications" / "priority_queue.json"


def cover_letter(company: str, role: str) -> str:
    tmpl = (ROOT / "materials" / "cover_letter_data_engineer.txt").read_text()
    return tmpl.replace("{{COMPANY}}", company.title()).replace("{{ROLE}}", role)


def fill_basic(page, company: str, role: str) -> None:
    page.fill("#first_name", PROFILE["first_name"])
    page.fill("#last_name", PROFILE["last_name"])
    page.fill("#email", PROFILE["email"])
    if page.locator("#phone").count():
        page.fill("#phone", PROFILE["phone"])
    if page.locator("#preferred_name").count():
        page.fill("#preferred_name", PROFILE["first_name"])
    # preferred name custom questions
    for sel in ["#question_66111063", "input[aria-label='Preferred First Name']"]:
        if page.locator(sel).count():
            page.fill(sel, PROFILE["first_name"])
            break
    for sel in ["#question_66111064", "input[aria-label='Preferred Last Name']"]:
        if page.locator(sel).count():
            page.fill(sel, PROFILE["last_name"])
            break
    if page.locator("#candidate-location").count():
        loc = PROFILE.get("city_state") or "Arlington, Texas, United States"
        page.fill("#candidate-location", loc)
        page.wait_for_timeout(800)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
    if page.locator("#resume").count():
        page.set_input_files("#resume", str(RESUME))
    # optional linkedin
    li = PROFILE.get("linkedin") or ""
    if li and not li.startswith("TODO"):
        for sel in [
            "input[aria-label='LinkedIn Profile']",
            "input[aria-label*='LinkedIn']",
        ]:
            if page.locator(sel).count():
                page.fill(sel, li)
                break
    zip_code = PROFILE.get("zip") or ""
    if zip_code:
        for sel in [
            "input[aria-label*='zip' i]",
            "input[aria-label*='Zip']",
            "#question_66111071",
            "#question_68359739",
        ]:
            if page.locator(sel).count():
                page.fill(sel, zip_code)
                break
    # cover letter textareas
    for sel in ["textarea#cover_letter_text", "textarea[id*='cover']", "textarea"]:
        loc = page.locator(sel)
        if loc.count():
            # only fill first substantial textarea that looks like cover/additional
            break


def react_select(page, question_substr: str, option_substr: str) -> bool:
    """Click a Greenhouse react-select whose question text contains question_substr."""
    # Find the question block
    blocks = page.locator("div").filter(has_text=re.compile(question_substr, re.I))
    # Too broad — use label-like text near select
    q = page.get_by_text(re.compile(question_substr, re.I)).first
    try:
        q.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        return False
    # Click nearest select input container
    container = q.locator("xpath=ancestor::div[contains(@class,'field') or contains(@class,'question') or contains(@class,'application')][1]")
    target = container.locator(".select__input-container, [class*='select__control']").first
    try:
        target.click(force=True, timeout=4000)
    except Exception:
        # fallback: click following sibling area
        try:
            page.locator(".select__input-container").nth(0).click(force=True)
        except Exception:
            return False
    page.wait_for_timeout(400)
    opt = page.locator("[role='option']").filter(has_text=re.compile(option_substr, re.I)).first
    try:
        opt.click(timeout=4000)
        return True
    except Exception:
        page.keyboard.type(option_substr)
        page.keyboard.press("Enter")
        return True


def has_auth_questions(page) -> bool:
    text = page.inner_text("body")
    return bool(
        re.search(
            r"sponsor|legally authorized to work|require.*immigration|visa",
            text,
            re.I,
        )
    )


def apply_one(page, job: dict, dry_run: bool = True) -> dict:
    company = job["company"]
    role = job["title"]
    jid = job.get("id")
    url = f"https://boards.greenhouse.io/embed/job_app?for={company}&token={jid}"
    result = {"company": company, "title": role, "url": job.get("url"), "status": "failed", "notes": ""}
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        if page.locator("#first_name").count() == 0:
            # try job-boards page
            page.goto(job["url"], wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            for sel in ["a:has-text('Apply')", "button:has-text('Apply')"]:
                try:
                    page.locator(sel).first.click(timeout=2000)
                except Exception:
                    pass
        if page.locator("#first_name").count() == 0:
            result["status"] = "blocked"
            result["notes"] = "No Greenhouse form found (custom ATS)"
            return result

        if has_auth_questions(page):
            auth = PROFILE.get("work_authorized_us")
            sponsor = PROFILE.get("needs_sponsorship")
            if auth is None or sponsor is None:
                result["status"] = "blocked_auth"
                result["notes"] = "Form asks work auth/sponsorship; profile incomplete"
                shot = LOG_DIR / f"blocked_{company}_{jid}.png"
                page.screenshot(path=str(shot), full_page=True)
                return result

        fill_basic(page, company, role)

        # Answer known experience/education if present
        if PROFILE.get("years_experience"):
            react_select(page, "years of experience", str(PROFILE["years_experience"]))
        if PROFILE.get("education_level"):
            react_select(page, "highest level of education", PROFILE["education_level"])

        # Auth answers when known
        if PROFILE.get("needs_sponsorship") is True:
            react_select(page, "sponsor", "Yes")
        elif PROFILE.get("needs_sponsorship") is False:
            react_select(page, "sponsor", "No")
        if PROFILE.get("work_authorized_us") is True:
            react_select(page, "legally authorized", "Yes")
        elif PROFILE.get("work_authorized_us") is False:
            react_select(page, "legally authorized", "No")

        # Decline EEO when possible
        for q, ans in [
            ("gender identity", "Decline"),
            ("race/ethnicity", "Decline"),
            ("veteran status", "Decline"),
            ("disability", "Decline"),
            ("prefer not", "Prefer not"),
        ]:
            try:
                react_select(page, q, ans)
            except Exception:
                pass

        shot = LOG_DIR / f"filled_{company}_{jid}.png"
        page.screenshot(path=str(shot), full_page=True)

        if dry_run:
            result["status"] = "ready_dry_run"
            result["notes"] = f"Form filled; dry-run only. Screenshot {shot.name}"
            return result

        # Submit
        for sel in ["button:has-text('Submit application')", "button:has-text('Submit')", "input[type=submit]"]:
            if page.locator(sel).count():
                page.locator(sel).first.click()
                break
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        if re.search(r"thank you|application.*(received|submitted)|successfully", body, re.I):
            result["status"] = "applied"
            result["notes"] = "Confirmation detected"
        else:
            result["status"] = "submitted_unconfirmed"
            result["notes"] = "Clicked submit; no clear confirmation"
        page.screenshot(path=str(LOG_DIR / f"result_{company}_{jid}.png"), full_page=True)
        return result
    except Exception as e:
        result["status"] = "failed"
        result["notes"] = str(e)[:300]
        return result


def update_tracker(results: list[dict]) -> None:
    if not TRACKER.exists():
        return
    rows = list(csv.DictReader(TRACKER.open()))
    by_url = {r["url"]: r for r in rows}
    for res in results:
        url = res.get("url")
        if url in by_url:
            by_url[url]["status"] = res["status"]
            by_url[url]["notes"] = res.get("notes", "")
    with TRACKER.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "company", "title", "role_bucket", "location", "url", "source", "status", "notes"])
        w.writeheader()
        for r in rows:
            w.writerow(by_url.get(r["url"], r))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--submit", action="store_true", help="Actually submit (default dry-run)")
    ap.add_argument("--company", default="")
    args = ap.parse_args()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    jobs = json.loads(QUEUE.read_text())
    if args.company:
        jobs = [j for j in jobs if j["company"] == args.company]
    jobs = jobs[: args.limit]

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for job in jobs:
            print(f"Applying: {job['company']} — {job['title']}")
            res = apply_one(page, job, dry_run=not args.submit)
            print(" ->", res["status"], res["notes"])
            results.append(res)
        browser.close()

    out = LOG_DIR / f"session_{date.today().isoformat()}.json"
    out.write_text(json.dumps(results, indent=2))
    update_tracker(results)
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
