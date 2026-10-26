# Data Dictionary

Generated from the live PostgreSQL catalog: table and column comments come from `COMMENT ON` statements in the migrations (which quote the xlsx sheet and row).


## Schema `core`


### `core.allotment`

One record per share allotment transaction. Xlsx: "Share Allotments".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `round_reference` | text | yes |  |
| `shareholder_id` | bigint | NO |  |
| `share_class_id` | bigint | NO |  |
| `number_of_shares` | bigint | NO |  |
| `allotment_date` | date | NO |  |
| `face_value` | numeric | NO |  |
| `premium_per_share` | numeric | NO |  |
| `issue_price` | numeric | NO |  |
| `face_value_amount` | numeric | NO |  |
| `premium_amount` | numeric | NO |  |
| `total_amount` | numeric | NO |  |
| `distinctive_from` | text | yes |  |
| `distinctive_to` | text | yes |  |
| `client_id` | text | yes |  |
| `dp_id` | text | yes |  |
| `certificate_no` | text | yes |  |
| `stamp_duty_payable` | numeric | yes |  |
| `stamp_duty_paid` | numeric | yes |  |
| `stamp_duty_paid_on` | date | yes |  |
| `board_meeting_id` | bigint | yes |  |
| `government_filing_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.app_user`

Platform users. No passwords stored — authentication is handled by the FastAPI layer (later phase).

Primary key: `id`  |  Unique: `email`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `email` | text | NO |  |
| `name` | text | NO |  |
| `role_id` | bigint | yes |  |
| `is_active` | boolean | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.auditor`

Auditor engagement records per company. Xlsx: "Auditors".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `auditor_type_id` | bigint | yes |  |
| `name` | text | NO |  |
| `pan` | text | yes |  |
| `frn` | text | yes | Firm Registration Number (ICAI). Xlsx row 4. |
| `address` | text | yes |  |
| `email` | text | yes |  |
| `board_recommendation_date` | date | yes | Date the Board recommended the auditor. Xlsx row 3. |
| `gm_appointment_date` | date | yes | Date the General Meeting appointed the auditor. Xlsx row 4. |
| `account_period_from` | date | yes |  |
| `account_period_to` | date | yes |  |
| `term_years` | integer | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.capital_event`

Events that change the capital structure (split, consolidation, increase, decrease). Xlsx: "Share Capital Summary".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `event_type` | text | NO |  |
| `reason_id` | bigint | yes |  |
| `event_date` | date | NO |  |
| `details` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.capital_snapshot`

Authorised, issued, subscribed and paid-up capital per class per financial year (opening and closing). Xlsx: "Share Capital Summary" rows 2-5.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `share_class_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `snapshot_type` | text | NO |  |
| `as_of_date` | date | NO |  |
| `authorised_shares` | bigint | yes |  |
| `authorised_amount` | numeric | yes |  |
| `issued_shares` | bigint | yes |  |
| `issued_amount` | numeric | yes |  |
| `subscribed_shares` | bigint | yes |  |
| `subscribed_amount` | numeric | yes |  |
| `paid_up_shares` | bigint | yes |  |
| `paid_up_amount` | numeric | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.circular_resolution`

Resolutions passed by circulation under Sec 175. Xlsx: "Circular Resolutions".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `reference` | text | yes |  |
| `circulated_on` | date | NO |  |
| `subject` | text | NO |  |
| `text` | text | yes |  |
| `passed_on` | date | yes |  |
| `noted_in_meeting_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.circular_resolution_response`

Each director's response to a circular resolution. Xlsx: "Circular Resolutions" rows 4-5.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `resolution_id` | bigint | NO |  |
| `directorship_id` | bigint | NO |  |
| `response` | text | yes |  |
| `responded_on` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.committee`

Board committees (Audit, NRC, SRC, CSR, Risk, etc.) per company. Xlsx: "Committees".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `name` | text | NO |  |
| `constituted_on` | date | yes |  |
| `dissolved_on` | date | yes |  |
| `meeting_frequency` | text | yes |  |
| `description` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.committee_member`

Members of each committee with period and chairperson flag. Xlsx: "Committees" rows 4-6.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `committee_id` | bigint | NO |  |
| `directorship_id` | bigint | NO |  |
| `is_chairperson` | boolean | NO |  |
| `start_date` | date | NO |  |
| `end_date` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.company`

One row per client company. Central entity of the platform. Xlsx: "Company Details".

