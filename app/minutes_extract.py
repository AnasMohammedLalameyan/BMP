"""Offline, rule-based reader for meeting minutes (.docx / .pdf).

Everything returned is a SUGGESTION for the person to review; nothing here touches the database or the network.
Word files are read with the standard library (zipfile + XML); PDFs with PyMuPDF. Scanned PDFs are not supported.
"""
from __future__ import annotations

import io
import re
import zipfile


class ScannedPdfError(ValueError):
    pass


SCANNED_MSG = ("This looks like a scanned image PDF, which the reader can't read yet. Please upload a "
               "text-based PDF or a Word copy, or enter the agenda by hand.")
UNSUPPORTED_MSG = "Please upload a Word (.docx) or PDF file."

I = re.I

# ---------------------------------------------------------------- text extraction

_ENT = (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&#39;", "'"), ("&amp;", "&"))


def _unescape(s: str) -> str:
    for a, b in _ENT:
        s = s.replace(a, b)
    return s


def _docx_lines(raw: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError):
        raise ValueError("This Word file could not be read. Please save it as .docx and try again.")
    out = []
    for para in xml.split("</w:p>"):
        text = "".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", para, re.S))
        text = _unescape(re.sub(r"<[^>]+>", "", text)).strip()
        if text:
            out.append(text)
    return out


def _pdf_lines(raw: bytes) -> list[str]:
    try:
        import pymupdf as fitz
    except ImportError:                      # older PyMuPDF
        import fitz
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception:
        raise ValueError("This PDF could not be read. Please upload a text-based PDF or a Word copy.")
    lines, pages = [], doc.page_count
    for page in doc:
        lines += [ln.strip() for ln in page.get_text().splitlines() if ln.strip()]
    if sum(len(x) for x in lines) < 40 * max(pages, 1):
        raise ScannedPdfError(SCANNED_MSG)
    return lines


def extract_lines(filename: str, raw: bytes) -> list[str]:
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return _docx_lines(raw)
    if name.endswith(".pdf"):
        return _pdf_lines(raw)
    raise ValueError(UNSUPPORTED_MSG)


# ---------------------------------------------------------------- meeting date

def _iso(d: int, m: int, y: int) -> str | None:
    if y < 100:
        y += 2000
    if 1 <= d <= 31 and 1 <= m <= 12 and 2000 <= y <= 2099:
        return f"{y:04d}-{m:02d}-{d:02d}"
    return None


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"])}


def _month(name: str) -> int | None:
    n = name.lower()
    for full, i in _MONTHS.items():
        if full == n or (len(n) >= 3 and full.startswith(n[:3]) and full.startswith(n)):
            return i
    return None


def _date_from_filename(filename: str) -> str | None:
    base = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    m = re.search(r"(?<!\d)(\d{1,2})[._\-](\d{1,2})[._\-](\d{2}|\d{4})(?!\d)", base)
    return _iso(int(m[1]), int(m[2]), int(m[3])) if m else None


def _date_from_body(lines: list[str]) -> str | None:
    head = " ".join(lines[:60])
    m = re.search(r"held on[^0-9]{0,20}(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", head, I)
    if m:
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"held on[^0-9]{0,20}(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})", head, I)
    if m and _month(m[2]):
        return _iso(int(m[1]), _month(m[2]), int(m[3]))
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", head)
    return _iso(int(m[1]), int(m[2]), int(m[3])) if m else None


# ---------------------------------------------------------------- agenda detection

AGENDA_VERB = re.compile(
    r"^(?:to\b|taking\b|take\b|noting\b|note\b|approv|adopt|appoint|re-?appoint|consider|confirm|grant|authoris|"
    r"authoriz|ratif|declar|discuss|conven|regularis|resignation|cessation|allot|issue|creat|convert|shift|alter|"
    r"opening|review of|recommend|any other|election of|fix|chair|quorum|leave\b|disclosur|presence|ascertain|"
    r"welcom|receipt|read\b|reading|vote of thanks|confirmation|notice\b|resolv)", I)
