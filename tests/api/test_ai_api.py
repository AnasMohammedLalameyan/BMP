"""AI endpoints: off by default, access and company isolation, nothing written, notice approval. Fake model, dummy data."""
import pytest

from app.ai import index, llm, notice
from app.ai.schemas import AgendaFound, AskAnswer, Claim, Found, IntakePlan, MeetingExtraction, NoticeCover, Route
from tests.ai.helpers import MINUTES, docx_bytes, fake_embed, make_ai

BRIGHT, NEXA = 2, 1
COUNTED = ("core.meeting", "core.meeting_agenda_item", "core.meeting_attendance", "core.document", "core.evidence_link",
           "core.government_filing", "ops.activity_instance", "ops.task_instance", "activity.activity_template")


def counts(owner):
    return {t: owner.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in COUNTED}


@pytest.fixture(scope="module", autouse=True)
def leave_no_meetings_behind(admin, owner):
    """The test database is shared by the whole session: archive the meetings created here (nothing is deleted)."""
    first = owner.execute("SELECT coalesce(max(id), 0) AS n FROM core.meeting").fetchone()["n"]
    yield
    for r in owner.execute("SELECT id FROM core.meeting WHERE id > %s AND NOT is_archived", (first,)).fetchall():
        admin.ok(admin.post(f"/entities/meeting/{r['id']}/archive"))


@pytest.fixture
def ai_on(app, tmp_path):
    """Switch AI on for one test, with a fake model and a fake embedder; always switched back off."""
    app.state.ai_settings = make_ai(tmp_path)
    llm.reset_limiter()
    index.set_embedder(fake_embed)
    yield app.state.ai_settings
    llm.set_runner(None)
    index.set_embedder(None)
    app.state.ai_settings = None


def upload(sess, company, name, data):
    r = sess.http.post("/api/documents/upload", data={"company_id": str(company)}, files={"file": (name, data)})
    assert r.status_code == 201, r.text
    return r.json()["document"]["id"]


def extraction(*_):
    return MeetingExtraction(
        meeting_date=Found(value="12th September 2026", source_quote="held on 12th September 2026"),
        chairman=Found(value="Rajan Patel", source_quote="Mr. Rajan Patel was elected chairman"),
        agenda=[AgendaFound(text="To approve the appointment of the statutory auditor",
                            source_quote="1. To approve the appointment of the statutory auditor")])


def test_ai_off_by_default(app, admin, client, tmp_path):
    app.state.ai_settings = make_ai(tmp_path, enabled=False)           # whatever the local .env says, switch it off here
    assert admin.ok(admin.get("/ai/status"))["enabled"] is False
    assert client.ok(client.get("/ai/status"))["enabled"] is False
    for r in (admin.post("/ai/suggest", {"company_id": BRIGHT, "document_id": 1}),
              admin.post("/ai/intake", {"text": "board meeting"}),
              admin.post("/ai/board/ask", {"company_id": BRIGHT, "question": "q"}),
              admin.post("/ai/meetings/1/board/notice/draft"), admin.get(f"/ai/documents?company_id={BRIGHT}")):
        assert r.status_code == 503 and r.json()["error"]["code"] == "ai_unavailable"
    assert admin.ok(admin.get("/minutes/registers"))["registers"]            # the rest of the dashboard is untouched
    assert admin.http.get("/api/health").json()["ai"] is False
    app.state.ai_settings = None


def test_real_data_is_blocked_until_confirmed(app, tmp_path):
    app.state.ai_settings = make_ai(tmp_path, data_mode="real")
    try:
        st = app.state.ai_settings.status()
        assert st["enabled"] is False and "Zero Data Retention" in st["reason_if_disabled"]
        assert make_ai(tmp_path, data_mode="real", zdr_confirmed=True, outside_india_approved=True).status()["enabled"]
        assert "secret" not in str(st).lower() and "test-key" not in str(st)
    finally:
        app.state.ai_settings = None


def test_status_when_on_never_shows_a_key(admin, ai_on):
    st = admin.ok(admin.get("/ai/status"))
    assert st["enabled"] is True and "test-key" not in str(st) and st["models"]["extract"] == "m1"


def test_suggest_reads_a_stored_document_and_writes_nothing(admin, owner, ai_on):
    doc = upload(admin, BRIGHT, "dummy_minutes.docx", docx_bytes(MINUTES))
    llm.set_runner(lambda p, s, u, sc: extraction())
    before = counts(owner)
    docs = admin.ok(admin.get(f"/ai/documents?company_id={BRIGHT}"))["documents"]
    assert {"id": doc, "name": "dummy_minutes.docx"} in docs
    before = counts(owner)
    res = admin.ok(admin.post("/ai/suggest", {"company_id": BRIGHT, "document_id": doc}))
    keys = {f["key"]: f for f in res["fields"]}
    assert keys["meeting_date"]["proposed"] == "2026-09-12" and keys["meeting_date"]["tier"] == "high"
    assert res["agenda"][0]["forms"] == "ADT-1"
    assert counts(owner) == before                                           # suggesting changes no row at all


