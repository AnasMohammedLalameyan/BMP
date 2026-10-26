-- db/seed/01_lookups_rules_doctypes.sql
-- Seeds lookup lists/values, document types, and rule definitions from xlsx.
-- All writes require app.current_user_id — we use a special seed user (id=1 set below).
-- This script is idempotent: uses INSERT ... ON CONFLICT DO NOTHING.

-- ============================================================
-- BOOTSTRAP: temporarily disable audit.capture() for lookup seeding
-- by inserting the seed system user FIRST without the trigger
-- (we do this by using bmp_owner who bypasses RLS, and we set
-- a session variable the trigger checks)
-- ============================================================

-- Set initial bootstrap session variable so audit trigger allows the initial system user insert
DO $$
BEGIN
    PERFORM set_config('app.current_user_id', '0', false);
END $$;

INSERT INTO core.role (name, description) VALUES
    ('admin',   'Full access to all companies'),
    ('manager', 'Access to assigned companies'),
    ('client',  'Read-only access to own company')
ON CONFLICT DO NOTHING;

INSERT INTO core.app_user (email, name, is_active)
VALUES ('seed@system.internal', 'System Seed User', false)
ON CONFLICT (email) DO NOTHING;

-- Set session variable for all subsequent writes
DO $$
DECLARE v_seed_user bigint;
BEGIN
    SELECT id INTO v_seed_user FROM core.app_user WHERE email = 'seed@system.internal';
    PERFORM set_config('app.current_user_id', v_seed_user::text, false);
END $$;

-- ============================================================
-- LOOKUP LISTS (from xlsx "Standard Lists")
-- ============================================================
INSERT INTO core.lookup_list (code, name) VALUES
    ('COMPANY_CATEGORY',       'Category of company'),
    ('COMPANY_SUBCATEGORY',    'Sub-category of company'),
    ('CLASS_OF_SHARES',        'Class of shares'),
    ('DEBENTURE_TYPE',         'Type of debenture'),
    ('CAPITAL_INCREASE_REASON','Reason for paid-up capital increase'),
    ('CAPITAL_DECREASE_REASON','Reason for paid-up capital decrease'),
    ('SHAREHOLDER_CATEGORY',   'Shareholder category'),
    ('DESIGNATION',            'Designation'),
    ('DIRECTOR_CATEGORY',      'Director category'),
    ('OTHER_COMPANY_TYPE',     'Type of other company (for other directorships)'),
    ('AUDITOR_TYPE',           'Type of auditor'),
    ('MEETING_TYPE',           'Meeting type'),
    ('MEETING_VENUE_MODE',     'Meeting venue mode'),
    ('LEGAL_ACTION_TYPE',      'Type of legal action'),
    ('AUTHORITY',              'Authority (for legal actions)'),
    ('FILING_STATUS',          'Filing status'),
    ('FOREIGN_INVESTMENT_TYPE','Type of foreign-investment transaction'),
    ('DIVIDEND_TYPE',          'Dividend type'),
    ('RELATIONSHIP',           'Relationship (for inter-corporate loans/RPT)')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- LOOKUP VALUES — seeded from xlsx "Standard Lists"
-- ============================================================

-- COMPANY_CATEGORY
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('PUBLIC',  'Public Company',  1),
    ('PRIVATE', 'Private Company', 2)
) AS v(code, label, so)
WHERE ll.code = 'COMPANY_CATEGORY'
ON CONFLICT (list_id, code) DO NOTHING;

