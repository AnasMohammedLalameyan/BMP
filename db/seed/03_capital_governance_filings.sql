-- db/seed/03_capital_governance_filings.sql
-- Share classes, capital, shareholdings, meetings, committees, filings, related-party, loans.

DO $$
DECLARE
    -- Companies
    v_c1 bigint; v_c2 bigint; v_c3 bigint; v_c4 bigint; v_c5 bigint;
    -- Directors
    v_d1 bigint; v_d2 bigint; v_d3 bigint; v_d4 bigint; v_d5 bigint;
    v_d6 bigint; v_d7 bigint; v_d8 bigint; v_d9 bigint; v_d10 bigint;
    v_d11 bigint; v_d12 bigint;
    -- Lookup values
    v_eq_class bigint; v_physical bigint; v_board_type bigint; v_agm_type bigint;
    v_not_filed bigint; v_filed_ot bigint; v_filed_late bigint;
    v_promoter_ind bigint; v_pub_ind bigint; v_pub_foreign bigint;
    v_penalty_lv bigint; v_nclt bigint;
    v_relationship_sub bigint;
    -- Directorships (current)
    v_dst_c1_arjun bigint; v_dst_c1_sunita bigint; v_dst_c1_prashant bigint;
    v_dst_c2_rajan bigint; v_dst_c2_nalini bigint; v_dst_c2_prashant bigint;
    v_dst_c3_anil bigint; v_dst_c3_kavitha bigint; v_dst_c3_devraj bigint; v_dst_c3_vikram bigint;
    v_dst_c4_vikram bigint; v_dst_c4_sunita bigint; v_dst_c4_thomas bigint;
    -- Misc
    v_class_c1 bigint; v_class_c2 bigint; v_class_c4 bigint; v_class_c5 bigint;
    v_sh_promoter_c1 bigint; v_sh_promoter_c2 bigint; v_sh_promoter_c5 bigint;
    v_sh_foreign bigint;
    v_sh2_c1 bigint; v_sh3_c2 bigint;
    v_meet_c2_bm1 bigint; v_meet_c2_bm2 bigint; v_meet_c2_bm3 bigint; v_meet_c2_agm bigint;
    v_audit_comm bigint;
    v_filing_c2_dir12 bigint; v_filing_c2_mgt7 bigint; v_filing_overdue bigint;
    v_allot_c5 bigint; v_transfer_c1 bigint;
    v_venue_vc bigint;
    v_rpt_nature bigint;
