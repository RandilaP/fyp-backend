-- Migration script to add approval workflow and analytics fields to bht_records table
-- Run this in your Supabase SQL editor

-- Add approval workflow columns (FR3)
ALTER TABLE bht_records
ADD COLUMN IF NOT EXISTS approved_by_consultant_id UUID REFERENCES users(user_id),
ADD COLUMN IF NOT EXISTS rejected_by_consultant_id UUID REFERENCES users(user_id),
ADD COLUMN IF NOT EXISTS finalized_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS rejected_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
ADD COLUMN IF NOT EXISTS discharge_timestamp TIMESTAMPTZ;

-- Add performance analytics columns (FR6 - Objective R07)
ALTER TABLE bht_records
ADD COLUMN IF NOT EXISTS wer DOUBLE PRECISION,  -- Word Error Rate
ADD COLUMN IF NOT EXISTS ner_f1_score DOUBLE PRECISION;  -- NER F1-Score

-- Create index for performance queries
CREATE INDEX IF NOT EXISTS idx_bht_records_status ON bht_records(status);
CREATE INDEX IF NOT EXISTS idx_bht_records_upload_date ON bht_records(upload_date);
CREATE INDEX IF NOT EXISTS idx_bht_records_finalized_date ON bht_records(finalized_date);

-- Create e-IMMR exports table for audit trail (optional but recommended)
CREATE TABLE IF NOT EXISTS eimmr_exports (
    export_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bht_id UUID REFERENCES bht_records(bht_id) ON DELETE CASCADE,
    export_data JSONB NOT NULL,
    exported_by UUID REFERENCES users(user_id),
    exported_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eimmr_exports_bht_id ON eimmr_exports(bht_id);
CREATE INDEX IF NOT EXISTS idx_eimmr_exports_exported_at ON eimmr_exports(exported_at);

-- Create audit_log table for tracking rejections and notifications (optional but recommended)
CREATE TABLE IF NOT EXISTS audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    performed_by UUID REFERENCES users(user_id),
    target_user UUID REFERENCES users(user_id),
    details JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);

-- Add comments for documentation
COMMENT ON COLUMN bht_records.approved_by_consultant_id IS 'Consultant who approved/finalized the record (FR3)';
COMMENT ON COLUMN bht_records.rejected_by_consultant_id IS 'Consultant who rejected the record (FR3)';
COMMENT ON COLUMN bht_records.finalized_date IS 'Timestamp when record was finalized for KPI calculations';
COMMENT ON COLUMN bht_records.discharge_timestamp IS 'Patient discharge time for Bed Occupancy Rate (BOR) calculation';
COMMENT ON COLUMN bht_records.wer IS 'Word Error Rate - OCR accuracy metric (Objective R07)';
COMMENT ON COLUMN bht_records.ner_f1_score IS 'Named Entity Recognition F1-Score (Objective R07)';

COMMENT ON TABLE eimmr_exports IS 'e-IMMR (Electronic Integrated Medical Record) exports for approved BHT records';
COMMENT ON TABLE audit_log IS 'Audit trail for tracking system actions, approvals, rejections, and notifications';