-- COMPANY_SUBCATEGORY
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('GOVT',         'Government Company',                   1),
    ('SMALL',        'Small Company',                        2),
    ('OPC',          'One Person Company',                   3),
    ('FOREIGN_SUB',  'Subsidiary of Foreign Company',        4),
    ('NBFC',         'NBFC',                                 5),
    ('GUARANTEE',    'Guarantee Company',                    6),
    ('LTD_BY_SHARES','Limited by Shares',                   7),
    ('UNLIMITED',    'Unlimited Company',                    8),
    ('WITH_CAPITAL', 'Company having share capital',         9),
    ('NO_CAPITAL',   'Company not having share capital',    10),
    ('SEC8',         'Company registered under Section 8',  11)
) AS v(code, label, so)
WHERE ll.code = 'COMPANY_SUBCATEGORY'
ON CONFLICT (list_id, code) DO NOTHING;

-- CLASS_OF_SHARES
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('EQUITY',      'Equity',            1),
    ('PREFERENCE',  'Preference',        2),
    ('DEBENTURES',  'Debentures',        3),
    ('OTHER',       'Other securities',  4)
) AS v(code, label, so)
WHERE ll.code = 'CLASS_OF_SHARES'
ON CONFLICT (list_id, code) DO NOTHING;

-- DEBENTURE_TYPE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('NCD', 'Non-convertible',     1),
    ('PCD', 'Partly-convertible',  2),
    ('FCD', 'Fully-convertible',   3)
) AS v(code, label, so)
WHERE ll.code = 'DEBENTURE_TYPE'
ON CONFLICT (list_id, code) DO NOTHING;

-- CAPITAL_INCREASE_REASON
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('PUBLIC_ISSUE',   'Public issue',                                   1),
    ('PRIVATE_PLACE',  'Private placement / preferential allotment',     2),
    ('ESOP',           'ESOP',                                           3),
    ('SWEAT_EQUITY',   'Sweat equity',                                   4),
    ('CONV_PREF_DEB',  'Conversion of preference shares/debentures',     5),
    ('CONV_EQUITY',    'Conversion into equity',                         6),
    ('GDR_ADR',        'GDR/ADR',                                        7),
    ('OTHER',          'Other',                                          8)
) AS v(code, label, so)
WHERE ll.code = 'CAPITAL_INCREASE_REASON'
ON CONFLICT (list_id, code) DO NOTHING;

-- CAPITAL_DECREASE_REASON
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('BUYBACK',    'Buy-back',                      1),
    ('FORFEITURE', 'Forfeiture',                    2),
    ('REISSUE',    'Re-issue of forfeited shares',  3),
    ('REDUCTION',  'Reduction',                     4),
    ('OTHER',      'Other',                         5)
) AS v(code, label, so)
WHERE ll.code = 'CAPITAL_DECREASE_REASON'
ON CONFLICT (list_id, code) DO NOTHING;

-- SHAREHOLDER_CATEGORY
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('PROMOTER_IND',   'Promoter — Indian',                         1),
    ('PROMOTER_FOR',   'Promoter — Foreign',                        2),
    ('PUB_MF',         'Public Institution — Mutual Fund',           3),
    ('PUB_BANK',       'Public Institution — Bank/Financial Institution', 4),
    ('PUB_GOVT',       'Public Institution — Government',            5),
    ('PUB_INS',        'Public Institution — Insurance Company',     6),
    ('PUB_FII',        'Public Institution — FII',                   7),
    ('PUB_VC',         'Public Institution — Venture Capital Fund',  8),
    ('PUB_CORP',       'Public Non-Institution — Body Corporate',    9),
    ('PUB_IND',        'Public Non-Institution — Individual',       10),
    ('CUSTODIAN',      'Custodian for GDR/ADR',                     11)
) AS v(code, label, so)
WHERE ll.code = 'SHAREHOLDER_CATEGORY'
ON CONFLICT (list_id, code) DO NOTHING;

