-- Migration: Add patient summary fields to llm_reports table
-- This allows llm_reports to store patient summaries (combining all BHTs)
-- instead of just individual BHT summaries

-- Add new columns
ALTER TABLE llm_reports 
  ADD COLUMN IF NOT EXISTS patient_id UUID REFERENCES patients(patient_id),
  ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(user_id),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Make bht_id nullable (since patient summaries don't have a single bht_id)
ALTER TABLE llm_reports 
  ALTER COLUMN bht_id DROP NOT NULL;

-- Create unique index to ensure one summary per patient
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_reports_patient 
  ON llm_reports(patient_id) 
  WHERE patient_id IS NOT NULL;

-- Add check constraint for status values
ALTER TABLE llm_reports 
  ADD CONSTRAINT chk_llm_report_status 
  CHECK (status IN ('draft', 'submitted', 'approved', 'rejected'));

-- Add comment
COMMENT ON COLUMN llm_reports.patient_id IS 'Patient ID for patient-level summaries (null for BHT-level reports)';
COMMENT ON COLUMN llm_reports.status IS 'Status: draft, submitted, approved, rejected';
COMMENT ON COLUMN llm_reports.created_by IS 'User who created the summary (doctor)';
