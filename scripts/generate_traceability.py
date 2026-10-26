"""
generate_traceability.py — Reads the master checklist Excel file and generates
docs/FIELD_TRACEABILITY.md with 100% of data sheet rows mapped to database objects.
"""

import openpyxl
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
XLSX_PATH = BASE_DIR / "BMP_Master Checklist_Dashboard Requirements.xlsx"
OUTPUT_MD = BASE_DIR / "docs" / "FIELD_TRACEABILITY.md"

# Mapping dictionary keyed by (sheet_name, row_num, field_name_prefix)
# Format: (mapped_to, stored_or_derived, notes)
MAPPINGS = {
    # -------------------------------------------------------------
    # Company Details
    # -------------------------------------------------------------
    ("Company Details", 1): ("core.company.name", "Stored", "Legal name of company per Certificate of Incorporation"),
    ("Company Details", 2): ("core.company.cin", "Stored", "21-character Corporate Identification Number (unique constraint)"),
    ("Company Details", 3): ("core.company.date_of_incorporation", "Stored", "Statutory incorporation date per COI"),
    ("Company Details", 4): ("core.company.pan", "Stored", "10-character Permanent Account Number"),
    ("Company Details", 5): ("core.company.category_id", "Stored", "FK to core.lookup_value (COMPANY_CATEGORY: Public / Private)"),
    ("Company Details", 6): ("core.company.subcategory_id", "Stored", "FK to core.lookup_value (COMPANY_SUBCATEGORY: Small / Other)"),
    ("Company Details", 7): ("core.company.category_id", "Stored", "Class of company represented by category/subcategory lookups"),
    ("Company Details", 8): ("core.company.registered_address", "Stored", "Full registered office address per MCA records"),
    ("Company Details", 9): ("core.company.correspondence_address", "Stored", "Corporate/correspondence office address if different"),
    ("Company Details", 10): ("core.company.phone", "Stored", "Primary contact telephone number"),
    ("Company Details", 11): ("core.company.fax", "Stored", "Fax number (optional)"),
    ("Company Details", 12): ("core.company.email", "Stored", "Official company email address"),
    ("Company Details", 13): ("core.company.website", "Stored", "Official company website URL"),
    ("Company Details", 14): ("core.company_rta", "Stored", "Separate table core.company_rta tracking RTA name, address, contact, and period"),
    ("Company Details", 15): ("core.company.is_listed", "Stored", "Boolean flag; drives multiple applicability rules (audit committee, etc.)"),
    ("Company Details", 16): ("core.company.stock_exchange", "Stored", "Name of stock exchanges where listed (BSE, NSE)"),
    ("Company Details", 17): ("core.company.market_value_rank", "Stored", "Market cap ranking among top 500/1000/2000 per SEBI LODR"),
    ("Company Details", 18): ("core.company_business_activity", "Stored", "Table core.company_business_activity with NIC code, description, and % turnover"),
    ("Company Details", 19): ("core.company_relationship", "Stored", "Table core.company_relationship with relationship type lookup, related name/CIN, stake %, period"),
    ("Company Details", 20): ("core.company_financials.turnover", "Stored", "Stored per financial year in core.company_financials"),
    ("Company Details", 21): ("core.company_financials.net_worth", "Stored", "Stored per financial year in core.company_financials"),
    ("Company Details", 22): ("core.company_financials.net_profit", "Stored", "Stored per financial year in core.company_financials"),
    ("Company Details", 23): ("core.company_financials.free_reserves", "Stored", "Stored per financial year in core.company_financials"),
    ("Company Details", 24): ("core.company_financials.securities_premium", "Stored", "Stored per financial year in core.company_financials"),
    ("Company Details", 25): ("core.company_financials.borrowings_banks_fis", "Stored", "Stored per financial year; drives internal audit applicability"),
    ("Company Details", 26): ("core.company_financials.public_deposits", "Stored", "Stored per financial year; drives committee rules"),
    ("Company Details", 27): ("core.company_financials.debentures_outstanding", "Stored", "Stored per financial year in core.company_financials"),
    ("Company Details", 28): ("core.company_financials.csr_spend_required", "Stored", "CSR obligation per FY; triggers CSR committee rule"),
    ("Company Details", 29): ("core.company_financials.s185_limit", "Stored", "Limits under Section 185 for loans to directors"),
    ("Company Details", 30): ("core.company_financials.s186_limit", "Stored", "Limits under Section 186 for inter-corporate loans/investments"),
    ("Company Details", 31): ("core.v_company_shareholder_counts / core.company_financials.total_security_holders", "Derived / Stored", "Count derived from active shareholdings; stored in financials snapshot for listed historical filing"),

    # -------------------------------------------------------------
    # Directors & Key Managers
    # -------------------------------------------------------------
    ("Directors & Key Managers", 1): ("core.director.full_name", "Stored", "Master record for individual director/KMP"),
    ("Directors & Key Managers", 2): ("core.director.din", "Stored", "8-digit unique Director Identification Number"),
    ("Directors & Key Managers", 3): ("core.director.pan", "Stored", "10-character PAN of the director/officer"),
    ("Directors & Key Managers", 4): ("core.director.relative_name", "Stored", "Father/Mother/Spouse name per DIN records"),
    ("Directors & Key Managers", 5): ("core.director.aadhaar_encrypted / aadhaar_last4", "Stored (Encrypted)", "Encrypted with pgcrypto or last 4 digits only; no plaintext secrets per decision 10"),
    ("Directors & Key Managers", 6): ("core.director.date_of_birth", "Stored", "Date of birth of the director"),
    ("Directors & Key Managers", 7): ("core.v_director_age.age_years", "Derived", "Calculated on the fly from date_of_birth via core.v_director_age; not stored per decision 7"),
    ("Directors & Key Managers", 8): ("core.director.gender", "Stored", "Gender (Male/Female/Other); used for woman director rule evaluation"),
    ("Directors & Key Managers", 9): ("core.director.nationality", "Stored", "Nationality of the director"),
    ("Directors & Key Managers", 10): ("core.director.address", "Stored", "Residential address per KYC"),
    ("Directors & Key Managers", 11): ("core.director.email", "Stored", "Personal/official email address for notices"),
    ("Directors & Key Managers", 12): ("core.director.phone", "Stored", "Contact mobile/telephone number"),
    ("Directors & Key Managers", 13): ("core.director.occupation", "Stored", "Professional occupation"),
    ("Directors & Key Managers", 14): ("core.director_residency.resident_over_182_days", "Stored", "Stored per financial year in core.director_residency (>182 days rule)"),
    ("Directors & Key Managers", 15): ("core.directorship_role.designation_id", "Stored", "Tracked over time in core.directorship_role referencing core.lookup_value (DESIGNATION)"),
    ("Directors & Key Managers", 16): ("core.directorship.director_category_id", "Stored", "Promoter / Professional / Independent / Nominee lookup"),
    ("Directors & Key Managers", 17): ("core.directorship.start_date", "Stored", "Date of appointment for this specific directorship stint"),
    ("Directors & Key Managers", 18): ("core.directorship.end_date", "Stored", "Date of cessation/resignation; nullable for active stints"),
    ("Directors & Key Managers", 19): ("core.directorship.cessation_reason", "Stored", "Reason for vacation/resignation/disqualification per Sec 167/168"),
    ("Directors & Key Managers", 20): ("core.directorship.is_whole_time", "Stored", "Boolean flag for Whole-Time Director (WTD)"),
    ("Directors & Key Managers", 21): ("core.directorship.is_independent", "Stored", "Boolean flag for Independent Director under Sec 149(6)"),
    ("Directors & Key Managers", 22): ("core.v_independent_director_years.years_served", "Derived", "Calculated by view core.v_independent_director_years from terms; not manually stored"),
    ("Directors & Key Managers", 23): ("core.independent_director_term", "Stored", "Table core.independent_director_term tracking term 1 & 2 start and end dates"),
    ("Directors & Key Managers", 24): ("core.directorship.is_nominee", "Stored", "Boolean flag for Nominee Director"),
    ("Directors & Key Managers", 25): ("core.directorship.is_additional", "Stored", "Boolean flag for Additional Director appointed under Sec 161(1)"),
    ("Directors & Key Managers", 26): ("core.directorship.is_alternate", "Stored", "Boolean flag for Alternate Director appointed under Sec 161(2)"),
    ("Directors & Key Managers", 27): ("core.directorship.retires_by_rotation", "Stored", "Boolean flag for Sec 152(6) rotational retirement"),
    ("Directors & Key Managers", 28): ("core.directorship.is_kmp / core.directorship_role", "Stored", "Key Managerial Personnel flag and role assignment (CEO, CFO, CS)"),
    ("Directors & Key Managers", 29): ("core.directorship.is_signatory", "Stored", "Authorized signatory authorization flag"),
    ("Directors & Key Managers", 30): ("core.director.dsc_valid_until", "Stored", "Expiry date of Digital Signature Certificate"),
    ("Directors & Key Managers", 31): ("core.director_kyc", "Stored", "Table core.director_kyc tracking annual DIR-3 KYC filing, SRN, and date"),
    ("Directors & Key Managers", 32): ("core.director_other_directorship", "Stored", "Table core.director_other_directorship tracking other companies, DIN limits per Sec 165"),
    ("Directors & Key Managers", 33): ("core.director_declaration", "Stored", "Table core.director_declaration tracking MBP-1 interest disclosures and DIR-8 non-disqualification"),
    ("Directors & Key Managers", 34): ("core.directorship.shares_held", "Stored", "Number of qualification / equity shares held in the company"),
    ("Directors & Key Managers", 35): ("core.v_director_history / core.directorship", "Derived / Stored", "All stints preserved with exclusion constraint daterange; viewed via core.v_director_history"),
    ("Directors & Key Managers", 36): ("core.v_director_attendance_summary", "Derived", "Board meetings held vs attended calculated in core.v_director_attendance_summary"),

    # -------------------------------------------------------------
    # Shareholders
    # -------------------------------------------------------------
    ("Shareholders", 1): ("core.shareholder.name", "Stored", "Master record in core.shareholder"),
    ("Shareholders", 2): ("core.shareholding.number_of_shares", "Stored", "Stored per holding stint in core.shareholding"),
    ("Shareholders", 3): ("core.shareholding.face_value", "Stored", "Face value per share from core.share_class / core.shareholding"),
    ("Shareholders", 4): ("core.shareholding.number_of_shares * face_value", "Derived", "Calculated value; never manually typed"),
    ("Shareholders", 5): ("core.shareholding.folio_number", "Stored", "Folio number for physical holdings; unique with shareholder and class"),
    ("Shareholders", 6): ("core.shareholding.share_class_id", "Stored", "FK to core.share_class (Equity, Preference, etc.)"),
    ("Shareholders", 7): ("core.shareholder.category_id", "Stored", "FK to core.lookup_value (SHAREHOLDER_CATEGORY: Promoter, Public, FII, etc.)"),
    ("Shareholders", 8): ("core.v_shareholding_percent.holding_percent", "Derived", "Calculated on the fly in core.v_shareholding_percent; not stored per decision 7"),
    ("Shareholders", 9): ("core.shareholding.is_demat", "Stored", "Boolean flag: true for demat holdings, false for physical"),
    ("Shareholders", 10): ("core.shareholding.client_id / dp_id", "Stored", "Client ID and Depository Participant ID for demat holdings"),
    ("Shareholders", 11): ("core.shareholding.distinctive_from / distinctive_to", "Stored", "Distinctive number range of physical share certificates"),
    ("Shareholders", 12): ("core.shareholding.pledged_percent", "Stored", "Percentage of holding pledged/encumbered"),
    ("Shareholders", 13): ("core.shareholder.address", "Stored", "Registered address of the member"),
    ("Shareholders", 14): ("core.shareholder.pan", "Stored", "PAN of the shareholder"),
    ("Shareholders", 15): ("core.shareholder.email", "Stored", "Email address for notices and dividend payments"),
    ("Shareholders", 16): ("core.shareholding.valid_from / valid_to", "Stored", "Temporal history: changes close old row and create new row with dates"),

    # -------------------------------------------------------------
    # Committees
    # -------------------------------------------------------------
    ("Committees", 1): ("core.committee.name", "Stored", "Audit / NRC / SRC / CSR / Risk Management Committee"),
    ("Committees", 2): ("core.v_rule_committee / core.rule_evaluation", "Derived", "Calculated from core.rule_definition and financials; never hardcoded"),
    ("Committees", 3): ("core.committee.constituted_on", "Stored", "Date committee was constituted by Board resolution"),
    ("Committees", 4): ("core.committee_member.is_chairperson", "Stored", "Boolean flag in core.committee_member for the committee chairperson"),
    ("Committees", 5): ("core.committee_member.directorship_id", "Stored", "FK to core.directorship; individual members linked properly, not comma-separated text"),
    ("Committees", 6): ("core.committee.meeting_frequency", "Stored", "Statutory or charter meeting cadence (e.g. at least 4 times a year)"),
    ("Committees", 7): ("core.committee.dissolved_on", "Stored", "Date committee was dissolved or restructured if applicable"),
    ("Committees", 8): ("core.committee.description", "Stored", "Terms of reference / charter of the committee"),
    ("Committees", 9): ("core.v_committee_attendance_percent", "Derived", "Calculated attendance % per member in core.v_committee_attendance_percent"),
    ("Committees", 10): ("core.rule_evaluation", "Derived / Stored", "Applicability evaluations recorded in core.rule_evaluation per FY"),

    # -------------------------------------------------------------
    # Share Capital Summary
    # -------------------------------------------------------------
    ("Share Capital Summary", 1): ("core.share_class.class_id", "Stored", "FK to core.lookup_value (CLASS_OF_SHARES)"),
    ("Share Capital Summary", 2): ("core.capital_snapshot.authorised_shares / authorised_amount", "Stored", "Opening and closing authorised capital in core.capital_snapshot"),
    ("Share Capital Summary", 3): ("core.capital_snapshot.issued_shares / issued_amount", "Stored", "Opening and closing issued capital in core.capital_snapshot"),
    ("Share Capital Summary", 4): ("core.capital_snapshot.subscribed_shares / subscribed_amount", "Stored", "Opening and closing subscribed capital in core.capital_snapshot"),
    ("Share Capital Summary", 5): ("core.capital_snapshot.paid_up_shares / paid_up_amount", "Stored", "Opening and closing paid-up capital in core.capital_snapshot"),
    ("Share Capital Summary", 6): ("core.capital_event", "Stored", "Table core.capital_event tracking split, consolidation, increase, decrease with reason lookup"),
    ("Share Capital Summary", 7): ("core.capital_event.reason_id", "Stored", "FK to core.lookup_value (CAPITAL_INCREASE_REASON / CAPITAL_DECREASE_REASON)"),
    ("Share Capital Summary", 8): ("core.capital_event.event_date", "Stored", "Date of capital alteration / board/general meeting approval"),
    ("Share Capital Summary", 9): ("core.capital_snapshot.as_of_date", "Stored", "Snapshot date for financial year opening/closing reconciliation"),
    ("Share Capital Summary", 10): ("core.share_class.nominal_value", "Stored", "Nominal / face value per share in core.share_class"),
    ("Share Capital Summary", 11): ("core.share_class.debenture_type_id", "Stored", "FK to core.lookup_value (DEBENTURE_TYPE) for debenture classes"),
    ("Share Capital Summary", 12): ("core.share_class.description", "Stored", "Terms of preference / debenture rights"),

    # -------------------------------------------------------------
    # Share Allotments
    # -------------------------------------------------------------
    ("Share Allotments", 1): ("core.allotment.round_reference", "Stored", "Reference name (e.g. MOA subscription, Series A, Rights Issue 1)"),
    ("Share Allotments", 2): ("core.allotment.shareholder_id", "Stored", "FK to core.shareholder master (allottee name)"),
    ("Share Allotments", 3): ("core.allotment.number_of_shares", "Stored", "Quantity of shares allotted"),
    ("Share Allotments", 4): ("core.allotment.allotment_date", "Stored", "Date of board resolution allotting shares"),
    ("Share Allotments", 5): ("core.allotment.face_value / premium_per_share / issue_price", "Stored", "Pricing breakdown; issue_price = face_value + premium"),
    ("Share Allotments", 6): ("core.allotment.face_value_amount / premium_amount / total_amount", "Stored", "Amounts calculated and stored for PAS-3 filing reconciliation"),
    ("Share Allotments", 7): ("core.allotment.distinctive_numbers", "Stored", "Distinctive number range allotted"),
    ("Share Allotments", 8): ("core.allotment.client_dp_id", "Stored", "Client/DP ID if credited in demat mode"),
    ("Share Allotments", 9): ("core.allotment.certificate_number", "Stored", "Share certificate number if issued in physical form"),
    ("Share Allotments", 10): ("core.allotment.stamp_duty_payable", "Stored", "Stamp duty liability assessed"),
    ("Share Allotments", 11): ("core.allotment.stamp_duty_paid", "Stored", "Stamp duty amount paid"),
    ("Share Allotments", 12): ("core.allotment.stamp_duty_paid_on", "Stored", "Date stamp duty was remitted to state revenue authority"),
    ("Share Allotments", 13): ("core.allotment.board_meeting_id", "Stored", "FK to core.meeting linking the board meeting where allotment occurred"),
    ("Share Allotments", 14): ("core.allotment.government_filing_id", "Stored", "FK to core.government_filing linking Form PAS-3"),
    ("Share Allotments", 15): ("core.allotment.share_class_id", "Stored", "FK to core.share_class"),

    # -------------------------------------------------------------
    # Share Transfers
    # -------------------------------------------------------------
    ("Share Transfers", 1): ("core.share_transfer.transferor_id", "Stored", "FK to core.shareholder (transferor)"),
    ("Share Transfers", 2): ("core.share_transfer.transferee_id", "Stored", "FK to core.shareholder (transferee)"),
    ("Share Transfers", 3): ("core.share_transfer.share_class_id", "Stored", "FK to core.share_class"),
    ("Share Transfers", 4): ("core.share_transfer.number_of_shares", "Stored", "Number of shares transferred"),
    ("Share Transfers", 5): ("core.share_transfer.transfer_date", "Stored", "Date of Board approval for registration of transfer"),
    ("Share Transfers", 6): ("core.share_transfer.board_meeting_id", "Stored", "FK to core.meeting where transfer was approved"),
    ("Share Transfers", 7): ("core.share_transfer.face_value", "Stored", "Face value of shares transferred"),
    ("Share Transfers", 8): ("core.share_transfer.consideration", "Stored", "Total purchase consideration paid for transfer"),
    ("Share Transfers", 9): ("core.share_transfer.stamp_duty_paid", "Stored", "Stamp duty paid via stamp stamps / e-stamping"),
    ("Share Transfers", 10): ("core.share_transfer.distinctive_numbers", "Stored", "Distinctive number ranges of transferred shares"),
    ("Share Transfers", 11): ("core.share_transfer.client_dp_id", "Stored", "Demat execution reference / DIS number"),
    ("Share Transfers", 12): ("core.share_transfer.transferee_folio", "Stored", "New folio number assigned to transferee"),
    ("Share Transfers", 13): ("core.share_transfer.sh4_available", "Stored", "Boolean flag confirming Form SH-4 transfer deed is on file"),
    ("Share Transfers", 14): ("core.share_transfer.involves_non_resident", "Stored", "Boolean flag: triggers FC-TRS compliance check if non-resident involved"),
    ("Share Transfers", 15): ("core.foreign_investment.share_transfer_id", "Stored", "FK link to core.foreign_investment for FC-TRS filings"),
    ("Share Transfers", 16): ("core.share_transfer.notes", "Stored", "Operational transfer notes and verification comments"),

    # -------------------------------------------------------------
    # Foreign Investment — Shares Issued (FC-GPR)
    # -------------------------------------------------------------
    ("Foreign Investment — Shares Iss", 1): ("core.foreign_investment.foreign_amount", "Stored", "Foreign remittance amount in foreign currency"),
    ("Foreign Investment — Shares Iss", 2): ("core.foreign_investment.foreign_currency", "Stored", "Currency code (USD, EUR, GBP, SGD)"),
    ("Foreign Investment — Shares Iss", 3): ("core.foreign_investment.conversion_rate", "Stored", "Exchange conversion rate applied by AD bank"),
    ("Foreign Investment — Shares Iss", 4): ("core.foreign_investment.amount_inr", "Stored", "Equivalent INR amount received"),
    ("Foreign Investment — Shares Iss", 5): ("core.foreign_investment.firc_number", "Stored", "Foreign Inward Remittance Certificate reference number"),
    ("Foreign Investment — Shares Iss", 6): ("core.foreign_investment.allotment_id", "Stored", "FK to core.allotment; links allottee and share allotment"),
    ("Foreign Investment — Shares Iss", 7): ("core.foreign_investment.ad_bank", "Stored", "Name and branch of Authorized Dealer Category-I bank"),
    ("Foreign Investment — Shares Iss", 8): ("core.foreign_investment.board_approval_date", "Stored", "Date of Board approval for foreign allotment"),
    ("Foreign Investment — Shares Iss", 9): ("core.foreign_investment.funds_received_date", "Stored", "Date foreign funds credited to company account"),
    ("Foreign Investment — Shares Iss", 10): ("core.foreign_investment.filing_due_date", "Stored", "Statutory due date (30 days from allotment on FIRMS portal)"),
    ("Foreign Investment — Shares Iss", 11): ("core.foreign_investment.filing_date", "Stored", "Date Form FC-GPR submitted to RBI"),
    ("Foreign Investment — Shares Iss", 12): ("core.foreign_investment.approval_date", "Stored", "Date RBI approved the FC-GPR filing"),
    ("Foreign Investment — Shares Iss", 13): ("core.foreign_investment.status_id", "Stored", "FK to core.lookup_value (FILING_STATUS: Pending / Filed / Approved)"),
    ("Foreign Investment — Shares Iss", 14): ("core.foreign_investment.type_id", "Stored", "FK to core.lookup_value (FOREIGN_INVESTMENT_TYPE: FC-GPR)"),
    ("Foreign Investment — Shares Iss", 15): ("core.evidence_link", "Stored", "FIRC and KYC documents linked via core.evidence_link"),

    # -------------------------------------------------------------
    # Foreign Investment — Shares Transferred (FC-TRS)
    # -------------------------------------------------------------
    ("Foreign Investment — Shares Tra", 1): ("core.foreign_investment.foreign_amount", "Stored", "Consideration amount in foreign currency"),
    ("Foreign Investment — Shares Tra", 2): ("core.foreign_investment.foreign_currency", "Stored", "Currency code (USD, EUR, etc.)"),
    ("Foreign Investment — Shares Tra", 3): ("core.foreign_investment.conversion_rate", "Stored", "Exchange rate used for transfer consideration"),
    ("Foreign Investment — Shares Tra", 4): ("core.foreign_investment.amount_inr", "Stored", "Amount in INR"),
    ("Foreign Investment — Shares Tra", 5): ("core.foreign_investment.firc_number", "Stored", "Inward / outward remittance certificate reference"),
    ("Foreign Investment — Shares Tra", 6): ("core.foreign_investment.share_transfer_id", "Stored", "FK to core.share_transfer linking transferor and transferee"),
    ("Foreign Investment — Shares Tra", 7): ("core.foreign_investment.ad_bank", "Stored", "AD Bank processing the transfer reporting"),
    ("Foreign Investment — Shares Tra", 8): ("core.foreign_investment.board_approval_date", "Stored", "Date transfer noted/approved by Board"),
    ("Foreign Investment — Shares Tra", 9): ("core.foreign_investment.funds_received_date", "Stored", "Date consideration was received or remitted"),
    ("Foreign Investment — Shares Tra", 10): ("core.foreign_investment.filing_due_date", "Stored", "Due date for filing Form FC-TRS (60 days from transfer)"),
    ("Foreign Investment — Shares Tra", 11): ("core.foreign_investment.filing_date", "Stored", "Actual filing date on RBI FIRMS portal"),
    ("Foreign Investment — Shares Tra", 12): ("core.foreign_investment.approval_date", "Stored", "Date RBI / AD bank acknowledgement received"),
    ("Foreign Investment — Shares Tra", 13): ("core.foreign_investment.status_id", "Stored", "FK to core.lookup_value (FILING_STATUS)"),
    ("Foreign Investment — Shares Tra", 14): ("core.foreign_investment.type_id", "Stored", "FK to core.lookup_value (FOREIGN_INVESTMENT_TYPE: FC-TRS)"),
    ("Foreign Investment — Shares Tra", 15): ("core.evidence_link", "Stored", "SH-4, valuation certificate, and FIRC linked via core.evidence_link"),
    ("Foreign Investment — Shares Tra", 16): ("core.foreign_investment.notes", "Stored", "Pricing guideline compliance notes (FDI non-resident pricing)"),

    # -------------------------------------------------------------
    # Auditors
    # -------------------------------------------------------------
    ("Auditors", 1): ("core.auditor.name", "Stored", "Name of audit firm or individual auditor"),
    ("Auditors", 2): ("core.auditor.type_id", "Stored", "FK to core.lookup_value (AUDITOR_TYPE: Statutory, Internal, Cost, Secretarial)"),
    ("Auditors", 3): ("core.auditor.board_recommendation_date", "Stored", "Date of Board recommendation to members"),
    ("Auditors", 4): ("core.auditor.general_meeting_appointment_date", "Stored", "Date of appointment in AGM/EGM"),
    ("Auditors", 5): ("core.auditor.period_from / period_to", "Stored", "Financial period appointed for (start and end dates)"),
    ("Auditors", 6): ("core.auditor.term_years", "Stored", "Tenure in years (e.g. 5-year term for statutory auditors under Sec 139)"),
    ("Auditors", 7): ("core.auditor.pan", "Stored", "PAN of the audit firm / auditor"),
    ("Auditors", 8): ("core.auditor.frn", "Stored", "Firm Registration Number (ICAI/ICSI/ICMAI)"),
    ("Auditors", 9): ("core.auditor.address", "Stored", "Registered address of audit firm"),
    ("Auditors", 10): ("core.auditor.email", "Stored", "Official communication email of the auditor"),
    ("Auditors", 11): ("core.auditor.board_meeting_id", "Stored", "FK to core.meeting linking recommending board meeting"),
    ("Auditors", 12): ("core.auditor.general_meeting_id", "Stored", "FK to core.meeting linking appointing AGM/EGM"),
    ("Auditors", 13): ("core.government_filing", "Stored", "Linked Form ADT-1 in core.government_filing"),
    ("Auditors", 14): ("core.evidence_link", "Stored", "Written consent, eligibility certificate under Sec 141 linked via evidence_link"),

    # -------------------------------------------------------------
    # Board Meetings
    # -------------------------------------------------------------
    ("Board Meetings", 1): ("core.meeting.meeting_number", "Stored", "Meeting serial identifier (e.g. BM/2024-25/01)"),
    ("Board Meetings", 2): ("core.meeting.meeting_date", "Stored", "Date meeting was held or scheduled"),
    ("Board Meetings", 3): ("core.meeting.start_time / end_time", "Stored", "Start and conclusion times"),
    ("Board Meetings", 4): ("core.meeting.venue", "Stored", "Meeting location address or electronic conferencing host"),
    ("Board Meetings", 5): ("core.meeting.venue_mode_id", "Stored", "FK to core.lookup_value (MEETING_VENUE_MODE: Physical, VC, Hybrid)"),
    ("Board Meetings", 6): ("core.meeting.chairperson_directorship_id", "Stored", "FK to core.directorship of the director chairing the meeting"),
    ("Board Meetings", 7): ("core.meeting_attendance", "Stored", "Junction table core.meeting_attendance recording director presence and mode"),
    ("Board Meetings", 8): ("core.meeting_agenda_item", "Stored", "Table core.meeting_agenda_item recording numbered agenda items and resolutions"),
    ("Board Meetings", 9): ("core.meeting.status", "Stored", "Status: planned / held / cancelled"),
    ("Board Meetings", 10): ("core.evidence_link", "Stored", "Notice, agenda notes, and signed minutes linked via core.evidence_link"),
    ("Board Meetings", 11): ("core.v_director_attendance_summary", "Derived", "Director attendance percentage calculated in core.v_director_attendance_summary"),
    ("Board Meetings", 12): ("core.meeting.financial_year", "Stored", "Financial year (e.g. 2024-25) with check constraint"),
    ("Board Meetings", 13): ("core.meeting.remarks", "Stored", "General remarks, leave of absence records"),

    # -------------------------------------------------------------
    # Circular Resolutions
    # -------------------------------------------------------------
    ("Circular Resolutions", 1): ("core.circular_resolution.reference", "Stored", "Resolution reference identifier"),
    ("Circular Resolutions", 2): ("core.circular_resolution.circulated_on", "Stored", "Date draft resolution circulated to directors"),
    ("Circular Resolutions", 3): ("core.circular_resolution.subject", "Stored", "Subject matter of the resolution"),
    ("Circular Resolutions", 4): ("core.circular_resolution.text", "Stored", "Full statutory text of the proposed resolution"),
    ("Circular Resolutions", 5): ("core.circular_resolution_response", "Stored", "Table core.circular_resolution_response recording approval/dissent and dates"),
    ("Circular Resolutions", 6): ("core.circular_resolution.passed_on", "Stored", "Date deemed passed when majority approval received"),
    ("Circular Resolutions", 7): ("core.circular_resolution.noted_in_meeting_id", "Stored", "FK to core.meeting where resolution was noted in subsequent BM per Sec 175(2)"),
    ("Circular Resolutions", 8): ("core.circular_resolution.is_approved", "Derived / Stored", "Determined from responses or recorded in passed_on date"),
    ("Circular Resolutions", 9): ("core.evidence_link", "Stored", "Circulation proof and signed assent forms linked via core.evidence_link"),
    ("Circular Resolutions", 10): ("core.circular_resolution.company_id", "Stored", "FK to core.company"),
    ("Circular Resolutions", 11): ("core.circular_resolution.notes", "Stored", "Explanatory notes and secretarial observations"),

    # -------------------------------------------------------------
    # General Meetings (AGM & EGM)
    # -------------------------------------------------------------
    ("General Meetings (AGM & EGM)", 1): ("core.meeting.meeting_type_id", "Stored", "FK to core.lookup_value (MEETING_TYPE: AGM / EGM)"),
    ("General Meetings (AGM & EGM)", 2): ("core.meeting.meeting_number", "Stored", "Meeting serial number or AGM designation (e.g. 15th AGM)"),
    ("General Meetings (AGM & EGM)", 3): ("core.meeting.meeting_date", "Stored", "Date of general meeting"),
    ("General Meetings (AGM & EGM)", 4): ("core.meeting.start_time / end_time", "Stored", "Start and end times of general meeting"),
    ("General Meetings (AGM & EGM)", 5): ("core.meeting.venue / venue_mode_id", "Stored", "Physical venue or VC/OAVM mode lookup"),
    ("General Meetings (AGM & EGM)", 6): ("core.meeting.due_date", "Stored", "Statutory due date for holding AGM (Sec 96: within 6 months of FY end)"),
    ("General Meetings (AGM & EGM)", 7): ("core.meeting.chairperson_directorship_id", "Stored", "FK to core.directorship for Chairperson of the meeting"),
    ("General Meetings (AGM & EGM)", 8): ("core.meeting.members_entitled", "Stored", "Total number of members entitled to attend and vote"),
    ("General Meetings (AGM & EGM)", 9): ("core.meeting.members_attended", "Stored", "Number of members present in person or through proxy/VC (quorum check)"),
    ("General Meetings (AGM & EGM)", 10): ("core.meeting_agenda_item", "Stored", "Ordinary and special business resolutions recorded in core.meeting_agenda_item"),
    ("General Meetings (AGM & EGM)", 11): ("core.meeting_attendance", "Stored", "Attendance records for directors, members, and auditors"),
    ("General Meetings (AGM & EGM)", 12): ("core.evidence_link", "Stored", "AGM notice, newspaper publication, and signed minutes linked via evidence_link"),
    ("General Meetings (AGM & EGM)", 13): ("core.government_filing", "Stored", "Form MGT-14 for special resolutions and Form MGT-7 linked in filings"),
    ("General Meetings (AGM & EGM)", 14): ("core.meeting.status", "Stored", "Status: planned / held / cancelled"),

    # -------------------------------------------------------------
    # Committee Meetings & Attendance
    # -------------------------------------------------------------
    ("Committee Meetings & Attendance", 1): ("core.meeting.committee_id", "Stored", "FK to core.committee (Audit, NRC, CSR, etc.)"),
    ("Committee Meetings & Attendance", 2): ("core.meeting.meeting_date", "Stored", "Date committee meeting was held"),
    ("Committee Meetings & Attendance", 3): ("core.meeting.start_time / venue", "Stored", "Time and venue of committee meeting"),
    ("Committee Meetings & Attendance", 4): ("core.meeting.meeting_number", "Stored", "Serial identifier (e.g. AC/2024-25/01)"),
    ("Committee Meetings & Attendance", 5): ("core.meeting_attendance", "Stored", "Director presence recorded in core.meeting_attendance with physical/VC mode"),
    ("Committee Meetings & Attendance", 6): ("core.v_committee_attendance_percent", "Derived", "Calculated on the fly in core.v_committee_attendance_percent"),
    ("Committee Meetings & Attendance", 7): ("core.meeting_agenda_item", "Stored", "Committee agenda items and recommendations to the Board"),
    ("Committee Meetings & Attendance", 8): ("core.meeting.chairperson_directorship_id", "Stored", "Chairperson presiding over the committee meeting"),
    ("Committee Meetings & Attendance", 9): ("core.meeting.status", "Stored", "Meeting status: planned / held / cancelled"),
    ("Committee Meetings & Attendance", 10): ("core.evidence_link", "Stored", "Committee agenda papers and minutes linked via core.evidence_link"),
    ("Committee Meetings & Attendance", 11): ("core.meeting.financial_year", "Stored", "Financial year for committee frequency validation"),
    ("Committee Meetings & Attendance", 12): ("core.meeting.remarks", "Stored", "Committee findings and special invitee attendance notes"),
    ("Committee Meetings & Attendance", 13): ("core.meeting_attendance.mode", "Stored", "Attendance mode (Physical, VC, Audio-Visual)"),

    # -------------------------------------------------------------
    # Loans & Deposits
    # -------------------------------------------------------------
    ("Loans & Deposits", 1): ("core.loan_deposit.financial_year", "Stored", "Financial year of the borrowing snapshot (e.g. 2024-25)"),
    ("Loans & Deposits", 2): ("core.loan_deposit.borrowing_type", "Stored", "Secured loans / Unsecured loans / Deposits / Public deposits"),
    ("Loans & Deposits", 3): ("core.loan_deposit.opening_principal", "Stored", "Principal amount outstanding at start of financial year"),
    ("Loans & Deposits", 4): ("core.loan_deposit.opening_interest_unpaid", "Stored", "Interest accrued and due but unpaid at start of year"),
    ("Loans & Deposits", 5): ("core.loan_deposit.opening_interest_accrued", "Stored", "Interest accrued but not due at start of year"),
    ("Loans & Deposits", 6): ("core.loan_deposit.added_principal", "Stored", "Fresh borrowings / deposits received during the year"),
    ("Loans & Deposits", 7): ("core.loan_deposit.reduced_principal", "Stored", "Principal repaid during the year"),
    ("Loans & Deposits", 8): ("core.loan_deposit.closing_principal", "Stored", "Principal outstanding at close of financial year"),
    ("Loans & Deposits", 9): ("core.loan_deposit.closing_interest_unpaid", "Stored", "Closing interest due and unpaid"),
    ("Loans & Deposits", 10): ("core.loan_deposit.closing_interest_accrued", "Stored", "Closing interest accrued but not due"),
    ("Loans & Deposits", 11): ("core.loan_deposit.company_id", "Stored", "FK to core.company; total borrowings summarized in views"),

    # -------------------------------------------------------------
    # Remuneration
    # -------------------------------------------------------------
    ("Remuneration", 1): ("core.remuneration.directorship_id / person_name", "Stored", "FK to core.directorship (nullable for non-director KMP) and name"),
    ("Remuneration", 2): ("core.remuneration.salary", "Stored", "Basic salary and fixed allowances"),
    ("Remuneration", 3): ("core.remuneration.perquisites", "Stored", "Value of taxable perquisites under Income Tax Act"),
    ("Remuneration", 4): ("core.remuneration.profits_in_lieu", "Stored", "Profits in lieu of salary"),
    ("Remuneration", 5): ("core.remuneration.stock_options", "Stored", "ESOP / stock option value per Sec 197"),
    ("Remuneration", 6): ("core.remuneration.sweat_equity", "Stored", "Sweat equity value allotted"),
    ("Remuneration", 7): ("core.remuneration.commission", "Stored", "Commission on net profits approved by Board/shareholders"),
    ("Remuneration", 8): ("core.remuneration.sitting_fees", "Stored", "Board and committee sitting fees paid"),
    ("Remuneration", 9): ("core.remuneration.other_payments", "Stored", "Performance bonus or other remuneration components"),
    ("Remuneration", 10): ("core.remuneration.total", "Derived (Generated)", "Stored as generated column: sum of all components; never manually typed"),
    ("Remuneration", 11): ("core.remuneration.ceiling", "Stored", "Statutory remuneration ceiling under Sec 197 / Schedule V"),

    # -------------------------------------------------------------
    # Penalties & Legal Actions
    # -------------------------------------------------------------
    ("Penalties & Legal Actions", 1): ("core.penalty_action.relates_to", "Stored", "Target: company / directorship / officer in default"),
    ("Penalties & Legal Actions", 2): ("core.penalty_action.action_type_id", "Stored", "FK to core.lookup_value (LEGAL_ACTION_TYPE: Penalty, Prosecution, Compounding)"),
    ("Penalties & Legal Actions", 3): ("core.penalty_action.section", "Stored", "Section of Companies Act 2013 involved"),
    ("Penalties & Legal Actions", 4): ("core.penalty_action.description", "Stored", "Brief factual summary of alleged violation"),
    ("Penalties & Legal Actions", 5): ("core.penalty_action.details_or_amount", "Stored", "Monetary penalty amount or compounding fee imposed"),
    ("Penalties & Legal Actions", 6): ("core.penalty_action.authority_id", "Stored", "FK to core.lookup_value (AUTHORITY: ROC, RD, NCLT, Court)"),
    ("Penalties & Legal Actions", 7): ("core.penalty_action.appealed / appeal_details", "Stored", "Boolean flag and details of appeal / stay order"),

    # -------------------------------------------------------------
    # Government Filings Tracker
    # -------------------------------------------------------------
    ("Government Filings Tracker", 1): ("core.government_filing.form_name", "Stored", "MCA Form name (e.g. MGT-7, AOC-4, DIR-12, ADT-1, PAS-3)"),
    ("Government Filings Tracker", 2): ("core.government_filing.description", "Stored", "Purpose and statutory context of the form"),
    ("Government Filings Tracker", 3): ("core.government_filing.due_date", "Stored", "Statutory due date calculated from trigger event"),
    ("Government Filings Tracker", 4): ("core.government_filing.filing_date", "Stored", "Actual date of filing with MCA"),
    ("Government Filings Tracker", 5): ("core.government_filing.fee_paid", "Stored", "Filing fee and additional/penalty fee paid in INR"),
    ("Government Filings Tracker", 6): ("core.government_filing.status_id / core.v_filings_overdue", "Derived / Stored", "Status lookup (NOT_FILED, FILED_ON_TIME, FILED_LATE); overdue tracked via core.v_filings_overdue"),

    # -------------------------------------------------------------
    # Other Yearly Disclosures
    # -------------------------------------------------------------
    ("Other Yearly Disclosures", 1): ("core.yearly_disclosure.type = 'register_closure'", "Stored", "Stored in core.yearly_disclosure with closure dates and details JSON"),
    ("Other Yearly Disclosures", 2): ("core.yearly_disclosure.type = 'dividend'", "Stored", "Stored in core.yearly_disclosure with dividend type, rate %, and record date"),
    ("Other Yearly Disclosures", 3): ("core.yearly_disclosure.type = 'delisting'", "Stored", "Stored in core.yearly_disclosure with delisting rationale"),
    ("Other Yearly Disclosures", 4): ("core.yearly_disclosure.type = 'nominal_value_change'", "Stored", "Stored in core.yearly_disclosure with sub-division/consolidation details"),
    ("Other Yearly Disclosures", 5): ("core.director_declaration / core.yearly_disclosure", "Stored", "Director interest disclosures under Sec 184(1) (Form MBP-1)"),
    ("Other Yearly Disclosures", 6): ("core.director_declaration.declaration_type = 'independence'", "Stored", "Independent director declarations under Sec 149(7)"),

    # -------------------------------------------------------------
    # Loans to Directors (Sec 185)
    # -------------------------------------------------------------
    ("Loans to Directors (Sec 185)", 1): ("core.s185_loan.recipient_name / director_id", "Stored", "Borrower / beneficiary details and director interested"),
    ("Loans to Directors (Sec 185)", 2): ("core.s185_loan.transaction_type", "Stored", "Loan / Guarantee / Security"),
    ("Loans to Directors (Sec 185)", 3): ("core.s185_loan.amount", "Stored", "Principal monetary value of loan or guarantee"),
    ("Loans to Directors (Sec 185)", 4): ("core.s185_loan.exception_relied_on", "Stored", "Statutory exemption under Sec 185(2) or 185(3) (MD/WTD loan scheme, etc.)"),
    ("Loans to Directors (Sec 185)", 5): ("core.s185_loan.shareholder_approval_obtained", "Stored", "Boolean flag confirming special resolution passed by members"),
    ("Loans to Directors (Sec 185)", 6): ("core.s185_loan.board_resolution_date", "Stored", "Date Board of Directors approved the transaction"),
    ("Loans to Directors (Sec 185)", 7): ("core.s185_loan.repayment_terms / interest_rate", "Stored", "Repayment schedule, maturity date, and interest rate"),
    ("Loans to Directors (Sec 185)", 8): ("core.s185_loan.outstanding_balance", "Stored", "Current outstanding balance"),

    # -------------------------------------------------------------
    # Loans & Investments (Sec 186)
    # -------------------------------------------------------------
    ("Loans & Investments (Sec 186)", 1): ("core.s186_transaction.recipient_entity", "Stored", "Name of corporate body or entity receiving investment/loan"),
    ("Loans & Investments (Sec 186)", 2): ("core.s186_transaction.transaction_type", "Stored", "Loan / Guarantee / Security / Acquisition of Securities"),
    ("Loans & Investments (Sec 186)", 3): ("core.s186_transaction.amount", "Stored", "Monetary value of the transaction"),
    ("Loans & Investments (Sec 186)", 4): ("core.v_s186_running_total.running_total", "Derived", "Calculated on the fly in core.v_s186_running_total; not stored per decision 7"),
    ("Loans & Investments (Sec 186)", 5): ("core.s186_transaction.prior_shareholder_approval_needed", "Derived / Stored", "Derived from limit calculation (60% paid-up+reserves or 100% free reserves); approval tracked"),
    ("Loans & Investments (Sec 186)", 6): ("core.s186_transaction.board_unanimous_approval", "Stored", "Boolean flag confirming unanimous board resolution passed per Sec 186(5)"),
    ("Loans & Investments (Sec 186)", 7): ("core.s186_transaction.interest_rate", "Stored", "Interest rate (must not be lower than prevailing yield of govt security)"),
    ("Loans & Investments (Sec 186)", 8): ("core.s186_transaction.more_than_two_layers", "Stored", "Boolean flag: compliance with two-layer investment company restriction under Sec 186(1)"),

    # -------------------------------------------------------------
    # Related Party Txns (Sec 188)
    # -------------------------------------------------------------
    ("Related Party Txns (Sec 188)", 1): ("core.s188_related_party_txn.related_party_name", "Stored", "Name of related party entity or individual"),
    ("Related Party Txns (Sec 188)", 2): ("core.s188_related_party_txn.nature_of_relationship", "Stored", "Relationship definition under Sec 2(76) (Director, relative, holding, subsidiary)"),
    ("Related Party Txns (Sec 188)", 3): ("core.s188_related_party_txn.value", "Stored", "Contract / monetary value of the transaction"),
    ("Related Party Txns (Sec 188)", 4): ("core.s188_related_party_txn.is_ordinary_course_and_arms_length", "Stored", "Boolean flag: exempts from Board/shareholder approval requirements under Sec 188(1) proviso"),
    ("Related Party Txns (Sec 188)", 5): ("core.s188_related_party_txn.audit_committee_approval_date", "Stored", "Date omnibus or specific approval granted by Audit Committee under Sec 177"),
    ("Related Party Txns (Sec 188)", 6): ("core.s188_related_party_txn.board_approval_date", "Stored", "Date of Board approval where required"),
    ("Related Party Txns (Sec 188)", 7): ("core.s188_related_party_txn.shareholder_approval_obtained", "Stored", "Boolean flag confirming resolution passed for transactions exceeding threshold"),
    ("Related Party Txns (Sec 188)", 8): ("core.s188_related_party_txn.interested_directors", "Stored", "Interested directors excluded from quorum and voting"),
    ("Related Party Txns (Sec 188)", 9): ("core.s188_related_party_txn.disclosed_in_aoc2", "Stored", "Boolean flag confirming disclosure in Board's Report (Form AOC-2)"),

    # -------------------------------------------------------------
    # Postal Ballot
    # -------------------------------------------------------------
    ("Postal Ballot", 1): ("core.postal_ballot.particulars", "Stored", "Full text and particulars of resolution proposed through postal ballot"),
    ("Postal Ballot", 2): ("core.postal_ballot.reason", "Stored", "Statutory mandate under Sec 110 or business rationale"),
    ("Postal Ballot", 3): ("core.postal_ballot.notice_date", "Stored", "Date postal ballot notice dispatched to members"),
    ("Postal Ballot", 4): ("core.postal_ballot.voting_opens / voting_closes", "Stored", "30-day voting window start and end timestamps"),
    ("Postal Ballot", 5): ("core.postal_ballot.scrutinizer", "Stored", "Name of appointed Scrutinizer (Practicing CS / Advocate)"),
    ("Postal Ballot", 6): ("core.postal_ballot.votes_for / votes_against / votes_invalid", "Stored", "Scrutinizer tally of votes cast in favor, against, and invalid"),
    ("Postal Ballot", 7): ("core.postal_ballot.passed", "Derived (Generated)", "Boolean outcome derived from vote count vs statutory threshold"),
    ("Postal Ballot", 8): ("core.postal_ballot.result_declared_date", "Stored", "Date Chairman announced voting result"),
    ("Postal Ballot", 9): ("core.postal_ballot.result_filed_date", "Stored", "Date Form MGT-14 filed with ROC"),

    # -------------------------------------------------------------
    # ODI Compliances
    # -------------------------------------------------------------
    ("ODI Compliances", 1): ("core.odi.foreign_subsidiary_name", "Stored", "Name of overseas direct investment entity / JV / WOS"),
    ("ODI Compliances", 2): ("core.odi.uin", "Stored", "Unique Identification Number issued by Reserve Bank of India"),
    ("ODI Compliances", 3): ("core.odi.shares_purchased", "Stored", "Quantity of shares acquired in foreign entity"),
    ("ODI Compliances", 4): ("core.odi_step_down_subsidiary.sds_name / country", "Stored", "Tracked in child table core.odi_step_down_subsidiary"),
    ("ODI Compliances", 5): ("core.odi_step_down_subsidiary.parent_name", "Stored", "Immediate parent entity of the Step Down Subsidiary"),
    ("ODI Compliances", 6): ("core.odi_step_down_subsidiary.investment_amount / date", "Stored", "Investment amount in foreign currency and date"),
    ("ODI Compliances", 7): ("core.odi_step_down_subsidiary.activity_code", "Stored", "NIC activity codes of the SDS"),
    ("ODI Compliances", 8): ("core.odi_step_down_subsidiary.stake_percent", "Stored", "Percentage equity stake held in SDS"),
    ("ODI Compliances", 9): ("core.odi_step_down_subsidiary.is_financial_services", "Stored", "Boolean flag for financial services sector compliance"),
    ("ODI Compliances", 10): ("core.odi_step_down_subsidiary.wound_up_details", "Stored", "Particulars of SDS divested or wound up"),
    ("ODI Compliances", 11): ("core.odi.financial_year", "Stored", "Financial year of the foreign entity"),
    ("ODI Compliances", 12): ("core.odi.apr_filing_date", "Stored", "Date Annual Performance Report (APR) filed with RBI via AD Bank"),
    ("ODI Compliances", 13): ("core.evidence_link", "Stored", "Share certificates, audited accounts of foreign JV/WOS linked via core.evidence_link"),

    # -------------------------------------------------------------
    # ECB
    # -------------------------------------------------------------
    ("ECB", 1): ("core.ecb.lender_name", "Stored", "Name of recognized non-resident lender"),
    ("ECB", 2): ("core.ecb.lender_country", "Stored", "Country of jurisdiction of the lender"),
    ("ECB", 3): ("core.ecb.lrn", "Stored", "Loan Registration Number issued by RBI"),
    ("ECB", 4): ("core.ecb.amount", "Stored", "Principal amount of ECB borrowed"),
    ("ECB", 5): ("core.ecb.interest_rate", "Stored", "Interest rate spread over benchmark (SOFR/EURIBOR)"),
    ("ECB", 6): ("core.ecb.minimum_average_maturity", "Stored", "MAMP (Minimum Average Maturity Period) compliance"),
    ("ECB", 7): ("core.ecb.repayment_or_conversion", "Stored", "Tracked: Repayable in cash or convertible to equity"),
    ("ECB", 8): ("core.ecb.conversion_exchange_rate", "Stored", "Agreed conversion exchange rate if convertible"),
    ("ECB", 9): ("core.ecb.end_use", "Stored", "Permitted end-use per RBI master directions"),
    ("ECB", 10): ("core.ecb.agreement_date", "Stored", "Date of loan agreement with overseas lender"),
    ("ECB", 11): ("core.ecb.assets_security", "Stored", "Details of charge created on Indian assets (Form CHG-1)"),
    ("ECB", 12): ("core.evidence_link", "Stored", "Loan agreement, Form ECB, and Form ECB-2 monthly returns linked via evidence_link"),

    # -------------------------------------------------------------
    # Portal Access
    # -------------------------------------------------------------
    ("Portal Access", 1): ("core.portal_access.portal_name", "Stored", "MCA V2/V3, Income Tax, RBI FIRMS, DGFT, NSDL/CDSL"),
    ("Portal Access", 2): ("core.portal_access.username", "Stored", "Portal login username / user ID"),
    ("Portal Access", 3): ("core.portal_access.held_by", "Stored", "Designated officer / CS holding custody of credentials"),
    ("Portal Access", 4): ("core.portal_access.notes", "Stored", "Operational notes, security guidelines, OTP instructions"),
    ("Portal Access", 5): ("core.portal_access.secret_encrypted / Deliberately Not Stored", "Encrypted / Excluded", "Decision 10: Never stored in plaintext. Encrypted bytea via pgp_sym_encrypt with runtime session key only; seed data has no secret.")
}


