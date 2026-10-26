# BMP Compliance Platform

The system of record (PostgreSQL, Phase 1) with its web application (FastAPI + the approved dashboard UI).

| What | Where |
|---|---|
| Database structure, seed data, tests | `db/`, `tests/` (unchanged Phase 1 database) |
| Web application (API + UI) | `app/` |
| Set-up, run and demo, step by step | **`BMP_UI_Backend_Implementation_Guide.md`** |
| What was built, tested, fixed, and not done | `BMP_UI_Backend_Implementation_Log.md` |
| Technical guide: commands, structure, back end, front end, pipelines, core logic, Postman | **`BMP_Project_Technical_Guide.pdf`** |
| Postman collection + environment (tests every API) | `docs/postman/` |
| Database explanation | `BMP_Phase1_Database_Guide.md`, `docs/ERD.md`, `docs/DATA_DICTIONARY.md` |

## Quick start (Windows PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then edit the passwords in .env
python scripts/setup_db.py --seed                 # creates and fills the database
python scripts/manage_users.py init-demo          # sets a password for the three demo users
python scripts/run_server.py                      # open http://127.0.0.1:8000
python -m pytest                                  # run all tests
BMP_UI_TESTS=1 python -m pytest tests/ui           # optional browser tests (needs: pip install playwright, and Chrome installed)
```

Demo users: `admin@bmpco.in` (all five companies), `manager@bmpco.in` (three companies, can edit),
`client@nexatech.co.in` (Nexatech only, read-only).

## AI assistant in the Activities Dashboard (optional, off by default)

The Activities Dashboard (meeting registers) can use a Groq-hosted model to **suggest and draft**. It never writes company data:
anything it proposes lands in the open form for a person to review, and saving or sending stays with the normal Save and an
explicit approval click.

| Where | What it does |
|---|---|
| Add / edit meeting | **Describe it instead**: a sentence fills the form. **Suggest from document**: reads a stored minutes or notice and suggests the details, each with the exact words and page it came from |
| Meeting card | **Draft notice**: notice text from the meeting's recorded details, recipients from the database, a short covering paragraph from the model; sent only after "Approve and send" |
| Register | **Ask**: an answer with citations from the company's documents and the statute library |

Settings (all in `.env`, see `.env.example`; the app runs normally with `AI_ENABLED=false`):

| Key | Meaning |
|---|---|
| `AI_ENABLED` | `true` switches the assistant on (needs `GROQ_API_KEY`) |
| `GROQ_API_KEY` | your Groq key. Never commit it |
| `AI_MODEL_EXTRACT` / `AI_MODEL_CHAT` / `AI_MODEL_FAST` | model ids. Check Groq's current model list and limits |
| `AI_DATA_MODE` | `dummy` (default) or `real`. `real` stays blocked until `AI_ZDR_CONFIRMED` and `AI_OUTSIDE_INDIA_APPROVED` are both `true` |
| `AI_SMTP_*`, `AI_SMTP_SANDBOX` | mail for notices. With `AI_SMTP_SANDBOX=true` (default, and always in dummy mode) mail goes only to a local test server: `python -m aiosmtpd -n -l localhost:1025` |
| `AI_EMBEDDING_MODEL`, `AI_INDEX_DIR`, `AI_LIBRARY_DIR` | local search index for **Ask**; put statute text as `.txt` files in the library folder |

PAN, DIN, phone numbers and email addresses are masked before any text goes to the model; Aadhaar numbers are removed and never
sent or stored. Calls are logged without any document text. Use dummy data only until the Zero Data Retention, outside-India and
email-system questions are answered. Tests: `pytest tests/ai tests/api/test_ai_api.py` (a fake model, no network).