Primary key: `id`  |  Unique: `cin`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `cin` | text | NO | Corporate Identification Number. 21 chars. Xlsx row 2. |
| `name` | text | NO |  |
| `pan` | text | yes |  |
| `date_of_incorporation` | date | NO |  |
| `roc` | text | yes |  |
| `category_id` | bigint | yes | Public/Private. References lookup_list code COMPANY_CATEGORY. Xlsx row 5. |
| `subcategory_id` | bigint | yes | Government/Small/OPC etc. References lookup_list code COMPANY_SUBCATEGORY. Xlsx row 6. |
| `registered_address` | text | yes |  |
| `correspondence_address` | text | yes |  |
| `phone` | text | yes |  |
| `fax` | text | yes |  |
| `email` | text | yes |  |
| `website` | text | yes |  |
| `is_listed` | boolean | NO |  |
| `market_value_rank` | integer | yes | Rank by market capitalisation among listed companies; used for SEBI top-1000 rules. |
| `ind_as_applicable` | boolean | NO | Whether Indian Accounting Standards (Ind AS) apply. Xlsx row 9 (implied). |
| `status` | text | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.company_business_activity`

Business activities of the company. Xlsx: "Company Details" row 19.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `description` | text | NO |  |
| `nic_code` | text | yes |  |
| `turnover_percent` | numeric | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.company_financials`

Annual financial figures per company per year. Used by rule evaluation views. Xlsx: "Company Details" rows 13-18, 26-30.

Primary key: `id`  |  Unique: `company_id, financial_year`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `turnover` | numeric | yes |  |
| `net_worth` | numeric | yes |  |
| `net_profit` | numeric | yes |  |
| `free_reserves` | numeric | yes |  |
| `securities_premium` | numeric | yes |  |
| `borrowings_banks_fi` | numeric | yes |  |
| `public_deposits` | numeric | yes |  |
| `debentures_outstanding` | numeric | yes |  |
| `csr_spend` | numeric | yes |  |
| `s185_limit` | numeric | yes |  |
| `s186_limit` | numeric | yes |  |
| `total_security_holders` | integer | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.company_relationship`

Holding/subsidiary/associate relationships. Xlsx: "Company Details" rows 21-24.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `relationship_type_id` | bigint | yes |  |
| `related_name` | text | NO |  |
| `related_cin` | text | yes |  |
| `related_company_id` | bigint | yes |  |
| `stake_percent` | numeric | yes |  |
| `valid_from` | date | yes |  |
| `valid_to` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.company_rta`

Registrar and Transfer Agent details, with period of engagement.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `name` | text | NO |  |
| `address` | text | yes |  |
| `phone` | text | yes |  |
| `email` | text | yes |  |
| `sebi_reg_no` | text | yes |  |
| `valid_from` | date | NO |  |
| `valid_to` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.director`

Individual master record for directors and KMPs. One row per person, not per company. Xlsx: "Directors & Key Managers".

Primary key: `id`  |  Unique: `din`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `din` | text | yes | Director Identification Number. 8 digits. NULL for non-director KMPs (CS, CFO). Xlsx row 2. |
| `full_name` | text | NO |  |
| `pan` | text | yes |  |
| `relative_name` | text | yes |  |
| `aadhaar_encrypted` | bytea | yes | Aadhaar encrypted with pgp_sym_encrypt. Key supplied at runtime. Never stored in plaintext. Xlsx row 5. |
| `date_of_birth` | date | yes |  |
| `gender` | text | yes |  |
| `nationality` | text | yes |  |
| `address` | text | yes |  |
| `email` | text | yes |  |
| `phone` | text | yes |  |
| `occupation` | text | yes |  |
| `dsc_valid_until` | date | yes | Digital Signature Certificate expiry date. Xlsx row 20. |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.director_declaration`

Annual interest, non-disqualification and independence declarations. Xlsx rows 34-36.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `directorship_id` | bigint | NO |  |
| `declaration_type` | text | NO |  |
| `financial_year` | text | NO |  |
| `on_file` | boolean | NO |  |
| `document_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.director_kyc`

DIR-3 KYC filing status per director per year. Xlsx row 21.

Primary key: `id`  |  Unique: `director_id, financial_year`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `director_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `dir3_kyc_filed` | boolean | NO |  |
| `filed_on` | date | yes |  |
| `srn` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.director_other_directorship`