-- DESIGNATION
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('DIRECTOR',     'Director',                              1),
    ('MD',           'Managing Director',                    2),
    ('WTD',          'Whole-time Director',                  3),
    ('CHAIRMAN',     'Chairman',                             4),
    ('CMD',          'Chairman-cum-Managing Director',       5),
    ('CWMD',         'Chairman-cum-Whole-time Director',     6),
    ('ADD_DIR',      'Additional Director',                  7),
    ('ALT_DIR',      'Alternate Director',                   8),
    ('NOM_DIR',      'Nominee Director',                     9),
    ('IND_DIR',      'Independent Director',                10),
    ('PROMOTER',     'Promoter',                            11),
    ('CS',           'Company Secretary',                   12),
    ('MANAGER',      'Manager',                             13),
    ('CEO',          'CEO',                                 14),
    ('CFO',          'CFO',                                 15)
) AS v(code, label, so)
WHERE ll.code = 'DESIGNATION'
ON CONFLICT (list_id, code) DO NOTHING;

-- DIRECTOR_CATEGORY
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('INDEPENDENT', 'Independent',             1),
    ('NOMINEE',     'Nominee',                 2),
    ('ALTERNATE',   'Alternate',               3),
    ('EXECUTIVE',   'Executive Director',      4),
    ('NON_EXEC',    'Non-Executive Director',  5)
) AS v(code, label, so)
WHERE ll.code = 'DIRECTOR_CATEGORY'
ON CONFLICT (list_id, code) DO NOTHING;

-- OTHER_COMPANY_TYPE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('LISTED',      'Listed',               1),
    ('UNLISTED_PUB','Unlisted Public',       2),
    ('PRIVATE',     'Private',              3),
    ('OPC',         'One Person Company',   4)
) AS v(code, label, so)
WHERE ll.code = 'OTHER_COMPANY_TYPE'
ON CONFLICT (list_id, code) DO NOTHING;

-- AUDITOR_TYPE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('FIRST',        'First Auditor',  1),
    ('STATUTORY',    'Statutory',      2),
    ('INTERNAL',     'Internal',       3),
    ('COST',         'Cost',           4),
    ('SECRETARIAL',  'Secretarial',    5)
) AS v(code, label, so)
WHERE ll.code = 'AUDITOR_TYPE'
ON CONFLICT (list_id, code) DO NOTHING;

-- MEETING_TYPE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('BOARD',          'Board Meeting',                    1),
    ('COMMITTEE',      'Committee Meeting',                2),
    ('AGM',            'Annual General Meeting',           3),
    ('EGM',            'Extraordinary General Meeting',    4),
    ('CLASS_MEETING',  'Class Meeting',                    5),
    ('NCLT',           'NCLT/Court-convened Meeting',      6),
    ('REQUISITIONED',  'Requisitioned Meeting',            7),
    ('POSTAL_BALLOT',  'Postal Ballot',                    8)
) AS v(code, label, so)
WHERE ll.code = 'MEETING_TYPE'
ON CONFLICT (list_id, code) DO NOTHING;

-- MEETING_VENUE_MODE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('PHYSICAL', 'Physical',         1),
    ('VC',       'Video Call (VC)',  2),
    ('MIX',      'Mix of both',      3)
) AS v(code, label, so)
WHERE ll.code = 'MEETING_VENUE_MODE'
ON CONFLICT (list_id, code) DO NOTHING;

-- LEGAL_ACTION_TYPE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('PENALTY',     'Penalty',                      1),
    ('PROSECUTION', 'Punishment (Prosecution)',      2),
    ('COMPOUNDING', 'Compounding of Offence',        3)
) AS v(code, label, so)
WHERE ll.code = 'LEGAL_ACTION_TYPE'
ON CONFLICT (list_id, code) DO NOTHING;

-- AUTHORITY
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('RD',   'Regional Director',           1),
    ('NCLT', 'National Company Law Tribunal',2),
    ('COURT','Court',                        3)
) AS v(code, label, so)
WHERE ll.code = 'AUTHORITY'
ON CONFLICT (list_id, code) DO NOTHING;

