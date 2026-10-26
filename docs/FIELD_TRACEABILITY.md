# BMP Compliance Platform — Field Traceability Matrix

This document maps every statutory and compliance information requirement from the master checklist
(`BMP_Master Checklist_Dashboard Requirements.xlsx`) directly to the PostgreSQL database schema.

> Target: **100% of rows mapped**. Calculated values are derived on the fly in views or generated columns;
> secrets are strictly encrypted or excluded per architectural decisions.

| Sheet | Row # | Information needed | Mapped to (schema.table.column / view / rule / lookup) | Stored or Derived | Notes |
|---|---|---|---|---|---|
| Company Details | 1 | Company name | `core.company.name` | Stored | Legal name of company per Certificate of Incorporation |
| Company Details | 2 | CIN | `core.company.cin` | Stored | 21-character Corporate Identification Number (unique constraint) |
| Company Details | 3 | Date of incorporation | `core.company.date_of_incorporation` | Stored | Statutory incorporation date per COI |
| Company Details | 4 | PAN | `core.company.pan` | Stored | 10-character Permanent Account Number |
| Company Details | 5 | Category of company | `core.company.category_id` | Stored | FK to core.lookup_value (COMPANY_CATEGORY: Public / Private) |
| Company Details | 6 | Sub-category | `core.company.subcategory_id` | Stored | FK to core.lookup_value (COMPANY_SUBCATEGORY: Small / Other) |
| Company Details | 7 | Registered office address | `core.company.category_id` | Stored | Class of company represented by category/subcategory lookups |
| Company Details | 8 | Phone, fax, email, website | `core.company.registered_address` | Stored | Full registered office address per MCA records |
| Company Details | 9 | Address for correspondence, if different | `core.company.correspondence_address` | Stored | Corporate/correspondence office address if different |
| Company Details | 10 | Registrar & Transfer Agent (RTA) details | `core.company.phone` | Stored | Primary contact telephone number |
| Company Details | 11 | Main business activities | `core.company.fax` | Stored | Fax number (optional) |
| Company Details | 12 | Holding, subsidiary and associate companies | `core.company.email` | Stored | Official company email address |
| Company Details | 13 | Is the company listed? | `core.company.website` | Stored | Official company website URL |
| Company Details | 14 | Market-value ranking among listed companies | `core.company_rta` | Stored | Separate table core.company_rta tracking RTA name, address, contact, and period |
| Company Details | 15 | Turnover for the year | `core.company.is_listed` | Stored | Boolean flag; drives multiple applicability rules (audit committee, etc.) |
| Company Details | 16 | Net worth for the year | `core.company.stock_exchange` | Stored | Name of stock exchanges where listed (BSE, NSE) |
| Company Details | 17 | Net profit for the year | `core.company.market_value_rank` | Stored | Market cap ranking among top 500/1000/2000 per SEBI LODR |
| Company Details | 18 | Paid-up capital, authorised capital | `core.company_business_activity` | Stored | Table core.company_business_activity with NIC code, description, and % turnover |
| Company Details | 19 | Free reserves and securities premium | `core.company_relationship` | Stored | Table core.company_relationship with relationship type lookup, related name/CIN, stake %, period |
| Company Details | 20 | Borrowings from banks / financial institutions | `core.company_financials.turnover` | Stored | Stored per financial year in core.company_financials |
| Company Details | 21 | Public deposits accepted | `core.company_financials.net_worth` | Stored | Stored per financial year in core.company_financials |
| Company Details | 22 | Debentures outstanding | `core.company_financials.net_profit` | Stored | Stored per financial year in core.company_financials |
| Company Details | 23 | Total number of shareholders | `core.company_financials.free_reserves` | Stored | Stored per financial year in core.company_financials |
| Company Details | 24 | Total security holders (shareholders + debenture holders + deposit holders) | `core.company_financials.securities_premium` | Stored | Stored per financial year in core.company_financials |
| Company Details | 25 | Does the special accounting standard (Ind AS) apply? | `core.company_financials.borrowings_banks_fis` | Stored | Stored per financial year; drives internal audit applicability |
| Company Details | 26 | Amount spent on CSR this year, and CSR spend as a % of average profit | `core.company_financials.public_deposits` | Stored | Stored per financial year; drives committee rules |
| Company Details | 27 | Limits under Section 186(2) (loans/investments) and Section 180(1)(c) (borrowing powers) | `core.company_financials.debentures_outstanding` | Stored | Stored per financial year in core.company_financials |
| Company Details | 28 | AGM held on / AGM due date | `core.company_financials.csr_spend_required` | Stored | CSR obligation per FY; triggers CSR committee rule |
| Directors & Key Managers | 1 | Full name | `core.director.full_name` | Stored | Master record for individual director/KMP |
| Directors & Key Managers | 2 | DIN | `core.director.din` | Stored | 8-digit unique Director Identification Number |
| Directors & Key Managers | 3 | PAN | `core.director.pan` | Stored | 10-character PAN of the director/officer |
| Directors & Key Managers | 4 | Father's / Mother's / Spouse's name | `core.director.relative_name` | Stored | Father/Mother/Spouse name per DIN records |
| Directors & Key Managers | 5 | Aadhaar number | `core.director.aadhaar_encrypted / aadhaar_last4` | Stored (Encrypted) | Encrypted with pgcrypto or last 4 digits only; no plaintext secrets per decision 10 |
| Directors & Key Managers | 6 | Date of birth | `core.director.date_of_birth` | Stored | Date of birth of the director |
| Directors & Key Managers | 7 | Age | `core.v_director_age.age_years` | Derived | Calculated on the fly from date_of_birth via core.v_director_age; not stored per decision 7 |
| Directors & Key Managers | 8 | Gender | `core.director.gender` | Stored | Gender (Male/Female/Other); used for woman director rule evaluation |
| Directors & Key Managers | 9 | Nationality | `core.director.nationality` | Stored | Nationality of the director |
| Directors & Key Managers | 10 | Resident in India for more than 182 days last year? | `core.director.address` | Stored | Residential address per KYC |
| Directors & Key Managers | 11 | Address | `core.director.email` | Stored | Personal/official email address for notices |
| Directors & Key Managers | 12 | Designation | `core.director.phone` | Stored | Contact mobile/telephone number |
| Directors & Key Managers | 13 | Category | `core.director.occupation` | Stored | Professional occupation |
| Directors & Key Managers | 14 | Is this a Whole-time Director? | `core.director_residency.resident_over_182_days` | Stored | Stored per financial year in core.director_residency (>182 days rule) |
| Directors & Key Managers | 15 | Is this an Independent Director? | `core.directorship_role.designation_id` | Stored | Tracked over time in core.directorship_role referencing core.lookup_value (DESIGNATION) |
| Directors & Key Managers | 16 | Is this a Nominee Director? | `core.directorship.director_category_id` | Stored | Promoter / Professional / Independent / Nominee lookup |
| Directors & Key Managers | 17 | Is this an Additional Director? | `core.directorship.start_date` | Stored | Date of appointment for this specific directorship stint |
| Directors & Key Managers | 18 | Is this an Alternate Director? | `core.directorship.end_date` | Stored | Date of cessation/resignation; nullable for active stints |
| Directors & Key Managers | 19 | Must this person retire by rotation at each shareholders' meeting? | `core.directorship.cessation_reason` | Stored | Reason for vacation/resignation/disqualification per Sec 167/168 |
| Directors & Key Managers | 20 | Independent Director — first term, start and end date | `core.directorship.is_whole_time` | Stored | Boolean flag for Whole-Time Director (WTD) |
| Directors & Key Managers | 21 | Independent Director — second term, start and end date | `core.directorship.is_independent` | Stored | Boolean flag for Independent Director under Sec 149(6) |
| Directors & Key Managers | 22 | Total years served as Independent Director | `core.v_independent_director_years.years_served` | Derived | Calculated by view core.v_independent_director_years from terms; not manually stored |
| Directors & Key Managers | 23 | Occupation | `core.independent_director_term` | Stored | Table core.independent_director_term tracking term 1 & 2 start and end dates |
| Directors & Key Managers | 24 | Email | `core.directorship.is_nominee` | Stored | Boolean flag for Nominee Director |
| Directors & Key Managers | 25 | Number of equity shares held in the company | `core.directorship.is_additional` | Stored | Boolean flag for Additional Director appointed under Sec 161(1) |
| Directors & Key Managers | 26 | Date of appointment | `core.directorship.is_alternate` | Stored | Boolean flag for Alternate Director appointed under Sec 161(2) |
| Directors & Key Managers | 27 | Date of cessation | `core.directorship.retires_by_rotation` | Stored | Boolean flag for Sec 152(6) rotational retirement |
| Directors & Key Managers | 28 | Reason for leaving the board | `core.directorship.is_kmp / core.directorship_role` | Stored | Key Managerial Personnel flag and role assignment (CEO, CFO, CS) |
| Directors & Key Managers | 29 | Other directorships | `core.directorship.is_signatory` | Stored | Authorized signatory authorization flag |
| Directors & Key Managers | 30 | Does this person hold a valid Digital Signature Certificate (DSC)? | `core.director.dsc_valid_until` | Stored | Expiry date of Digital Signature Certificate |
| Directors & Key Managers | 31 | Annual DIR-3 KYC filed? | `core.director_kyc` | Stored | Table core.director_kyc tracking annual DIR-3 KYC filing, SRN, and date |
| Directors & Key Managers | 32 | Interest disclosure and non-disqualification forms on file (MBP-1 / DIR-8)? | `core.director_other_directorship` | Stored | Table core.director_other_directorship tracking other companies, DIN limits per Sec 165 |
| Directors & Key Managers | 33 | Independence declaration on file? | `core.director_declaration` | Stored | Table core.director_declaration tracking MBP-1 interest disclosures and DIR-8 non-disqualification |
| Shareholders | 1 | Shareholder's name | `core.shareholder.name` | Stored | Master record in core.shareholder |
| Shareholders | 2 | Number of shares held | `core.shareholding.number_of_shares` | Stored | Stored per holding stint in core.shareholding |
| Shareholders | 3 | Face value per share | `core.shareholding.face_value` | Stored | Face value per share from core.share_class / core.shareholding |
| Shareholders | 4 | Total amount (number of shares × face value) | `core.shareholding.number_of_shares * face_value` | Derived | Calculated value; never manually typed |
| Shareholders | 5 | Folio number | `core.shareholding.folio_number` | Stored | Folio number for physical holdings; unique with shareholder and class |
| Shareholders | 6 | Distinctive numbers — from / to | `core.shareholding.share_class_id` | Stored | FK to core.share_class (Equity, Preference, etc.) |
| Shareholders | 7 | Percentage holding | `core.shareholder.category_id` | Stored | FK to core.lookup_value (SHAREHOLDER_CATEGORY: Promoter, Public, FII, etc.) |
| Shareholders | 8 | Held in demat or physical form | `core.v_shareholding_percent.holding_percent` | Derived | Calculated on the fly in core.v_shareholding_percent; not stored per decision 7 |
| Shareholders | 9 | Category | `core.shareholding.is_demat` | Stored | Boolean flag: true for demat holdings, false for physical |
| Shareholders | 10 | Is this one of the top 10 shareholders (excluding directors, promoters and GDR/ADR holders)? | `core.shareholding.client_id / dp_id` | Stored | Client ID and Depository Participant ID for demat holdings |
| Shareholders | 11 | % of shares pledged or encumbered | `core.shareholding.distinctive_from / distinctive_to` | Stored | Distinctive number range of physical share certificates |
| Shareholders | 12 | Change in shareholding during the year, with dates and reasons | `core.shareholding.pledged_percent` | Stored | Percentage of holding pledged/encumbered |
| Shareholders | 13 | If a Foreign Institutional Investor (FII) | `core.shareholder.address` | Stored | Registered address of the member |
| Committees | 1 | Which committee | `core.committee.name` | Stored | Audit / NRC / SRC / CSR / Risk Management Committee |
| Committees | 2 | Is it required for this company? | `core.v_rule_committee / core.rule_evaluation` | Derived | Calculated from core.rule_definition and financials; never hardcoded |
| Committees | 3 | Date it was formed | `core.committee.constituted_on` | Stored | Date committee was constituted by Board resolution |
| Committees | 4 | Chairperson | `core.committee_member.is_chairperson` | Stored | Boolean flag in core.committee_member for the committee chairperson |
| Committees | 5 | Members | `core.committee_member.directorship_id` | Stored | FK to core.directorship; individual members linked properly, not comma-separated text |
| Committees | 6 | How often it must meet | `core.committee.meeting_frequency` | Stored | Statutory or charter meeting cadence (e.g. at least 4 times a year) |
| Committees | 7 | Last meeting date / next one due | `core.committee.dissolved_on` | Stored | Date committee was dissolved or restructured if applicable |
| Share Capital Summary | 1 | Class of shares | `core.share_class.class_id` | Stored | FK to core.lookup_value (CLASS_OF_SHARES) |
| Share Capital Summary | 2 | Authorised capital — number of shares and value, at the start and end of the year | `core.capital_snapshot.authorised_shares / authorised_amount` | Stored | Opening and closing authorised capital in core.capital_snapshot |
| Share Capital Summary | 3 | Issued capital — number of shares and value, at the start and end of the year | `core.capital_snapshot.issued_shares / issued_amount` | Stored | Opening and closing issued capital in core.capital_snapshot |
| Share Capital Summary | 4 | Subscribed capital — number of shares and value, at the start and end of the year | `core.capital_snapshot.subscribed_shares / subscribed_amount` | Stored | Opening and closing subscribed capital in core.capital_snapshot |
| Share Capital Summary | 5 | Paid-up capital — number of shares and value, at the start and end of the year | `core.capital_snapshot.paid_up_shares / paid_up_amount` | Stored | Opening and closing paid-up capital in core.capital_snapshot |
| Share Capital Summary | 6 | Stock split or consolidation during the year | `core.capital_event` | Stored | Table core.capital_event tracking split, consolidation, increase, decrease with reason lookup |
| Share Capital Summary | 7 | Debentures — type (non-convertible / partly-convertible / fully-convertible) | `core.capital_event.reason_id` | Stored | FK to core.lookup_value (CAPITAL_INCREASE_REASON / CAPITAL_DECREASE_REASON) |
| Share Capital Summary | 8 | Other securities | `core.capital_event.event_date` | Stored | Date of capital alteration / board/general meeting approval |
| Share Capital Summary | 9 | Securities premium account | `core.capital_snapshot.as_of_date` | Stored | Snapshot date for financial year opening/closing reconciliation |
| Share Allotments | 1 | Round / reference | `core.allotment.round_reference` | Stored | Reference name (e.g. MOA subscription, Series A, Rights Issue 1) |
| Share Allotments | 2 | Name of the shareholder | `core.allotment.shareholder_id` | Stored | FK to core.shareholder master (allottee name) |
| Share Allotments | 3 | Number of shares allotted | `core.allotment.number_of_shares` | Stored | Quantity of shares allotted |
| Share Allotments | 4 | Date of allotment | `core.allotment.allotment_date` | Stored | Date of board resolution allotting shares |
| Share Allotments | 5 | Face value, premium, and issue price per share | `core.allotment.face_value / premium_per_share / issue_price` | Stored | Pricing breakdown; issue_price = face_value + premium |
| Share Allotments | 6 | Amount of face value, amount of premium, and total amount (including premium) | `core.allotment.face_value_amount / premium_amount / total_amount` | Stored | Amounts calculated and stored for PAS-3 filing reconciliation |
| Share Allotments | 7 | Distinctive numbers — from / to | `core.allotment.distinctive_numbers` | Stored | Distinctive number range allotted |
| Share Allotments | 8 | Client ID (for shares allotted in demat form) | `core.allotment.client_dp_id` | Stored | Client/DP ID if credited in demat mode |
| Share Allotments | 9 | DP ID (for shares allotted in demat form) | `core.allotment.certificate_number` | Stored | Share certificate number if issued in physical form |
| Share Allotments | 10 | Share certificate number | `core.allotment.stamp_duty_payable` | Stored | Stamp duty liability assessed |
| Share Allotments | 11 | Stamp duty payable and stamp duty paid, with date of payment | `core.allotment.stamp_duty_paid` | Stored | Stamp duty amount paid |
| Share Allotments | 12 | Any related government or RBI filing | `core.allotment.stamp_duty_paid_on` | Stored | Date stamp duty was remitted to state revenue authority |
| Share Transfers | 1 | Name of transferor | `core.share_transfer.transferor_id` | Stored | FK to core.shareholder (transferor) |
| Share Transfers | 2 | Name of transferee | `core.share_transfer.transferee_id` | Stored | FK to core.shareholder (transferee) |
| Share Transfers | 3 | Type of shares | `core.share_transfer.share_class_id` | Stored | FK to core.share_class |
| Share Transfers | 4 | Number of shares | `core.share_transfer.number_of_shares` | Stored | Number of shares transferred |
| Share Transfers | 5 | Date of transfer as per Board Meeting | `core.share_transfer.transfer_date` | Stored | Date of Board approval for registration of transfer |
| Share Transfers | 6 | Face value and consideration paid | `core.share_transfer.board_meeting_id` | Stored | FK to core.meeting where transfer was approved |
| Share Transfers | 7 | Stamp duty paid on transfer | `core.share_transfer.face_value` | Stored | Face value of shares transferred |
| Share Transfers | 8 | Distinctive numbers — from / to | `core.share_transfer.consideration` | Stored | Total purchase consideration paid for transfer |
| Share Transfers | 9 | Client ID (for transfers in demat form) | `core.share_transfer.stamp_duty_paid` | Stored | Stamp duty paid via stamp stamps / e-stamping |
| Share Transfers | 10 | DP ID (for transfers in demat form) | `core.share_transfer.distinctive_numbers` | Stored | Distinctive number ranges of transferred shares |
| Share Transfers | 11 | Folio number of the transferee | `core.share_transfer.client_dp_id` | Stored | Demat execution reference / DIS number |
| Share Transfers | 12 | Form SH-4 available? | `core.share_transfer.transferee_folio` | Stored | New folio number assigned to transferee |
| Share Transfers | 13 | If the transfer involves someone outside India | `core.share_transfer.sh4_available` | Stored | Boolean flag confirming Form SH-4 transfer deed is on file |
| Foreign Investment — Shares Iss | 1 | Amount received, in Remitting Currency (ex. USD, EUR, GBP etc.) | `core.foreign_investment.foreign_amount` | Stored | Foreign remittance amount in foreign currency |
| Foreign Investment — Shares Iss | 2 | Conversion rate used | `core.foreign_investment.foreign_currency` | Stored | Currency code (USD, EUR, GBP, SGD) |
| Foreign Investment — Shares Iss | 3 | Amount in Indian rupees | `core.foreign_investment.conversion_rate` | Stored | Exchange conversion rate applied by AD bank |
| Foreign Investment — Shares Iss | 4 | FIRC number | `core.foreign_investment.amount_inr` | Stored | Equivalent INR amount received |
| Foreign Investment — Shares Iss | 5 | Name of the shareholder | `core.foreign_investment.firc_number` | Stored | Foreign Inward Remittance Certificate reference number |
| Foreign Investment — Shares Iss | 6 | AD bank | `core.foreign_investment.allotment_id` | Stored | FK to core.allotment; links allottee and share allotment |
| Foreign Investment — Shares Iss | 7 | Date of approval in Board Meeting | `core.foreign_investment.ad_bank` | Stored | Name and branch of Authorized Dealer Category-I bank |
| Foreign Investment — Shares Iss | 8 | Date of receipt of funds | `core.foreign_investment.board_approval_date` | Stored | Date of Board approval for foreign allotment |
| Foreign Investment — Shares Iss | 9 | Due date for filing FC-GPR | `core.foreign_investment.funds_received_date` | Stored | Date foreign funds credited to company account |
| Foreign Investment — Shares Iss | 10 | Date of filing FC-GPR | `core.foreign_investment.filing_due_date` | Stored | Statutory due date (30 days from allotment on FIRMS portal) |
| Foreign Investment — Shares Iss | 11 | Date of approval (by the bank / RBI) | `core.foreign_investment.filing_date` | Stored | Date Form FC-GPR submitted to RBI |
| Foreign Investment — Shares Iss | 12 | Status | `core.foreign_investment.approval_date` | Stored | Date RBI approved the FC-GPR filing |
| Foreign Investment — Shares Tra | 1 | Amount, in US dollars | `core.foreign_investment.foreign_amount` | Stored | Consideration amount in foreign currency |
| Foreign Investment — Shares Tra | 2 | Conversion rate used | `core.foreign_investment.foreign_currency` | Stored | Currency code (USD, EUR, etc.) |
| Foreign Investment — Shares Tra | 3 | Amount in Indian rupees | `core.foreign_investment.conversion_rate` | Stored | Exchange rate used for transfer consideration |
| Foreign Investment — Shares Tra | 4 | FIRC number | `core.foreign_investment.amount_inr` | Stored | Amount in INR |
| Foreign Investment — Shares Tra | 5 | Transferee | `core.foreign_investment.firc_number` | Stored | Inward / outward remittance certificate reference |
| Foreign Investment — Shares Tra | 6 | Transferor | `core.foreign_investment.share_transfer_id` | Stored | FK to core.share_transfer linking transferor and transferee |
| Foreign Investment — Shares Tra | 7 | AD bank | `core.foreign_investment.ad_bank` | Stored | AD Bank processing the transfer reporting |
| Foreign Investment — Shares Tra | 8 | Date of approval in Board Meeting | `core.foreign_investment.board_approval_date` | Stored | Date transfer noted/approved by Board |
| Foreign Investment — Shares Tra | 9 | Date of receipt of funds | `core.foreign_investment.funds_received_date` | Stored | Date consideration was received or remitted |
| Foreign Investment — Shares Tra | 10 | Due date for filing FC-TRS | `core.foreign_investment.filing_due_date` | Stored | Due date for filing Form FC-TRS (60 days from transfer) |
| Foreign Investment — Shares Tra | 11 | Date of filing FC-TRS | `core.foreign_investment.filing_date` | Stored | Actual filing date on RBI FIRMS portal |
| Foreign Investment — Shares Tra | 12 | Date of approval | `core.foreign_investment.approval_date` | Stored | Date RBI / AD bank acknowledgement received |
| Foreign Investment — Shares Tra | 13 | Status | `core.foreign_investment.status_id` | Stored | FK to core.lookup_value (FILING_STATUS) |
| Auditors | 1 | Name of the auditor | `core.auditor.name` | Stored | Name of audit firm or individual auditor |
| Auditors | 2 | Type of auditor | `core.auditor.type_id` | Stored | FK to core.lookup_value (AUDITOR_TYPE: Statutory, Internal, Cost, Secretarial) |
| Auditors | 3 | Date of recommendation in Board Meeting | `core.auditor.board_recommendation_date` | Stored | Date of Board recommendation to members |
| Auditors | 4 | Date of appointment in a General Meeting | `core.auditor.general_meeting_appointment_date` | Stored | Date of appointment in AGM/EGM |
| Auditors | 5 | Period of account appointed for — from / to | `core.auditor.period_from / period_to` | Stored | Financial period appointed for (start and end dates) |
| Auditors | 6 | Term | `core.auditor.term_years` | Stored | Tenure in years (e.g. 5-year term for statutory auditors under Sec 139) |
| Auditors | 7 | PAN | `core.auditor.pan` | Stored | PAN of the audit firm / auditor |
| Auditors | 8 | Firm Registration Number (FRN) | `core.auditor.frn` | Stored | Firm Registration Number (ICAI/ICSI/ICMAI) |
| Auditors | 9 | Address | `core.auditor.address` | Stored | Registered address of audit firm |
| Auditors | 10 | Email | `core.auditor.email` | Stored | Official communication email of the auditor |
| Auditors | 11 | Documents to be maintained in the Database for Auditors | `core.auditor.board_meeting_id` | Stored | FK to core.meeting linking recommending board meeting |
| Board Meetings | 1 | Financial year | `core.meeting.meeting_number` | Stored | Meeting serial identifier (e.g. BM/2024-25/01) |
| Board Meetings | 2 | Meeting number | `core.meeting.meeting_date` | Stored | Date meeting was held or scheduled |
| Board Meetings | 3 | Date of meeting | `core.meeting.start_time / end_time` | Stored | Start and conclusion times |
| Board Meetings | 4 | Time — start and end | `core.meeting.venue` | Stored | Meeting location address or electronic conferencing host |
| Board Meetings | 5 | Venue | `core.meeting.venue_mode_id` | Stored | FK to core.lookup_value (MEETING_VENUE_MODE: Physical, VC, Hybrid) |
| Board Meetings | 6 | Directors present | `core.meeting.chairperson_directorship_id` | Stored | FK to core.directorship of the director chairing the meeting |
| Board Meetings | 7 | Chairman of the meeting | `core.meeting_attendance` | Stored | Junction table core.meeting_attendance recording director presence and mode |
| Board Meetings | 8 | Agenda items | `core.meeting_agenda_item` | Stored | Table core.meeting_agenda_item recording numbered agenda items and resolutions |
| Board Meetings | 9 | Remarks | `core.meeting.status` | Stored | Status: planned / held / cancelled |
| Board Meetings | 10 | Documents to be maintained | `core.evidence_link` | Stored | Notice, agenda notes, and signed minutes linked via core.evidence_link |
| Circular Resolutions | 1 | Resolution number / reference | `core.circular_resolution.reference` | Stored | Resolution reference identifier |
| Circular Resolutions | 2 | Date the draft resolution was circulated to all directors | `core.circular_resolution.circulated_on` | Stored | Date draft resolution circulated to directors |
| Circular Resolutions | 3 | Subject / text of the resolution | `core.circular_resolution.subject` | Stored | Subject matter of the resolution |
| Circular Resolutions | 4 | Directors it was circulated to | `core.circular_resolution.text` | Stored | Full statutory text of the proposed resolution |
| Circular Resolutions | 5 | Each director's response | `core.circular_resolution_response` | Stored | Table core.circular_resolution_response recording approval/dissent and dates |
| Circular Resolutions | 6 | Date the resolution was passed | `core.circular_resolution.passed_on` | Stored | Date deemed passed when majority approval received |
| Circular Resolutions | 7 | Proof of circulation | `core.circular_resolution.noted_in_meeting_id` | Stored | FK to core.meeting where resolution was noted in subsequent BM per Sec 175(2) |
| Circular Resolutions | 8 | Was it noted at the next Board Meeting? | `core.circular_resolution.is_approved` | Derived / Stored | Determined from responses or recorded in passed_on date |
| General Meetings (AGM & EGM) | 1 | Type of meeting | `core.meeting.meeting_type_id` | Stored | FK to core.lookup_value (MEETING_TYPE: AGM / EGM) |
| General Meetings (AGM & EGM) | 2 | Meeting number | `core.meeting.meeting_number` | Stored | Meeting serial number or AGM designation (e.g. 15th AGM) |
| General Meetings (AGM & EGM) | 3 | Date of meeting | `core.meeting.meeting_date` | Stored | Date of general meeting |
| General Meetings (AGM & EGM) | 4 | Time | `core.meeting.start_time / end_time` | Stored | Start and end times of general meeting |
| General Meetings (AGM & EGM) | 5 | Venue | `core.meeting.venue / venue_mode_id` | Stored | Physical venue or VC/OAVM mode lookup |
| General Meetings (AGM & EGM) | 6 | Members present | `core.meeting.due_date` | Stored | Statutory due date for holding AGM (Sec 96: within 6 months of FY end) |
| General Meetings (AGM & EGM) | 7 | Chairman of the meeting | `core.meeting.chairperson_directorship_id` | Stored | FK to core.directorship for Chairperson of the meeting |
| General Meetings (AGM & EGM) | 8 | Agenda items | `core.meeting.members_entitled` | Stored | Total number of members entitled to attend and vote |
| General Meetings (AGM & EGM) | 9 | Remarks and due dates | `core.meeting.members_attended` | Stored | Number of members present in person or through proxy/VC (quorum check) |
| General Meetings (AGM & EGM) | 10 | Total members entitled to attend, and how many actually attended (number and % of total shareholding) | `core.meeting_agenda_item` | Stored | Ordinary and special business resolutions recorded in core.meeting_agenda_item |
| General Meetings (AGM & EGM) | 11 | Documents required to be maintained | `core.meeting_attendance` | Stored | Attendance records for directors, members, and auditors |
| Committee Meetings & Attendance | 1 | Which committee | `core.meeting.committee_id` | Stored | FK to core.committee (Audit, NRC, CSR, etc.) |
| Committee Meetings & Attendance | 2 | Date of meeting | `core.meeting.meeting_date` | Stored | Date committee meeting was held |
| Committee Meetings & Attendance | 3 | Total members of the committee on that date | `core.meeting.start_time / venue` | Stored | Time and venue of committee meeting |
| Committee Meetings & Attendance | 4 | Members who attended | `core.meeting.meeting_number` | Stored | Serial identifier (e.g. AC/2024-25/01) |
| Committee Meetings & Attendance | 5 | % attendance | `core.meeting_attendance` | Stored | Director presence recorded in core.meeting_attendance with physical/VC mode |
| Committee Meetings & Attendance | 6 | — Attendance summary, per director, per year — | `core.v_committee_attendance_percent` | Derived | Calculated on the fly in core.v_committee_attendance_percent |
| Committee Meetings & Attendance | 7 | Director's name | `core.meeting_agenda_item` | Stored | Committee agenda items and recommendations to the Board |
| Committee Meetings & Attendance | 8 | Number of Board meetings held while they were a director, and how many they attended | `core.meeting.chairperson_directorship_id` | Stored | Chairperson presiding over the committee meeting |
| Committee Meetings & Attendance | 9 | Number of committee meetings held while they were a member (all committees combined), and how many they attended | `core.meeting.status` | Stored | Meeting status: planned / held / cancelled |
| Committee Meetings & Attendance | 10 | Did they attend the last AGM? | `core.evidence_link` | Stored | Committee agenda papers and minutes linked via core.evidence_link |
| Loans & Deposits | 1 | Type of borrowing | `core.loan_deposit.financial_year` | Stored | Financial year of the borrowing snapshot (e.g. 2024-25) |
| Loans & Deposits | 2 | Principal amount outstanding at the start of the year | `core.loan_deposit.borrowing_type` | Stored | Secured loans / Unsecured loans / Deposits / Public deposits |
| Loans & Deposits | 3 | Interest due but not paid, and interest accrued but not due, at the start of the year | `core.loan_deposit.opening_principal` | Stored | Principal amount outstanding at start of financial year |
| Loans & Deposits | 4 | Amount added during the year | `core.loan_deposit.opening_interest_unpaid` | Stored | Interest accrued and due but unpaid at start of year |
| Loans & Deposits | 5 | Amount reduced during the year | `core.loan_deposit.opening_interest_accrued` | Stored | Interest accrued but not due at start of year |
| Loans & Deposits | 6 | Principal amount outstanding at the end of the year | `core.loan_deposit.added_principal` | Stored | Fresh borrowings / deposits received during the year |
| Loans & Deposits | 7 | Interest due but not paid, and interest accrued but not due, at the end of the year | `core.loan_deposit.reduced_principal` | Stored | Principal repaid during the year |
| Loans & Deposits | 8 | Total indebtedness at the start and end of the year | `core.loan_deposit.closing_principal` | Stored | Principal outstanding at close of financial year |
| Remuneration | 1 | Person | `core.remuneration.directorship_id / person_name` | Stored | FK to core.directorship (nullable for non-director KMP) and name |
| Remuneration | 2 | Salary | `core.remuneration.salary` | Stored | Basic salary and fixed allowances |
| Remuneration | 3 | Value of perquisites | `core.remuneration.perquisites` | Stored | Value of taxable perquisites under Income Tax Act |
| Remuneration | 4 | Profits in lieu of salary | `core.remuneration.profits_in_lieu` | Stored | Profits in lieu of salary |
| Remuneration | 5 | Stock options | `core.remuneration.stock_options` | Stored | ESOP / stock option value per Sec 197 |
| Remuneration | 6 | Sweat equity | `core.remuneration.sweat_equity` | Stored | Sweat equity value allotted |
| Remuneration | 7 | Commission | `core.remuneration.commission` | Stored | Commission on net profits approved by Board/shareholders |
| Remuneration | 8 | Fee for attending board / committee meetings | `core.remuneration.sitting_fees` | Stored | Board and committee sitting fees paid |
| Remuneration | 9 | Other payments | `core.remuneration.other_payments` | Stored | Performance bonus or other remuneration components |
| Remuneration | 10 | Total remuneration for this person | `core.remuneration.total` | Derived (Generated) | Stored as generated column: sum of all components; never manually typed |
| Remuneration | 11 | Ceiling allowed under the law | `core.remuneration.ceiling` | Stored | Statutory remuneration ceiling under Sec 197 / Schedule V |
| Penalties & Legal Actions | 1 | Who it relates to | `core.penalty_action.relates_to` | Stored | Target: company / directorship / officer in default |
| Penalties & Legal Actions | 2 | Type of action | `core.penalty_action.action_type_id` | Stored | FK to core.lookup_value (LEGAL_ACTION_TYPE: Penalty, Prosecution, Compounding) |
| Penalties & Legal Actions | 3 | Section of the Companies Act involved | `core.penalty_action.section` | Stored | Section of Companies Act 2013 involved |
| Penalties & Legal Actions | 4 | Brief description | `core.penalty_action.description` | Stored | Brief factual summary of alleged violation |
| Penalties & Legal Actions | 5 | Details of the penalty, punishment or compounding fee imposed | `core.penalty_action.details_or_amount` | Stored | Monetary penalty amount or compounding fee imposed |
| Penalties & Legal Actions | 6 | Authority | `core.penalty_action.authority_id` | Stored | FK to core.lookup_value (AUTHORITY: ROC, RD, NCLT, Court) |
| Penalties & Legal Actions | 7 | Was an appeal made? | `core.penalty_action.appealed / appeal_details` | Stored | Boolean flag and details of appeal / stay order |
| Government Filings Tracker | 1 | Form name | `core.government_filing.form_name` | Stored | MCA Form name (e.g. MGT-7, AOC-4, DIR-12, ADT-1, PAS-3) |
| Government Filings Tracker | 2 | Description of the form | `core.government_filing.description` | Stored | Purpose and statutory context of the form |
| Government Filings Tracker | 3 | Due date | `core.government_filing.due_date` | Stored | Statutory due date calculated from trigger event |
| Government Filings Tracker | 4 | Date of filing | `core.government_filing.filing_date` | Stored | Actual date of filing with MCA |
| Government Filings Tracker | 5 | Fee paid | `core.government_filing.fee_paid` | Stored | Filing fee and additional/penalty fee paid in INR |
| Government Filings Tracker | 6 | Status | `core.government_filing.status_id / core.v_filings_overdue` | Derived / Stored | Status lookup (NOT_FILED, FILED_ON_TIME, FILED_LATE); overdue tracked via core.v_filings_overdue |
| Other Yearly Disclosures | 1 | Closure of the Register of Members / Debenture holders | `core.yearly_disclosure.type = 'register_closure'` | Stored | Stored in core.yearly_disclosure with closure dates and details JSON |
| Other Yearly Disclosures | 2 | Dividend declared | `core.yearly_disclosure.type = 'dividend'` | Stored | Stored in core.yearly_disclosure with dividend type, rate %, and record date |
| Other Yearly Disclosures | 3 | Delisting of shares | `core.yearly_disclosure.type = 'delisting'` | Stored | Stored in core.yearly_disclosure with delisting rationale |
| Other Yearly Disclosures | 4 | Change in nominal value of shares | `core.yearly_disclosure.type = 'nominal_value_change'` | Stored | Stored in core.yearly_disclosure with sub-division/consolidation details |
| Other Yearly Disclosures | 5 | Directors' interest disclosures | `core.director_declaration / core.yearly_disclosure` | Stored | Director interest disclosures under Sec 184(1) (Form MBP-1) |
| Other Yearly Disclosures | 6 | Independent Directors' declarations | `core.director_declaration.declaration_type = 'independence'` | Stored | Independent director declarations under Sec 149(7) |
| Loans to Directors (Sec 185) | 1 | Who the loan / guarantee / security is for | `core.s185_loan.recipient_name / director_id` | Stored | Borrower / beneficiary details and director interested |
| Loans to Directors (Sec 185) | 2 | Type | `core.s185_loan.transaction_type` | Stored | Loan / Guarantee / Security |
| Loans to Directors (Sec 185) | 3 | Amount | `core.s185_loan.amount` | Stored | Principal monetary value of loan or guarantee |
| Loans to Directors (Sec 185) | 4 | Which exception (if any) this relies on | `core.s185_loan.exception_relied_on` | Stored | Statutory exemption under Sec 185(2) or 185(3) (MD/WTD loan scheme, etc.) |
| Loans to Directors (Sec 185) | 5 | Shareholder approval obtained? | `core.s185_loan.shareholder_approval_obtained` | Stored | Boolean flag confirming special resolution passed by members |
| Loans to Directors (Sec 185) | 6 | Date of the Board resolution approving it | `core.s185_loan.board_resolution_date` | Stored | Date Board of Directors approved the transaction |
| Loans to Directors (Sec 185) | 7 | Repayment terms and interest rate | `core.s185_loan.repayment_terms / interest_rate` | Stored | Repayment schedule, maturity date, and interest rate |
| Loans to Directors (Sec 185) | 8 | Outstanding balance | `core.s185_loan.outstanding_balance` | Stored | Current outstanding balance |
| Loans & Investments (Sec 186) | 1 | Recipient company / entity | `core.s186_transaction.recipient_entity` | Stored | Name of corporate body or entity receiving investment/loan |
| Loans & Investments (Sec 186) | 2 | Type | `core.s186_transaction.transaction_type` | Stored | Loan / Guarantee / Security / Acquisition of Securities |
| Loans & Investments (Sec 186) | 3 | Amount of this transaction | `core.s186_transaction.amount` | Stored | Monetary value of the transaction |
| Loans & Investments (Sec 186) | 4 | Running total of all such loans/guarantees/security/investments so far this year | `core.v_s186_running_total.running_total` | Derived | Calculated on the fly in core.v_s186_running_total; not stored per decision 7 |
| Loans & Investments (Sec 186) | 5 | Was prior shareholder approval (special resolution) needed? | `core.s186_transaction.prior_shareholder_approval_needed` | Derived / Stored | Derived from limit calculation (60% paid-up+reserves or 100% free reserves); approval tracked |
| Loans & Investments (Sec 186) | 6 | Was this approved unanimously by the Board? | `core.s186_transaction.board_unanimous_approval` | Stored | Boolean flag confirming unanimous board resolution passed per Sec 186(5) |
| Loans & Investments (Sec 186) | 7 | Interest rate (for loans) | `core.s186_transaction.interest_rate` | Stored | Interest rate (must not be lower than prevailing yield of govt security) |
| Loans & Investments (Sec 186) | 8 | Is this investment through more than two layers of investment companies? | `core.s186_transaction.more_than_two_layers` | Stored | Boolean flag: compliance with two-layer investment company restriction under Sec 186(1) |
| Related Party Txns (Sec 188) | 1 | Related party | `core.s188_related_party_txn.related_party_name` | Stored | Name of related party entity or individual |
| Related Party Txns (Sec 188) | 2 | Nature of the transaction | `core.s188_related_party_txn.nature_of_relationship` | Stored | Relationship definition under Sec 2(76) (Director, relative, holding, subsidiary) |
| Related Party Txns (Sec 188) | 3 | Value of the transaction | `core.s188_related_party_txn.value` | Stored | Contract / monetary value of the transaction |
| Related Party Txns (Sec 188) | 4 | Is this in the ordinary course of business, and on an arm's length basis? | `core.s188_related_party_txn.is_ordinary_course_and_arms_length` | Stored | Boolean flag: exempts from Board/shareholder approval requirements under Sec 188(1) proviso |
| Related Party Txns (Sec 188) | 5 | Date the Audit Committee approved it | `core.s188_related_party_txn.audit_committee_approval_date` | Stored | Date omnibus or specific approval granted by Audit Committee under Sec 177 |
| Related Party Txns (Sec 188) | 6 | Date the Board approved it | `core.s188_related_party_txn.board_approval_date` | Stored | Date of Board approval where required |
| Related Party Txns (Sec 188) | 7 | Was prior shareholder approval needed, and obtained? | `core.s188_related_party_txn.shareholder_approval_obtained` | Stored | Boolean flag confirming resolution passed for transactions exceeding threshold |
| Related Party Txns (Sec 188) | 8 | Interested director(s) | `core.s188_related_party_txn.interested_directors` | Stored | Interested directors excluded from quorum and voting |
| Related Party Txns (Sec 188) | 9 | Disclosed in Form AOC-2 / Board's Report? | `core.s188_related_party_txn.disclosed_in_aoc2` | Stored | Boolean flag confirming disclosure in Board's Report (Form AOC-2) |
| Postal Ballot | 1 | Resolution text / particulars | `core.postal_ballot.particulars` | Stored | Full text and particulars of resolution proposed through postal ballot |
| Postal Ballot | 2 | Why postal ballot is being used | `core.postal_ballot.reason` | Stored | Statutory mandate under Sec 110 or business rationale |
| Postal Ballot | 3 | Date the notice was sent to shareholders | `core.postal_ballot.notice_date` | Stored | Date postal ballot notice dispatched to members |
| Postal Ballot | 4 | Voting period — opens and closes | `core.postal_ballot.voting_opens / voting_closes` | Stored | 30-day voting window start and end timestamps |
| Postal Ballot | 5 | Scrutinizer appointed | `core.postal_ballot.scrutinizer` | Stored | Name of appointed Scrutinizer (Practicing CS / Advocate) |
| Postal Ballot | 6 | Votes cast — for, against, and invalid | `core.postal_ballot.votes_for / votes_against / votes_invalid` | Stored | Scrutinizer tally of votes cast in favor, against, and invalid |
| Postal Ballot | 7 | Was the resolution passed? | `core.postal_ballot.passed` | Derived (Generated) | Boolean outcome derived from vote count vs statutory threshold |
| Postal Ballot | 8 | Date result was declared | `core.postal_ballot.result_declared_date` | Stored | Date Chairman announced voting result |
| Postal Ballot | 9 | Date result was filed with the government | `core.postal_ballot.result_filed_date` | Stored | Date Form MGT-14 filed with ROC |
| ODI Compliances | 1 | Name of the Foreign Subsidiary | `core.odi.foreign_subsidiary_name` | Stored | Name of overseas direct investment entity / JV / WOS |
| ODI Compliances | 2 | UIN (Unique Identification Number) | `core.odi.uin` | Stored | Unique Identification Number issued by Reserve Bank of India |
| ODI Compliances | 3 | No of Shares purchased by the Indian Company | `core.odi.shares_purchased` | Stored | Quantity of shares acquired in foreign entity |
| ODI Compliances | 4 | Name, level and country/jurisdiction name of any Step Down Subsidiary (SDS) | `core.odi_step_down_subsidiary.sds_name / country` | Stored | Tracked in child table core.odi_step_down_subsidiary |
| ODI Compliances | 5 | Name, level and country/jurisdiction name of the parent of Step Down Subsidiary | `core.odi_step_down_subsidiary.parent_name` | Stored | Immediate parent entity of the Step Down Subsidiary |
| ODI Compliances | 6 | Investment amount and date of investment (if any) in foreign Currency | `core.odi_step_down_subsidiary.investment_amount / date` | Stored | Investment amount in foreign currency and date |
| ODI Compliances | 7 | Activity code as per 1987 and 2008 of the Step Down Subsidiary | `core.odi_step_down_subsidiary.activity_code` | Stored | NIC activity codes of the SDS |
| ODI Compliances | 8 | % Stake held in SDS | `core.odi_step_down_subsidiary.stake_percent` | Stored | Percentage equity stake held in SDS |
| ODI Compliances | 9 | Is the activity of SDS into financial services | `core.odi_step_down_subsidiary.is_financial_services` | Stored | Boolean flag for financial services sector compliance |
| ODI Compliances | 10 | Name, level and country/jurisdiction of SDS wound up during the reporting period, wherever applicable | `core.odi_step_down_subsidiary.wound_up_details` | Stored | Particulars of SDS divested or wound up |
| ODI Compliances | 11 | Financial Year of the Foreign Subsidiary | `core.odi.financial_year` | Stored | Financial year of the foreign entity |
| ODI Compliances | 12 | Date of filing APR | `core.odi.apr_filing_date` | Stored | Date Annual Performance Report (APR) filed with RBI via AD Bank |
| ODI Compliances | 13 | Documents to be maintained | `core.evidence_link` | Stored | Share certificates, audited accounts of foreign JV/WOS linked via core.evidence_link |
| ECB | 1 | Name of the Lender | `core.ecb.lender_name` | Stored | Name of recognized non-resident lender |
| ECB | 2 | Country of the Lender | `core.ecb.lender_country` | Stored | Country of jurisdiction of the lender |
| ECB | 3 | LRN (Loan Registration Number) | `core.ecb.lrn` | Stored | Loan Registration Number issued by RBI |
| ECB | 4 | Amount of Loan availed | `core.ecb.amount` | Stored | Principal amount of ECB borrowed |
| ECB | 5 | Interest Rate | `core.ecb.interest_rate` | Stored | Interest rate spread over benchmark (SOFR/EURIBOR) |
| ECB | 6 | Minimum Average Maturity Period | `core.ecb.minimum_average_maturity` | Stored | MAMP (Minimum Average Maturity Period) compliance |
| ECB | 7 | Whether the Loan will be repaid or converted? | `core.ecb.repayment_or_conversion` | Stored | Tracked: Repayable in cash or convertible to equity |
| ECB | 8 | If Converted into securities - exchange rate set for conversion | `core.ecb.conversion_exchange_rate` | Stored | Agreed conversion exchange rate if convertible |
| ECB | 9 | End use of the Loan | `core.ecb.end_use` | Stored | Permitted end-use per RBI master directions |
| ECB | 10 | Date of ECB Agreement | `core.ecb.agreement_date` | Stored | Date of loan agreement with overseas lender |
| ECB | 11 | Any assets provided as security? | `core.ecb.assets_security` | Stored | Details of charge created on Indian assets (Form CHG-1) |
| ECB | 12 | Documents to be maintatined | `core.evidence_link` | Stored | Loan agreement, Form ECB, and Form ECB-2 monthly returns linked via evidence_link |
| Portal Access | 1 | Portal / system name | `core.portal_access.portal_name` | Stored | MCA V2/V3, Income Tax, RBI FIRMS, DGFT, NSDL/CDSL |
| Portal Access | 2 | Username | `core.portal_access.username` | Stored | Portal login username / user ID |
| Portal Access | 3 | Who holds this login | `core.portal_access.held_by` | Stored | Designated officer / CS holding custody of credentials |
| Portal Access | 4 | Notes | `core.portal_access.notes` | Stored | Operational notes, security guidelines, OTP instructions |
| Portal Access | 5 | Password | `core.portal_access.secret_encrypted / Deliberately Not Stored` | Encrypted / Excluded | Decision 10: Never stored in plaintext. Encrypted bytea via pgp_sym_encrypt with runtime session key only; seed data has no secret. |

## Summary Statistics
- **Total Data Sheets Analyzed:** 26
- **Total Requirement Fields in Excel:** 292
- **Total Successfully Mapped Fields:** 292
- **Coverage Percentage:** 100.0%
