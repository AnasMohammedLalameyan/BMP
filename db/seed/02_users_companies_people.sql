-- db/seed/02_users_companies_people.sql
-- Seeds app users, 5 companies and ~12 directors with realistic fictional data.
-- No real CINs, DINs, PANs or secrets.

-- Set session user for audit
DO $$
DECLARE v_seed_user bigint;
BEGIN
    SELECT id INTO v_seed_user FROM core.app_user WHERE email = 'seed@system.internal';
    IF v_seed_user IS NOT NULL THEN
        PERFORM set_config('app.current_user_id', v_seed_user::text, false);
    ELSE
        PERFORM set_config('app.current_user_id', '0', false);
    END IF;
END $$;

-- ============================================================
-- APP USERS
-- ============================================================
-- Roles (already seeded in 01; just reference them)
DO $$
DECLARE
    v_admin_role   bigint;
    v_manager_role bigint;
    v_client_role  bigint;
BEGIN
    SELECT id INTO v_admin_role   FROM core.role WHERE name = 'admin';
    SELECT id INTO v_manager_role FROM core.role WHERE name = 'manager';
    SELECT id INTO v_client_role  FROM core.role WHERE name = 'client';

    INSERT INTO core.app_user (email, name, role_id, is_active) VALUES
        ('admin@bmpco.in',        'Aashima Gupta',       v_admin_role,   true),
        ('manager@bmpco.in',      'Rohit Sharma',        v_manager_role, true),
        ('client@nexatech.co.in', 'Priya Mehta',         v_client_role,  true)
    ON CONFLICT (email) DO NOTHING;
END $$;

-- ============================================================
-- COMPANIES — 5 fictional companies
-- CIN format: L/U + 5-digit NIC + 2-letter state + 4-digit year + PLC/PTC/OPC + 6-digit reg
-- All CINs are fictional (do not match any real company)
-- ============================================================
DO $$
DECLARE
    v_pub_cat   bigint;
    v_priv_cat  bigint;
    v_small_sub bigint;
    v_listed_city bigint;
BEGIN
    SELECT id INTO v_pub_cat   FROM core.lookup_value WHERE code = 'PUBLIC'  AND list_id = (SELECT id FROM core.lookup_list WHERE code = 'COMPANY_CATEGORY');
    SELECT id INTO v_priv_cat  FROM core.lookup_value WHERE code = 'PRIVATE' AND list_id = (SELECT id FROM core.lookup_list WHERE code = 'COMPANY_CATEGORY');
    SELECT id INTO v_small_sub FROM core.lookup_value WHERE code = 'SMALL'   AND list_id = (SELECT id FROM core.lookup_list WHERE code = 'COMPANY_SUBCATEGORY');

    -- Company 1: Small Private (no committees required)
    INSERT INTO core.company (cin, name, pan, date_of_incorporation, roc, category_id, subcategory_id,
        registered_address, phone, email, is_listed, status)
    VALUES
        ('U72200DL2015PTC112001', 'Nexatech Solutions Private Limited',
         'AANCN1234A', '2015-03-12', 'Delhi', v_priv_cat, v_small_sub,
         '14, Connaught Place, New Delhi - 110001', '01141234567', 'admin@nexatech.co.in',
         false, 'active')
    ON CONFLICT (cin) DO NOTHING;

    -- Company 2: Public company with paid-up > 10 Cr (requires Audit Committee etc.)
    INSERT INTO core.company (cin, name, pan, date_of_incorporation, roc, category_id,
        registered_address, phone, email, is_listed, status)
    VALUES
        ('L24100MH2010PLC178002', 'BrightMed Pharma Limited',
         'AANCB5678B', '2010-07-22', 'Mumbai', v_pub_cat,
         '5th Floor, Nariman Point, Mumbai - 400021', '02222334455', 'info@brightmed.co.in',
         false, 'active')
    ON CONFLICT (cin) DO NOTHING;

    -- Company 3: Large public company > 50 Cr paid-up
    INSERT INTO core.company (cin, name, pan, date_of_incorporation, roc, category_id,
        registered_address, phone, email, is_listed, status)
    VALUES
        ('L45200KA2005PLC134003', 'Greenfield Industries Limited',
         'AANCG9012C', '2005-01-15', 'Bangalore', v_pub_cat,
         '27, Outer Ring Road, Bengaluru - 560103', '08044556677', 'contact@greenfield.co.in',
         false, 'active')
    ON CONFLICT (cin) DO NOTHING;

    -- Company 4: Listed company with > 1000 security holders
    INSERT INTO core.company (cin, name, pan, date_of_incorporation, roc, category_id,
        registered_address, phone, email, website, is_listed, market_value_rank, status)
    VALUES
        ('L62010MH2000PLC156004', 'Skyward Technologies Limited',
         'AANCS3456D', '2000-06-10', 'Mumbai', v_pub_cat,
         'Skyward Tower, BKC, Bandra East, Mumbai - 400051', '02244556677', 'investor@skyward.co.in',
         'https://www.skyward.co.in', true, 450, 'active')
    ON CONFLICT (cin) DO NOTHING;

    -- Company 5: Company with foreign shareholder and FC-GPR record
    INSERT INTO core.company (cin, name, pan, date_of_incorporation, roc, category_id, subcategory_id,
        registered_address, phone, email, is_listed, status)
    VALUES
        ('U74110MH2018PTC201005', 'Indovance Fintech Private Limited',
         'AANCI7890E', '2018-11-05', 'Mumbai', v_priv_cat,
         (SELECT id FROM core.lookup_value WHERE code = 'FOREIGN_SUB'
          AND list_id = (SELECT id FROM core.lookup_list WHERE code = 'COMPANY_SUBCATEGORY')),
         'Unit 3, Powai Tech Park, Mumbai - 400076', '02266778899', 'ops@indovance.in',
         false, 'active')
    ON CONFLICT (cin) DO NOTHING;

