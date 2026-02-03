-- Migration script to add ward assignment to users table
-- Run this in your Supabase SQL editor

-- Add ward_id column to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS ward_id UUID REFERENCES wards(ward_id);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_users_ward_id ON users(ward_id);

-- Add comment for documentation
COMMENT ON COLUMN users.ward_id IS 'Ward assignment for doctors. Required during doctor registration, optional for consultants/admins.';

-- Note: Existing users will have NULL ward_id
-- Doctors should update their ward assignment or be assigned by admins
