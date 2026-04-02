CREATE TABLE IF NOT EXISTS accounts_emailverificationotp (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(254) NOT NULL,
    code VARCHAR(6) NOT NULL,
    session_token VARCHAR(128) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    attempts INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_otp_email ON accounts_emailverificationotp(email);
CREATE INDEX IF NOT EXISTS idx_otp_session ON accounts_emailverificationotp(session_token);

CREATE TABLE IF NOT EXISTS notifications_emaillog (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(500) NOT NULL,
    to_email VARCHAR(254) NOT NULL,
    template VARCHAR(200) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'sent',
    error TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_emaillog_created ON notifications_emaillog(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emaillog_status ON notifications_emaillog(status);