def test_suggest_access(app, admin, manager, client, owner, tmp_path):
    app.state.ai_settings = make_ai(tmp_path)
    llm.set_runner(lambda p, s, u, sc: extraction())
    try:
        nexa_doc = upload(admin, NEXA, "nexa_minutes.docx", docx_bytes(MINUTES))
        bright_doc = upload(admin, BRIGHT, "bright_minutes.docx", docx_bytes(MINUTES))
        assert client.post("/ai/suggest", {"company_id": NEXA, "document_id": nexa_doc}).status_code == 403    # read-only
        assert client.post("/ai/suggest", {"company_id": BRIGHT, "document_id": bright_doc}).status_code == 404  # not theirs
        assert admin.post("/ai/suggest", {"company_id": BRIGHT, "document_id": nexa_doc}).status_code == 404     # other company's file
        assert manager.post("/ai/suggest", {"company_id": NEXA, "document_id": nexa_doc}).status_code == 404
        assert client.get(f"/ai/documents?company_id={BRIGHT}").status_code == 404
        assert client.get(f"/ai/documents?company_id={NEXA}").status_code == 200                                # reading is allowed
    finally:
        llm.set_runner(None)
        app.state.ai_settings = None


def test_intake_pre_fills_and_creates_nothing(admin, client, owner, ai_on):
    llm.set_runner(lambda p, s, u, sc: Route(intent="intake") if sc is Route else IntakePlan(
        register_key="board", company="BrightMed", meeting_date="2026-06-12", mode="video conferencing", agenda=["Approve accounts"]))
    before = counts(owner)
    res = admin.ok(admin.post("/ai/intake", {"text": "Board meeting of BrightMed on 12 June 2026 by video", "company_id": BRIGHT}))
    assert res["kind"] == "intake" and res["company_id"] == BRIGHT and res["fields"]["meeting_date"] == "2026-06-12"
    assert res["fields"]["mode"] == "Video conferencing" and res["missing"] == [] and res["agenda"] == ["Approve accounts"]
    assert counts(owner) == before
    assert client.post("/ai/intake", {"text": "x", "company_id": NEXA}).status_code == 403          # read-only
    assert client.post("/ai/intake", {"text": "x", "company_id": BRIGHT}).status_code == 404


def test_intake_question_is_redirected_to_ask(admin, ai_on):
    llm.set_runner(lambda p, s, u, sc: Route(intent="ask"))
    res = admin.ok(admin.post("/ai/intake", {"text": "What is the quorum for a board meeting?"}))
    assert res["kind"] == "ask" and "Ask" in res["message"]


def board_meeting(admin, **kw):
    body = {"meeting_date": "2026-09-12", "mode": "Video conferencing", "meeting_time": "11:00 AM to 12:00 PM",
            "agenda": [{"text": "Approve accounts"}], **kw}
    return admin.ok(admin.post(f"/minutes/board?company_id={BRIGHT}", body), 201)["meeting"]


def test_notice_draft_recipients_match_the_database(admin, manager, client, owner, ai_on):
    llm.set_runner(lambda p, s, u, sc: NoticeCover(cover="Dear {recipient_name},\nPlease find the notice below."))
    m = board_meeting(admin)
    expected = {r["full_name"] for r in owner.execute(
        """SELECT d.full_name FROM core.directorship ds JOIN core.director d ON d.id = ds.director_id
           WHERE ds.company_id = %s AND NOT ds.is_archived AND ds.start_date <= %s
             AND (ds.end_date IS NULL OR ds.end_date >= %s)""", (BRIGHT, "2026-09-12", "2026-09-12")).fetchall()}
    before = counts(owner)
    draft = admin.ok(admin.post(f"/ai/meetings/{m['meeting_id']}/board/notice/draft"))
    assert {r["name"] for r in draft["recipients"]} == expected and expected
    assert draft["missing"] == [] and draft["sandbox"] is True and "{recipient_name}" in draft["cover"]
    assert "Approve accounts" in draft["notice"] and "12 September 2026" in draft["notice"]
    assert counts(owner) == before
    nx = owner.execute("SELECT id FROM core.meeting WHERE company_id = %s LIMIT 1", (NEXA,)).fetchone()["id"]
    assert client.post(f"/ai/meetings/{nx}/board/notice/draft").status_code == 403              # read-only
    assert manager.post(f"/ai/meetings/{nx}/board/notice/draft").status_code == 404             # another company's meeting
    assert admin.post(f"/ai/meetings/{m['meeting_id']}/agm/notice/draft").status_code == 404    # wrong register for it