BEGIN
    -- Set session user for audit
    PERFORM set_config('app.current_user_id', (SELECT id FROM core.app_user WHERE email='seed@system.internal')::text, false);

    -- Resolve IDs
    SELECT id INTO v_c1 FROM core.company WHERE cin = 'U72200DL2015PTC112001';
    SELECT id INTO v_c2 FROM core.company WHERE cin = 'L24100MH2010PLC178002';
    SELECT id INTO v_c3 FROM core.company WHERE cin = 'L45200KA2005PLC134003';
    SELECT id INTO v_c4 FROM core.company WHERE cin = 'L62010MH2000PLC156004';
    SELECT id INTO v_c5 FROM core.company WHERE cin = 'U74110MH2018PTC201005';

    SELECT id INTO v_d1  FROM core.director WHERE din = '12340001';
    SELECT id INTO v_d2  FROM core.director WHERE din = '12340002';
    SELECT id INTO v_d3  FROM core.director WHERE din = '12340003';
    SELECT id INTO v_d4  FROM core.director WHERE din = '12340004';
    SELECT id INTO v_d5  FROM core.director WHERE din = '12340005';
    SELECT id INTO v_d6  FROM core.director WHERE din = '12340006';
    SELECT id INTO v_d7  FROM core.director WHERE din = '12340007';
    SELECT id INTO v_d8  FROM core.director WHERE din = '12340008';
    SELECT id INTO v_d9  FROM core.director WHERE din = '12340009';
    SELECT id INTO v_d10 FROM core.director WHERE din = '12340010';
    SELECT id INTO v_d11 FROM core.director WHERE din = '12340011';
    SELECT id INTO v_d12 FROM core.director WHERE din = '12340012';

    -- Lookup IDs
    SELECT lv.id INTO v_eq_class    FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='CLASS_OF_SHARES'   AND lv.code='EQUITY';
    SELECT lv.id INTO v_physical    FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='MEETING_VENUE_MODE' AND lv.code='PHYSICAL';
    SELECT lv.id INTO v_venue_vc    FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='MEETING_VENUE_MODE' AND lv.code='VC';
    SELECT lv.id INTO v_board_type  FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='MEETING_TYPE'       AND lv.code='BOARD';
    SELECT lv.id INTO v_agm_type    FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='MEETING_TYPE'       AND lv.code='AGM';
    SELECT lv.id INTO v_not_filed   FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='FILING_STATUS'      AND lv.code='NOT_FILED';
    SELECT lv.id INTO v_filed_ot    FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='FILING_STATUS'      AND lv.code='FILED_ON_TIME';
    SELECT lv.id INTO v_filed_late  FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='FILING_STATUS'      AND lv.code='FILED_LATE';
    SELECT lv.id INTO v_promoter_ind FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='SHAREHOLDER_CATEGORY' AND lv.code='PROMOTER_IND';
    SELECT lv.id INTO v_pub_ind     FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='SHAREHOLDER_CATEGORY' AND lv.code='PUB_IND';
    SELECT lv.id INTO v_pub_foreign FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='SHAREHOLDER_CATEGORY' AND lv.code='PROMOTER_FOR';
    SELECT lv.id INTO v_penalty_lv  FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='LEGAL_ACTION_TYPE'  AND lv.code='PENALTY';
    SELECT lv.id INTO v_nclt        FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='AUTHORITY'          AND lv.code='NCLT';
    SELECT lv.id INTO v_relationship_sub FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='RELATIONSHIP'  AND lv.code='SUBSIDIARY';

    -- Directorship IDs
    SELECT id INTO v_dst_c1_arjun   FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d1 AND end_date IS NULL;
    SELECT id INTO v_dst_c1_sunita  FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d2 AND end_date IS NULL;
    SELECT id INTO v_dst_c1_prashant FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d12 AND end_date IS NULL;
    SELECT id INTO v_dst_c2_rajan   FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d5 AND end_date IS NULL;
    SELECT id INTO v_dst_c2_nalini  FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d6 AND end_date IS NULL;
    SELECT id INTO v_dst_c2_prashant FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d12 AND end_date IS NULL;
    SELECT id INTO v_dst_c3_anil    FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d8 AND end_date IS NULL;
    SELECT id INTO v_dst_c3_kavitha FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d4 AND end_date IS NULL;
    SELECT id INTO v_dst_c3_devraj  FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d3 AND end_date IS NULL;
    SELECT id INTO v_dst_c3_vikram  FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d7 AND end_date IS NULL;
    SELECT id INTO v_dst_c4_vikram  FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d7 AND end_date IS NULL;
    SELECT id INTO v_dst_c4_sunita  FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d2 AND end_date IS NULL;
    SELECT id INTO v_dst_c4_thomas  FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d10 AND end_date IS NULL;

    -- ===========================================================
    -- SHARE CLASSES
    -- ===========================================================
    INSERT INTO core.share_class (company_id, class_id, nominal_value, description)
    VALUES (v_c1, v_eq_class, 10, 'Equity shares of Nexatech'), (v_c2, v_eq_class, 10, 'Equity shares of BrightMed'),
           (v_c4, v_eq_class,  1, 'Equity shares of Skyward'), (v_c5, v_eq_class, 10, 'Equity shares of Indovance')
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_class_c1 FROM core.share_class WHERE company_id=v_c1 AND class_id=v_eq_class;
    SELECT id INTO v_class_c2 FROM core.share_class WHERE company_id=v_c2 AND class_id=v_eq_class;
    SELECT id INTO v_class_c4 FROM core.share_class WHERE company_id=v_c4 AND class_id=v_eq_class;
    SELECT id INTO v_class_c5 FROM core.share_class WHERE company_id=v_c5 AND class_id=v_eq_class;

    -- ===========================================================
    -- CAPITAL SNAPSHOTS (two FYs for Nexatech)
    -- ===========================================================
    INSERT INTO core.capital_snapshot (company_id, share_class_id, financial_year, snapshot_type,
        as_of_date, authorised_shares, authorised_amount, issued_shares, issued_amount,
        subscribed_shares, subscribed_amount, paid_up_shares, paid_up_amount)
    VALUES
        (v_c1, v_class_c1, '2023-24', 'opening', '2023-04-01', 1000000, 10000000, 500000, 5000000, 500000, 5000000, 500000, 5000000),
        (v_c1, v_class_c1, '2023-24', 'closing', '2024-03-31', 1000000, 10000000, 500000, 5000000, 500000, 5000000, 500000, 5000000),
        (v_c1, v_class_c1, '2024-25', 'opening', '2024-04-01', 1000000, 10000000, 500000, 5000000, 500000, 5000000, 500000, 5000000),
        (v_c1, v_class_c1, '2024-25', 'closing', '2025-03-31', 1000000, 10000000, 550000, 5500000, 550000, 5500000, 550000, 5500000),
        -- BrightMed
        (v_c2, v_class_c2, '2024-25', 'opening', '2024-04-01', 2000000, 20000000, 1500000, 15000000, 1500000, 15000000, 1500000, 15000000),
        (v_c2, v_class_c2, '2024-25', 'closing', '2025-03-31', 2000000, 20000000, 1500000, 15000000, 1500000, 15000000, 1500000, 15000000),
        -- Skyward
        (v_c4, v_class_c4, '2024-25', 'opening', '2024-04-01', 600000000, 600000000, 450000000, 450000000, 450000000, 450000000, 450000000, 450000000),
        (v_c4, v_class_c4, '2024-25', 'closing', '2025-03-31', 600000000, 600000000, 450000000, 450000000, 450000000, 450000000, 450000000, 450000000)
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- SHAREHOLDERS
    -- ===========================================================
    INSERT INTO core.shareholder (name, pan, email, category_id, is_foreign, country)
    VALUES
        ('Arjun Kapoor (HUF)',   'ABCAK1001A', 'arjun.kapoor@mail.in',   v_promoter_ind, false, 'India'),
        ('Rajan Patel',          'ABCRP5005E', 'rajan.patel@mail.in',    v_promoter_ind, false, 'India'),
        ('Vikram Singh',         'ABCVS7007G', 'vikram.singh@mail.in',   v_promoter_ind, false, 'India'),
        ('General Public - A',   NULL,          'public1@mail.in',        v_pub_ind,      false, 'India'),
        ('Alpine Capital GmbH',  NULL,          'alpine@alpine.de',       v_pub_foreign,  true, 'Germany')
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_sh_promoter_c1 FROM core.shareholder WHERE name = 'Arjun Kapoor (HUF)';
    SELECT id INTO v_sh_promoter_c2 FROM core.shareholder WHERE name = 'Rajan Patel';
    SELECT id INTO v_sh_promoter_c5 FROM core.shareholder WHERE name = 'Vikram Singh';
    SELECT id INTO v_sh2_c1         FROM core.shareholder WHERE name = 'General Public - A';
    SELECT id INTO v_sh_foreign     FROM core.shareholder WHERE name = 'Alpine Capital GmbH';

    -- ===========================================================
    -- SHAREHOLDING (history with one change for Nexatech)
    -- ===========================================================
    -- Original holding (closed when new shares allotted)
    INSERT INTO core.shareholding (company_id, shareholder_id, share_class_id, folio_number, is_demat,
        number_of_shares, face_value, valid_from, valid_to)
    VALUES
        (v_c1, v_sh_promoter_c1, v_class_c1, 'NEX001', false, 400000, 10, '2015-03-12', '2025-01-15'),
        (v_c1, v_sh2_c1,         v_class_c1, 'NEX002', false, 100000, 10, '2015-03-12', NULL),
        (v_c2, v_sh_promoter_c2, v_class_c2, 'BRM001', true,  900000, 10, '2010-07-22', NULL),
        (v_c2, v_sh2_c1,         v_class_c2, 'BRM002', true,  600000, 10, '2010-07-22', NULL),
        (v_c5, v_sh_promoter_c5, v_class_c5, 'IND001', false, 100000, 10, '2018-11-05', NULL),
        (v_c5, v_sh_foreign,     v_class_c5, 'IND002', false,  50000, 10, '2022-03-01', NULL)
    ON CONFLICT DO NOTHING;

    -- New holding for Arjun after allotment on 2025-01-16
    INSERT INTO core.shareholding (company_id, shareholder_id, share_class_id, folio_number, is_demat,
        number_of_shares, face_value, valid_from)
    SELECT v_c1, v_sh_promoter_c1, v_class_c1, 'NEX001', false, 450000, 10, '2025-01-16'
    WHERE NOT EXISTS (
        SELECT 1 FROM core.shareholding WHERE company_id=v_c1 AND shareholder_id=v_sh_promoter_c1
          AND valid_from='2025-01-16');

    -- ===========================================================
    -- MEETINGS (BrightMed: 3 board meetings + 1 AGM)
    -- ===========================================================
    INSERT INTO core.meeting (company_id, meeting_type_id, financial_year, meeting_number,
        meeting_date, start_time, end_time, venue, venue_mode_id, status,
        chairperson_directorship_id)
    VALUES
        (v_c2, v_board_type, '2024-25', 'BM-1', '2024-05-10', '10:00', '12:00',
         '5th Floor, Nariman Point, Mumbai', v_physical, 'held', v_dst_c2_rajan),
        (v_c2, v_board_type, '2024-25', 'BM-2', '2024-08-22', '11:00', '13:00',
         'VC - Mumbai Office', v_venue_vc, 'held', v_dst_c2_rajan),
        (v_c2, v_board_type, '2024-25', 'BM-3', '2024-11-15', '10:30', '12:30',
         '5th Floor, Nariman Point, Mumbai', v_physical, 'held', v_dst_c2_rajan),
        (v_c2, v_agm_type, '2024-25', 'AGM 1', '2024-09-25', '11:00', '14:00',
         '5th Floor, Nariman Point, Mumbai', v_physical, 'held', v_dst_c2_rajan)
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_meet_c2_bm1 FROM core.meeting WHERE company_id=v_c2 AND meeting_number='BM-1';
    SELECT id INTO v_meet_c2_bm2 FROM core.meeting WHERE company_id=v_c2 AND meeting_number='BM-2';
    SELECT id INTO v_meet_c2_bm3 FROM core.meeting WHERE company_id=v_c2 AND meeting_number='BM-3';
    SELECT id INTO v_meet_c2_agm FROM core.meeting WHERE company_id=v_c2 AND meeting_number='AGM 1';

    -- Agenda items
    INSERT INTO core.meeting_agenda_item (meeting_id, item_no, text)
    VALUES
        (v_meet_c2_bm1, 1, 'To note the minutes of the previous board meeting'),
        (v_meet_c2_bm1, 2, 'To approve the audited financial statements for FY 2023-24'),
        (v_meet_c2_bm1, 3, 'To consider declaration of interim dividend'),
        (v_meet_c2_bm2, 1, 'Review of Q1 financial results for FY 2024-25'),
        (v_meet_c2_bm2, 2, 'To approve related party transactions under Sec 188'),
        (v_meet_c2_bm3, 1, 'Review of half-yearly financial performance'),
        (v_meet_c2_bm3, 2, 'To consider increase in borrowing limits'),
        (v_meet_c2_agm, 1, 'To receive and adopt the Directors Report and Audited Financial Statements'),
        (v_meet_c2_agm, 2, 'To declare final dividend for FY 2023-24'),
        (v_meet_c2_agm, 3, 'To re-appoint director retiring by rotation')
    ON CONFLICT DO NOTHING;

    -- Attendance for BM-1 (all 3 directors present)
    INSERT INTO core.meeting_attendance (meeting_id, attendee_type, directorship_id, attended, mode)
    VALUES
        (v_meet_c2_bm1, 'director', v_dst_c2_rajan,    true,  'Physical'),
        (v_meet_c2_bm1, 'director', v_dst_c2_nalini,   true,  'Physical'),
        (v_meet_c2_bm1, 'director', v_dst_c2_prashant, true,  'Physical'),
        (v_meet_c2_bm2, 'director', v_dst_c2_rajan,    true,  'VC'),
        (v_meet_c2_bm2, 'director', v_dst_c2_nalini,   true,  'VC'),
        (v_meet_c2_bm2, 'director', v_dst_c2_prashant, false, 'VC'),
        (v_meet_c2_bm3, 'director', v_dst_c2_rajan,    true,  'Physical'),
        (v_meet_c2_bm3, 'director', v_dst_c2_nalini,   false, 'Physical'),
        (v_meet_c2_bm3, 'director', v_dst_c2_prashant, true,  'Physical'),
        (v_meet_c2_agm, 'director', v_dst_c2_rajan,    true,  'Physical'),
        (v_meet_c2_agm, 'director', v_dst_c2_nalini,   true,  'Physical'),
        (v_meet_c2_agm, 'director', v_dst_c2_prashant, false, 'Physical')
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- COMMITTEE (BrightMed Audit Committee)
    -- ===========================================================
    INSERT INTO core.committee (company_id, name, constituted_on, description)
    VALUES (v_c2, 'Audit Committee', '2018-01-15', 'Constituted under Sec 177 of Companies Act 2013')
    ON CONFLICT DO NOTHING;
    SELECT id INTO v_audit_comm FROM core.committee WHERE company_id=v_c2 AND name='Audit Committee';

    INSERT INTO core.committee_member (committee_id, directorship_id, is_chairperson, start_date)
    VALUES
        (v_audit_comm, v_dst_c2_nalini,   true,  '2018-01-15'),
        (v_audit_comm, v_dst_c2_prashant, false, '2023-07-01'),
        (v_audit_comm, v_dst_c2_rajan,    false, '2018-01-15')
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- CIRCULAR RESOLUTION (Nexatech)
    -- ===========================================================
    INSERT INTO core.circular_resolution (company_id, reference, circulated_on, subject, text, passed_on)
    VALUES (v_c1, 'CR/2024-25/001', '2024-12-01',
            'Approval for new banking relationship',
            'Resolved that the company be authorised to open a current account with Axis Bank Limited at its Connaught Place branch for operational purposes.',
            '2024-12-03')
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- GOVERNMENT FILINGS (BrightMed) — one overdue
    -- ===========================================================
    INSERT INTO core.government_filing (company_id, form_name, description, financial_year,
        due_date, filing_date, srn, fee_paid, status_id)
    VALUES
        (v_c2, 'ADT-1', 'Auditor appointment notification', '2024-25', '2024-10-14', '2024-10-12', 'SRN00001234', 300.00, v_filed_ot),
        (v_c2, 'MGT-7', 'Annual Return for FY 2024-25',    '2024-25', '2025-11-29', NULL, NULL, NULL, v_not_filed),
        (v_c2, 'DIR-12','Change in directors - Prashant reappointment', '2024-25', '2023-07-31', '2023-08-15', 'SRN00005678', 600.00, v_filed_late)
    ON CONFLICT DO NOTHING;

    -- One overdue filing for demo (Nexatech — annual return from last year still not filed)
    INSERT INTO core.government_filing (company_id, form_name, description, financial_year,
        due_date, filing_date, status_id)
    VALUES (v_c1, 'MGT-7', 'Annual Return for FY 2023-24', '2023-24', '2024-11-29', NULL, v_not_filed)
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- RELATED PARTY TRANSACTION (BrightMed — Sec 188)
    -- ===========================================================
    INSERT INTO core.s188_related_party_txn (company_id, financial_year, related_party_name,
        relationship_type_id, nature_of_txn, transaction_value, is_ordinary_course, is_arms_length,
        audit_committee_approval_date, board_meeting_id)
    VALUES
        (v_c2, '2024-25', 'Patel Trading Company (Rajan Patel - Director)',
         v_relationship_sub,
         'Supply of raw materials for manufacturing',
         12500000, true, true, '2024-08-10', v_meet_c2_bm2)
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- LOAN/DEPOSIT (BrightMed)
    -- ===========================================================
    INSERT INTO core.loan_deposit (company_id, financial_year, borrowing_type,
        opening_principal, added_during_year, reduced_during_year, closing_principal)
    VALUES
        (v_c2, '2024-25', 'Secured loans (excluding deposits)',
         90000000, 20000000, 30000000, 80000000),
        (v_c2, '2024-25', 'Unsecured loans',
         10000000, 0, 0, 10000000)
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- REMUNERATION (BrightMed)
    -- ===========================================================
    INSERT INTO core.remuneration (company_id, financial_year, directorship_id, person_name,
        salary, sitting_fees, commission)
    VALUES
        (v_c2, '2024-25', v_dst_c2_rajan,    'Rajan Patel',   3600000, NULL, 500000),
        (v_c2, '2024-25', v_dst_c2_nalini,   'Nalini Sharma', NULL,    80000, NULL),
        (v_c2, '2024-25', v_dst_c2_prashant, 'Prashant Joshi',NULL,    40000, NULL)
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- ALLOTMENT (Nexatech — new shares in Jan 2025, coinciding with shareholding change)
    -- ===========================================================
    INSERT INTO core.allotment (company_id, round_reference, shareholder_id, share_class_id,
        number_of_shares, allotment_date, face_value, premium_per_share, issue_price,
        face_value_amount, premium_amount, total_amount)
    VALUES (v_c1, 'Rights Issue 1', v_sh_promoter_c1, v_class_c1,
            50000, '2025-01-16', 10, 40, 50, 500000, 2000000, 2500000)
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- FOREIGN INVESTMENT (Indovance — FC-GPR for Alpine Capital)
    -- ===========================================================
    DECLARE
        v_fi_type_gpr bigint;
        v_allot_c5_id bigint;
    BEGIN
        SELECT lv.id INTO v_fi_type_gpr FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='FOREIGN_INVESTMENT_TYPE' AND lv.code='FC_GPR';

        INSERT INTO core.allotment (company_id, round_reference, shareholder_id, share_class_id,
            number_of_shares, allotment_date, face_value, premium_per_share, issue_price,
            face_value_amount, premium_amount, total_amount)
        VALUES (v_c5, 'Series A - Foreign', v_sh_foreign, v_class_c5,
                50000, '2022-03-01', 10, 140, 150, 500000, 7000000, 7500000)
        ON CONFLICT DO NOTHING;

        SELECT id INTO v_allot_c5_id FROM core.allotment WHERE company_id=v_c5 AND round_reference='Series A - Foreign';

        INSERT INTO core.foreign_investment (company_id, type_id, allotment_id,
            foreign_currency, foreign_amount, conversion_rate, amount_inr,
            firc_number, ad_bank, board_approval_date, funds_received_date,
            filing_due_date, filing_date, status_id)
        VALUES (v_c5, v_fi_type_gpr, v_allot_c5_id,
                'EUR', 90000, 83.25, 7492500,
                'FIRC20220301001', 'ICICI Bank Ltd, Fort Branch, Mumbai',
                '2022-01-20', '2022-02-28', '2022-03-31', '2022-03-28', v_filed_ot)
        ON CONFLICT DO NOTHING;
    END;

    -- ===========================================================
    -- PENALTY RECORD (Nexatech — minor penalty for late filing)
    -- ===========================================================
    INSERT INTO core.penalty_action (company_id, relates_to, action_type_id,
        section, description, amount, authority_id, appealed)
    VALUES (v_c1, 'company', v_penalty_lv,
            'Sec 137', 'Late filing of financial statements (Form AOC-4) for FY 2022-23',
            1500, v_nclt, false)
    ON CONFLICT DO NOTHING;

    -- ===========================================================
    -- RULE EVALUATIONS (sample — manually entered for demo)
    -- ===========================================================
    DECLARE v_rule_resident bigint; v_rule_woman bigint; v_rule_src bigint;
    BEGIN
        SELECT id INTO v_rule_resident FROM core.rule_definition WHERE code='RESIDENT_DIRECTOR';
        SELECT id INTO v_rule_woman    FROM core.rule_definition WHERE code='WOMAN_DIRECTOR';
        SELECT id INTO v_rule_src      FROM core.rule_definition WHERE code='SRC_COMMITTEE';

        INSERT INTO core.rule_evaluation (company_id, rule_id, financial_year, applies, status, notes)
        VALUES
            (v_c1, v_rule_resident, '2024-25', true, 'met', 'Arjun Kapoor resident >182 days'),
            (v_c1, v_rule_woman,    '2024-25', false, 'not_applicable', 'Small private company below listed / turnover threshold'),
            (v_c1, v_rule_src,      '2024-25', false, 'not_applicable', 'Only 12 security holders; threshold is 1000'),
            (v_c2, v_rule_resident, '2024-25', true, 'met', 'Rajan Patel resident >182 days'),
            (v_c2, v_rule_woman,    '2024-25', false, 'action_required', 'Public company, no woman director currently on board'),
            (v_c4, v_rule_src,      '2024-25', true, 'met', 'Listed company with 16500 security holders; SRC constituted')
        ON CONFLICT DO NOTHING;
    END;

END $$;
