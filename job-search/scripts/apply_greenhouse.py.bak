#!/usr/bin/env python3
"""Greenhouse job-board apply helper for Revanth Mallol."""
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

EMPLOYER = "University of Texas at Arlington"


def cover_letter(company: str, role: str) -> str:
    tmpl = (ROOT / "materials" / "cover_letter_data_engineer.txt").read_text()
    return tmpl.replace("{{COMPANY}}", company.replace("-", " ").title()).replace("{{ROLE}}", role)


def click_option(page, option_text: str) -> bool:
    opt = page.locator("[role='option']").filter(has_text=re.compile(re.escape(option_text), re.I)).first
    try:
        if opt.count():
            opt.click(timeout=2500)
            return True
    except Exception:
        pass
    page.keyboard.type(option_text[:48])
    page.wait_for_timeout(200)
    page.keyboard.press("Enter")
    return True


def open_select_near(page, question_re: str):
    label = page.get_by_text(re.compile(question_re, re.I)).first
    label.scroll_into_view_if_needed(timeout=4000)
    block = label.locator(
        "xpath=ancestor::*[contains(@class,'field') or contains(@class,'question') or self::fieldset or self::div][1]"
    )
    ctrl = block.locator(".select__control, .select__input-container").first
    ctrl.click(force=True, timeout=5000)
    page.wait_for_timeout(250)
    return True


def set_select_near_text(page, question_re: str, option_text: str) -> bool:
    try:
        open_select_near(page, question_re)
        return click_option(page, option_text)
    except Exception:
        return False


def fill_text_near(page, question_re: str, value: str) -> bool:
    try:
        label = page.get_by_text(re.compile(question_re, re.I)).first
        label.scroll_into_view_if_needed(timeout=3000)
        # input in same container
        block = label.locator("xpath=ancestor::*[self::div or self::fieldset][1]")
        inp = block.locator("input[type='text'], input:not([type]), textarea").first
        if inp.count():
            inp.fill(value)
            return True
    except Exception:
        pass
    return False


def check_near(page, question_re: str) -> bool:
    """Click checkbox/consent associated with question text."""
    try:
        # Click label text itself if it's a checkbox label
        lab = page.get_by_text(re.compile(question_re, re.I)).first
        lab.scroll_into_view_if_needed(timeout=3000)
        # Prefer checkbox in container
        block = lab.locator("xpath=ancestor::*[self::div or self::label or self::fieldset][1]")
        box = block.locator("input[type=checkbox], [role=checkbox]").first
        if box.count():
            box.click(force=True, timeout=3000)
            return True
        lab.click(force=True, timeout=3000)
        return True
    except Exception:
        return False


def fill_basic(page, company: str, role: str) -> None:
    page.fill("#first_name", PROFILE["first_name"])
    page.fill("#last_name", PROFILE["last_name"])
    page.fill("#email", PROFILE["email"])
    if page.locator("#phone").count():
        page.fill("#phone", PROFILE["phone"])
    if page.locator("#preferred_name").count():
        page.fill("#preferred_name", PROFILE["first_name"])
    for sel, val in [
        ("#question_66111063", PROFILE["first_name"]),
        ("#question_66111064", PROFILE["last_name"]),
    ]:
        if page.locator(sel).count():
            page.fill(sel, val)
    if page.locator("input[aria-label='Preferred First Name']").count():
        page.fill("input[aria-label='Preferred First Name']", PROFILE["first_name"])
    if page.locator("input[aria-label='Preferred Last Name']").count():
        page.fill("input[aria-label='Preferred Last Name']", PROFILE["last_name"])

    if page.locator("#candidate-location").count():
        loc = PROFILE.get("city_state") or "Arlington, Texas, United States"
        page.click("#candidate-location")
        page.fill("#candidate-location", loc)
        page.wait_for_timeout(1000)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")

    if page.locator("#country").count():
        try:
            page.click("#country")
            page.fill("#country", "United States")
            page.wait_for_timeout(600)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        except Exception:
            pass

    if page.locator("#resume").count():
        page.set_input_files("#resume", str(RESUME))

    li = PROFILE.get("linkedin") or ""
    if li:
        for sel in ["input[aria-label='LinkedIn Profile']", "input[aria-label*='LinkedIn']"]:
            if page.locator(sel).count():
                page.fill(sel, li)
                break

    port = PROFILE.get("portfolio") or ""
    gh = PROFILE.get("github") or ""
    if port and page.locator("input[aria-label*='Website'], input[aria-label*='Portfolio']").count():
        page.locator("input[aria-label*='Website'], input[aria-label*='Portfolio']").first.fill(port)
    if gh and page.locator("input[aria-label*='GitHub'], input[aria-label*='Github']").count():
        page.locator("input[aria-label*='GitHub'], input[aria-label*='Github']").first.fill(gh)

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
        fill_text_near(page, r"zip code|postal code", zip_code)

    cl = cover_letter(company, role)
    if page.locator("textarea").count():
        try:
            page.locator("textarea").first.fill(cl)
        except Exception:
            pass


