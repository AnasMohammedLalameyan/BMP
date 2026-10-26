# Entity-Relationship Diagrams

Generated from the live PostgreSQL catalog (`pg_constraint`). `PK` = primary key, `FK` = foreign key, `UK` = unique key. Only key columns plus a few descriptive columns are drawn; see `DATA_DICTIONARY.md` for every column. Every relationship is `ON DELETE RESTRICT`.

Legend: `A ||--o{ B` means one A can have many B.

## Reference data and rules

```mermaid
erDiagram
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    lookup_list {
        bigint id PK
        text code UK
        text name
    }
    lookup_value {
        bigint id PK
        bigint list_id FK
        text code
        text label
        integer sort_order
    }
    rule_definition {
        bigint id PK
        text code UK
        text name
        text law_reference
        text applies_to_description
    }
    rule_evaluation {
        bigint id PK
        bigint company_id FK
        bigint rule_id FK
        text financial_year
        timestamp_with_time_zone evaluated_on
        boolean applies
    }
    company ||--o{ rule_evaluation : "company_id"
    lookup_list ||--o{ lookup_value : "list_id"
    lookup_value ||--o{ company : "category_id"
    lookup_value ||--o{ company : "subcategory_id"
    rule_definition ||--o{ rule_evaluation : "rule_id"
```

## Company

```mermaid
erDiagram
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    company_business_activity {
        bigint id PK
        bigint company_id FK
        text description
        text nic_code
        numeric turnover_percent
    }
    company_financials {
        bigint id PK
        bigint company_id FK
        text financial_year
        numeric turnover
        numeric net_worth
    }
    company_relationship {
        bigint id PK
        bigint company_id FK
        bigint relationship_type_id FK
        text related_name
        text related_cin
        bigint related_company_id FK
        numeric stake_percent
    }
    company_rta {
        bigint id PK
        bigint company_id FK
        text name
        text address
        text phone
    }
    lookup_value {
        bigint id PK
        bigint list_id FK
        text code
        text label
        integer sort_order
    }
    company ||--o{ company_business_activity : "company_id"
    company ||--o{ company_financials : "company_id"
    company ||--o{ company_relationship : "company_id"
    company ||--o{ company_relationship : "related_company_id"
    company ||--o{ company_rta : "company_id"
    lookup_value ||--o{ company : "category_id"
    lookup_value ||--o{ company : "subcategory_id"
    lookup_value ||--o{ company_relationship : "relationship_type_id"
```

## People, directors and auditors

```mermaid
erDiagram
    auditor {
        bigint id PK
        bigint company_id FK
        bigint auditor_type_id FK
        text name
        text pan
        text frn
    }
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    director {
        bigint id PK
        text din UK
        text full_name
        text pan
        text relative_name
    }
    director_declaration {
        bigint id PK
        bigint directorship_id FK
        text declaration_type
        text financial_year
        boolean on_file
        bigint document_id FK
    }
    director_kyc {
        bigint id PK
        bigint director_id FK
        text financial_year
        boolean dir3_kyc_filed
        date filed_on
    }
    director_other_directorship {
        bigint id PK
        bigint director_id FK
        text other_company_name
        text cin
        bigint company_type_id FK
        text designation
    }
    director_residency {
        bigint id PK
        bigint director_id FK
        text financial_year
        boolean resident_over_182
    }
    directorship {
        bigint id PK
        bigint company_id FK
        bigint director_id FK
        date start_date
        date end_date
        text cessation_reason
        bigint director_category_id FK
    }
    directorship_role {
        bigint id PK
        bigint directorship_id FK
        bigint designation_id FK
        date start_date
        date end_date
    }
    document {
        bigint id PK
        bigint company_id FK
        bigint document_type_id FK
        text filename
        text storage_path
        text mime_type
        bigint uploaded_by FK
    }
    independent_director_term {
        bigint id PK
        bigint directorship_id FK
        integer term_no
        date start_date
        date end_date
    }
    lookup_value {
        bigint id PK
        bigint list_id FK
        text code
        text label
        integer sort_order
    }
    company ||--o{ auditor : "company_id"
    company ||--o{ directorship : "company_id"
    company ||--o{ document : "company_id"
    director ||--o{ director_kyc : "director_id"
    director ||--o{ director_other_directorship : "director_id"
    director ||--o{ director_residency : "director_id"
    director ||--o{ directorship : "director_id"
    directorship ||--o{ director_declaration : "directorship_id"
    directorship ||--o{ directorship_role : "directorship_id"
    directorship ||--o{ independent_director_term : "directorship_id"
    document ||--o{ director_declaration : "document_id"
    lookup_value ||--o{ auditor : "auditor_type_id"
    lookup_value ||--o{ company : "category_id"
    lookup_value ||--o{ company : "subcategory_id"
    lookup_value ||--o{ director_other_directorship : "company_type_id"
    lookup_value ||--o{ directorship : "director_category_id"
    lookup_value ||--o{ directorship_role : "designation_id"
```