END $$;

-- ============================================================
-- COMPANY FINANCIALS (two financial years)
-- ============================================================
DO $$
DECLARE v_c1 bigint; v_c2 bigint; v_c3 bigint; v_c4 bigint; v_c5 bigint;
BEGIN
    SELECT id INTO v_c1 FROM core.company WHERE cin = 'U72200DL2015PTC112001';
    SELECT id INTO v_c2 FROM core.company WHERE cin = 'L24100MH2010PLC178002';
    SELECT id INTO v_c3 FROM core.company WHERE cin = 'L45200KA2005PLC134003';
    SELECT id INTO v_c4 FROM core.company WHERE cin = 'L62010MH2000PLC156004';
    SELECT id INTO v_c5 FROM core.company WHERE cin = 'U74110MH2018PTC201005';

    INSERT INTO core.company_financials
        (company_id, financial_year, turnover, net_worth, net_profit, free_reserves,
         securities_premium, borrowings_banks_fi, public_deposits, total_security_holders)
    VALUES
        -- Nexatech (small private)
        (v_c1, '2023-24',  48000000, 25000000,   3000000, 12000000,   5000000,  10000000,  0, 12),
        (v_c1, '2024-25',  55000000, 28000000,   4000000, 15000000,   5000000,   8000000,  0, 12),
        -- BrightMed (public, paid-up > 10Cr)
        (v_c2, '2023-24', 520000000,180000000,  22000000, 80000000,  30000000, 100000000,  0, 340),
        (v_c2, '2024-25', 600000000,200000000,  28000000, 95000000,  30000000,  90000000,  0, 380),
        -- Greenfield (large public > 50 Cr)
        (v_c3, '2023-24',3500000000,900000000, 180000000,400000000, 200000000,600000000,  0, 870),
        (v_c3, '2024-25',4000000000,1050000000,220000000,480000000, 200000000,550000000,  0, 920),
        -- Skyward (listed, >1000 security holders)
        (v_c4, '2023-24',8000000000,3000000000,600000000,1200000000,500000000,2000000000,0,15000),
        (v_c4, '2024-25',9200000000,3500000000,720000000,1400000000,500000000,1800000000,0,16500),
        -- Indovance (foreign shareholder)
        (v_c5, '2023-24',  90000000, 60000000,   8000000, 20000000,  30000000,  20000000,  0, 8),
        (v_c5, '2024-25', 130000000, 68000000,  10000000, 28000000,  30000000,  15000000,  0, 8)
    ON CONFLICT (company_id, financial_year) DO NOTHING;
END $$;

