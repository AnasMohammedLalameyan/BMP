-- 008_core_documents_evidence_users.sql
-- Documents, evidence links, document chunks (vector), users, roles, RLS.

-- ============================================================
-- DOCUMENT
-- ============================================================
CREATE TABLE IF NOT EXISTS core.document (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id        bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    document_type_id  bigint REFERENCES core.document_type(id) ON DELETE RESTRICT,
    filename          text   NOT NULL,
    storage_path      text,
    mime_type         text,
    sha256            text,
    version           int    NOT NULL DEFAULT 1,
    uploaded_by       bigint,   -- FK to core.app_user set after users table
    extracted_data    jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.document IS 'Document records with type, storage path, hash and version. Phase 1: metadata only; no file upload.';
COMMENT ON COLUMN core.document.sha256 IS 'SHA-256 of the file for integrity checking.';
CREATE INDEX IF NOT EXISTS document_company_idx ON core.document (company_id);
CREATE INDEX IF NOT EXISTS document_type_idx    ON core.document (document_type_id);

-- ============================================================
-- EVIDENCE_LINK
-- Durable link from a document to any core record or to an ops task.
-- FR-3 requirement.
-- ============================================================
CREATE TABLE IF NOT EXISTS core.evidence_link (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id       bigint NOT NULL REFERENCES core.document(id) ON DELETE RESTRICT,
    entity_type       text   NOT NULL,   -- e.g. 'meeting', 'directorship', 'allotment'
    entity_id         bigint NOT NULL,
    task_instance_id  bigint,            -- FK to ops.task_instance, set in migration 009
    note              text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.evidence_link IS 'Links a document to any core entity or ops task instance. entity_type validated against a registry list.';
CREATE INDEX IF NOT EXISTS evidence_link_doc_idx    ON core.evidence_link (document_id);
CREATE INDEX IF NOT EXISTS evidence_link_entity_idx ON core.evidence_link (entity_type, entity_id);

-- ============================================================
-- DOCUMENT_CHUNK  (for future RAG / vector search)
-- Structure only in Phase 1 — stays empty.
-- Vector dimension 1536 is a placeholder; confirm before loading embeddings.
-- ============================================================
-- The vector extension is mandatory (created by setup_db.py); no text fallback.
CREATE TABLE IF NOT EXISTS core.document_chunk (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id bigint NOT NULL REFERENCES core.document(id) ON DELETE RESTRICT,
    chunk_no    int    NOT NULL,
    content     text,
    embedding   vector(1536),   -- placeholder dimension — confirm before real embeddings
    metadata    jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (document_id, chunk_no)
);
CREATE INDEX IF NOT EXISTS doc_chunk_document_idx ON core.document_chunk (document_id);
CREATE INDEX IF NOT EXISTS doc_chunk_embedding_hnsw_idx ON core.document_chunk USING hnsw (embedding vector_cosine_ops);
COMMENT ON TABLE core.document_chunk IS 'Document chunks for RAG/vector search. Stays empty in Phase 1. Embedding dimension 1536 is a placeholder — must be confirmed before real embeddings are loaded. IMPLEMENTATION LOG: 1536-dim placeholder.';

-- ============================================================
-- APP_USER
-- ============================================================
CREATE TABLE IF NOT EXISTS core.app_user (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       text   NOT NULL UNIQUE,
    name        text   NOT NULL,
    role_id     bigint,   -- FK set after role table
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.app_user IS 'Platform users. No passwords stored — authentication is handled by the FastAPI layer (later phase).';

-- ============================================================
-- ROLE & PERMISSIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS core.role (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text   NOT NULL UNIQUE,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);

CREATE TABLE IF NOT EXISTS core.permission (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        text   NOT NULL UNIQUE,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);

CREATE TABLE IF NOT EXISTS core.role_permission (
    role_id       bigint NOT NULL REFERENCES core.role(id)       ON DELETE RESTRICT,
    permission_id bigint NOT NULL REFERENCES core.permission(id) ON DELETE RESTRICT,
    PRIMARY KEY (role_id, permission_id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
CREATE INDEX IF NOT EXISTS role_perm_role_idx ON core.role_permission (role_id);

-- ============================================================
-- USER_COMPANY_ACCESS
-- ============================================================
CREATE TABLE IF NOT EXISTS core.user_company_access (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      bigint NOT NULL REFERENCES core.app_user(id) ON DELETE RESTRICT,
    company_id   bigint NOT NULL REFERENCES core.company(id)  ON DELETE RESTRICT,
    access_level text   NOT NULL DEFAULT 'read',
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    is_archived  boolean     NOT NULL DEFAULT false,
    archived_at  timestamptz,
    archived_by  bigint,
    UNIQUE (user_id, company_id)
);
CREATE INDEX IF NOT EXISTS uca_user_idx    ON core.user_company_access (user_id);
CREATE INDEX IF NOT EXISTS uca_company_idx ON core.user_company_access (company_id);

-- ============================================================
-- Add deferred FKs now that app_user and role exist
-- ============================================================
ALTER TABLE core.app_user
    ADD CONSTRAINT app_user_role_fk
    FOREIGN KEY (role_id) REFERENCES core.role(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS app_user_role_idx ON core.app_user (role_id);

ALTER TABLE core.document
    ADD CONSTRAINT document_uploaded_by_fk
    FOREIGN KEY (uploaded_by) REFERENCES core.app_user(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS document_uploaded_by_idx ON core.document (uploaded_by);

-- Add deferred FK from director_declaration to document
ALTER TABLE core.director_declaration
    ADD CONSTRAINT director_declaration_document_fk
    FOREIGN KEY (document_id) REFERENCES core.document(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS dir_declaration_doc_idx ON core.director_declaration (document_id);