-- FILING_STATUS
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('NOT_FILED',   'Not yet filed',    1),
    ('FILED_ON_TIME','Filed on time',   2),
    ('FILED_LATE',  'Filed late',       3),
    ('APPROVED',    'Approved',         4)
) AS v(code, label, so)
WHERE ll.code = 'FILING_STATUS'
ON CONFLICT (list_id, code) DO NOTHING;

-- FOREIGN_INVESTMENT_TYPE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('FC_GPR', 'New shares issued to a foreign investor (FC-GPR)', 1),
    ('FC_TRS', 'Transfer involving a foreign party (FC-TRS)',       2)
) AS v(code, label, so)
WHERE ll.code = 'FOREIGN_INVESTMENT_TYPE'
ON CONFLICT (list_id, code) DO NOTHING;

-- DIVIDEND_TYPE
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('INTERIM', 'Interim', 1),
    ('FINAL',   'Final',   2)
) AS v(code, label, so)
WHERE ll.code = 'DIVIDEND_TYPE'
ON CONFLICT (list_id, code) DO NOTHING;

-- RELATIONSHIP
INSERT INTO core.lookup_value (list_id, code, label, sort_order)
SELECT ll.id, v.code, v.label, v.so
FROM core.lookup_list ll, (VALUES
    ('HOLDING',       'Holding',               1),
    ('SUBSIDIARY',    'Subsidiary',            2),
    ('ASSOCIATE',     'Associate',             3),
    ('OTHER_RELATED', 'Other related party',   4)
) AS v(code, label, so)
WHERE ll.code = 'RELATIONSHIP'
ON CONFLICT (list_id, code) DO NOTHING;

-- ============================================================
-- DOCUMENT TYPES (common ones)
-- ============================================================
INSERT INTO core.document_type (code, name, applies_to_entity, is_mandatory, description)
VALUES
    ('BOARD_NOTICE',      'Board Meeting Notice',        'meeting',       true,  'Notice issued 7 days before board meeting per SS-1'),
    ('BOARD_AGENDA',      'Board Meeting Agenda',        'meeting',       true,  'Agenda circulated with notice'),
    ('BOARD_MINUTES',     'Board Meeting Minutes (Draft)','meeting',      true,  'Draft minutes to be prepared within 15 days'),
    ('BOARD_MINUTES_SIGNED','Board Meeting Minutes (Signed)','meeting',   true,  'Signed minutes within 30 days of the meeting'),
    ('AGM_NOTICE',        'AGM Notice',                  'meeting',       true,  '21 days notice for AGM per Sec 101'),
    ('AGM_MINUTES',       'AGM Minutes',                 'meeting',       true,  'Signed minutes of AGM'),
    ('ADT1',              'Form ADT-1',                  'government_filing',true,'Auditor appointment filing'),
    ('DIR12',             'Form DIR-12',                 'government_filing',true,'Change in directors filing'),
    ('MGT14',             'Form MGT-14',                 'government_filing',false,'Filing of resolutions and agreements'),
    ('MGT7',              'Form MGT-7 (Annual Return)',  'government_filing',true,'Annual return'),
    ('ODI_FORM',          'Form ODI',                    'odi',           true,  'Overseas Direct Investment form'),
    ('ECB1',              'Form ECB-1',                  'ecb',           true,  'External Commercial Borrowing form'),
    ('FC_GPR_FORM',       'Form FC-GPR',                 'foreign_investment',true,'Foreign investment — shares issued'),
    ('FC_TRS_FORM',       'Form FC-TRS',                 'foreign_investment',true,'Foreign investment — shares transferred'),
    ('DIR3_KYC',          'Form DIR-3 KYC',              'director',      true,  'Annual KYC for directors'),
    ('INTEREST_DISC',     'Form MBP-1 (Interest Disclosure)','director',  true,  'Director disclosure of interest'),
    ('INDEPENDENCE_DECL', 'Independence Declaration',    'director',      true,  'Declaration of independence under Sec 149(6)')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- RULE DEFINITIONS (from xlsx "When Something Becomes Required")