## Capital and members

```mermaid
erDiagram
    allotment {
        bigint id PK
        bigint company_id FK
        text round_reference
        bigint shareholder_id FK
        bigint share_class_id FK
        bigint number_of_shares
        date allotment_date
        bigint board_meeting_id FK
        bigint government_filing_id FK
    }
    capital_event {
        bigint id PK
        bigint company_id FK
        text financial_year
        text event_type
        bigint reason_id FK
        date event_date
    }
    capital_snapshot {
        bigint id PK
        bigint company_id FK
        bigint share_class_id FK
        text financial_year
        text snapshot_type
        date as_of_date
    }
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    foreign_investment {
        bigint id PK
        bigint company_id FK
        bigint type_id FK
        bigint allotment_id FK
        bigint share_transfer_id FK
        text foreign_currency
        numeric foreign_amount
        numeric conversion_rate
        bigint status_id FK
    }
    meeting {
        bigint id PK
        bigint company_id FK
        bigint meeting_type_id FK
        bigint committee_id FK
        text financial_year
        text meeting_number
        date meeting_date
        bigint venue_mode_id FK
        bigint chairperson_directorship_id FK
    }
    share_class {
        bigint id PK
        bigint company_id FK
        bigint class_id FK
        numeric nominal_value
        bigint debenture_type_id FK
        text description
    }
    share_transfer {
        bigint id PK
        bigint company_id FK
        bigint transferor_id FK
        bigint transferee_id FK
        bigint share_class_id FK
        bigint number_of_shares
        date transfer_date
        bigint board_meeting_id FK
        numeric face_value
    }
    shareholder {
        bigint id PK
        text name
        text father_spouse
        text pan
        bigint category_id FK
    }
    shareholding {
        bigint id PK
        bigint company_id FK
        bigint shareholder_id FK
        bigint share_class_id FK
        text folio_number
        boolean is_demat
        text client_id
    }
    allotment ||--o{ foreign_investment : "allotment_id"
    company ||--o{ allotment : "company_id"
    company ||--o{ capital_event : "company_id"
    company ||--o{ capital_snapshot : "company_id"
    company ||--o{ foreign_investment : "company_id"
    company ||--o{ meeting : "company_id"
    company ||--o{ share_class : "company_id"
    company ||--o{ share_transfer : "company_id"
    company ||--o{ shareholding : "company_id"
    meeting ||--o{ allotment : "board_meeting_id"
    meeting ||--o{ share_transfer : "board_meeting_id"
    share_class ||--o{ allotment : "share_class_id"
    share_class ||--o{ capital_snapshot : "share_class_id"
    share_class ||--o{ share_transfer : "share_class_id"
    share_class ||--o{ shareholding : "share_class_id"
    share_transfer ||--o{ foreign_investment : "share_transfer_id"
    shareholder ||--o{ allotment : "shareholder_id"
    shareholder ||--o{ share_transfer : "transferee_id"
    shareholder ||--o{ share_transfer : "transferor_id"
    shareholder ||--o{ shareholding : "shareholder_id"
```

## Governance (meetings and committees)

```mermaid
erDiagram
    circular_resolution {
        bigint id PK
        bigint company_id FK
        text reference
        date circulated_on
        text subject
        bigint noted_in_meeting_id FK
    }
    circular_resolution_response {
        bigint id PK
        bigint resolution_id FK
        bigint directorship_id FK
        text response
        date responded_on
    }
    committee {
        bigint id PK
        bigint company_id FK
        text name
        date constituted_on
        date dissolved_on
    }
    committee_member {
        bigint id PK
        bigint committee_id FK
        bigint directorship_id FK
        boolean is_chairperson
        date start_date
        date end_date
    }
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    directorship {
        bigint id PK
        bigint company_id FK
        bigint director_id FK
        date start_date
        date end_date
        text cessation_reason
        bigint director_category_id FK
    }
    meeting {
        bigint id PK
        bigint company_id FK
        bigint meeting_type_id FK
        bigint committee_id FK
        text financial_year
        text meeting_number
        date meeting_date
        bigint venue_mode_id FK
        bigint chairperson_directorship_id FK
    }
    meeting_agenda_item {
        bigint id PK
        bigint meeting_id FK
        integer item_no
        text text
    }
    meeting_attendance {
        bigint id PK
        bigint meeting_id FK
        text attendee_type
        bigint directorship_id FK
        bigint shareholder_id FK
        boolean attended
        text mode
    }
    postal_ballot {
        bigint id PK
        bigint company_id FK
        text particulars
        text reason
        date notice_date
    }
    shareholder {
        bigint id PK
        text name
        text father_spouse
        text pan
        bigint category_id FK
    }
    circular_resolution ||--o{ circular_resolution_response : "resolution_id"
    committee ||--o{ committee_member : "committee_id"
    committee ||--o{ meeting : "committee_id"
    company ||--o{ circular_resolution : "company_id"
    company ||--o{ committee : "company_id"
    company ||--o{ directorship : "company_id"
    company ||--o{ meeting : "company_id"
    company ||--o{ postal_ballot : "company_id"
    directorship ||--o{ circular_resolution_response : "directorship_id"
    directorship ||--o{ committee_member : "directorship_id"
    directorship ||--o{ meeting : "chairperson_directorship_id"
    directorship ||--o{ meeting_attendance : "directorship_id"
    meeting ||--o{ circular_resolution : "noted_in_meeting_id"
    meeting ||--o{ meeting_agenda_item : "meeting_id"
    meeting ||--o{ meeting_attendance : "meeting_id"
    shareholder ||--o{ meeting_attendance : "shareholder_id"
```

