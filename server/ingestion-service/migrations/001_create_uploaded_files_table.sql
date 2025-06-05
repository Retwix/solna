-- Migration: Create uploaded_files table
-- Description: Creates a table to store file upload events with metadata
-- Date: 2024

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the uploaded_files table
CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(1000) NOT NULL,
    event VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_uploaded_files_filename ON uploaded_files(filename);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_event ON uploaded_files(event);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_created_at ON uploaded_files(created_at);

-- Add comments for documentation
COMMENT ON TABLE uploaded_files IS 'Stores metadata about uploaded files and their associated events';
COMMENT ON COLUMN uploaded_files.id IS 'Unique identifier for each file upload record';
COMMENT ON COLUMN uploaded_files.filename IS 'Full path of the uploaded file';
COMMENT ON COLUMN uploaded_files.event IS 'Name of the root file where this file is being hosted';
COMMENT ON COLUMN uploaded_files.created_at IS 'Timestamp when the record was created';