ITEM_MARKER = re.compile(r"^\(?\s*(?:item|agenda(?:\s+item)?)\s*(?:no\.?)?\s*\d{1,3}\s*[:.\)-]*\s*(.*)$", I)
NUMBERED = re.compile(r"^\(?\s*\d{1,2}\s*[.\)]\s+(.*)$")
NUM_REJECT = re.compile(r"^(?:that|whereas|resolved|it was|the said)", I)
SKIP_HEADING = re.compile(
    r"^\s*minutes of\b|meeting of the board of directors|^\s*physically present|"
    r"present through (?:video|vc|audio|electronic)|^\s*in attendance\b|"
    r"^\s*(?:directors|members|also|those)\s+present\b|^\s*present\s*[:.]?\s*$|^\s*absent\s*[:.]?\s*$|"
    r"^\s*invitees?\b|leave of absence was granted|\bcalled at\b|\broll call\b|^\s*proceedings of the meeting|"
    r"^\s*proceedings\s*[:.]?\s*$|^\s*ordinary business\s*[:.]?\s*$|^\s*special business\s*[:.]?\s*$", I)
CLOCK = re.compile(r"\d{1,2}[:.]\d{2}\s*(a\.?\s?m|p\.?\s?m|hrs|hours)", I)
ADDRESS = re.compile(
    r"\b\d{6}\b|board room|b-wing|\bwing\b|\bfloor\b|\d(st|nd|rd|th)\s+floor|^date\s*[:.]|^place\s*[:.]|"
    r"registered office of the company,", I)
DANGLING = re.compile(
    r"\b(for|and|of|to|the|with|in|on|or|by|a|an|as|at|from|under|into|regarding|pursuant|including)\s*[,:;-]?\s*$", I)


def _is_caps_heading(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 4 or s.lstrip().startswith(('"', "“")):
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) >= 0.85 and 1 <= len(s.split()) <= 32


def _is_structural(s: str) -> bool:
    return bool(ITEM_MARKER.match(s) or NUMBERED.match(s) or SKIP_HEADING.search(s) or CLOCK.search(s)
                or ADDRESS.search(s))


def _stitch(title: str, lines: list[str], i: int) -> tuple[str, int]:
    """Append following lines while the title ends on a dangling connector. Returns (title, last index used)."""
    while DANGLING.search(title) and i + 1 < len(lines):
        nxt = lines[i + 1]
        if not nxt.strip() or _is_structural(nxt):
            break
        title = f"{title} {nxt.strip()}"
        i += 1
    return title, i


def _candidates(lines: list[str]):
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        m = ITEM_MARKER.match(line)
        if m:
            rest = m[1].strip()
            if len(rest.split()) >= 2:
                title, last = _stitch(rest, lines, i)
            else:
                title, last = (lines[i + 1].strip(), i + 1) if i + 1 < len(lines) else (rest, i)
                title, last = _stitch(title, lines, last)
            out.append((title, i, "num"))
            i = last + 1
            continue
        m = NUMBERED.match(line)
        if m:
            rest = m[1].strip()
            if len(rest) >= 3 and (AGENDA_VERB.match(rest) or _is_caps_heading(rest)
                                   or (len(rest.split()) <= 6 and rest[:1].isupper() and not NUM_REJECT.match(rest))):
                title, last = _stitch(rest, lines, i)
                out.append((title, i, "num"))
                i = last + 1
                continue
        elif _is_caps_heading(line):
            title, last = _stitch(line.strip(), lines, i)
            out.append((title, i, "caps"))
            i = last + 1
            continue
        i += 1
    if sum(1 for c in out if c[2] == "num") >= 3:
        out = [c for c in out if c[2] == "num"]
    return out


KEEP_UPPER = {"AGM", "EGM", "CSR", "KMP", "MOA", "AOA", "ROC", "CFO", "MD", "WTD", "TDS", "GST", "NCLT", "RD", "MCA"}