## Financial, legal and filings

```mermaid
erDiagram
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    directorship {
        bigint id PK
        bigint company_id FK
        bigint director_id FK
        date start_date
        date end_date
        text cessation_reason
        bigint director_category_id FK
    }
    ecb {
        bigint id PK
        bigint company_id FK
        text lender_name
        text lender_country
        text lrn
        bigint status_id FK
    }
    government_filing {
        bigint id PK
        bigint company_id FK
        text form_name
        text description
        text financial_year
        bigint status_id FK
    }
    loan_deposit {
        bigint id PK
        bigint company_id FK
        text financial_year
        text borrowing_type
        numeric opening_principal
    }
    odi {
        bigint id PK
        bigint company_id FK
        text foreign_subsidiary_name
        text uin
        bigint shares_purchased
        bigint status_id FK
    }
    odi_step_down_subsidiary {
        bigint id PK
        bigint odi_id FK
        text name
        integer level
        text country
    }
    penalty_action {
        bigint id PK
        bigint company_id FK
        text relates_to
        bigint directorship_id FK
        bigint action_type_id FK
        text section
        text description
        bigint authority_id FK
    }
    portal_access {
        bigint id PK
        bigint company_id FK
        text portal_name
        text username
        text held_by
    }
    remuneration {
        bigint id PK
        bigint company_id FK
        text financial_year
        bigint directorship_id FK
        text person_name
        numeric salary
    }
    s185_loan {
        bigint id PK
        bigint company_id FK
        text beneficiary_description
        bigint directorship_id FK
        text loan_type
        numeric amount
        bigint board_meeting_id FK
    }
    s186_transaction {
        bigint id PK
        bigint company_id FK
        text financial_year
        text recipient_name
        text transaction_type
        bigint board_meeting_id FK
        bigint relationship_type_id FK
    }
    s188_related_party_txn {
        bigint id PK
        bigint company_id FK
        text financial_year
        text related_party_name
        bigint relationship_type_id FK
        bigint related_directorship_id FK
        text nature_of_txn
        bigint board_meeting_id FK
    }
    yearly_disclosure {
        bigint id PK
        bigint company_id FK
        text financial_year
        text disclosure_type
        jsonb details
        bigint dividend_type_id FK
    }
    company ||--o{ directorship : "company_id"
    company ||--o{ ecb : "company_id"
    company ||--o{ government_filing : "company_id"
    company ||--o{ loan_deposit : "company_id"
    company ||--o{ odi : "company_id"
    company ||--o{ penalty_action : "company_id"
    company ||--o{ portal_access : "company_id"
    company ||--o{ remuneration : "company_id"
    company ||--o{ s185_loan : "company_id"
    company ||--o{ s186_transaction : "company_id"
    company ||--o{ s188_related_party_txn : "company_id"
    company ||--o{ yearly_disclosure : "company_id"
    directorship ||--o{ penalty_action : "directorship_id"
    directorship ||--o{ remuneration : "directorship_id"
    directorship ||--o{ s185_loan : "directorship_id"
    directorship ||--o{ s188_related_party_txn : "related_directorship_id"
    odi ||--o{ odi_step_down_subsidiary : "odi_id"
```

## Documents, evidence and users

