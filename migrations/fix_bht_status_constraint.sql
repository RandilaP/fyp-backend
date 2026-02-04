-- Migration to fix BHT records status constraint
-- This updates the check constraint to allow 'finalized' status

-- First, drop the existing constraint
ALTER TABLE bht_records DROP CONSTRAINT IF EXISTS bht_records_status_check;

-- Add the corrected constraint with all valid status values
ALTER TABLE bht_records
ADD CONSTRAINT bht_records_status_check
CHECK (status IN ('draft', 'finalized', 'approved', 'rejected'));

-- Verify the constraint
SELECT constraint_name, check_clause 
FROM information_schema.check_constraints 
WHERE constraint_name = 'bht_records_status_check';
