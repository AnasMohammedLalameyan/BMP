"""Change 10: financial-year-specific director filtering (server rule and the browser helper that mirrors it).

FY 2024-25 is the window 2024-04-01 .. 2025-03-31. A stint is active when start <= window end AND (end is empty OR end >= window start)."""
import itertools
import json
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.routers.people import active_in_window, fy_window

BOUNDARY = [  # (label, start, end, fy, active in that year, ended during that year)
    ("appointed on the last day of the FY", "2025-03-31", None, "2024-25", True, False),
    ("appointed the day after the FY ends", "2025-04-01", None, "2024-25", False, False),
    ("appointed on the first day of the FY", "2024-04-01", None, "2024-25", True, False),
    ("ceased on the first day of the FY", "2020-01-01", "2024-04-01", "2024-25", True, True),
    ("ceased the day before the FY", "2020-01-01", "2024-03-31", "2024-25", False, False),
    ("ceased on the last day of the FY", "2020-01-01", "2025-03-31", "2024-25", True, True),
    ("ceased in the middle of the FY", "2020-01-01", "2024-10-10", "2024-25", True, True),
    ("no end date", "2010-05-05", None, "2024-25", True, False),
    ("ceased after the FY", "2020-01-01", "2026-01-01", "2024-25", True, False),
    ("inside the FY entirely", "2024-06-01", "2024-12-31", "2024-25", True, True),
    ("same stint, previous year", "2024-04-01", "2025-03-31", "2023-24", False, False),
    ("same stint, next year", "2024-04-01", "2025-03-31", "2025-26", False, False),
]


@pytest.fixture(scope="module")
def fy_company(admin, uniq):
    """A throw-away company whose board holds one person per distinct (start, end) pair above. Archived at the end."""
    cin = f"U{uniq():020d}"
    company = admin.ok(admin.post("/companies", {"cin": cin, "name": "FY Filter Test Company", "status": "active", "date_of_incorporation": "2001-04-01"}), status=201)["row"]
    people = {}
    for i, (start, end) in enumerate(sorted({(b[1], b[2]) for b in BOUNDARY}, key=lambda x: (x[0], x[1] or ""))):
        person = admin.ok(admin.post("/entities/director", {"full_name": f"FY Case {cin[-4:]} {i:02d}"}), status=201)["row"]
        stint = {"company_id": company["id"], "director_id": person["id"], "start_date": start}
        if end:
            stint["end_date"] = end
        admin.ok(admin.post("/entities/directorship", stint), status=201)
        people[(start, end)] = (person["id"], person["full_name"])
    yield company["id"], people
    admin.post(f"/entities/company/{company['id']}/archive")
    for pid, _ in people.values():
        admin.post(f"/entities/director/{pid}/archive")


@pytest.mark.parametrize("label,start,end,fy,active,ended", BOUNDARY, ids=[b[0] + " @" + b[3] for b in BOUNDARY])
def test_the_fy_predicate_at_every_boundary(admin, fy_company, label, start, end, fy, active, ended):
    cid, people = fy_company
    name = people[(start, end)][1]
    rows = admin.ok(admin.get(f"/companies/{cid}/directors-register", params={"fy": fy}))["rows"]
    row = next(r for r in rows if r["full_name"] == name)
    assert row["active_in_fy"] is active and row["ceased_in_fy"] is ended, label
    only_active = admin.ok(admin.get(f"/companies/{cid}/directors-register", params={"fy": fy, "include_inactive": "false"}))["rows"]
    assert (name in {r["full_name"] for r in only_active}) is active, label
    assert all(r["active_in_fy"] for r in only_active)
    window = fy_window(fy)                                                                                     # the rule, stated plainly
    assert (start <= window[1].isoformat() and (end is None or end >= window[0].isoformat())) is active


def test_a_director_who_resigned_and_was_reappointed_is_handled_per_year(admin):
    """The demo data: Prashant Joshi at BrightMed - 2016-06-01 to 2021-05-31, then again from 2023-07-01."""
    def stints(fy):
        rows = admin.ok(admin.get("/companies/2/directors-register", params={"fy": fy}))["rows"]
        return {r["start_date"]: (r["active_in_fy"], r["ceased_in_fy"]) for r in rows if r["full_name"] == "Prashant Joshi"}
    assert stints("2020-21") == {"2016-06-01": (True, False), "2023-07-01": (False, False)}     # still serving when the year ended
    assert stints("2021-22") == {"2016-06-01": (True, True), "2023-07-01": (False, False)}      # resigned during this year
    assert stints("2022-23") == {"2016-06-01": (False, False), "2023-07-01": (False, False)}    # in between: on no board
    assert stints("2023-24") == {"2016-06-01": (False, False), "2023-07-01": (True, False)}     # back on the board
    only = admin.ok(admin.get("/companies/2/directors-register", params={"fy": "2022-23", "include_inactive": "false"}))["rows"]
    assert "Prashant Joshi" not in {r["full_name"] for r in only}


