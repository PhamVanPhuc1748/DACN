SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID('dbo.users', 'U') IS NULL
    THROW 51000, 'dbo.users must exist before applying the auth OTP migration.', 1;

IF COL_LENGTH('dbo.users', 'phone') IS NULL
    ALTER TABLE dbo.users ADD phone NVARCHAR(20) NULL;
IF COL_LENGTH('dbo.users', 'email_verified') IS NULL
    ALTER TABLE dbo.users ADD email_verified BIT NOT NULL
        CONSTRAINT DF_users_email_verified DEFAULT (0) WITH VALUES;
IF COL_LENGTH('dbo.users', 'phone_verified') IS NULL
    ALTER TABLE dbo.users ADD phone_verified BIT NOT NULL
        CONSTRAINT DF_users_phone_verified DEFAULT (0) WITH VALUES;

DECLARE @email_unique_constraint SYSNAME;
SELECT TOP (1) @email_unique_constraint = kc.name
FROM sys.key_constraints AS kc
JOIN sys.index_columns AS ic
  ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
JOIN sys.columns AS c
  ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE kc.parent_object_id = OBJECT_ID('dbo.users')
  AND kc.type = 'UQ'
  AND c.name = 'email'
  AND ic.key_ordinal = 1
  AND NOT EXISTS (
      SELECT 1
      FROM sys.index_columns AS extra
      WHERE extra.object_id = kc.parent_object_id
        AND extra.index_id = kc.unique_index_id
        AND extra.key_ordinal > 1
  );
IF @email_unique_constraint IS NOT NULL
BEGIN
    DECLARE @drop_email_constraint NVARCHAR(512);
    SET @drop_email_constraint = N'ALTER TABLE dbo.users DROP CONSTRAINT '
        + QUOTENAME(@email_unique_constraint);
    EXEC sys.sp_executesql @drop_email_constraint;
END;

IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.users')
      AND name = 'email' AND is_nullable = 0
)
    ALTER TABLE dbo.users ALTER COLUMN email NVARCHAR(320) NULL;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.users') AND name = 'UX_users_email'
)
    EXEC sys.sp_executesql N'CREATE UNIQUE INDEX UX_users_email
        ON dbo.users(email) WHERE email IS NOT NULL';
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.users') AND name = 'UX_users_phone'
)
    EXEC sys.sp_executesql N'CREATE UNIQUE INDEX UX_users_phone
        ON dbo.users(phone) WHERE phone IS NOT NULL';
IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.users')
      AND name = 'CK_users_contact'
)
    EXEC sys.sp_executesql N'ALTER TABLE dbo.users ADD CONSTRAINT CK_users_contact
        CHECK (email IS NOT NULL OR phone IS NOT NULL)';

IF OBJECT_ID('dbo.auth_otp_challenges', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.auth_otp_challenges (
        challenge_id CHAR(64) NOT NULL PRIMARY KEY,
        destination NVARCHAR(320) NOT NULL,
        channel NVARCHAR(10) NOT NULL
            CHECK (channel IN ('email', 'sms')),
        purpose NVARCHAR(24) NOT NULL
            CHECK (purpose IN ('login', 'registration', 'password_reset')),
        salt CHAR(32) NOT NULL,
        code_hash CHAR(64) NOT NULL,
        created_at DATETIME2(3) NOT NULL,
        expires_at DATETIME2(3) NOT NULL,
        attempts TINYINT NOT NULL DEFAULT (0)
            CHECK (attempts BETWEEN 0 AND 5),
        consumed_at DATETIME2(3) NULL,
        CHECK (expires_at > created_at)
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.auth_otp_challenges')
      AND name = 'IX_auth_otp_destination_purpose_created'
)
    CREATE INDEX IX_auth_otp_destination_purpose_created
        ON dbo.auth_otp_challenges(destination, purpose, created_at);

COMMIT TRANSACTION;
