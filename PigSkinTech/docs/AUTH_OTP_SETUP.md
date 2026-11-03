# Authentication OTP upgrade

## What changed

- The login screen now supports existing email/password accounts, email or
  Vietnamese mobile OTP login, verified email/phone registration, and password
  recovery.
- Email registration also offers a no-OTP option. These accounts can sign in
  with their password, remain unverified, and must verify email ownership later
  to use OTP-based password recovery.
- New self-registrations always receive the `user` role. Existing roles and
  account records are not rewritten.
- OTPs are generated with `secrets`, expire after five minutes, are stored as
  a peppered HMAC digest, are single-use, allow at most five guesses, and are
  rate-limited to one request per minute and five requests per hour per
  destination and purpose.
- SMTP email and HTTPS JSON SMS delivery adapters are provided. Neither
  provider is enabled until configured. No provider credentials or OTP values
  are written to application logs.

## LocalDB migration

The current `dbo.users` table has a required unique email column and no phone
or verification fields. OTP challenges also require a new table. The
backward-compatible, idempotent SQL proposal is
[`../migrations/001_auth_otp.sql`](../migrations/001_auth_otp.sql). It:

1. Adds nullable `phone` plus `email_verified` and `phone_verified` fields.
   Existing rows receive verification state `0`; their email/password login
   remains unchanged. A legacy account may verify its saved email via the
   password-reset OTP flow; successful ownership verification marks it verified.
2. Makes `email` nullable, replacing the email constraint with filtered unique
   indexes for non-null email and phone values. This permits phone-only
   accounts without changing existing email values.
3. Adds the OTP challenge table and a rate-limit index. Only salted, peppered
   digests are stored; OTP plaintext is never stored.

The approved migration was applied to the local `PigSkinAI` database on
2026-11-04 after creating and verifying a `COPY_ONLY` SQL Server backup. The
backup is stored locally and is not included in this repository. All three
existing account rows, including their email, password hashes, and roles, were
fingerprint-checked and remained unchanged. OTP remains unavailable until an
email or SMS provider and the OTP pepper are configured.
When applying this migration with `sqlcmd`, enable `QUOTED_IDENTIFIER` with
the `-I` option; filtered indexes require that SQL session setting.

The prior first-signup-as-Admin behavior is intentionally removed for new
registrations. To provision an administrator in a brand-new installation,
use a separately approved owner-controlled setup procedure; the signup form
cannot create or promote an Expert or Admin. Existing Admin accounts are
unchanged.

## Provider configuration

Set secrets in the Windows user or machine environment, not in source files or
checked-in `.env` files. `PIGSKIN_OTP_PEPPER` must be a randomly generated
secret of at least 32 bytes; keep it in a protected secret store and back it up
separately from the database. Losing it invalidates outstanding OTPs, but does
not affect account passwords.

### SMTP email

Required variables:

- `PIGSKIN_SMTP_HOST`
- `PIGSKIN_SMTP_PORT` (defaults to `587`)
- `PIGSKIN_SMTP_USER`
- `PIGSKIN_SMTP_PASSWORD`
- `PIGSKIN_SMTP_FROM`
- `PIGSKIN_OTP_PEPPER`

Port 587 uses STARTTLS. Set `PIGSKIN_SMTP_SSL=1` for implicit TLS (typically
port 465). The app only reports that SMTP accepted the message; it cannot
guarantee delivery to the recipient's inbox.

For Gmail, create a Google App Password after enabling 2-Step Verification,
then run
`powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\configure_gmail_otp.ps1`
from the application folder. The script prompts for the App Password without
echoing it, generates a fresh random OTP pepper, and saves the values in the
current Windows user's environment. Do not paste the App Password into chat or
source files. Restart the application after configuration.

### SMS provider

Required variables:

- `PIGSKIN_SMS_ENDPOINT` (HTTPS endpoint)
- `PIGSKIN_SMS_API_KEY` (Bearer token)
- `PIGSKIN_OTP_PEPPER`

The adapter sends a JSON `POST` with `to` (E.164, e.g. `+84901234567`) and
`message` fields, and treats a 2xx response as provider acceptance. Configure
only a provider that supports Vietnamese numbers and this request contract, or
adapt `SMSOTPProvider` to that provider's documented API. No provider is
selected or purchased by this application.

With missing provider settings or pepper, OTP requests display
**“Chưa cấu hình dịch vụ gửi mã.”** In the forgot-password flow, responses stay
generic to avoid disclosing whether an account exists.

## Safe verification

The OTP unit tests use scripted database connections and mock providers. The
migration and SQL-backed OTP create/verify/expiry/one-use/hourly-limit paths
were also exercised on uniquely named disposable LocalDB databases seeded
with the legacy `dbo.users` schema and an Admin row. The email, password hash,
and role remained unchanged; the migration succeeded twice; and both test
databases were removed afterward. The migration is not auto-applied by
application startup; it was separately approved, backed up, and applied to
`PigSkinAI` as described above.
