-- db/seed/05_required_seed_completion.sql
-- Completes the seed data required by guidelines.md section 8 that files 01-04 left out:
--   * a large public company above Rs 50 crore paid-up capital (Greenfield: Rs 60 crore)
--   * capital snapshots for two financial years for every company that has a share class
--   * one share transfer (BrightMed, approved at board meeting BM-2), with the matching
--     shareholding change (old holding rows closed, new rows opened)
--   * one independent director with a first term (and a second term) so that
--     core.v_independent_director_years returns data
-- All data is fictional. Every insert is guarded so that running this file twice adds nothing.

DO $$
DECLARE
    v_c2 bigint; v_c3 bigint; v_c4 bigint; v_c5 bigint;
    v_eq_class bigint;
    v_class_c2 bigint; v_class_c3 bigint; v_class_c4 bigint; v_class_c5 bigint;
    v_rajan bigint; v_public bigint;
    v_meet_bm2 bigint;
    v_dst_nalini bigint;
BEGIN
    PERFORM set_config('app.current_user_id',
        (SELECT id FROM core.app_user WHERE email = 'seed@system.internal')::text, false);

    SELECT id INTO v_c2 FROM core.company WHERE cin = 'L24100MH2010PLC178002';  -- BrightMed
    SELECT id INTO v_c3 FROM core.company WHERE cin = 'L45200KA2005PLC134003';  -- Greenfield
    SELECT id INTO v_c4 FROM core.company WHERE cin = 'L62010MH2000PLC156004';  -- Skyward
    SELECT id INTO v_c5 FROM core.company WHERE cin = 'U74110MH2018PTC201005';  -- Indovance

    SELECT lv.id INTO v_eq_class
      FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id
     WHERE ll.code = 'CLASS_OF_SHARES' AND lv.code = 'EQUITY';

    -- ------------------------------------------------------------------
    -- Greenfield needs a share class before it can have capital snapshots
    -- ------------------------------------------------------------------
    INSERT INTO core.share_class (company_id, class_id, nominal_value, description)
    SELECT v_c3, v_eq_class, 10, 'Equity shares of Greenfield'
    WHERE NOT EXISTS (SELECT 1 FROM core.share_class WHERE company_id = v_c3 AND class_id = v_eq_class);

    SELECT id INTO v_class_c2 FROM core.share_class WHERE company_id = v_c2 AND class_id = v_eq_class;
    SELECT id INTO v_class_c3 FROM core.share_class WHERE company_id = v_c3 AND class_id = v_eq_class;
    SELECT id INTO v_class_c4 FROM core.share_class WHERE company_id = v_c4 AND class_id = v_eq_class;
    SELECT id INTO v_class_c5 FROM core.share_class WHERE company_id = v_c5 AND class_id = v_eq_class;

    -- ------------------------------------------------------------------
    -- Capital snapshots (amounts in INR; Greenfield paid-up = Rs 60 crore)
    -- ------------------------------------------------------------------
    INSERT INTO core.capital_snapshot (company_id, share_class_id, financial_year, snapshot_type, as_of_date,
        authorised_shares, authorised_amount, issued_shares, issued_amount,
        subscribed_shares, subscribed_amount, paid_up_shares, paid_up_amount)
    SELECT v.company_id, v.share_class_id, v.fy, v.stype, v.as_of,
           v.auth_sh, v.auth_amt, v.iss_sh, v.iss_amt, v.iss_sh, v.iss_amt, v.iss_sh, v.iss_amt
    FROM (VALUES
        -- Greenfield (large public company, > Rs 50 crore paid-up): both years
        (v_c3, v_class_c3, '2023-24', 'opening', DATE '2023-04-01', 75000000::bigint, 750000000::numeric, 60000000::bigint, 600000000::numeric),
        (v_c3, v_class_c3, '2023-24', 'closing', DATE '2024-03-31', 75000000::bigint, 750000000::numeric, 60000000::bigint, 600000000::numeric),
        (v_c3, v_class_c3, '2024-25', 'opening', DATE '2024-04-01', 75000000::bigint, 750000000::numeric, 60000000::bigint, 600000000::numeric),
        (v_c3, v_class_c3, '2024-25', 'closing', DATE '2025-03-31', 75000000::bigint, 750000000::numeric, 60000000::bigint, 600000000::numeric),
        -- Indovance (150,000 shares issued = 100,000 + 50,000 foreign): both years
        (v_c5, v_class_c5, '2023-24', 'opening', DATE '2023-04-01', 200000::bigint, 2000000::numeric, 150000::bigint, 1500000::numeric),
        (v_c5, v_class_c5, '2023-24', 'closing', DATE '2024-03-31', 200000::bigint, 2000000::numeric, 150000::bigint, 1500000::numeric),
        (v_c5, v_class_c5, '2024-25', 'opening', DATE '2024-04-01', 200000::bigint, 2000000::numeric, 150000::bigint, 1500000::numeric),
        (v_c5, v_class_c5, '2024-25', 'closing', DATE '2025-03-31', 200000::bigint, 2000000::numeric, 150000::bigint, 1500000::numeric),
        -- BrightMed: add the earlier year (2024-25 already seeded in file 03)
        (v_c2, v_class_c2, '2023-24', 'opening', DATE '2023-04-01', 2000000::bigint, 20000000::numeric, 1500000::bigint, 15000000::numeric),
        (v_c2, v_class_c2, '2023-24', 'closing', DATE '2024-03-31', 2000000::bigint, 20000000::numeric, 1500000::bigint, 15000000::numeric),
        -- Skyward: add the earlier year (nominal value Rs 1 per share)
        (v_c4, v_class_c4, '2023-24', 'opening', DATE '2023-04-01', 600000000::bigint, 600000000::numeric, 450000000::bigint, 450000000::numeric),
        (v_c4, v_class_c4, '2023-24', 'closing', DATE '2024-03-31', 600000000::bigint, 600000000::numeric, 450000000::bigint, 450000000::numeric)
    ) AS v(company_id, share_class_id, fy, stype, as_of, auth_sh, auth_amt, iss_sh, iss_amt)
    WHERE NOT EXISTS (
        SELECT 1 FROM core.capital_snapshot cs
         WHERE cs.company_id = v.company_id AND cs.share_class_id = v.share_class_id
           AND cs.financial_year = v.fy AND cs.snapshot_type = v.stype);

    -- ------------------------------------------------------------------
    -- Share transfer (BrightMed): Rajan Patel -> General Public - A, 50,000 shares,
    -- approved at board meeting BM-2 (22 Aug 2024). Demat transfer, so no SH-4 on file.
    -- Holdings are closed and re-opened so the "current holding = valid_to IS NULL" rule holds.
    -- ------------------------------------------------------------------
    SELECT id INTO v_rajan  FROM core.shareholder WHERE name = 'Rajan Patel' ORDER BY id LIMIT 1;
    SELECT id INTO v_public FROM core.shareholder WHERE name = 'General Public - A' ORDER BY id LIMIT 1;
    SELECT id INTO v_meet_bm2 FROM core.meeting
     WHERE company_id = v_c2 AND meeting_number = 'BM-2' ORDER BY id LIMIT 1;

    IF NOT EXISTS (SELECT 1 FROM core.share_transfer
                    WHERE company_id = v_c2 AND transferor_id = v_rajan AND transferee_id = v_public
                      AND transfer_date = DATE '2024-08-22') THEN

        INSERT INTO core.share_transfer (company_id, transferor_id, transferee_id, share_class_id,
            number_of_shares, transfer_date, board_meeting_id, face_value, consideration,
            stamp_duty_paid, distinctive_from, distinctive_to, client_id, dp_id, transferee_folio,
            sh4_available, involves_non_resident)
        VALUES (v_c2, v_rajan, v_public, v_class_c2,
            50000, DATE '2024-08-22', v_meet_bm2, 10, 1250000,
            187.50, '850001', '900000', '12345678', 'IN301234', 'BRM002',
            false, false);

        -- Close the two holdings that changed ...
        UPDATE core.shareholding SET valid_to = DATE '2024-08-21'
         WHERE company_id = v_c2 AND share_class_id = v_class_c2 AND valid_to IS NULL
           AND ((shareholder_id = v_rajan  AND folio_number = 'BRM001')
             OR (shareholder_id = v_public AND folio_number = 'BRM002'));

        -- ... and open the new ones from the transfer date.
        INSERT INTO core.shareholding (company_id, shareholder_id, share_class_id, folio_number, is_demat,
            number_of_shares, face_value, valid_from)
        VALUES (v_c2, v_rajan,  v_class_c2, 'BRM001', true, 850000, 10, DATE '2024-08-22'),
               (v_c2, v_public, v_class_c2, 'BRM002', true, 650000, 10, DATE '2024-08-22');
    END IF;

    -- ------------------------------------------------------------------
    -- Independent director terms: Nalini Sharma at BrightMed
    -- (first term of five years, then a second term still running)
    -- ------------------------------------------------------------------
    SELECT ds.id INTO v_dst_nalini
      FROM core.directorship ds JOIN core.director d ON d.id = ds.director_id
     WHERE ds.company_id = v_c2 AND d.din = '12340006' AND ds.end_date IS NULL;

    INSERT INTO core.independent_director_term (directorship_id, term_no, start_date, end_date)
    SELECT v_dst_nalini, 1, DATE '2018-01-01', DATE '2022-12-31'
    WHERE v_dst_nalini IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM core.independent_director_term WHERE directorship_id = v_dst_nalini AND term_no = 1);

    INSERT INTO core.independent_director_term (directorship_id, term_no, start_date, end_date)
    SELECT v_dst_nalini, 2, DATE '2023-01-01', NULL
    WHERE v_dst_nalini IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM core.independent_director_term WHERE directorship_id = v_dst_nalini AND term_no = 2);
END $$;