-- All 39 rows from the sheet.
-- ============================================================
INSERT INTO core.rule_definition (code, name, law_reference, applies_to_description, trigger_description, inputs_needed, decides, responsible_party, frequency, is_active)
VALUES
('CSR_SPENDING',        'CSR spending',
 'Companies Act, Sec 135', 'Every company',
 'Net worth >= 500 Cr OR turnover >= 1000 Cr OR net profit >= 5 Cr (previous year)',
 'Net worth, turnover, net profit (previous year) from company_financials',
 'Whether CSR spending and CSR Committee are required',
 'CSR Committee (spend > 50 lakh) or Board', 'Every year', true),

('INTERNAL_AUDITOR',    'Internal auditor',
 'Companies Act, Sec 138', 'Listed always; unlisted public/private above thresholds',
 'Listed: always. Unlisted public: paid-up >= 50 Cr OR turnover >= 200 Cr OR borrowings > 100 Cr OR deposits >= 25 Cr. Private: turnover >= 200 Cr OR borrowings > 100 Cr',
 'is_listed, paid_up_capital, turnover, borrowings, deposits from company_financials',
 'Whether an internal auditor is required',
 'Internal Auditor', 'Ongoing', true),

('AUDIT_COMMITTEE',     'Audit Committee',
 'Companies Act, Sec 177', 'Listed always; public companies above thresholds',
 'Listed: always. Public: paid-up >= 10 Cr OR turnover >= 100 Cr OR combined loans/debentures/deposits > 50 Cr',
 'is_listed, paid_up_capital, turnover, borrowings+debentures+deposits from company_financials',
 'Whether Audit Committee is required (min 3 members, majority Independent)',
 'Audit Committee', 'Ongoing', true),

('NRC_COMMITTEE',       'Nomination & Remuneration Committee',
 'Companies Act, Sec 178', 'Same as Audit Committee',
 'Same conditions as Audit Committee',
 'Same as Audit Committee',
 'Whether NRC is required (min 3 NED, half Independent)',
 'Committee', 'Ongoing', true),

('SRC_COMMITTEE',       'Stakeholders Relationship Committee',
 'Companies Act, Sec 178(5)', 'Every company',
 'Required if company has more than 1,000 shareholders/debenture/deposit holders at any point in year',
 'total_security_holders from company_financials',
 'Whether SRC is required',
 'Stakeholders Relationship Committee', 'Ongoing', true),

('RISK_COMMITTEE',      'Risk Management Committee',
 'SEBI regulations', 'Listed companies only',
 'Required for top 1,000 listed companies by market value',
 'is_listed, market_value_rank from company',
 'Whether Risk Management Committee is required',
 'Risk Management Committee', 'Ongoing', true),

('MIN_INDEPENDENT_DIR', 'Minimum number of Independent Directors',
 'Companies Act, Sec 149', 'Listed always; public above thresholds',
 'Listed: at least 1/3 board. Public: paid-up >= 10 Cr OR turnover >= 100 Cr OR borrowings > 50 Cr: at least 2 IDs',
 'is_listed, paid_up_capital, turnover, borrowings; current IDs from directorship',
 'Minimum IDs required and whether met',
 'Independent Director(s)', 'Ongoing', true),

('WOMAN_DIRECTOR',      'Woman Director',
 'Companies Act, Sec 149', 'Listed always; large public companies',
 'Listed: always. Public: paid-up >= 100 Cr OR turnover >= 300 Cr',
 'is_listed, paid_up_capital, turnover; gender of directors',
 'Whether woman director required and met',
 'A woman director on the board', 'Ongoing', true),

('RESIDENT_DIRECTOR',   'Resident director',
 'Companies Act, Sec 149', 'Every company',
 'At least one director must have been resident >182 days in the financial year',
 'director_residency.resident_over_182 for each director',
 'Whether condition is met across the board',
 'At least one director', 'Ongoing', true),