Other directorships held by a person (outside this system). Used for Sec 165 directorship-limit check. Xlsx row 30-32.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `director_id` | bigint | NO |  |
| `other_company_name` | text | NO |  |
| `cin` | text | yes |  |
| `company_type_id` | bigint | yes |  |
| `designation` | text | yes |  |
| `start_date` | date | yes |  |
| `end_date` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.director_residency`

Whether a director was resident in India for >182 days in a financial year. Used by v_rule_resident_director. Xlsx row 26.

Primary key: `id`  |  Unique: `director_id, financial_year`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `director_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `resident_over_182` | boolean | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.directorship`

One row per stint of a director/KMP at a company. A resigned-and-reappointed person has two rows. Xlsx: "Directors & Key Managers" cols date-related.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `director_id` | bigint | NO |  |
| `start_date` | date | NO |  |
| `end_date` | date | yes | NULL if still serving. Xlsx row 18. |
| `cessation_reason` | text | yes | Why the stint ended (resignation, removal, expiry of term, death, etc.). Xlsx row 19. |
| `is_whole_time` | boolean | NO |  |
| `is_independent` | boolean | NO |  |
| `is_nominee` | boolean | NO |  |
| `is_additional` | boolean | NO |  |
| `is_alternate` | boolean | NO |  |
| `retires_by_rotation` | boolean | NO |  |
| `is_signatory` | boolean | NO |  |
| `is_board_member` | boolean | NO | False for non-director KMPs (CS, CFO without director designation). Xlsx row 33. |
| `director_category_id` | bigint | yes |  |
| `shares_held` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.directorship_role`

Designation history within a stint (e.g. Director -> Managing Director). Xlsx row 9.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `directorship_id` | bigint | NO |  |
| `designation_id` | bigint | NO |  |
| `start_date` | date | NO |  |
| `end_date` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.document`

Document records with type, storage path, hash and version. Phase 1: metadata only; no file upload.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `document_type_id` | bigint | yes |  |
| `filename` | text | NO |  |
| `storage_path` | text | yes |  |
| `mime_type` | text | yes |  |
| `sha256` | text | yes | SHA-256 of the file for integrity checking. |
| `version` | integer | NO |  |
| `uploaded_by` | bigint | yes |  |
| `extracted_data` | jsonb | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.document_chunk`

Document chunks for RAG/vector search. Stays empty in Phase 1. Embedding dimension 1536 is a placeholder — must be confirmed before real embeddings are loaded. IMPLEMENTATION LOG: 1536-dim placeholder.

Primary key: `id`  |  Unique: `document_id, chunk_no`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `document_id` | bigint | NO |  |
| `chunk_no` | integer | NO |  |
| `content` | text | yes |  |
| `embedding` | vector | yes |  |
| `metadata` | jsonb | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.document_type`

Registry of document types required or used across the platform. Seeded from xlsx sheets (Board Meetings, General Meetings, Auditors, ODI, ECB, etc.).

Primary key: `id`  |  Unique: `code`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `code` | text | NO |  |
| `name` | text | NO |  |
| `applies_to_entity` | text | yes |  |
| `is_mandatory` | boolean | NO |  |
| `description` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.ecb`

External Commercial Borrowing records. Xlsx: "ECB".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `lender_name` | text | NO |  |
| `lender_country` | text | NO |  |
| `lrn` | text | yes |  |
| `loan_amount` | numeric | NO |  |
| `currency` | text | NO |  |
| `interest_rate` | numeric | yes |  |
| `draw_down_date` | date | yes |  |
| `maturity_date` | date | yes |  |
| `amount_inr` | numeric | yes |  |
| `conversion_rate` | numeric | yes |  |
| `status_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.evidence_link`

