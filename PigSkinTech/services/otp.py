"""OTP delivery and one-time challenge handling for desktop account flows."""

import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.error import URLError
from urllib.request import Request, urlopen

from services.database import conn

CODE_LIFETIME = timedelta(minutes=5)
RESEND_INTERVAL = timedelta(seconds=60)
MAX_REQUESTS_PER_HOUR = 5
MAX_ATTEMPTS = 5


class OTPError(ValueError):
    """An expected, safe-to-display OTP flow error."""


class OTPNotConfiguredError(OTPError):
    """No usable delivery provider or OTP pepper is configured."""

class OTPMigrationRequiredError(OTPError):
    """The explicitly approved account/OTP schema migration is not applied."""


class OTPDeliveryError(OTPError):
    """A provider did not accept the OTP message."""


class OTPRateLimitError(OTPError):
    """The destination exceeded an OTP resend limit."""


class OTPInvalidError(OTPError):
    """The challenge is invalid, expired, exhausted, or already used."""


def normalize_email(value):
    if not isinstance(value, str):
        raise ValueError('Vui lòng nhập địa chỉ email hợp lệ.')
    address = value.strip().lower()
    if len(address) > 320 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', address):
        raise ValueError('Vui lòng nhập địa chỉ email hợp lệ.')
    return address


def normalize_vietnam_phone(value):
    if not isinstance(value, str):
        raise ValueError('Vui lòng nhập số điện thoại di động Việt Nam hợp lệ.')
    digits = re.sub(r'[\s().-]', '', value)
    if digits.startswith('+84'):
        digits = '0' + digits[3:]
    elif digits.startswith('84'):
        digits = '0' + digits[2:]
    if not re.fullmatch(r'0(?:3|5|7|8|9)\d{8}', digits):
        raise ValueError('Vui lòng nhập số điện thoại di động Việt Nam hợp lệ.')
    return '+84' + digits[1:]


def normalize_contact(value, channel):
    if channel == 'email':
        return normalize_email(value)
    if channel == 'sms':
        return normalize_vietnam_phone(value)
    raise ValueError('Phương thức xác minh không hợp lệ.')


class EmailOTPProvider:
    """SMTP provider configured only through process environment variables."""

    def __init__(self, environ=None):
        self.environ = os.environ if environ is None else environ

    @property
    def configured(self):
        required = ('PIGSKIN_SMTP_HOST', 'PIGSKIN_SMTP_USER',
                    'PIGSKIN_SMTP_PASSWORD', 'PIGSKIN_SMTP_FROM')
        return all(self.environ.get(key) for key in required)

    def send(self, destination, code):
        if not self.configured:
            raise OTPNotConfiguredError('Chưa cấu hình dịch vụ gửi mã.')
        try:
            host = self.environ['PIGSKIN_SMTP_HOST']
            port = int(self.environ.get('PIGSKIN_SMTP_PORT', '587'))
            username = self.environ['PIGSKIN_SMTP_USER']
            password = self.environ['PIGSKIN_SMTP_PASSWORD']
            sender = self.environ['PIGSKIN_SMTP_FROM']
            use_ssl = self.environ.get('PIGSKIN_SMTP_SSL', '').lower() in {
                '1', 'true', 'yes'
            }
            message = EmailMessage()
            message['Subject'] = 'Mã xác minh PigSkin AI Studio'
            message['From'] = sender
            message['To'] = destination
            message.set_content(
                f'Mã xác minh của bạn là {code}. Mã có hiệu lực trong 5 phút '
                'và chỉ sử dụng được một lần. Không chia sẻ mã này với người khác.'
            )
            if use_ssl:
                with smtplib.SMTP_SSL(
                    host, port, timeout=15, context=ssl.create_default_context()
                ) as client:
                    client.login(username, password)
                    client.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=15) as client:
                    client.ehlo()
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
                    client.login(username, password)
                    client.send_message(message)
        except OTPError:
            raise
        except (OSError, ValueError, smtplib.SMTPException):
            raise OTPDeliveryError(
                'Không thể gửi email xác minh. Vui lòng kiểm tra cấu hình SMTP và kết nối.'
            ) from None