-- ============================================================
-- DIRECTORS (12 fictional individuals)
-- No real DINs, PANs or Aadhaar
-- ============================================================
INSERT INTO core.director (din, full_name, pan, relative_name, date_of_birth, gender, nationality, address, email, phone, occupation)
VALUES
    ('12340001', 'Arjun Kapoor',     'ABCAK1001A', 'Ramesh Kapoor',   '1972-05-14', 'M', 'Indian', '21, Vasant Vihar, New Delhi-110057',        'arjun.kapoor@mail.in',    '9811001001', 'Business'),
    ('12340002', 'Sunita Rao',       'ABCSR2002B', 'Vikram Rao',      '1978-09-22', 'F', 'Indian', '12, Banjara Hills, Hyderabad-500034',       'sunita.rao@mail.in',      '9822002002', 'Business'),
    ('12340003', 'Devraj Menon',     'ABCDM3003C', 'Krishnan Menon',  '1969-03-08', 'M', 'Indian', '8, Koramangala, Bengaluru-560034',          'devraj.menon@mail.in',    '9833003003', 'Professional'),
    ('12340004', 'Kavitha Nair',     'ABCKN4004D', 'Suresh Nair',     '1985-11-30', 'F', 'Indian', '5, Marine Drive, Mumbai-400002',           'kavitha.nair@mail.in',    '9844004004', 'Business'),
    ('12340005', 'Rajan Patel',      'ABCRP5005E', 'Amrit Patel',     '1965-07-19', 'M', 'Indian', '3, Paldi, Ahmedabad-380007',               'rajan.patel@mail.in',     '9855005005', 'Business'),
    ('12340006', 'Nalini Sharma',    'ABCNS6006F', 'Anand Sharma',    '1980-02-14', 'F', 'Indian', '7, Sector 21, Gurugram-122016',            'nalini.sharma@mail.in',   '9866006006', 'Consultant'),
    ('12340007', 'Vikram Singh',     'ABCVS7007G', 'Harinder Singh',  '1975-08-03', 'M', 'Indian', '14, Chandigarh Sector 8-160008',           'vikram.singh@mail.in',    '9877007007', 'Business'),
    ('12340008', 'Anil Desai',       'ABCAD8008H', 'Ramnik Desai',    '1962-12-25', 'M', 'Indian', '9, Colaba, Mumbai-400005',                 'anil.desai@mail.in',      '9888008008', 'Business'),
    ('12340009', 'Sonia Verma',      'ABCSV9009I', 'Rakesh Verma',    '1990-04-17', 'F', 'Indian', '31, Civil Lines, Jaipur-302006',           'sonia.verma@mail.in',     '9899009009', 'Professional'),
    ('12340010', 'Thomas George',    'ABCTG0010J', 'Philip George',   '1968-06-28', 'M', 'Indian', '22, Ernakulam, Kochi-682031',              'thomas.george@mail.in',   '9800010010', 'Business'),
    ('12340011', 'Elena Kowalski',   NULL,          'Jan Kowalski',    '1982-10-10', 'F', 'Polish', '12, Belgravia, London SW1W 8RH, UK',        'elena.kowalski@mail.com', '+441234567890', 'Business'),   -- Non-resident director
    ('12340012', 'Prashant Joshi',   'ABCPJ2012L', 'Vinayak Joshi',   '1983-01-21', 'M', 'Indian', '4, Deccan Gymkhana, Pune-411004',          'prashant.joshi@mail.in',  '9812012012', 'Professional')
ON CONFLICT (din) DO NOTHING;

-- ============================================================
-- DIRECTORSHIPS
-- ============================================================
DO $$
DECLARE
    -- Directors
    v_d1 bigint; v_d2 bigint; v_d3 bigint; v_d4 bigint; v_d5 bigint;
    v_d6 bigint; v_d7 bigint; v_d8 bigint; v_d9 bigint; v_d10 bigint;
    v_d11 bigint; v_d12 bigint;
    -- Companies
    v_c1 bigint; v_c2 bigint; v_c3 bigint; v_c4 bigint; v_c5 bigint;
    -- Lookup IDs
    v_ind_cat bigint; v_non_exec_cat bigint; v_exec_cat bigint;
    v_ind_desg bigint; v_dir_desg bigint; v_md_desg bigint; v_wmd_desg bigint;