def answer_common_questions(page) -> list[str]:
    notes = []

    # Auth / sponsorship
    if PROFILE.get("needs_sponsorship") is True:
        notes.append(f"sponsor={set_select_near_text(page, r'sponsor|immigration case', 'Yes')}")
    if PROFILE.get("work_authorized_us") is True:
        notes.append(f"auth={set_select_near_text(page, r'legally authorized to work', 'Yes')}")

    # Consents / policies
    for q in [
        r"Processing of Personal Data",
        r"AI Policy for Interviewers",
        r"I confirm that I reside in the United States",
        r"I have read and agree",
        r"privacy policy",
        r"terms and conditions",
        r"consent",
    ]:
        if re.search(q, page.inner_text("body"), re.I):
            notes.append(f"check:{q[:30]}={check_near(page, q)}")

    # Yes/No common
    set_select_near_text(page, r"previously worked at|previously worked for|worked for Instacart|worked at Samsara|worked for Coinbase|worked at Brex|worked at Gusto", "No")
    set_select_near_text(page, r"currently, or have you previously, worked", "No")
    set_select_near_text(page, r"require relocation assistance", "No")
    set_select_near_text(page, r"accept the listed salary range|comfortable with the (base )?salary", "Yes")
    set_select_near_text(page, r"authorized to work without sponsorship|require sponsorship for employment", "Yes" if PROFILE.get("needs_sponsorship") else "No")
    # Sometimes inverted wording
    set_select_near_text(page, r"will you require sponsorship", "Yes")

    # Experience / education
    for q in [
        r"years of experience.*data engineer",
        r"years of experience.*software engineer",
        r"years of experience.*data engineering",
        r"years of experience.*production-grade",
        r"years of experience.*pipeline",
        r"How many years of experience",
    ]:
        set_select_near_text(page, q, "3")
        set_select_near_text(page, q, "3-5")
        set_select_near_text(page, q, "3+")

    set_select_near_text(page, r"highest level of education", "Master")
    set_select_near_text(page, r"how did you hear", "Other")
    set_select_near_text(page, r"Where have you learned about", "Other")
    # multi-select sources — pick Career Page / Other
    set_select_near_text(page, r"Where have you learned about Samsara", "Company website")
    set_select_near_text(page, r"Where have you learned about Samsara", "Other")

    # Employer / company name / country
    fill_text_near(page, r"Most Recent Employer|Current employer|Company name|Employer name", EMPLOYER)
    # Coinbase often has "Company name*" as text
    for sel in ["input[aria-label*='Company']", "input[aria-label*='Employer']", "input[aria-label*='employer']"]:
        if page.locator(sel).count():
            page.locator(sel).first.fill(EMPLOYER)

    set_select_near_text(page, r"What country are you based in|Country of residence|based in\?", "United States")
    fill_text_near(page, r"What country are you based in", "United States")

    if PROFILE.get("us_citizen") is False:
        set_select_near_text(page, r"US citizen|U\.S\. citizen|United States citizen", "No")
    if PROFILE.get("security_clearance") is False:
        set_select_near_text(page, r"security clearance|active clearance", "No")

    # EEO decline
    for q, ans in [
        (r"gender identity", "Decline"),
        (r"race/ethnicity|race or ethnicity", "Decline"),
        (r"veteran status", "I am not a protected veteran"),
        (r"disability", "No, I do not have"),
        (r"hispanic|latino", "Decline"),
    ]:
        set_select_near_text(page, q, ans)
        set_select_near_text(page, q, "Prefer not")
        set_select_near_text(page, q, "Decline to")

    return notes