class SMSOTPProvider:
    """Bearer-authenticated JSON SMS adapter for a configured provider endpoint.

    The endpoint must accept POST JSON with ``to`` and ``message`` fields and
    return a 2xx status only when it has accepted the message for delivery.
    """

    def __init__(self, environ=None):
        self.environ = os.environ if environ is None else environ

    @property
    def configured(self):
        endpoint = self.environ.get('PIGSKIN_SMS_ENDPOINT', '')
        return endpoint.startswith('https://') and all(self.environ.get(key) for key in (
            'PIGSKIN_SMS_ENDPOINT', 'PIGSKIN_SMS_API_KEY'
        ))

    def send(self, destination, code):
        if not self.configured:
            raise OTPNotConfiguredError('Chưa cấu hình dịch vụ gửi mã.')
        try:
            endpoint = self.environ['PIGSKIN_SMS_ENDPOINT']
            api_key = self.environ['PIGSKIN_SMS_API_KEY']
            body = json.dumps({
                'to': destination,
                'message': (
                    f'Ma xac minh PigSkin AI Studio: {code}. '
                    'Ma co hieu luc 5 phut, chi su dung mot lan.'
                ),
            }).encode('utf-8')
            request = Request(endpoint, data=body, method='POST', headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            })
            with urlopen(request, timeout=15) as response:
                if not 200 <= response.status < 300:
                    raise OTPDeliveryError('Dịch vụ SMS không chấp nhận yêu cầu gửi mã.')
        except OTPError:
            raise
        except (OSError, URLError, ValueError):
            raise OTPDeliveryError(
                'Không thể gửi SMS xác minh. Vui lòng kiểm tra cấu hình dịch vụ và kết nối.'
            ) from None


class SQLServerOTPRepository:
    """Persistence adapter; its table is provisioned by the explicit migration."""

    def create(self, challenge):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with conn() as connection:
            recent = connection.execute('''SELECT COUNT(*) AS request_count,
                    MAX(created_at) AS latest_request
                FROM dbo.auth_otp_challenges WITH (
                    UPDLOCK, HOLDLOCK, INDEX(IX_auth_otp_destination_purpose_created))
                WHERE destination=? AND purpose=?
                  AND created_at>=DATEADD(hour,-1,SYSUTCDATETIME())''', (
                challenge['destination'], challenge['purpose']
            )).fetchone()
            if recent['latest_request'] is not None:
                latest = recent['latest_request']
                if latest.tzinfo is not None:
                    latest = latest.astimezone(timezone.utc).replace(tzinfo=None)
                wait = RESEND_INTERVAL - (now - latest)
                if wait.total_seconds() > 0:
                    seconds = max(1, int(wait.total_seconds() + 0.999))
                    raise OTPRateLimitError(
                        f'Vui lòng đợi {seconds} giây trước khi yêu cầu mã mới.'
                    )
            if recent['request_count'] >= MAX_REQUESTS_PER_HOUR:
                raise OTPRateLimitError(
                    'Đã đạt giới hạn 5 mã trong một giờ. Vui lòng thử lại sau.'
                )
            connection.execute('''INSERT INTO dbo.auth_otp_challenges
                (challenge_id, destination, channel, purpose, salt, code_hash,
                 created_at, expires_at, attempts, consumed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)''', (
                challenge['challenge_id'], challenge['destination'],
                challenge['channel'], challenge['purpose'], challenge['salt'],
                challenge['code_hash'], now, now + CODE_LIFETIME
            ))

    def activate(self, challenge):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with conn() as connection:
            connection.execute('''UPDATE dbo.auth_otp_challenges
                SET consumed_at=?
                WHERE destination=? AND purpose=? AND challenge_id<>?
                  AND consumed_at IS NULL''', (
                now, challenge['destination'], challenge['purpose'],
                challenge['challenge_id'],
            ))

    def consume(self, challenge_id, destination, purpose, code, pepper):
        failure = None
        result = None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with conn() as connection:
            row = connection.execute('''SELECT challenge_id, destination, channel,
                    purpose, salt, code_hash, expires_at, attempts, consumed_at
                FROM dbo.auth_otp_challenges WITH (UPDLOCK, ROWLOCK)
                WHERE challenge_id=?''', (challenge_id,)).fetchone()
            if (row is None or row['destination'] != destination
                    or row['purpose'] != purpose):
                failure = OTPInvalidError('Mã xác minh không hợp lệ.')
            elif row['consumed_at'] is not None or row['attempts'] >= MAX_ATTEMPTS:
                failure = OTPInvalidError('Mã xác minh đã hết lượt hoặc đã được sử dụng.')
            else:
                expires_at = row['expires_at']
                if expires_at.tzinfo is not None:
                    expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
                if expires_at <= now:
                    connection.execute('''UPDATE dbo.auth_otp_challenges
                        SET consumed_at=? WHERE challenge_id=?''', (now, challenge_id))
                    failure = OTPInvalidError('Mã xác minh đã hết hạn. Vui lòng yêu cầu mã mới.')
                else:
                    expected = _code_digest(pepper, row['salt'], code)
                    if not hmac.compare_digest(expected, row['code_hash']):
                        attempts = row['attempts'] + 1
                        connection.execute('''UPDATE dbo.auth_otp_challenges
                            SET attempts=?, consumed_at=?
                            WHERE challenge_id=?''', (
                            attempts, now if attempts >= MAX_ATTEMPTS else None,
                            challenge_id
                        ))
                        failure = OTPInvalidError(
                            'Mã xác minh không chính xác.'
                            if attempts < MAX_ATTEMPTS
                            else 'Mã xác minh đã hết lượt. Vui lòng yêu cầu mã mới.'
                        )
                    else:
                        connection.execute('''UPDATE dbo.auth_otp_challenges
                            SET consumed_at=? WHERE challenge_id=?''', (now, challenge_id))
                        result = {
                            'destination': row['destination'],
                            'channel': row['channel'],
                            'purpose': row['purpose'],
                        }
        if failure is not None:
            raise failure
        return result