BEGIN
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

    SELECT id INTO v_c1 FROM core.company WHERE cin = 'U72200DL2015PTC112001';
    SELECT id INTO v_c2 FROM core.company WHERE cin = 'L24100MH2010PLC178002';
    SELECT id INTO v_c3 FROM core.company WHERE cin = 'L45200KA2005PLC134003';
    SELECT id INTO v_c4 FROM core.company WHERE cin = 'L62010MH2000PLC156004';
    SELECT id INTO v_c5 FROM core.company WHERE cin = 'U74110MH2018PTC201005';

    SELECT lv.id INTO v_ind_cat     FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DIRECTOR_CATEGORY' AND lv.code='INDEPENDENT';
    SELECT lv.id INTO v_non_exec_cat FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DIRECTOR_CATEGORY' AND lv.code='NON_EXEC';
    SELECT lv.id INTO v_exec_cat    FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DIRECTOR_CATEGORY' AND lv.code='EXECUTIVE';

    SELECT lv.id INTO v_ind_desg  FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DESIGNATION' AND lv.code='IND_DIR';
    SELECT lv.id INTO v_dir_desg  FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DESIGNATION' AND lv.code='DIRECTOR';
    SELECT lv.id INTO v_md_desg   FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DESIGNATION' AND lv.code='MD';
    SELECT lv.id INTO v_wmd_desg  FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DESIGNATION' AND lv.code='WTD';

    -- -------------------------------------------------------
    -- Nexatech (C1): Arjun (MD), Sunita (ID), Prashant (Director)
    -- -------------------------------------------------------
    INSERT INTO core.directorship (company_id, director_id, start_date, is_whole_time, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c1, v_d1, '2015-03-12', true, false, false, v_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d1 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c1, v_d2, '2015-03-12', true, false, v_ind_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d2 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c1, v_d12, '2021-04-01', false, true, v_non_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d12 AND end_date IS NULL);

    -- -------------------------------------------------------
    -- BrightMed (C2): Rajan (MD), Nalini (ID, woman), Elena (NR director), Prashant (resigned + reappointed)
    -- -------------------------------------------------------
    INSERT INTO core.directorship (company_id, director_id, start_date, is_whole_time,
        is_independent, retires_by_rotation, director_category_id)
    SELECT v_c2, v_d5, '2010-07-22', true, false, false, v_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d5 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c2, v_d6, '2018-01-01', true, false, v_ind_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d6 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c2, v_d11, '2020-04-01', false, false, v_non_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d11 AND end_date IS NULL);

    -- Prashant: first stint 2016-2021 (resigned), re-appointed 2023 (two rows)
    INSERT INTO core.directorship (company_id, director_id, start_date, end_date, cessation_reason,
        is_independent, retires_by_rotation, director_category_id)
    SELECT v_c2, v_d12, '2016-06-01', '2021-05-31', 'Resignation', false, true, v_non_exec_cat
    WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d12
          AND start_date='2016-06-01');

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c2, v_d12, '2023-07-01', false, true, v_non_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d12 AND end_date IS NULL);

    -- -------------------------------------------------------
    -- Greenfield (C3): Anil (MD), Kavitha (ID, woman), Devraj (Director), Vikram (Director)
    -- -------------------------------------------------------
    INSERT INTO core.directorship (company_id, director_id, start_date, is_whole_time,
        retires_by_rotation, director_category_id)
    SELECT v_c3, v_d8, '2005-01-15', true, false, v_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d8 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c3, v_d4, '2015-04-01', true, false, v_ind_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d4 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date,
        retires_by_rotation, director_category_id)
    SELECT v_c3, v_d3, '2008-09-01', true, v_non_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d3 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date,
        retires_by_rotation, director_category_id)
    SELECT v_c3, v_d7, '2012-01-01', true, v_non_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d7 AND end_date IS NULL);

    -- -------------------------------------------------------
    -- Skyward (C4): Vikram (MD), Sunita (ID), Thomas (Director), Sonia (NED), Elena (NR)
    -- -------------------------------------------------------
    INSERT INTO core.directorship (company_id, director_id, start_date, is_whole_time,
        retires_by_rotation, director_category_id)
    SELECT v_c4, v_d7, '2000-06-10', true, false, v_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d7 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c4, v_d2, '2010-05-01', true, false, v_ind_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d2 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date,
        retires_by_rotation, director_category_id)
    SELECT v_c4, v_d10, '2015-07-01', true, v_non_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d10 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date,
        retires_by_rotation, director_category_id)
    SELECT v_c4, v_d9, '2020-01-01', false, v_non_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d9 AND end_date IS NULL);

    -- -------------------------------------------------------
    -- Indovance (C5): Arjun (Director), Nalini (Director)
    -- -------------------------------------------------------
    INSERT INTO core.directorship (company_id, director_id, start_date,
        retires_by_rotation, director_category_id)
    SELECT v_c5, v_d1, '2018-11-05', true, v_exec_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c5 AND director_id=v_d1 AND end_date IS NULL);

    INSERT INTO core.directorship (company_id, director_id, start_date, is_independent,
        retires_by_rotation, director_category_id)
    SELECT v_c5, v_d6, '2019-01-01', true, false, v_ind_cat WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship WHERE company_id=v_c5 AND director_id=v_d6 AND end_date IS NULL);

