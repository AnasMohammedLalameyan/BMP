"""Parser tests - pure unit tests, no database."""
import io
import zipfile
from xml.sax.saxutils import escape

import pytest

from app.minutes_extract import ScannedPdfError, parse_minutes


def docx(lines):
    paras = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(l)}</w:t></w:r></w:p>" for l in lines)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="x"><w:body>{paras}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def agenda_texts(res):
    return [a["text"] for a in res["agenda"]]


HOUSE = [
    "MINUTES OF THE MEETING OF THE BOARD OF DIRECTORS",
    "Held on 15.04.2025 at 11:00 A.M. at the Board Room, 4th Floor, Mumbai 400001",
    "PRESENT:",
    "Mr. Arjun Kapoor",
    "Ms. Sunita Rao",
    "IN ATTENDANCE:",
    "Mr. Vikram Shah",
    "APPOINTMENT OF CHAIRPERSON",
    "TO CONSIDER AND APPROVE THE FINANCIAL STATEMENTS FOR",
    "THE YEAR ENDED 31ST MARCH 2025",
    "TO NOTE DISCLOSURE OF INTEREST BY DIRECTORS",
    "The meeting commenced at 11:00 a.m. and concluded at 12:30 p.m.",
]


def test_caps_house_format_detects_items_and_skips_structure():
    res = parse_minutes("minutes.docx", docx(HOUSE))
    texts = agenda_texts(res)
    assert any("Financial Statements" in t and "Year Ended" in t for t in texts)   # wrapped heading stitched
    assert any("Disclosure Of Interest" in t for t in texts)
    assert not any("Present" == t for t in texts)
    skipped = " | ".join(res["skipped"])
    assert "PRESENT" in skipped and "Board Room" in skipped and "11:00" in skipped
    fin = next(a for a in res["agenda"] if "Financial" in a["text"])
    assert "AOC-4" in fin["forms"] and fin["reg30"] == "NA"
    dis = next(a for a in res["agenda"] if "Disclosure" in a["text"])
    assert "Form DIR-8" in dis["docs"] and "DIR-8" not in dis["forms"] and "MBP-1" not in dis["forms"]
    assert res["particulars"]["meeting_time"] == "11:00 AM to 12:30 PM"
    assert res["particulars"]["directors_present"] == "Arjun Kapoor, Sunita Rao"


def test_numbered_document_ignores_wrapped_caps_lines():
    lines = ["1. To approve the minutes of the previous meeting", "2. To consider the borrowing limits",
             "WORKING CAPITAL FACILITY", "3. To authorise the opening of a bank account", "ANY OTHER BUSINESS"]
    res = parse_minutes("m.docx", docx(lines))
    assert len(res["agenda"]) == 3
    assert not any(t.lower().startswith("working capital") for t in agenda_texts(res))


def test_wrapped_heading_ending_in_and_or_for_is_stitched():
    res = parse_minutes("m.docx", docx(["TO CONSIDER AND", "APPROVE THE ANNUAL RETURN"]))
    assert len(res["agenda"]) == 1 and "Approve The Annual Return" in res["agenda"][0]["text"]
    res = parse_minutes("m.docx", docx(["TO APPROVE THE REQUEST FOR", "ISSUE OF SHARES"]))
    assert len(res["agenda"]) == 1


def test_leave_of_absence_negation_and_affirmative():
    no = parse_minutes("m.docx", docx(["1. To grant leave of absence, if any", "No leave of absence was granted."]))
    assert "Leave request from the director" not in no["agenda"][0]["docs"]
    assert no["particulars"]["leave_of_absence"] == "None"
    yes = parse_minutes("m.docx", docx(["1. To grant leave of absence, if any",
                                        "Leave of absence was granted to Mr. Ravi Menon."]))
    assert "Leave request from the director" in yes["agenda"][0]["docs"]
    assert yes["particulars"]["leave_of_absence"] == "Ravi Menon"


def test_filename_date_beats_body_date():
    lines = ["Held on 01.01.2025 the previous meeting", "1. To note the minutes"]
    assert parse_minutes("BM_15.04.2025.docx", docx(lines))["meeting_date"] == "2025-04-15"
    assert parse_minutes("minutes.docx", docx(lines))["meeting_date"] == "2025-01-01"


def test_signing_date_equal_to_meeting_date_is_dropped():
    base = ["The meeting was held on 15.04.2025", "1. To note the minutes"]
    same = parse_minutes("m.docx", docx(base + ["DATE: 15.04.2025", "PLACE: Mumbai"]))
    assert same["particulars"]["signing_date"] is None and same["particulars"]["signing_place"] == "Mumbai"
    later = parse_minutes("m.docx", docx(base + ["DATE: 28.04.2025", "PLACE: Mumbai"]))
    assert later["particulars"]["signing_date"] == "2025-04-28"


def test_registered_office_between_states():
    res = parse_minutes("m.docx", docx(["1. To approve shifting of registered office from Maharashtra to Karnataka"
                                        " - shift registered office to the state of Karnataka"]))
    assert res["agenda"][0]["forms"][:4] == ["MGT-14", "INC-23", "INC-28", "INC-22"]


def test_named_form_comes_first():
    res = parse_minutes("m.docx", docx(["1. To approve the filing of Form DPT-3 and the annual return"]))
    forms = res["agenda"][0]["forms"]
    assert forms[0] == "DPT-3" and "MGT-7" in forms
    assert [f["form"] for f in res["roc_forms"]] == forms


def test_unsupported_and_scanned():
    with pytest.raises(ValueError):
        parse_minutes("notes.txt", b"hello")
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    d = fitz.open()
    d.new_page()
    with pytest.raises(ScannedPdfError):
        parse_minutes("scan.pdf", d.tobytes())


def test_text_pdf_is_read():
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    d = fitz.open()
    p = d.new_page()
    p.insert_text((50, 80), "1. To approve the appointment of the statutory auditor of the company", fontsize=9)
    res = parse_minutes("m.pdf", d.tobytes())
    assert res["agenda"] and "ADT-1" in res["agenda"][0]["forms"]
