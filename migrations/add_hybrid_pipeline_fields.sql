-- Migration: Add hybrid pipeline fields to bht_records table
-- Date: 2026-02-16
-- Description: Adds raw_ocr_text and confidence_score columns to support 
--              the hybrid TrOCR + Gemini RAG pipeline

-- Add raw_ocr_text field to store the unprocessed TrOCR output
ALTER TABLE bht_records 
ADD COLUMN IF NOT EXISTS raw_ocr_text TEXT;

-- Add confidence_score field to track extraction confidence
ALTER TABLE bht_records 
ADD COLUMN IF NOT EXISTS confidence_score DECIMAL(3,2) 
CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);

-- Add comments for documentation
COMMENT ON COLUMN bht_records.raw_ocr_text IS 
'Raw OCR output from TrOCR Stage 1 before semantic post-correction (hybrid pipeline only)';

COMMENT ON COLUMN bht_records.confidence_score IS 
'Confidence score of the extraction process (0.0 to 1.0), calculated by Gemini Stage 2';

-- Create index on confidence_score for analytics queries
CREATE INDEX IF NOT EXISTS idx_bht_records_confidence_score 
ON bht_records(confidence_score DESC) 
WHERE confidence_score IS NOT NULL;

-- Migration complete