('DIRECTOR_ROTATION',   'Directors retirement by rotation',
 'Companies Act, Sec 152', 'Public companies',
 'At least 2/3 of directors (excl. IDs) must be liable to retire by rotation',
 'retires_by_rotation flag and count of directors from directorship',
 'Whether 2/3 requirement is met',
 'The Board / shareholders at each AGM', 'Checked at every AGM', true),

('ID_TENURE_LIMIT',     'Independent Director tenure limit',
 'Companies Act, Sec 149(10)/(11)', 'Every company with IDs',
 'Max 2 consecutive 5-year terms; 3-year gap needed before re-appointment',
 'independent_director_term start/end dates',
 'Total tenure served and whether limit reached',
 '—', 'Checked continuously', true),

('WHOLETIME_KMP',       'Whole-time Key Managerial Personnel',
 'Companies Act, Sec 203', 'Listed always; public with paid-up >= 10 Cr',
 'Must appoint MD/CEO/Manager or WTD, CS, and CFO',
 'is_listed, paid_up_capital; KMP designations from directorship_role',
 'Whether appointments are compulsory and in place',
 'MD/CEO/WTD, CS, CFO', 'Ongoing', true),

('WHOLETIME_CS',        'Whole-time Company Secretary',
 'Companies Act, Sec 203', 'Every company with paid-up >= 10 Cr',
 'Required if paid-up capital >= 10 Cr (including private)',
 'paid_up_capital from company_financials; CS in directorship_role',
 'Whether full-time CS is required',
 'Company Secretary', 'Ongoing', true),

('SECRETARIAL_AUDIT',   'Secretarial audit',
 'Companies Act, Sec 204', 'Listed always; public above thresholds',
 'Listed: always. Public: paid-up >= 50 Cr OR turnover >= 250 Cr OR borrowings >= 100 Cr',
 'is_listed, paid_up_capital, turnover, borrowings from company_financials',
 'Whether secretarial audit is required',
 'A practising Company Secretary', 'Every year', true),

('MIN_BOARD_MEETINGS',  'Minimum board meetings',
 'Companies Act, Sec 173', 'Every company',
 'At least 4 board meetings/year, no more than 120 days apart. Small company/OPC/dormant: 2 meetings, 90 days apart',
 'Company type from company; meeting dates from meeting',
 'Whether minimum has been met',
 'The Board', 'Every year', true),

('AGM_TIMING',          'Annual General Meeting timing',
 'Companies Act, Sec 96', 'Every company except OPC',
 'Within 6 months of FY end (9 months for first). No more than 15 months between two AGMs',
 'FY end date from company; last AGM date from meeting',
 'Due date for next AGM',
 'Shareholders', 'Every year', true),

('ANNUAL_RETURN_VERSION','Annual return version and certification',
 'Companies Act, Sec 92', 'Every company',
 'OPC/small: shorter form. Listed OR paid-up >= 10 Cr OR turnover >= 50 Cr: CS certification',
 'Company type, paid_up, turnover from company_financials',
 'Which version and whether certification needed',
 'A practising Company Secretary (for certification)', 'Every year', true),

('XBRL_FILING',         'Filing accounts in XBRL',
 'XBRL filing rules', 'Listed and their subsidiaries; large/Ind-AS companies',
 'Listed OR paid-up >= 5 Cr OR turnover >= 100 Cr OR Ind AS applies',
 'is_listed, paid_up, turnover, ind_as_applicable from company',
 'Whether XBRL filing is required',
 'The Board', 'Every year', true),

('AUDITOR_ROTATION',    'Statutory auditor rotation',
 'Companies Act, Sec 139', 'Listed; public with paid-up >= 10 Cr; private with paid-up >= 50 Cr; borrowings/deposits >= 50 Cr',
 'Rotation required after 5 or 10 years depending on type',
 'is_listed, paid_up, borrowings from company_financials; auditor term from auditor',
 'Whether rotation required and when',
 'Statutory Auditor', 'Every 5 or 10 years', true),