Links a document to any core entity or ops task instance. entity_type validated against a registry list.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `document_id` | bigint | NO |  |
| `entity_type` | text | NO |  |
| `entity_id` | bigint | NO |  |
| `task_instance_id` | bigint | yes |  |
| `note` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.foreign_investment`

FC-GPR (new shares to foreign investor) and FC-TRS (transfer involving non-resident). Xlsx: Foreign Investment sheets.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `type_id` | bigint | NO | FC-GPR or FC-TRS from FOREIGN_INVESTMENT_TYPE lookup. |
| `allotment_id` | bigint | yes | Set for FC-GPR; NULL for FC-TRS. |
| `share_transfer_id` | bigint | yes | Set for FC-TRS; NULL for FC-GPR. |
| `foreign_currency` | text | NO |  |
| `foreign_amount` | numeric | NO |  |
| `conversion_rate` | numeric | NO |  |
| `amount_inr` | numeric | NO |  |
| `firc_number` | text | yes |  |
| `ad_bank` | text | yes |  |
| `board_approval_date` | date | yes |  |
| `funds_received_date` | date | yes |  |
| `filing_due_date` | date | yes |  |
| `filing_date` | date | yes |  |
| `approval_date` | date | yes |  |
| `status_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.government_filing`

Government e-form filings tracker. Xlsx: "Government Filings Tracker".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `form_name` | text | NO |  |
| `description` | text | yes |  |
| `financial_year` | text | yes |  |
| `due_date` | date | yes |  |
| `filing_date` | date | yes |  |
| `srn` | text | yes |  |
| `fee_paid` | numeric | yes |  |
| `status_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.independent_director_term`

First and second 5-year terms for independent directors. Total years served computed in v_independent_director_years. Xlsx row 22-24.

Primary key: `id`  |  Unique: `directorship_id, term_no`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `directorship_id` | bigint | NO |  |
| `term_no` | integer | NO |  |
| `start_date` | date | NO |  |
| `end_date` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.loan_deposit`

Outstanding borrowings in MGT-7 format: opening balance, movement, closing. Xlsx: "Loans & Deposits".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `borrowing_type` | text | NO |  |
| `opening_principal` | numeric | yes |  |
| `opening_interest_due` | numeric | yes |  |
| `opening_interest_accrued` | numeric | yes |  |
| `added_during_year` | numeric | yes |  |
| `reduced_during_year` | numeric | yes |  |
| `closing_principal` | numeric | yes |  |
| `closing_interest_due` | numeric | yes |  |
| `closing_interest_accrued` | numeric | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.lookup_list`

Master list of dropdown categories. Each row defines a named set of fixed options.

Primary key: `id`  |  Unique: `code`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `code` | text | NO |  |
| `name` | text | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.lookup_value`

Individual options within a lookup list. FK columns reference lookup_value.id and are validated by audit.validate_lookup().

Primary key: `id`  |  Unique: `list_id, code`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `list_id` | bigint | NO |  |
| `code` | text | NO |  |
| `label` | text | NO |  |
| `sort_order` | integer | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.meeting`

One record per meeting (board, committee, AGM, EGM, postal ballot meeting). Xlsx: "Board Meetings", "General Meetings", "Committee Meetings".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `meeting_type_id` | bigint | NO |  |
| `committee_id` | bigint | yes |  |
| `financial_year` | text | NO |  |
| `meeting_number` | text | yes | E.g. BM-1, AGM 1. Xlsx row 2. |
| `meeting_date` | date | NO |  |
| `start_time` | time without time zone | yes |  |
| `end_time` | time without time zone | yes |  |
| `venue` | text | yes |  |
| `venue_mode_id` | bigint | yes |  |
| `chairperson_directorship_id` | bigint | yes |  |
| `status` | text | NO |  |
| `remarks` | text | yes |  |
| `members_entitled` | integer | yes |  |
| `members_attended` | integer | yes |  |
| `due_date` | date | yes | Statutory due date — e.g. AGM must be held within 6 months of FY end. |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.meeting_agenda_item`

Agenda items for a meeting. Xlsx: "Board Meetings" row 6.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `meeting_id` | bigint | NO |  |
| `item_no` | integer | NO |  |
| `text` | text | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.meeting_attendance`

Attendance record per meeting per person. Xlsx: "Board Meetings" rows 9-11, "Committee Meetings & Attendance".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `meeting_id` | bigint | NO |  |
| `attendee_type` | text | NO |  |
| `directorship_id` | bigint | yes |  |
| `shareholder_id` | bigint | yes |  |
| `attended` | boolean | NO |  |
| `mode` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.odi`

ODI compliance records for companies with foreign subsidiaries. Xlsx: "ODI Compliances".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `foreign_subsidiary_name` | text | NO |  |
| `uin` | text | yes |  |
| `shares_purchased` | bigint | yes |  |
| `country` | text | yes |  |
| `total_investment_inr` | numeric | yes |  |
| `board_approval_date` | date | yes |  |
| `filing_date` | date | yes |  |
| `status_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.odi_step_down_subsidiary`

