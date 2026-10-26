-- 010_views.sql
-- All calculated views as required by guidelines section 5.9.

-- ============================================================
-- v_current_directors
-- Directors with an active (no end_date) directorship stint
-- ============================================================
CREATE OR REPLACE VIEW core.v_current_directors AS
SELECT
    d.company_id,
    co.name                 AS company_name,
    dir.id                  AS director_id,
    dir.full_name,
    dir.din,
    dir.gender,
    dir.email,
    d.id                    AS directorship_id,
    d.start_date            AS appointment_date,
    d.is_independent,
    d.is_whole_time,
    d.is_nominee,
    d.retires_by_rotation,
    d.is_board_member,
    d.shares_held,
    -- Current designation (latest active role)
    (SELECT lv.label
     FROM core.directorship_role dr2
     JOIN core.lookup_value lv ON lv.id = dr2.designation_id
     WHERE dr2.directorship_id = d.id
       AND NOT dr2.is_archived
     ORDER BY dr2.start_date DESC LIMIT 1) AS current_designation
FROM core.directorship d
JOIN core.company  co  ON co.id  = d.company_id
JOIN core.director dir ON dir.id = d.director_id
WHERE d.end_date IS NULL
  AND NOT d.is_archived;

COMMENT ON VIEW core.v_current_directors IS 'All directors currently serving (no end_date) per company. Designation from latest directorship_role row.';

-- ============================================================
-- v_director_history
-- All stints with computed duration (NULL end_date = still serving)
-- ============================================================
CREATE OR REPLACE VIEW core.v_director_history AS
SELECT
    d.company_id,
    co.name                      AS company_name,
    dir.id                       AS director_id,
    dir.full_name,
    dir.din,
    d.id                         AS directorship_id,
    d.start_date,
    d.end_date,
    d.cessation_reason,
    d.is_independent,
    d.is_whole_time,
    -- Duration in months (NULL end_date = current)
    EXTRACT(YEAR FROM age(COALESCE(d.end_date, CURRENT_DATE), d.start_date)) * 12
    + EXTRACT(MONTH FROM age(COALESCE(d.end_date, CURRENT_DATE), d.start_date)) AS duration_months,
    (d.end_date IS NULL)         AS is_current
FROM core.directorship d
JOIN core.company  co  ON co.id  = d.company_id
JOIN core.director dir ON dir.id = d.director_id
WHERE NOT d.is_archived
ORDER BY d.company_id, dir.id, d.start_date;

COMMENT ON VIEW core.v_director_history IS 'All directorship stints (past and current) with computed duration. Use alongside v_current_directors to show history differences.';

-- ============================================================
-- v_director_age
-- Calculated from date_of_birth — never stored
-- ============================================================
CREATE OR REPLACE VIEW core.v_director_age AS
SELECT
    id               AS director_id,
    full_name,
    din,
    date_of_birth,
    EXTRACT(YEAR FROM age(CURRENT_DATE, date_of_birth))::int AS age_years
FROM core.director
WHERE date_of_birth IS NOT NULL
  AND NOT is_archived;

COMMENT ON VIEW core.v_director_age IS 'Director age computed from date_of_birth. Age is never stored per guidelines.';

-- ============================================================
-- v_shareholding_percent
-- Current holdings as % of total paid-up shares per class
-- ============================================================
CREATE OR REPLACE VIEW core.v_shareholding_percent AS
WITH totals AS (
    SELECT company_id, share_class_id, SUM(number_of_shares) AS total_shares
    FROM core.shareholding
    WHERE valid_to IS NULL AND NOT is_archived
    GROUP BY company_id, share_class_id
)
SELECT
    sh.company_id,
    co.name                     AS company_name,
    sh.shareholder_id,
    s.name                      AS shareholder_name,
    lv.label                    AS shareholder_category,
    sh.share_class_id,
    sc.class_id,
    sh.number_of_shares,
    t.total_shares,
    ROUND(sh.number_of_shares * 100.0 / NULLIF(t.total_shares, 0), 4) AS holding_percent
FROM core.shareholding sh
JOIN core.shareholder  s  ON s.id  = sh.shareholder_id
JOIN core.company      co ON co.id = sh.company_id
JOIN core.share_class  sc ON sc.id = sh.share_class_id
LEFT JOIN core.lookup_value lv ON lv.id = s.category_id
JOIN totals t ON t.company_id = sh.company_id AND t.share_class_id = sh.share_class_id
WHERE sh.valid_to IS NULL AND NOT sh.is_archived;

COMMENT ON VIEW core.v_shareholding_percent IS 'Current shareholding percentages per company, class and shareholder.';

-- ============================================================
-- v_top10_shareholders
-- Top 10 by shares within each (company, share_class)
-- ============================================================
CREATE OR REPLACE VIEW core.v_top10_shareholders AS
SELECT *
FROM (
    SELECT
        vsp.*,
        RANK() OVER (
            PARTITION BY company_id, share_class_id
            ORDER BY number_of_shares DESC
        ) AS rank_in_class
    FROM core.v_shareholding_percent vsp
) ranked
WHERE rank_in_class <= 10;

