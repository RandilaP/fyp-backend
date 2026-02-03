-- Migration script to add account approval fields to users table
-- Run this in your Supabase SQL editor

-- Add account status and approval tracking columns
ALTER TABLE users
ADD COLUMN IF NOT EXISTS account_status VARCHAR(20) DEFAULT 'approved' CHECK (account_status IN ('pending', 'approved', 'rejected')),
ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(user_id),
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES users(user_id),
ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_account_status ON users(account_status);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Add comments for documentation
COMMENT ON COLUMN users.account_status IS 'Account approval status: pending (awaiting approval), approved (can login), rejected (registration denied)';
COMMENT ON COLUMN users.approved_by IS 'Consultant/Admin who approved the registration';
COMMENT ON COLUMN users.approved_at IS 'Timestamp when the account was approved';
COMMENT ON COLUMN users.rejected_by IS 'Consultant/Admin who rejected the registration';
COMMENT ON COLUMN users.rejected_at IS 'Timestamp when the account was rejected';
COMMENT ON COLUMN users.rejection_reason IS 'Reason provided for account rejection';

-- Update existing users to 'approved' status if they don't have a status
UPDATE users 
SET account_status = 'approved' 
WHERE account_status IS NULL;