Step-down subsidiaries of the foreign subsidiary. Xlsx: "ODI Compliances" rows 4-5.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `odi_id` | bigint | NO |  |
| `name` | text | NO |  |
| `level` | integer | yes |  |
| `country` | text | yes |  |
| `parent_name` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.penalty_action`

Penalties, prosecutions and compounding records. Xlsx: "Penalties & Legal Actions".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `relates_to` | text | NO |  |
| `directorship_id` | bigint | yes |  |
| `action_type_id` | bigint | yes |  |
| `section` | text | yes |  |
| `description` | text | yes |  |
| `details` | text | yes |  |
| `amount` | numeric | yes |  |
| `authority_id` | bigint | yes |  |
| `appealed` | boolean | NO |  |
| `appeal_details` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.permission`

Primary key: `id`  |  Unique: `code`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `code` | text | NO |  |
| `description` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.portal_access`

Government/bank portal access records. Passwords stored encrypted with pgp_sym_encrypt; key supplied at runtime. Xlsx: "Portal Access".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | yes |  |
| `portal_name` | text | NO |  |
| `username` | text | yes |  |
| `held_by` | text | yes |  |
| `notes` | text | yes |  |
| `secret_encrypted` | bytea | yes | pgp_sym_encrypt(password, session_key). Key is supplied at runtime and never stored. |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.postal_ballot`

Postal ballot records. Xlsx: "Postal Ballot".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `particulars` | text | NO |  |
| `reason` | text | yes |  |
| `notice_date` | date | yes |  |
| `voting_opens` | date | yes |  |
| `voting_closes` | date | yes |  |
| `scrutinizer` | text | yes |  |
| `votes_for` | bigint | yes |  |
| `votes_against` | bigint | yes |  |
| `votes_invalid` | bigint | yes |  |
| `passed` | boolean | yes |  |
| `result_declared_date` | date | yes |  |
| `result_filed_date` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.remuneration`

Remuneration paid to directors and KMPs per financial year. Total is a generated column. Xlsx: "Remuneration".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `directorship_id` | bigint | yes |  |
| `person_name` | text | yes |  |
| `salary` | numeric | yes |  |
| `perquisites` | numeric | yes |  |
| `profits_in_lieu` | numeric | yes |  |
| `stock_options` | numeric | yes |  |
| `sweat_equity` | numeric | yes |  |
| `commission` | numeric | yes |  |
| `sitting_fees` | numeric | yes |  |
| `other_payments` | numeric | yes |  |
| `total` | numeric | yes | **Calculated (generated column).** Sum of all pay components. GENERATED ALWAYS — not manually writable. |
| `ceiling` | numeric | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.role`

Primary key: `id`  |  Unique: `name`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `name` | text | NO |  |
| `description` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.role_permission`

Primary key: `role_id, permission_id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `role_id` | bigint | NO |  |
| `permission_id` | bigint | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.rule_definition`

Applicability rules sourced from xlsx "When Something Becomes Required". Each row is one rule/limit; evaluation is done in rule_evaluation or computed views.

Primary key: `id`  |  Unique: `code`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `code` | text | NO | Short snake-case code; used by application and views. |
| `name` | text | NO |  |
| `law_reference` | text | yes |  |
| `applies_to_description` | text | yes |  |
| `trigger_description` | text | yes | Plain-English description of when the rule kicks in. Xlsx col: "When it kicks in". |
| `inputs_needed` | text | yes | What data fields are checked. Xlsx col: "What we need to know to check this". |
| `decides` | text | yes | What the rule determines. Xlsx col: "What it decides". |
| `responsible_party` | text | yes |  |
| `frequency` | text | yes |  |
| `is_active` | boolean | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.rule_evaluation`

Recorded results of rule evaluations per company per financial year. Manual entries in Phase 1; automated in later phases.

Primary key: `id`  |  Unique: `company_id, rule_id, financial_year, evaluated_on`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `rule_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `evaluated_on` | timestamp with time zone | NO |  |
| `applies` | boolean | yes |  |
| `status` | text | yes |  |
| `inputs` | jsonb | yes |  |
| `notes` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.s185_loan`

Loans, guarantees and securities for directors/connected persons under Section 185. Xlsx: "Loans to Directors (Sec 185)".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `beneficiary_description` | text | NO |  |
| `directorship_id` | bigint | yes |  |
| `loan_type` | text | NO |  |
| `amount` | numeric | NO |  |
| `exception_relied_on` | text | yes |  |
| `shareholder_approval` | boolean | yes |  |
| `approval_date` | date | yes |  |
| `approval_special_res_date` | date | yes |  |
| `board_meeting_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.s186_transaction`