def page_requires_clearance_or_citizen(page) -> bool:
    text = page.inner_text("body")
    return bool(
        re.search(
            r"must be a (U\.?S\.?|United States) citizen|US citizenship required|active (secret|ts/sci|top secret) clearance required",
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
        page.wait_for_timeout(1200)
        if page.locator("#first_name").count() == 0:
            page.goto(job["url"], wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1200)
            for sel in ["a:has-text('Apply')", "button:has-text('Apply')"]:
                try:
                    page.locator(sel).first.click(timeout=2000)
                except Exception:
                    pass
        if page.locator("#first_name").count() == 0:
            result["status"] = "blocked"
            result["notes"] = "No Greenhouse form found"
            return result

        if page_requires_clearance_or_citizen(page):
            result["status"] = "skipped_citizen_clearance"
            result["notes"] = "Role requires US citizenship or clearance"
            return result

        fill_basic(page, company, role)
        notes = answer_common_questions(page)
        # second pass for leftover Select...
        for _ in range(2):
            notes.extend(answer_common_questions(page))

        shot = LOG_DIR / f"filled_{company}_{jid}.png"
        page.screenshot(path=str(shot), full_page=True)

        if dry_run:
            result["status"] = "ready_dry_run"
            result["notes"] = f"{'; '.join(notes[-6:])}; screenshot {shot.name}"
            return result

        for sel in [
            "button:has-text('Submit application')",
            "button:has-text('Submit Application')",
            "button:has-text('Submit')",
            "input[type=submit]",
        ]:
            if page.locator(sel).count():
                page.locator(sel).first.click()
                break
        page.wait_for_timeout(4000)
        body = page.inner_text("body")
        if re.search(r"thank you|application.*(received|submitted)|successfully", body, re.I):
            result["status"] = "applied"
            result["notes"] = "Confirmation detected"
        else:
            err_txt = ""
            # Find first required error-looking text still showing *
            for line in body.splitlines():
                if "is required" in line.lower() or (line.strip().endswith("*") and "Select" in body):
                    pass
            errs = page.locator("text=/required/i")
            if errs.count():
                err_txt = errs.first.inner_text()[:180]
            # Also capture visible validation near fields
            invalid = page.locator("[class*='error'], .field-error")
            if invalid.count():
                err_txt = (err_txt + " | " + invalid.first.inner_text()[:180]).strip(" |")
            result["status"] = "submitted_unconfirmed"
            result["notes"] = f"No clear confirmation; err={err_txt}"
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
        w = csv.DictWriter(
            f,
            fieldnames=["date", "company", "title", "role_bucket", "location", "url", "source", "status", "notes"],
        )
        w.writeheader()
        for r in rows:
            w.writerow(by_url.get(r["url"], r))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--company", default="")
    ap.add_argument("--offset", type=int, default=0)
    args = ap.parse_args()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    jobs = json.loads(QUEUE.read_text())
    if args.company:
        jobs = [j for j in jobs if j["company"] == args.company]
    jobs = jobs[args.offset : args.offset + args.limit]

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for job in jobs:
            print(f"Applying: {job['company']} — {job['title']}", flush=True)
            res = apply_one(page, job, dry_run=not args.submit)
            print(" ->", res["status"], res["notes"], flush=True)
            results.append(res)
        browser.close()

    out = LOG_DIR / f"session_{date.today().isoformat()}.json"
    prior = []
    if out.exists():
        try:
            prior = json.loads(out.read_text())
        except Exception:
            prior = []
    prior.extend(results)
    out.write_text(json.dumps(prior, indent=2))
    update_tracker(results)
    print("Wrote", out)
    from collections import Counter

    print(Counter(r["status"] for r in results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