('SEC185_LOANS',        'Loans to directors',
 'Companies Act, Sec 185', 'Every company',
 'Generally not allowed; limited exceptions',
 'Loan type, relationship, shareholder approval from s185_loan',
 'Whether loan is allowed and on what approval',
 'Board, and shareholders where needed', 'Each time it happens', true),

('SEC186_LIMITS',       'Loans, guarantees and investments by the company',
 'Companies Act, Sec 186', 'Every company (some exceptions)',
 'Shareholder approval needed if amount > higher of 60% of (paid-up + free reserves + securities premium) or 100% of (free reserves + securities premium)',
 'paid_up, free_reserves, securities_premium from company_financials; running total from s186_transaction',
 'Whether shareholder approval needed and maximum allowed',
 'Board (unanimous), then shareholders if needed', 'Each time it happens', true),

('SEC180_BORROWING',    'Borrowing beyond limit / selling major part of business',
 'Companies Act, Sec 180', 'Every company',
 'Shareholder approval if total borrowings exceed paid-up + free reserves + securities premium',
 'paid_up, free_reserves, securities_premium, borrowings from company_financials',
 'Whether shareholder approval needed',
 'Shareholders', 'Each time it happens', true),

('SEC188_RPT',          'Related party transactions',
 'Companies Act, Sec 188', 'Every company',
 'Audit Committee + Board approval; shareholder approval above value thresholds',
 'Transaction value, turnover, net_worth from company_financials; s188_related_party_txn',
 'Which level of approval is needed',
 'Audit Committee, Board, then shareholders if needed', 'Each time it happens', true),

('SBO',                 'Beneficial owners (SBO)',
 'Companies Act, Sec 90', 'Every company',
 'Applies if individual holds 10%+ beneficial interest indirectly',
 'Ownership chain behind shareholdings from shareholding',
 'Whether beneficial-owner filing is needed',
 'The Board', 'Whenever it happens', true),

('DEPOSITS_RETURN',     'Return of deposits',
 'Companies Act, Sec 73', 'Every company',
 'Yearly return due by 30 June each year',
 'Deposit amounts from loan_deposit',
 'Whether return is due',
 'The Board', 'Every year', true),

('FOREIGN_INV_REPORTING','Foreign investment reporting',
 'FEMA regulations', 'Any company with foreign investment',
 'FC-GPR: file within 30 days of allotment; FC-TRS: file within 60 days of funds receipt',
 'Allotment date / funds received date from foreign_investment',
 'Filing due date and whether met',
 'The Board / company secretary', 'Each time it happens', true),

('DEMAT_SHARES',        'Holding shares only in demat form',
 'Companies Act rules', 'Unlisted public always; certain private above threshold',
 'Unlisted public: must hold in demat. Private (non-small): move to demat by deadline',
 'Company type from company',
 'Whether company must move to demat-only shares',
 'Board, with help from share registrar', 'Ongoing', true),

('BRSR',                'Business Responsibility and Sustainability Report (BRSR)',
 'SEBI LODR Regulations', 'Listed companies only',
 'Required for top 1,000 listed companies by market value',
 'is_listed, market_value_rank from company',
 'Whether BRSR is required',
 'The Board', 'Every year', true),

('DIVIDEND_POLICY',     'Dividend Distribution Policy',
 'SEBI LODR Regulations', 'Listed companies only',
 'Required for top 1,000 listed companies by market value',
 'is_listed, market_value_rank from company',
 'Whether formal dividend policy must be in place',
 'The Board', 'Once, reviewed periodically', true),

('INDEP_WOMAN_DIR',     'At least one Independent Woman Director',
 'SEBI LODR Regulations', 'Listed companies only',
 'Required for top 1,000 listed companies',
 'is_listed, market_value_rank; gender and independence of directors',
 'Whether this specific requirement is met',
 'An Independent Woman Director', 'Ongoing', true),