Loans, guarantees, investments by the company under Section 186. Running total computed by v_s186_running_total. Xlsx: "Loans & Investments (Sec 186)".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `recipient_name` | text | NO |  |
| `transaction_type` | text | NO |  |
| `amount` | numeric | NO |  |
| `shareholder_approval` | boolean | NO |  |
| `approval_date` | date | yes |  |
| `board_meeting_id` | bigint | yes |  |
| `relationship_type_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.s188_related_party_txn`

Related party transactions under Section 188. Xlsx: "Related Party Txns (Sec 188)".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `related_party_name` | text | NO |  |
| `relationship_type_id` | bigint | yes |  |
| `related_directorship_id` | bigint | yes |  |
| `nature_of_txn` | text | NO |  |
| `transaction_value` | numeric | yes |  |
| `is_ordinary_course` | boolean | yes |  |
| `is_arms_length` | boolean | yes |  |
| `audit_committee_approval_date` | date | yes |  |
| `audit_committee_omnibus` | boolean | NO |  |
| `board_meeting_id` | bigint | yes |  |
| `shareholder_approval` | boolean | NO |  |
| `shareholder_approval_date` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.share_class`

A class of shares or debentures for a company. Xlsx: "Share Capital Summary" row 1.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `class_id` | bigint | NO |  |
| `nominal_value` | numeric | NO |  |
| `debenture_type_id` | bigint | yes |  |
| `description` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.share_transfer`

One record per share transfer. Xlsx: "Share Transfers".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `transferor_id` | bigint | NO |  |
| `transferee_id` | bigint | NO |  |
| `share_class_id` | bigint | NO |  |
| `number_of_shares` | bigint | NO |  |
| `transfer_date` | date | NO |  |
| `board_meeting_id` | bigint | yes |  |
| `face_value` | numeric | yes |  |
| `consideration` | numeric | yes |  |
| `stamp_duty_paid` | numeric | yes |  |
| `distinctive_from` | text | yes |  |
| `distinctive_to` | text | yes |  |
| `client_id` | text | yes |  |
| `dp_id` | text | yes |  |
| `transferee_folio` | text | yes |  |
| `sh4_available` | boolean | NO |  |
| `involves_non_resident` | boolean | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.shareholder`

Master record for each shareholder. One row per person/entity. Xlsx: "Shareholders".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `name` | text | NO |  |
| `father_spouse` | text | yes |  |
| `pan` | text | yes |  |
| `email` | text | yes |  |
| `address` | text | yes |  |
| `category_id` | bigint | yes | Promoter-Indian, Promoter-Foreign, Public etc. Xlsx row 9. |
| `is_fii` | boolean | NO |  |
| `is_foreign` | boolean | NO |  |
| `country` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.shareholding`

One row per holding period. Change in holding = new row + close old one. Current = valid_to IS NULL. Xlsx: "Shareholders".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `shareholder_id` | bigint | NO |  |
| `share_class_id` | bigint | NO |  |
| `folio_number` | text | yes |  |
| `is_demat` | boolean | NO |  |
| `client_id` | text | yes |  |
| `dp_id` | text | yes |  |
| `number_of_shares` | bigint | NO |  |
| `face_value` | numeric | NO |  |
| `distinctive_from` | text | yes |  |
| `distinctive_to` | text | yes |  |
| `pledged_percent` | numeric | yes |  |
| `valid_from` | date | NO |  |
| `valid_to` | date | yes | NULL when this is the current holding. Set to the date of the next change when superseded. |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.user_company_access`

Primary key: `id`  |  Unique: `user_id, company_id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `user_id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `access_level` | text | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `core.yearly_disclosure`

Other yearly disclosures required by MGT-7. Xlsx: "Other Yearly Disclosures".

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `financial_year` | text | NO |  |
| `disclosure_type` | text | NO |  |
| `details` | jsonb | yes |  |
| `key_date` | date | yes |  |
| `dividend_type_id` | bigint | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

## Schema `activity`


### `activity.activity_template`

Definition of a compliance activity (e.g. BOARD_MEETING). Versioned. Seeded with BOARD_MEETING v1.

Primary key: `id`  |  Unique: `code, version`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `code` | text | NO |  |
| `version` | integer | NO |  |
| `name` | text | NO |  |
| `obligation_ref` | text | yes |  |
| `description` | text | yes |  |
| `input_schema` | jsonb | yes |  |
| `status` | text | NO |  |
| `effective_from` | date | yes |  |
| `reviewed_by` | bigint | yes |  |
| `reviewed_on` | date | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `activity.entity_field_registry`

Registry of all core table columns. Populated from information_schema. Steps may only bind to registered fields.

Primary key: `id`  |  Unique: `table_name, column_name`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `table_name` | text | NO |  |
| `column_name` | text | NO |  |
| `description` | text | yes |  |
| `is_calculated` | boolean | NO | True for generated columns and view-derived values. step_data_binding rejects write on these. |

### `activity.step_data_binding`

Declares which core fields a step reads or writes. write on is_calculated=true is rejected by trigger.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `step_id` | bigint | NO |  |
| `field_id` | bigint | NO |  |
| `mode` | text | NO |  |
| `alias` | text | yes |  |
| `row_filter` | jsonb | yes |  |
| `note` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `activity.step_dependency`

DAG edges for step ordering. Same-template and no-cycle enforced by trigger.

Primary key: `step_id, depends_on_step_id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `step_id` | bigint | NO |  |
| `depends_on_step_id` | bigint | NO |  |