def test_without_the_new_parameters_the_register_behaves_exactly_as_before(admin):
    plain = admin.ok(admin.get("/companies/2/directors-register"))["rows"]
    assert plain == admin.ok(admin.get("/companies/2/directors-register", params={"include_ceased": "true"}))["rows"]
    assert len(plain) == 5 and not any("active_in_fy" in r or "ceased_in_fy" in r for r in plain)          # no new keys, nothing dropped
    assert plain == admin.ok(admin.get("/companies/2/directors-register", params={"include_inactive": "false"}))["rows"]   # needs fy to act
    current = admin.ok(admin.get("/companies/2/directors-register", params={"include_ceased": "false"}))["rows"]
    assert len(current) == 4 and all(r["is_current"] for r in current)                                  # the existing filter still works
    both = admin.ok(admin.get("/companies/2/directors-register", params={"include_ceased": "false", "fy": "2021-22"}))["rows"]
    assert all(r["is_current"] and "active_in_fy" in r for r in both)                                   # the two filters combine


@pytest.mark.parametrize("bad", ["2024", "2024-26", "24-25", "abcd-ef", "2024/25", "2024-5"])
def test_a_malformed_financial_year_is_refused_with_a_message(admin, bad):
    r = admin.get("/companies/2/directors-register", params={"fy": bad})
    assert r.status_code == 422 and r.json()["error"]["fields"]["fy"].startswith("Financial year must look like")


def test_the_register_still_respects_company_access(manager, client):
    assert manager.get("/companies/1/directors-register", params={"fy": "2024-25"}).status_code == 404
    assert client.get("/companies/2/directors-register", params={"fy": "2024-25"}).status_code == 404


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_the_browser_helper_gives_the_same_answers_as_the_server_rule(tmp_path):
    """util.js mirrors the Python predicate; compare them over the boundary days of several years, with and without an end date."""
    shutil.copy(Path(__file__).resolve().parents[2] / "app" / "static" / "scripts" / "util.js", tmp_path / "util.mjs")
    cases = []
    for fy in ("2019-20", "2020-21", "2024-25", "2025-26", "2099-00", "2024-26", "24-25", "", None, "2024", "2024-5"):
        for anchor in ("2020-04-01", "2021-04-01", "2024-04-01", "2025-04-01", "2100-04-01"):
            a = date.fromisoformat(anchor)
            days = [(a + timedelta(days=d)).isoformat() for d in (-366, -2, -1, 0, 1, 364, 365, 366)]
            for start, end in itertools.product(days, days + [None]):
                if end is None or end >= start:
                    cases.append({"fy": fy, "start": start, "end": end})
    (tmp_path / "run.mjs").write_text(
        'import { activeInFy, ceasedInFy, fyWindow } from "./util.mjs";\n'
        'const cases = JSON.parse(await new Promise((r) => { let s = ""; process.stdin.on("data", (d) => s += d).on("end", () => r(s)); }));\n'
        'console.log(JSON.stringify(cases.map((c) => [fyWindow(c.fy), activeInFy(c.start, c.end, c.fy), ceasedInFy(c.end, c.fy)])));\n',
        encoding="utf-8")
    out = subprocess.run(["node", str(tmp_path / "run.mjs")], input=json.dumps(cases), capture_output=True, text=True, check=True)
    results = json.loads(out.stdout)
    assert len(results) == len(cases) > 2000
    for c, (window, active, ceased) in zip(cases, results):
        try:
            w = fy_window(c["fy"])
        except Exception:
            assert window is None and active is False and ceased is False, c                                  # unreadable year: no window
            continue
        assert window == {"start": w[0].isoformat(), "end": w[1].isoformat()}, c
        assert active is active_in_window(date.fromisoformat(c["start"]), date.fromisoformat(c["end"]) if c["end"] else None, *w), c
        assert ceased is (c["end"] is not None and w[0].isoformat() <= c["end"] <= w[1].isoformat()), c