END $$;

-- ============================================================
-- DIRECTORSHIP ROLES (designations with history)
-- ============================================================
DO $$
DECLARE
    v_dir_desg bigint; v_md_desg bigint; v_ind_desg bigint;
    v_dst_c1_arjun bigint; v_dst_c2_rajan bigint; v_dst_c2_prashant_new bigint;
    v_dst_c3_anil bigint; v_dst_c4_vikram bigint;
    v_dst_c1_sunita bigint; v_dst_c3_kavitha bigint; v_dst_c4_sunita bigint;
    v_c1 bigint; v_c2 bigint; v_c3 bigint; v_c4 bigint;
    v_d1 bigint; v_d2 bigint; v_d4 bigint; v_d5 bigint; v_d7 bigint; v_d8 bigint; v_d12 bigint;
BEGIN
    SELECT lv.id INTO v_dir_desg FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DESIGNATION' AND lv.code='DIRECTOR';
    SELECT lv.id INTO v_md_desg  FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DESIGNATION' AND lv.code='MD';
    SELECT lv.id INTO v_ind_desg FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id WHERE ll.code='DESIGNATION' AND lv.code='IND_DIR';

    SELECT id INTO v_c1 FROM core.company WHERE cin = 'U72200DL2015PTC112001';
    SELECT id INTO v_c2 FROM core.company WHERE cin = 'L24100MH2010PLC178002';
    SELECT id INTO v_c3 FROM core.company WHERE cin = 'L45200KA2005PLC134003';
    SELECT id INTO v_c4 FROM core.company WHERE cin = 'L62010MH2000PLC156004';
    SELECT id INTO v_d1  FROM core.director WHERE din = '12340001';
    SELECT id INTO v_d2  FROM core.director WHERE din = '12340002';
    SELECT id INTO v_d4  FROM core.director WHERE din = '12340004';
    SELECT id INTO v_d5  FROM core.director WHERE din = '12340005';
    SELECT id INTO v_d7  FROM core.director WHERE din = '12340007';
    SELECT id INTO v_d8  FROM core.director WHERE din = '12340008';
    SELECT id INTO v_d12 FROM core.director WHERE din = '12340012';

    SELECT id INTO v_dst_c1_arjun FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d1 AND end_date IS NULL;
    SELECT id INTO v_dst_c2_rajan FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d5 AND end_date IS NULL;
    SELECT id INTO v_dst_c2_prashant_new FROM core.directorship WHERE company_id=v_c2 AND director_id=v_d12 AND end_date IS NULL;
    SELECT id INTO v_dst_c3_anil FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d8 AND end_date IS NULL;
    SELECT id INTO v_dst_c4_vikram FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d7 AND end_date IS NULL;
    SELECT id INTO v_dst_c1_sunita FROM core.directorship WHERE company_id=v_c1 AND director_id=v_d2 AND end_date IS NULL;
    SELECT id INTO v_dst_c3_kavitha FROM core.directorship WHERE company_id=v_c3 AND director_id=v_d4 AND end_date IS NULL;
    SELECT id INTO v_dst_c4_sunita FROM core.directorship WHERE company_id=v_c4 AND director_id=v_d2 AND end_date IS NULL;

    -- Arjun: Director -> MD designation change
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date, end_date)
    SELECT v_dst_c1_arjun, v_dir_desg, '2015-03-12', '2018-12-31' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c1_arjun AND designation_id=v_dir_desg AND start_date='2015-03-12');

    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c1_arjun, v_md_desg, '2019-01-01' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c1_arjun AND designation_id=v_md_desg AND start_date='2019-01-01');

    -- Rajan: MD from incorporation
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c2_rajan, v_md_desg, '2010-07-22' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c2_rajan AND designation_id=v_md_desg AND start_date='2010-07-22');

    -- Prashant (BrightMed, re-appointment): Director
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c2_prashant_new, v_dir_desg, '2023-07-01' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c2_prashant_new AND start_date='2023-07-01');

    -- Anil: MD at Greenfield
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c3_anil, v_md_desg, '2005-01-15' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c3_anil AND designation_id=v_md_desg AND start_date='2005-01-15');

    -- Vikram: MD at Skyward
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c4_vikram, v_md_desg, '2000-06-10' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c4_vikram AND designation_id=v_md_desg AND start_date='2000-06-10');

    -- Sunita (Nexatech): Independent Director
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c1_sunita, v_ind_desg, '2015-03-12' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c1_sunita AND start_date='2015-03-12');

    -- Kavitha (Greenfield): Independent Director
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c3_kavitha, v_ind_desg, '2015-04-01' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c3_kavitha AND start_date='2015-04-01');

    -- Sunita (Skyward): Independent Director
    INSERT INTO core.directorship_role (directorship_id, designation_id, start_date)
    SELECT v_dst_c4_sunita, v_ind_desg, '2010-05-01' WHERE NOT EXISTS (
        SELECT 1 FROM core.directorship_role WHERE directorship_id=v_dst_c4_sunita AND start_date='2010-05-01');