def test_notice_send_needs_approval_and_goes_only_to_the_test_server(app, admin, client, owner, ai_on, monkeypatch, request):
    llm.set_runner(lambda p, s, u, sc: NoticeCover(cover="Dear {recipient_name},\nNotice follows."))
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=0):
            sent.append(("connect", host, port))

        def send_message(self, msg):
            sent.append(("mail", msg["To"], msg.get_content()))

        def quit(self):
            pass

    monkeypatch.setattr(notice.smtplib, "SMTP", FakeSMTP)
    touched = [r["id"] for r in owner.execute(
        "UPDATE core.director SET email = lower(replace(full_name, ' ', '.')) || '@example.test' WHERE email IS NULL RETURNING id")]
    request.addfinalizer(lambda: owner.execute("UPDATE core.director SET email = NULL WHERE id = ANY(%s)", (touched,)))
    m = board_meeting(admin, meeting_date="2026-09-14")
    base = f"/ai/meetings/{m['meeting_id']}/board/notice"
    draft = admin.ok(admin.post(base + "/draft"))
    cover = draft["cover"]
    assert admin.post(base + "/send", {"cover": cover, "fingerprint": draft["fingerprint"]}).status_code == 422     # no approval
    assert admin.post(base + "/send", {"approve": True, "cover": cover, "fingerprint": "stale"}).status_code == 409
    assert client.post(base + "/send", {"approve": True, "cover": cover}).status_code in (403, 404)
    assert not sent
    res = admin.ok(admin.post(base + "/send", {"approve": True, "cover": cover, "fingerprint": draft["fingerprint"]}))
    mails = [x for x in sent if x[0] == "mail"]
    with_email = [r for r in draft["recipients"] if r["has_email"]]
    assert res["sent"] == len(mails) == len(with_email) > 0
    assert sent[0] == ("connect", "localhost", 1025)                                  # sandbox: the local test server only
    assert all(r["name"].split()[0] in mail[2] for r, mail in zip(with_email, mails))   # each message is addressed by name
    assert admin.post(base + "/send", {"approve": True, "cover": cover, "fingerprint": draft["fingerprint"]}).status_code == 409


def test_ask_is_cited_and_company_bound(app, admin, manager, client, ai_on, tmp_path):
    app.state.settings.storage_dir.mkdir(parents=True, exist_ok=True)
    upload(admin, BRIGHT, "quorum_guide.txt", b"A board meeting needs a quorum of one third of the directors or two, whichever is higher. " * 3)
    upload(admin, NEXA, "zebra_secret.txt", b"zebra confidential terms of the Nexatech arrangement. " * 3)
    prompts = []

    def runner(p, s, u, sc):
        prompts.append(u)
        return AskAnswer(claims=[Claim(text="The quorum is one third of the directors or two.", chunk_id="c1",
                                       quote="quorum of one third of the directors or two")])

    llm.set_runner(runner)
    res = admin.ok(admin.post("/ai/board/ask", {"company_id": BRIGHT, "question": "What quorum does a board meeting need?"}))
    assert res["declined"] is False and res["answer"][0]["citation"] == "quorum_guide.txt, page 1"
    # a Company B session asking about Company A's secret never sees it, and it is never even sent to the model
    prompts.clear()
    llm.set_runner(lambda p, s, u, sc: (prompts.append(u), AskAnswer(insufficient=True))[1])
    res = manager.ok(manager.post("/ai/board/ask", {"company_id": BRIGHT, "question": "zebra confidential terms"}))
    assert res["declined"] is True and prompts and all("zebra" not in u.split("Passages:")[1].lower() for u in prompts)
    assert client.post("/ai/board/ask", {"company_id": BRIGHT, "question": "q"}).status_code == 404
    assert client.post("/ai/board/ask", {"company_id": NEXA, "question": "zebra confidential terms"}).status_code == 200
    assert admin.post("/ai/nope/ask", {"company_id": BRIGHT, "question": "q"}).status_code == 404


def test_unavailable_model_gives_the_friendly_error(admin, ai_on):
    def boom(*_):
        raise RuntimeError("provider down")

    llm.set_runner(None)
    import app.ai.llm as m
    orig = m._chat_model
    m._chat_model = boom
    try:
        r = admin.post("/ai/intake", {"text": "board meeting on 12 June 2026"})
        assert r.status_code == 503 and "continue by hand" in r.json()["error"]["message"]
    finally:
        m._chat_model = orig