COMMENT ON VIEW core.v_top10_shareholders IS 'Top-10 shareholders by class per company. Top-10 flag derived in query, never stored.';

-- ============================================================
-- v_committee_attendance_percent
-- ============================================================
CREATE OR REPLACE VIEW core.v_committee_attendance_percent AS
WITH meetings_per_committee AS (
    SELECT committee_id, COUNT(*) AS meetings_held
    FROM core.meeting
    WHERE committee_id IS NOT NULL
      AND status = 'held'
      AND NOT is_archived
    GROUP BY committee_id
),
attendance_per_member AS (
    SELECT
        ma.directorship_id,
        m.committee_id,
        COUNT(*) FILTER (WHERE ma.attended) AS attended_count,
        COUNT(*)                             AS total_entitled
    FROM core.meeting_attendance ma
    JOIN core.meeting m ON m.id = ma.meeting_id
    WHERE m.committee_id IS NOT NULL
      AND m.status = 'held'
      AND ma.attendee_type = 'director'
      AND NOT ma.is_archived
    GROUP BY ma.directorship_id, m.committee_id
)
SELECT
    cm.committee_id,
    c.name                AS committee_name,
    cm.directorship_id,
    dir.full_name,
    COALESCE(ap.attended_count, 0)  AS meetings_attended,
    COALESCE(mpc.meetings_held, 0)  AS meetings_held,
    CASE WHEN COALESCE(mpc.meetings_held, 0) = 0 THEN NULL
         ELSE ROUND(COALESCE(ap.attended_count, 0) * 100.0 / mpc.meetings_held, 2)
    END                             AS attendance_percent
FROM core.committee_member cm
JOIN core.committee   c   ON c.id   = cm.committee_id
JOIN core.directorship d  ON d.id   = cm.directorship_id
JOIN core.director    dir ON dir.id = d.director_id
LEFT JOIN meetings_per_committee mpc ON mpc.committee_id = cm.committee_id
LEFT JOIN attendance_per_member  ap  ON ap.committee_id = cm.committee_id
                                    AND ap.directorship_id = cm.directorship_id
WHERE NOT cm.is_archived;

COMMENT ON VIEW core.v_committee_attendance_percent IS 'Attendance % per committee member. Calculated, not stored.';

-- ============================================================
-- v_director_attendance_summary
-- Board meetings held while a director, attended, attended last AGM
-- ============================================================
CREATE OR REPLACE VIEW core.v_director_attendance_summary AS
WITH board_eligible AS (
    SELECT
        ma.directorship_id,
        COUNT(*) FILTER (WHERE ma.attended) AS board_meetings_attended,
        COUNT(*)                             AS board_meetings_entitled
    FROM core.meeting_attendance ma
    JOIN core.meeting m ON m.id = ma.meeting_id
    JOIN core.lookup_value lv ON lv.id = m.meeting_type_id AND lv.code = 'BOARD'
    WHERE m.status = 'held' AND ma.attendee_type = 'director' AND NOT ma.is_archived
    GROUP BY ma.directorship_id
),
last_agm AS (
    SELECT DISTINCT ON (ma.directorship_id)
        ma.directorship_id,
        ma.attended AS attended_last_agm,
        m.meeting_date AS last_agm_date
    FROM core.meeting_attendance ma
    JOIN core.meeting m ON m.id = ma.meeting_id
    JOIN core.lookup_value lv ON lv.id = m.meeting_type_id AND lv.code = 'AGM'
    WHERE m.status = 'held' AND ma.attendee_type = 'director' AND NOT ma.is_archived
    ORDER BY ma.directorship_id, m.meeting_date DESC
)
SELECT
    d.company_id,
    d.id              AS directorship_id,
    dir.full_name,
    dir.din,
    COALESCE(be.board_meetings_entitled, 0) AS board_meetings_entitled,
    COALESCE(be.board_meetings_attended, 0) AS board_meetings_attended,
    CASE WHEN COALESCE(be.board_meetings_entitled,0) = 0 THEN NULL
         ELSE ROUND(be.board_meetings_attended * 100.0 / be.board_meetings_entitled, 2)
    END AS board_attendance_percent,
    la.attended_last_agm,
    la.last_agm_date
FROM core.directorship d
JOIN core.director dir ON dir.id = d.director_id
LEFT JOIN board_eligible be ON be.directorship_id = d.id
LEFT JOIN last_agm       la ON la.directorship_id = d.id
WHERE NOT d.is_archived;

COMMENT ON VIEW core.v_director_attendance_summary IS 'Board meetings entitled/attended per director, and whether they attended the last AGM.';

-- ============================================================
-- v_independent_director_years
-- Total years served as independent director (computed)
-- ============================================================
CREATE OR REPLACE VIEW core.v_independent_director_years AS
SELECT
    idt.directorship_id,
    d.company_id,
    dir.full_name,
    ROUND(
        SUM(COALESCE(idt.end_date, CURRENT_DATE) - idt.start_date)::numeric / 365.25,
        2
    ) AS total_years_served,
    MAX(idt.term_no) AS highest_term_no