def display_title(t: str) -> str:
    letters = [c for c in t if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.85:
        return t
    out = []
    for w in t.split():
        core = re.sub(r"[^\w]", "", w)
        if core in KEEP_UPPER or (len(core) <= 3 and core.isupper() and any(c.isdigit() for c in core)):
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


# ---------------------------------------------------------------- forms and documents

def _f(pattern):
    return re.compile(pattern, I)


_S = r"[-\s]?"
NAMED_FORMS = [
    ("DPT-3", rf"\bDPT{_S}3\b"), ("MSME-1", rf"\bMSME{_S}(?:form{_S})?(?:i|1)\b"),
    ("DIR-3 KYC", rf"\bDIR{_S}3\s*(?:web\s*)?kyc\b"), ("DIR-12", rf"\bDIR{_S}12\b"),
    ("MGT-14", rf"\bMGT{_S}14\b"), ("MGT-15", rf"\bMGT{_S}15\b"),
    ("MGT-7A", rf"\bMGT{_S}7A\b"), ("MGT-7", rf"\bMGT{_S}7(?!A)\b"),
    ("AOC-4 XBRL", rf"\bAOC{_S}4\s*XBRL\b"), ("AOC-4 CFS", rf"\bAOC{_S}4\s*CFS\b"),
    ("AOC-4", rf"\bAOC{_S}4\b"), ("ADT-1", rf"\bADT{_S}1\b"), ("ADT-3", rf"\bADT{_S}3\b"),
    ("PAS-3", rf"\bPAS{_S}3\b"), ("PAS-6", rf"\bPAS{_S}6\b"),
    ("CHG-1", rf"\bCHG{_S}1\b"), ("CHG-4", rf"\bCHG{_S}4\b"), ("CHG-9", rf"\bCHG{_S}9\b"),
    ("INC-20A", rf"\bINC{_S}20A\b"), ("INC-22", rf"\bINC{_S}22\b"), ("INC-23", rf"\bINC{_S}23\b"),
    ("INC-24", rf"\bINC{_S}24\b"), ("INC-28", rf"\bINC{_S}28\b"),
    ("SH-6", rf"\bSH{_S}6\b"), ("SH-7", rf"\bSH{_S}7\b"), ("SH-8", rf"\bSH{_S}8\b"), ("SH-11", rf"\bSH{_S}11\b"),
    ("MR-1", rf"\bMR{_S}1\b"), ("BEN-2", rf"\bBEN{_S}2\b"), ("MSC-1", rf"\bMSC{_S}1\b"), ("MSC-3", rf"\bMSC{_S}3\b"),
]
NAMED_FORMS = [(n, _f(p)) for n, p in NAMED_FORMS]

# (pattern, forms, reason) - list order = priority
FORM_RULES = [(_f(p), forms, why) for p, forms, why in [
    (r"shift.{0,40}registered office.{0,40}state|registered office.{0,30}from the state.{0,30}to the state",
     ["MGT-14", "INC-23", "INC-28", "INC-22"], "Registered office shifted between states"),
    (r"\bsection 13\b|alter\w*.{0,30}memorandum|memorandum of association", ["MGT-14"],
     "Alteration of the Memorandum (special resolution)"),
    (r"\bsection 14\b|alter\w*.{0,30}articles|articles of association", ["MGT-14"],
     "Alteration of the Articles (special resolution)"),
    (r"change of name|change.{0,20}name of the company", ["MGT-14", "INC-24"], "Change of company name"),
    (r"registered office", ["INC-22"], "Change of registered office"),
    (r"financial statement|annual account|audited account|adoption of.{0,20}account|statement of accounts",
     ["AOC-4"], "Financial statements to be filed"),
    (r"board.{0,3}s report|directors.{0,3} report", ["AOC-4"], "Board's report accompanies the accounts"),
    (r"statutory audit report|audit report", ["AOC-4"], "Audit report accompanies the accounts"),
    (r"annual return", ["MGT-7"], "Annual return"),
    (r"appoint\w*.{0,30}auditor|auditor.{0,20}appoint|ratif\w*.{0,20}auditor|re.?appoint\w*.{0,20}auditor|"
     r"casual vacancy.{0,20}auditor", ["ADT-1"], "Appointment of auditor"),
    (r"managing director|whole.?time director|\bwtd\b|chief executive|\bceo\b|\bcfo\b|chief financial officer|"
     r"appoint\w*.{0,30}(company secretary|manager)|\bkmp\b|key managerial", ["DIR-12", "MR-1"],
     "Appointment of managing director / KMP"),
    (r"appoint\w*.{0,30}director|resign\w*.{0,30}director|cessation.{0,20}director|change.{0,20}director|"
     r"director.{0,20}(appoint|resign|cease)|additional director|independent director", ["DIR-12"],
     "Change in directors"),
    (r"private placement|preferential (allotment|issue)", ["PAS-3", "MGT-14"], "Private placement / preferential issue"),
    (r"right\w* issue", ["PAS-3"], "Rights issue"),
    (r"allot\w*|issue of shares|issue of securities|further issue of", ["PAS-3"], "Allotment of securities"),
    (r"buy.?back|sh-?11|sh-?8", ["SH-11", "SH-8"], "Buy-back of shares"),
    (r"satisf\w*.{0,20}charge|charge.{0,20}satisf", ["CHG-4"], "Satisfaction of charge"),
    (r"creat\w*.{0,20}charge|modif\w*.{0,20}charge|charge.{0,20}(creat|modif)|mortgage|hypotheca|"
     r"secured.{0,20}(loan|borrow|debenture)", ["CHG-1"], "Creation / modification of charge"),
    (r"increase.{0,30}authoris\w*.{0,20}capital|authoris\w*.{0,10}(share )?capital", ["SH-7"],
     "Increase in authorised capital"),
    (r"employee stock option|\besop\b|\bpsop\b|sweat equity|stock option (plan|scheme)", ["MGT-14", "SH-6"],
     "Employee stock options / sweat equity"),
    (r"\bsection 186\b|inter.?corporate|loan.{0,30}investment.{0,30}guarantee", ["MGT-14"],
     "Loans, investments and guarantees (Sec 186)"),
    (r"special resolution", ["MGT-14"], "Special resolution"),
]]

DOC_RULES = [(_f(p), docs, why) for p, docs, why in [
    (r"disclosure of interest|interest of director|notice of interest|concern(ed)? or interest|\bmbp[-\s]?1\b|"
     r"form mbp|declarations? (of|by).{0,20}director", ["Form MBP-1", "Form DIR-8"], "Disclosure of interest"),
    (r"appoint\w*.{0,30}(director|kmp|managing director|whole.?time|\bmanager\b|chief executive|chief financial|"
     r"company secretary)|additional director|independent director|regularis\w*.{0,20}director|"
     r"re.?appoint\w*.{0,20}director",
     ["Form DIR-2 consent", "Form DIR-8", "Form MBP-1", "DIN & PAN proof"], "Appointment of director / KMP"),
    (r"resign\w*|cessation|vacat\w*.{0,20}office", ["Resignation letter", "Form DIR-11"], "Resignation / cessation"),
    (r"right\w* issue", ["Valuation report", "Letter of offer", "Record-date list"], "Rights issue"),
    (r"private placement|preferential (allotment|issue)|\bpas[-\s]?4\b",
     ["Valuation report", "Form PAS-4", "Special resolution"], "Private placement / preferential issue"),
    (r"allot\w*|issue of shares|issue of securities|further issue",
     ["Valuation report", "List of allottees", "Subscription bank statement"], "Allotment of securities"),
    (r"\bsection 186\b|inter.?corporate|loan.{0,30}(and|&).{0,10}investment|investment.{0,30}guarantee",
     ["Loan / investment agreement", "Form MBP-2 register", "Board resolution"], "Loans and investments (Sec 186)"),
    (r"\bloan\b|borrow\w*|credit facility|financial assistance|term loan|working capital|\bsanction\b",
     ["Loan / facility agreement", "Sanction letter", "Charge documents"], "Borrowing / facility"),
    (r"\bcharge\b|mortgage|hypotheca|\blien\b|\bpledge\b",
     ["Charge / security deed", "Sanction letter", "Form CHG-1"], "Creation of charge"),
    (r"related part|\brpt\b|\bsection 188\b|\baoc[-\s]?2\b",
     ["Draft RPT agreement", "Audit Committee approval", "Form AOC-2"], "Related party transaction"),
    (r"financial statement|annual account|audited account|adoption of.{0,20}account|statement of accounts|"
     r"balance sheet", ["Audited financial statements", "Auditor's report", "Board's report"], "Financial statements"),
    (r"board.{0,3}s report|directors.{0,3} report", ["Draft Board's report", "Board's report annexures"],
     "Board's report"),
    (r"appoint\w*.{0,20}auditor|ratif\w*.{0,20}auditor|auditor.{0,20}appoint|casual vacancy.{0,20}auditor|"
     r"re.?appoint\w*.{0,20}auditor", ["Auditor's consent", "Eligibility certificate", "Board resolution"],
     "Appointment of auditor"),
    (r"dividend", ["Dividend computation", "Profit / free-reserves working", "Bank balance confirmation"], "Dividend"),
    (r"registered office", ["Proof of new address", "NOC from the owner", "Board resolution"], "Registered office"),
    (r"authoris\w*.{0,10}(share )?capital|increase.{0,30}capital",
     ["Altered MOA", "Form SH-7 fee working", "Shareholder resolution"], "Authorised capital"),
    (r"change of name|alter\w*.{0,20}(memorandum|articles)|memorandum of association|articles of association",
     ["Altered MOA / AOA", "Special resolution", "Name-approval letter"], "Change of name / MOA / AOA"),
    (r"employee stock option|\besop\b|sweat equity|stock option",
     ["ESOP scheme", "Valuation report", "Special resolution"], "Employee stock options"),
    (r"buy.?back", ["Buy-back offer document", "Auditor's certificate", "Declaration of solvency"], "Buy-back"),
    (r"bank account|banking|signator|open\w*.{0,20}account",
     ["Account-opening resolution", "Signatories' KYC"], "Bank account"),
    (r"notice.{0,20}(meeting|agm|egm|general meeting)|conven\w*.{0,20}(meeting|agm|egm)",
     ["Notice with agenda", "Proof of circulation"], "Notice of meeting"),
    (r"confirm\w*.{0,20}minutes|minutes of (the )?previous|previous.{0,30}(minutes|meeting)|"
     r"(take |note )note of.{0,20}minutes|note of.{0,20}minutes", ["Signed previous minutes"],
     "Confirmation of previous minutes"),
    (r"annual return", ["Form MGT-7 / 7A", "Register of members"], "Annual return"),
]]

LEAVE_RE = re.compile(r"leave of absence (?:was |were |is |be |has been )?granted|granted leave of absence|"
                      r"was granted leave|leave of absence.{0,25}granted to", I)


def leave_granted(text: str) -> bool:
    for m in LEAVE_RE.finditer(text):
        before = text[max(0, m.start() - 14):m.start()].lower().rstrip()
        if re.search(r"\b(no|not|never|without)$", before) or "not granted" in m.group(0).lower():
            continue
        return True
    return False


def _forms_for(heading: str):
    forms: list[str] = []
    why: list[str] = []
    for name, rx in NAMED_FORMS:
        if rx.search(heading) and name not in forms:
            # MGT-7 would also match inside "MGT-7A"; the (?!A) guard handles it
            forms.append(name)
            why.append(f"{name} named in the heading")
    low = heading.lower()
    for rx, rule_forms, reason in FORM_RULES:
        if rx.search(low):
            added = [f for f in rule_forms if f not in forms]
            if added:
                forms += added
                why.append(reason)
    return forms, why


def _docs_for(heading: str, body: str):
    docs: list[str] = []
    why: list[str] = []
    low = heading.lower()
    for rx, rule_docs, reason in DOC_RULES:
        if rx.search(low):
            added = [d for d in rule_docs if d not in docs]
            if added:
                docs += added
                why.append(reason)
    if leave_granted(heading + " " + body) and "Leave request from the director" not in docs:
        docs.append("Leave request from the director")
        why.append("Leave of absence granted")
    return docs, why


# ---------------------------------------------------------------- particulars

_TITLE = r"(?:mr|ms|mrs|dr|shri|smt|miss)"
_NAMEPART = r"[A-Z][A-Za-z.'-]*"


def _clean_name(n: str) -> str:
    n = re.sub(r"\([^)]*\)", "", n)
    n = re.sub(r"\b(?:chairman|chairperson|director|managing director|whole[- ]time director|company secretary|"
               r"cfo|ceo|via vc|independent)\b.*$", "", n, flags=I)
    n = re.sub(r"^\s*" + _TITLE + r"\.?\s*", "", n, flags=I)
    return re.sub(r"\s+", " ", n).strip(" ,.;:-–")


def _norm_time(tok: str, ampm: str | None) -> str:
    tok = tok.replace(".", ":")
    h, m = tok.split(":")
    s = f"{int(h)}:{m}"
    if ampm:
        s += " " + ampm.replace(".", "").replace(" ", "").upper()
    return s


def _time_after(label: re.Pattern, text: str) -> str | None:
    m = label.search(text)
    if not m:
        return None
    t = re.search(r"(\d{1,2}[:.]\d{2})\s*([ap]\.?\s?m\.?)?", text[m.end():m.end() + 40], I)
    return _norm_time(t[1], t[2]) if t else None


def _names_under(lines: list[str], label: re.Pattern) -> str | None:
    for i, ln in enumerate(lines):
        if label.match(ln.strip()):
            names = []
            inline = re.sub(label, "", ln.strip(), count=1).lstrip(" :.-")
            cand = [inline] if inline and re.match(_TITLE + r"\b", inline, I) else []
            j = i + 1
            while j < len(lines) and re.match(_TITLE + r"\b", lines[j].strip(), I):
                cand.append(lines[j].strip())
                j += 1
            for c in cand:
                n = _clean_name(c)
                if n:
                    names.append(n)
            if names:
                return ", ".join(names)
    return None


def _particulars(lines: list[str], meeting_date: str | None) -> dict:
    text = " ".join(lines)
    out = {k: None for k in ("meeting_time", "chairman", "directors_present", "invitees_present",
                             "leave_of_absence", "notice_date", "signing_date", "signing_place")}
    a = _time_after(re.compile(r"meeting\s+commenced\s*[:\-]|\bcommenced\s+at\b", I), text)
    b = _time_after(re.compile(r"meeting\s+conclu\w*\s*[:\-]|\bconclu\w*\s+at\b", I), text)
    out["meeting_time"] = f"{a} to {b}" if a and b else (a or b)

    nm = rf"(?i:{_TITLE})\.?\s+{_NAMEPART}(?:\s+{_NAMEPART}){{0,3}}"
    m = re.search(rf"((?i:{_TITLE})\.?\s+{_NAMEPART}(?:\s+{_NAMEPART}){{0,3}})\s+(?i:(?:was|were|is|be|been)?\s*"
                  rf"(?:elected|appointed|chosen|nominated|acted))\b.{{0,30}}?(?i:chair)", text)
    if not m:
        m = re.search(rf"({nm})\s+(?i:took|occupied|chaired)\b.{{0,12}}?(?i:chair)", text)
    if m:
        out["chairman"] = _clean_name(m[1])

    out["directors_present"] = _names_under(lines, re.compile(r"(?:directors\s+|physically\s+)?present\b[\s:.]*", I))
    out["invitees_present"] = _names_under(lines, re.compile(r"(?:in attendance|invitees?)\b[\s:.]*", I))

    if leave_granted(text):
        g = re.search(rf"(?i:leave of absence)[^.]{{0,40}}?(?i:granted to)\s+({nm})", text) or \
            re.search(rf"(?i:granted leave of absence to)\s+({nm})", text)
        out["leave_of_absence"] = _clean_name(g[1]) if g else "Granted"
    else:
        out["leave_of_absence"] = "None"

    n = re.search(r"notice[^.\n]{0,50}?dated\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", text, I)
    if n:
        d = re.split(r"[./-]", n[1])
        out["notice_date"] = _iso(int(d[0]), int(d[1]), int(d[2]))

    sd = sp = None
    for ln in lines:
        m1 = re.search(r"\bdate\s*[:\-]\s*(.+)", ln, I)
        if m1:
            d = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", m1[1].strip())
            sd = _iso(int(d[1]), int(d[2]), int(d[3])) if d else sd
        m2 = re.search(r"\bplace\s*[:\-]\s*([A-Za-z][A-Za-z .,&-]*?)(?:\s{2,}|$)", ln, I)
        if m2:
            sp = m2[1].strip(" .,")
    out["signing_date"] = None if sd == meeting_date else sd
    out["signing_place"] = sp or None
    return out


# ---------------------------------------------------------------- public entry

def parse_minutes(filename: str, raw: bytes) -> dict:
    lines = extract_lines(filename, raw)
    meeting_date = _date_from_filename(filename) or _date_from_body(lines)

    cands = _candidates(lines)
    agenda, skipped, seen = [], [], set()
    for k, (title, idx, _src) in enumerate(cands):
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 4 or SKIP_HEADING.search(title) or CLOCK.search(title) or ADDRESS.search(title):
            skipped.append(title)
            continue
        key = re.sub(r"\W+", "", title.lower())[:60]
        if key in seen:
            continue
        seen.add(key)
        end = cands[k + 1][1] if k + 1 < len(cands) else len(lines)
        body = " ".join(lines[idx + 1:end])
        forms, fwhy = _forms_for(title)
        docs, dwhy = _docs_for(title, body)
        agenda.append({"text": display_title(title), "reg30": "NA", "forms": forms, "docs": docs,
                       "_why": fwhy + dwhy})

    roc, seen_f = [], set()
    for it in agenda:
        for f in it["forms"]:
            if f not in seen_f:
                seen_f.add(f)
                roc.append({"form": f, "srn": ""})
    mapping = [{"agenda": it["text"], "forms": it["forms"], "docs": it["docs"], "why": it.pop("_why")}
               for it in agenda]
    # lines that are structural (attendance, clock, address) are reported so the reviewer can see what was dropped
    for ln in lines:
        if (SKIP_HEADING.search(ln) or CLOCK.search(ln) or ADDRESS.search(ln)) and ln not in skipped:
            skipped.append(ln)
    return {"meeting_date": meeting_date, "agenda": agenda, "roc_forms": roc, "mapping": mapping,
            "particulars": _particulars(lines, meeting_date), "skipped": skipped, "line_count": len(lines)}