def generate_traceability():
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    data_sheets = [s for s in wb.sheetnames if s not in ['Read Me', "What's Included", 'When Something Becomes Required', 'Standard Lists']]

    lines = []
    lines.append("# BMP Compliance Platform — Field Traceability Matrix")
    lines.append("")
    lines.append("This document maps every statutory and compliance information requirement from the master checklist")
    lines.append("(`BMP_Master Checklist_Dashboard Requirements.xlsx`) directly to the PostgreSQL database schema.")
    lines.append("")
    lines.append("> Target: **100% of rows mapped**. Calculated values are derived on the fly in views or generated columns;")
    lines.append("> secrets are strictly encrypted or excluded per architectural decisions.")
    lines.append("")
    lines.append("| Sheet | Row # | Information needed | Mapped to (schema.table.column / view / rule / lookup) | Stored or Derived | Notes |")
    lines.append("|---|---|---|---|---|---|")

    total_rows = 0
    mapped_rows = 0

    for sheet_name in data_sheets:
        ws = wb[sheet_name]
        header_row = None
        for r in range(1, ws.max_row + 1):
            vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
            if vals and (vals[0] == '#' or (len(vals) > 1 and vals[1] == 'Information needed')):
                header_row = r
                continue
            if header_row and r > header_row:
                num_val = vals[0]
                info_val = vals[1] if len(vals) > 1 else None
                if num_val is None and info_val is None:
                    continue
                total_rows += 1
                
                # Look up mapping
                # Try by (sheet_name, num_val)
                key = (sheet_name, num_val)
                if key in MAPPINGS:
                    mapped_to, stored_derived, notes = MAPPINGS[key]
                    mapped_rows += 1
                else:
                    mapped_to = "core.unmapped"
                    stored_derived = "TBD"
                    notes = "Pending mapping"

                # Clean strings for markdown table
                clean_info = str(info_val or "").replace("|", "/").replace("\n", " ").strip()
                clean_notes = str(notes or "").replace("|", "/").replace("\n", " ").strip()
                clean_mapped = str(mapped_to).replace("|", "/")
                
                lines.append(f"| {sheet_name} | {num_val} | {clean_info} | `{clean_mapped}` | {stored_derived} | {clean_notes} |")

    lines.append("")
    lines.append("## Summary Statistics")
    lines.append(f"- **Total Data Sheets Analyzed:** {len(data_sheets)}")
    lines.append(f"- **Total Requirement Fields in Excel:** {total_rows}")
    lines.append(f"- **Total Successfully Mapped Fields:** {mapped_rows}")
    lines.append(f"- **Coverage Percentage:** {mapped_rows / total_rows * 100:.1f}%")
    lines.append("")

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {OUTPUT_MD}: {mapped_rows}/{total_rows} ({mapped_rows/total_rows*100:.1f}%) mapped.")


if __name__ == "__main__":
    generate_traceability()