('VIGIL_MECHANISM',     'Vigil mechanism (whistle-blower policy)',
 'Companies Act, Sec 177(9)', 'Listed; deposit-accepting; borrowings > 50 Cr',
 'Required if listed OR accepts deposits OR borrowings > 50 Cr from banks/FIs',
 'is_listed, deposits, borrowings from company_financials',
 'Whether vigil mechanism is required',
 'Audit Committee (or Board if no Audit Committee)', 'Once, then ongoing', true),

('MAX_DIRECTORSHIPS',   'Limit on total directorships held by one person',
 'Companies Act, Sec 165; SEBI LODR Regulations', 'Every director',
 'Max 20 companies total; max 10 public. Listed: ID in max 7 listed (or 3 if WTD anywhere)',
 'All directorships per director from director_other_directorship',
 'Whether any director has crossed the limit',
 'Each director, self-reporting', 'Checked continuously', true),

('EVOTING',             'Electronic voting (e-voting) facility',
 'Companies Act, Sec 108', 'Listed; company with >= 1,000 shareholders',
 'Listed OR >= 1,000 shareholders: must offer e-voting at general meetings',
 'is_listed, total_security_holders from company_financials',
 'Whether e-voting must be offered',
 'The Board / RTA', 'Each general meeting', true),

('MGRL_REMUNERATION',   'Limit on managerial remuneration',
 'Companies Act, Sec 197', 'Public companies',
 'Total to all MDs/WTDs/Managers cannot exceed 11% of net profit; single person 5%, multiple 10% (without special res)',
 'Net profit from company_financials; remuneration paid from remuneration',
 'Whether remuneration is within limit or needs special resolution',
 'Board / shareholders (special res if limit crossed)', 'Every year', true),

('BUYBACK_LIMIT',       'Limit on buy-back of shares',
 'Companies Act, Sec 68', 'Every company',
 'Cannot buy back > 25% of paid-up capital + free reserves; equity alone not > 25% of paid-up equity; debt:equity not > 2:1 after buy-back',
 'paid_up, free_reserves from company_financials',
 'Maximum amount company can buy back',
 'Board / shareholders depending on amount', 'Each time proposed', true),

('SUBSIDIARY_LAYERS',   'Limit on layers of subsidiaries',
 'Companies Act, Sec 2(87) and rules', 'Every company (some exceptions)',
 'Cannot have more than 2 layers of subsidiaries below it',
 'Holding-subsidiary structure from company_relationship',
 'Whether group structure breaches layer limit',
 'Board of holding company', 'Checked when structure changes', true),

('SECRETARIAL_STANDARDS','Secretarial Standards compliance',
 'Companies Act, Sec 118(10)', 'Every company',
 'Must follow SS-1 (board meetings) and SS-2 (general meetings)',
 'Meeting records from meeting',
 'Whether meetings conducted and documented per Standards',
 'Company Secretary', 'Every meeting', true),

('DEBENTURE_REDEMP_RESERVE','Debenture Redemption Reserve',
 'Companies Act, Sec 71', 'Companies that have issued debentures',
 'Certain companies must set aside a reserve — percentage and exemptions vary (verify current requirements)',
 'Debentures outstanding from capital_snapshot',
 'Whether reserve is required and how much',
 'The Board', 'Every year while debentures outstanding', true),

('REGISTERED_VALUER',   'Registered valuer required',
 'Companies Act, Sec 247', 'Every company for specified transactions',
 'Required for preferential issue, merger, Sec 192 transactions etc.',
 'Transaction type from allotment / share_transfer / foreign_investment',
 'Whether valuation report required before proceeding',
 'Board, supported by a Registered Valuer', 'Each time such transaction happens', true)
ON CONFLICT (code) DO NOTHING;