### `activity.step_evidence_requirement`

Documents required by a step.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `step_id` | bigint | NO |  |
| `document_type_id` | bigint | NO |  |
| `is_mandatory` | boolean | NO |  |
| `condition_note` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `activity.step_template`

Steps within an activity template. Each step has a type, deadline config and bindings.

Primary key: `id`  |  Unique: `template_id, step_key`; `template_id, seq`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `template_id` | bigint | NO |  |
| `step_key` | text | NO |  |
| `seq` | integer | NO |  |
| `title` | text | NO |  |
| `step_type` | text | NO |  |
| `instructions` | text | yes |  |
| `responsible_role` | text | yes |  |
| `is_mandatory` | boolean | NO |  |
| `deadline_anchor` | text | yes |  |
| `deadline_offset_days` | integer | yes |  |
| `deadline_direction` | text | yes |  |
| `ai_assisted` | boolean | NO |  |
| `requires_confirmation` | boolean | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

## Schema `ops`


### `ops.activity_instance`

One row per triggered compliance activity for a company.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `company_id` | bigint | NO |  |
| `template_id` | bigint | NO |  |
| `params` | jsonb | yes |  |
| `created_by` | bigint | NO |  |
| `status` | text | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `ops.confirmation`

Confirmation gate — no outbound communication happens without a named person confirming. Phase 1: table only.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `subject_type` | text | NO |  |
| `subject_id` | bigint | NO |  |
| `requested_by` | bigint | NO |  |
| `confirmed_by` | bigint | yes |  |
| `confirmed_at` | timestamp with time zone | yes |  |
| `status` | text | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `ops.task_instance`

One task per step per activity instance.

Primary key: `id`  |  Unique: `instance_id, step_id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `instance_id` | bigint | NO |  |
| `step_id` | bigint | NO |  |
| `status` | text | NO |  |
| `due_date` | date | yes |  |
| `completed_by` | bigint | yes |  |
| `completed_at` | timestamp with time zone | yes |  |
| `notes` | text | yes |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

### `ops.task_record_link`

Records which specific core rows each task involved.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `task_instance_id` | bigint | NO |  |
| `entity_type` | text | NO |  |
| `entity_id` | bigint | NO |  |
| `mode` | text | NO |  |
| `created_at` | timestamp with time zone | NO |  |
| `updated_at` | timestamp with time zone | NO |  |
| `is_archived` | boolean | NO |  |
| `archived_at` | timestamp with time zone | yes |  |
| `archived_by` | bigint | yes |  |

## Schema `audit`


### `audit.log`

Immutable change log. Every INSERT/UPDATE on business tables is recorded here via trigger.

Primary key: `id`

| Column | Type | Null? | Notes |
|---|---|---|---|
| `id` | bigint | NO |  |
| `table_schema` | text | NO |  |
| `table_name` | text | NO |  |
| `record_id` | bigint | yes |  |
| `operation` | text | NO |  |
| `actor` | bigint | NO | References core.app_user.id — not a FK to allow cross-schema flexibility. |
| `old_row` | jsonb | yes |  |
| `new_row` | jsonb | yes |  |
| `changed_at` | timestamp with time zone | NO |  |