FROM core.independent_director_term idt
JOIN core.directorship d ON d.id = idt.directorship_id
JOIN core.director dir   ON dir.id = d.director_id
WHERE NOT idt.is_archived
GROUP BY idt.directorship_id, d.company_id, dir.full_name, dir.din;

COMMENT ON VIEW core.v_independent_director_years IS 'Total years served as independent director per stint. Never stored.';

-- ============================================================
-- v_company_shareholder_counts
-- ============================================================
CREATE OR REPLACE VIEW core.v_company_shareholder_counts AS
SELECT
    sh.company_id,
    co.name             AS company_name,
    COUNT(DISTINCT sh.shareholder_id) AS current_shareholder_count
FROM core.shareholding sh
JOIN core.company co ON co.id = sh.company_id
WHERE sh.valid_to IS NULL AND NOT sh.is_archived
GROUP BY sh.company_id, co.name;

COMMENT ON VIEW core.v_company_shareholder_counts IS 'Current shareholder count per company.';

-- ============================================================
-- v_s186_running_total
-- Running total of loans/guarantees/investments per company per year
-- ============================================================
CREATE OR REPLACE VIEW core.v_s186_running_total AS
SELECT
    company_id,
    financial_year,
    transaction_type,
    SUM(amount) AS running_total
FROM core.s186_transaction
WHERE NOT is_archived
GROUP BY company_id, financial_year, transaction_type;

COMMENT ON VIEW core.v_s186_running_total IS 'Running total of Sec 186 loans/guarantees/investments per company per year. Compare against computed limit.';

-- ============================================================
-- v_filings_overdue
-- Government filings past due date and not yet filed
-- ============================================================
CREATE OR REPLACE VIEW core.v_filings_overdue AS
SELECT
    gf.id,
    gf.company_id,
    co.name         AS company_name,
    gf.form_name,
    gf.description,
    gf.financial_year,
    gf.due_date,
    gf.filing_date,
    (CURRENT_DATE - gf.due_date) AS days_overdue
FROM core.government_filing gf
JOIN core.company co ON co.id = gf.company_id
WHERE gf.filing_date IS NULL
  AND gf.due_date < CURRENT_DATE
  AND NOT gf.is_archived
ORDER BY days_overdue DESC;

COMMENT ON VIEW core.v_filings_overdue IS 'Government filings past due date and not yet filed.';

-- ============================================================
-- v_rule_resident_director
-- Example rule view: checks if at least one director was resident >182 days
-- ============================================================
CREATE OR REPLACE VIEW core.v_rule_resident_director AS
SELECT
    d.company_id,
    co.name AS company_name,
    dr.financial_year,
    bool_or(dr.resident_over_182) AS has_resident_director,
    COUNT(*) FILTER (WHERE dr.resident_over_182) AS resident_director_count
FROM core.director_residency dr
JOIN core.directorship d ON d.director_id = dr.director_id
     AND d.end_date IS NULL OR d.end_date >= make_date(
         left(dr.financial_year,4)::int, 3, 31
     )  -- director was on board during the year
JOIN core.company co ON co.id = d.company_id
WHERE NOT dr.is_archived AND NOT d.is_archived
GROUP BY d.company_id, co.name, dr.financial_year;

COMMENT ON VIEW core.v_rule_resident_director IS 'Example rule view: whether each company has at least one director resident in India >182 days. Corresponds to rule RESIDENT_DIRECTOR (Sec 149).';

-- ============================================================
-- v_rule_woman_director
-- Example rule view: checks woman-director requirement
-- ============================================================
CREATE OR REPLACE VIEW core.v_rule_woman_director AS
SELECT
    d.company_id,
    co.name            AS company_name,
    bool_or(dir.gender = 'F') AS has_woman_director,
    COUNT(*) FILTER (WHERE dir.gender = 'F') AS woman_director_count,
    co.is_listed,
    cf.turnover,
    cf.net_worth,
    -- The rule applies if listed, OR paid-up capital >= 100 Cr, OR turnover >= 300 Cr
    -- Capital is not in company_financials directly; this is simplified
    (co.is_listed OR COALESCE(cf.turnover,0) >= 30000000000) AS rule_applies
FROM core.directorship d
JOIN core.company  co  ON co.id  = d.company_id
JOIN core.director dir ON dir.id = d.director_id
LEFT JOIN core.company_financials cf ON cf.company_id = d.company_id
    AND cf.financial_year = to_char(CURRENT_DATE, 'YYYY') || '-' || to_char(CURRENT_DATE - interval '1 year', 'YY')
WHERE d.end_date IS NULL
  AND NOT d.is_archived
GROUP BY d.company_id, co.name, co.is_listed, cf.turnover, cf.net_worth;

COMMENT ON VIEW core.v_rule_woman_director IS 'Example rule view: whether each company satisfies the woman-director requirement (Sec 149). Rule logic is illustrative — verify thresholds with BMP professionals.';