END $$;

-- ============================================================
-- DIRECTOR RESIDENCY (2024-25)
-- ============================================================
DO $$
DECLARE v_d11 bigint;
BEGIN
    SELECT id INTO v_d11 FROM core.director WHERE din = '12340011';

    INSERT INTO core.director_residency (director_id, financial_year, resident_over_182)
    SELECT id, '2024-25', true FROM core.director WHERE din IN ('12340001','12340002','12340003','12340004','12340005','12340006','12340007','12340008','12340009','12340010','12340012')
    ON CONFLICT (director_id, financial_year) DO NOTHING;

    INSERT INTO core.director_residency (director_id, financial_year, resident_over_182)
    VALUES (v_d11, '2024-25', false)
    ON CONFLICT (director_id, financial_year) DO NOTHING;
END $$;

-- ============================================================
-- USER COMPANY ACCESS
-- ============================================================
DO $$
DECLARE
    v_admin bigint; v_manager bigint; v_client bigint;
    v_c1 bigint; v_c2 bigint; v_c3 bigint; v_c4 bigint; v_c5 bigint;
BEGIN
    SELECT id INTO v_admin   FROM core.app_user WHERE email = 'admin@bmpco.in';
    SELECT id INTO v_manager FROM core.app_user WHERE email = 'manager@bmpco.in';
    SELECT id INTO v_client  FROM core.app_user WHERE email = 'client@nexatech.co.in';
    SELECT id INTO v_c1 FROM core.company WHERE cin = 'U72200DL2015PTC112001';
    SELECT id INTO v_c2 FROM core.company WHERE cin = 'L24100MH2010PLC178002';
    SELECT id INTO v_c3 FROM core.company WHERE cin = 'L45200KA2005PLC134003';
    SELECT id INTO v_c4 FROM core.company WHERE cin = 'L62010MH2000PLC156004';
    SELECT id INTO v_c5 FROM core.company WHERE cin = 'U74110MH2018PTC201005';

    -- Admin sees all
    INSERT INTO core.user_company_access (user_id, company_id, access_level)
    VALUES (v_admin, v_c1, 'admin'), (v_admin, v_c2, 'admin'),
           (v_admin, v_c3, 'admin'), (v_admin, v_c4, 'admin'), (v_admin, v_c5, 'admin')
    ON CONFLICT (user_id, company_id) DO NOTHING;

    -- Manager sees C2, C3, C4
    INSERT INTO core.user_company_access (user_id, company_id, access_level)
    VALUES (v_manager, v_c2, 'write'), (v_manager, v_c3, 'write'), (v_manager, v_c4, 'write')
    ON CONFLICT (user_id, company_id) DO NOTHING;

    -- Client sees only C1 (Nexatech — their own company)
    INSERT INTO core.user_company_access (user_id, company_id, access_level)
    VALUES (v_client, v_c1, 'read')
    ON CONFLICT (user_id, company_id) DO NOTHING;
END $$;

-- ============================================================
-- AUDITOR (BrightMed)
-- ============================================================
DO $$
DECLARE v_c2 bigint; v_stat bigint;
BEGIN
    SELECT id INTO v_c2 FROM core.company WHERE cin = 'L24100MH2010PLC178002';
    SELECT lv.id INTO v_stat FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='AUDITOR_TYPE' AND lv.code='STATUTORY';
    INSERT INTO core.auditor (company_id, auditor_type_id, name, pan, frn, address, email,
        board_recommendation_date, gm_appointment_date, account_period_from, account_period_to, term_years)
    VALUES (v_c2, v_stat, 'K.P. Associates & Co.', 'ABCKP3456K', '103456W',
        'Office 12, Fort, Mumbai-400001', 'audit@kpassociates.co.in',
        '2020-04-15', '2020-09-25', '2020-04-01', '2025-03-31', 5)
    ON CONFLICT DO NOTHING;
END $$;