def _code_digest(pepper, salt, code):
    return hmac.new(
        pepper, (salt + code).encode('ascii'), hashlib.sha256
    ).hexdigest()


class OTPService:
    def __init__(self, channel, provider, repository=None, pepper=None,
                 code_generator=None):
        if channel not in {'email', 'sms'}:
            raise ValueError('Phương thức xác minh không hợp lệ.')
        self.channel = channel
        self.provider = provider
        self.repository = repository or SQLServerOTPRepository()
        configured_pepper = pepper or os.environ.get('PIGSKIN_OTP_PEPPER', '')
        if len(configured_pepper.encode('utf-8')) < 32:
            raise OTPNotConfiguredError('Chưa cấu hình dịch vụ gửi mã.')
        self.pepper = configured_pepper.encode('utf-8')
        self.code_generator = code_generator or (
            lambda: f'{secrets.randbelow(1_000_000):06d}'
        )

    def request_code(self, destination, purpose):
        if purpose not in {'login', 'registration', 'password_reset'}:
            raise ValueError('Mục đích xác minh không hợp lệ.')
        if not getattr(self.provider, 'configured', False):
            raise OTPNotConfiguredError('Chưa cấu hình dịch vụ gửi mã.')
        normalized = normalize_contact(destination, self.channel)
        code = self.code_generator()
        if not re.fullmatch(r'\d{6}', code):
            raise RuntimeError('OTP generator returned an invalid code.')
        salt = secrets.token_hex(16)
        challenge_id = secrets.token_hex(32)
        challenge = {
            'challenge_id': challenge_id,
            'destination': normalized,
            'channel': self.channel,
            'purpose': purpose,
            'salt': salt,
            'code_hash': _code_digest(self.pepper, salt, code),
        }
        self.repository.create(challenge)
        self.provider.send(normalized, code)
        self.repository.activate(challenge)
        return challenge_id

    def verify_code(self, challenge_id, destination, purpose, code):
        if not isinstance(challenge_id, str) or not re.fullmatch(
            r'[0-9a-f]{64}', challenge_id
        ):
            raise OTPInvalidError('Mã xác minh không hợp lệ.')
        if not isinstance(code, str) or not re.fullmatch(r'\d{6}', code):
            raise OTPInvalidError('Vui lòng nhập mã xác minh gồm 6 chữ số.')
        normalized = normalize_contact(destination, self.channel)
        return self.repository.consume(
            challenge_id, normalized, purpose, code, self.pepper
        )


def configured_provider(channel):
    if channel == 'email':
        return EmailOTPProvider()
    if channel == 'sms':
        return SMSOTPProvider()
    raise ValueError('Phương thức xác minh không hợp lệ.')