```mermaid
erDiagram
    app_user {
        bigint id PK
        text email UK
        text name
        bigint role_id FK
        boolean is_active
    }
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    document {
        bigint id PK
        bigint company_id FK
        bigint document_type_id FK
        text filename
        text storage_path
        text mime_type
        bigint uploaded_by FK
    }
    document_chunk {
        bigint id PK
        bigint document_id FK
        integer chunk_no
        text content
        vector embedding
    }
    document_type {
        bigint id PK
        text code UK
        text name
        text applies_to_entity
        boolean is_mandatory
    }
    evidence_link {
        bigint id PK
        bigint document_id FK
        text entity_type
        bigint entity_id
        bigint task_instance_id FK
        text note
    }
    permission {
        bigint id PK
        text code UK
        text description
    }
    role {
        bigint id PK
        text name UK
        text description
    }
    role_permission {
        bigint role_id FK
        bigint permission_id FK
    }
    task_instance {
        bigint id PK
        bigint instance_id FK
        bigint step_id FK
        text status
        date due_date
        bigint completed_by FK
        timestamp_with_time_zone completed_at
    }
    user_company_access {
        bigint id PK
        bigint user_id FK
        bigint company_id FK
        text access_level
    }
    app_user ||--o{ document : "uploaded_by"
    app_user ||--o{ task_instance : "completed_by"
    app_user ||--o{ user_company_access : "user_id"
    company ||--o{ document : "company_id"
    company ||--o{ user_company_access : "company_id"
    document ||--o{ document_chunk : "document_id"
    document ||--o{ evidence_link : "document_id"
    document_type ||--o{ document : "document_type_id"
    permission ||--o{ role_permission : "permission_id"
    role ||--o{ app_user : "role_id"
    role ||--o{ role_permission : "role_id"
    task_instance ||--o{ evidence_link : "task_instance_id"
```

## Activity (definitions) and Ops (instances)

```mermaid
erDiagram
    activity_instance {
        bigint id PK
        bigint company_id FK
        bigint template_id FK
        jsonb params
        bigint created_by FK
        text status
    }
    activity_template {
        bigint id PK
        text code
        integer version
        text name
        bigint reviewed_by FK
    }
    app_user {
        bigint id PK
        text email UK
        text name
        bigint role_id FK
        boolean is_active
    }
    company {
        bigint id PK
        text cin UK
        text name
        text pan
        date date_of_incorporation
        bigint category_id FK
        bigint subcategory_id FK
    }
    confirmation {
        bigint id PK
        text subject_type
        bigint subject_id
        bigint requested_by FK
        bigint confirmed_by FK
        timestamp_with_time_zone confirmed_at
    }
    document_type {
        bigint id PK
        text code UK
        text name
        text applies_to_entity
        boolean is_mandatory
    }
    entity_field_registry {
        bigint id PK
        text table_name
        text column_name
        text description
    }
    evidence_link {
        bigint id PK
        bigint document_id FK
        text entity_type
        bigint entity_id
        bigint task_instance_id FK
        text note
    }
    step_data_binding {
        bigint id PK
        bigint step_id FK
        bigint field_id FK
        text mode
        text alias
        jsonb row_filter
    }
    step_dependency {
        bigint step_id FK
        bigint depends_on_step_id FK
    }
    step_evidence_requirement {
        bigint id PK
        bigint step_id FK
        bigint document_type_id FK
        boolean is_mandatory
        text condition_note
    }
    step_template {
        bigint id PK
        bigint template_id FK
        text step_key
        integer seq
        text title
    }
    task_instance {
        bigint id PK
        bigint instance_id FK
        bigint step_id FK
        text status
        date due_date
        bigint completed_by FK
        timestamp_with_time_zone completed_at
    }
    task_record_link {
        bigint id PK
        bigint task_instance_id FK
        text entity_type
        bigint entity_id
        text mode
    }
    activity_instance ||--o{ task_instance : "instance_id"
    activity_template ||--o{ activity_instance : "template_id"
    activity_template ||--o{ step_template : "template_id"
    app_user ||--o{ activity_instance : "created_by"
    app_user ||--o{ activity_template : "reviewed_by"
    app_user ||--o{ confirmation : "confirmed_by"
    app_user ||--o{ confirmation : "requested_by"
    app_user ||--o{ task_instance : "completed_by"
    company ||--o{ activity_instance : "company_id"
    document_type ||--o{ step_evidence_requirement : "document_type_id"
    entity_field_registry ||--o{ step_data_binding : "field_id"
    step_template ||--o{ step_data_binding : "step_id"
    step_template ||--o{ step_dependency : "depends_on_step_id"
    step_template ||--o{ step_dependency : "step_id"
    step_template ||--o{ step_evidence_requirement : "step_id"
    step_template ||--o{ task_instance : "step_id"
    task_instance ||--o{ evidence_link : "task_instance_id"
    task_instance ||--o{ task_record_link : "task_instance_id"
```
