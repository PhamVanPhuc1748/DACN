"""OTP flow tests use scripted SQL connections and mock providers only."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from services import otp


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class ScriptedConnection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def execute(self, query, parameters=()):
        self.calls.append((' '.join(query.split()), tuple(parameters)))
        if 'SELECT COUNT(*) AS request_count' in query:
            return Result(self.rows.pop(0))
        if 'SELECT challenge_id, destination, channel' in query:
            return Result(self.rows.pop(0))
        return Result()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ConnectionFactory:
    def __init__(self, connections):
        self.connections = list(connections)

    def __call__(self):
        return self.connections.pop(0)


class MockProvider:
    configured = True

    def __init__(self):
        self.sent = []

    def send(self, destination, code):
        self.sent.append((destination, code))


class OTPTests(unittest.TestCase):
    def setUp(self):
        self.pepper = 'unit-test-pepper-material-32-bytes'

    def test_normalizes_email_and_vietnamese_mobile_numbers(self):
        self.assertEqual(otp.normalize_email('  USER@Example.COM  '),
                         'user@example.com')
        self.assertEqual(otp.normalize_vietnam_phone('0901 234 567'),
                         '+84901234567')
        self.assertEqual(otp.normalize_vietnam_phone('+84 (901) 234-567'),
                         '+84901234567')
        for value in ('0123456789', '+1 555 123 4567', '09012345'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                otp.normalize_vietnam_phone(value)

    def test_otp_is_randomly_generated_and_only_a_digest_is_persisted(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        connection = ScriptedConnection([{
            'request_count': 0, 'latest_request': None,
        }])
        activation = ScriptedConnection()
        provider = MockProvider()
        service = otp.OTPService(
            'email', provider, pepper=self.pepper,
            code_generator=lambda: '123456',
        )
        with patch.object(otp, 'conn', ConnectionFactory([connection, activation])):
            challenge_id = service.request_code('USER@example.test', 'login')

        self.assertEqual(provider.sent, [('user@example.test', '123456')])
        insert = next(call for call in connection.calls
                      if 'INSERT INTO dbo.auth_otp_challenges' in call[0])
        self.assertEqual(insert[1][0], challenge_id)
        self.assertEqual(insert[1][2:4], ('email', 'login'))
        self.assertEqual(len(insert[1][5]), 64)
        self.assertNotIn('123456', insert[1])
        self.assertGreaterEqual(
            (insert[1][7] - now).total_seconds(), 299
        )
        self.assertIn('UPDATE dbo.auth_otp_challenges', activation.calls[0][0])

    def test_valid_code_is_consumed_once(self):
        challenge_id = 'a' * 64
        salt = 'b' * 32
        row = {
            'challenge_id': challenge_id,
            'destination': 'user@example.test',
            'channel': 'email',
            'purpose': 'registration',
            'salt': salt,
            'code_hash': otp._code_digest(
                self.pepper.encode(), salt, '123456'
            ),
            'expires_at': datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(minutes=5),
            'attempts': 0,
            'consumed_at': None,
        }
        connection = ScriptedConnection([row])
        service = otp.OTPService('email', MockProvider(), pepper=self.pepper)
        with patch.object(otp, 'conn', ConnectionFactory([connection])):
            verified = service.verify_code(
                challenge_id, 'USER@example.test', 'registration', '123456'
            )
        self.assertEqual(verified, {
            'destination': 'user@example.test',
            'channel': 'email',
            'purpose': 'registration',
        })
        self.assertIn('SET consumed_at=?', connection.calls[-1][0])

    def test_wrong_code_increments_attempt_count_and_fifth_attempt_exhausts(self):
        service = otp.OTPService('email', MockProvider(), pepper=self.pepper)
        challenge_id = 'c' * 64
        salt = 'd' * 32
        connections = []
        for attempts in range(5):
            connection = ScriptedConnection([{
                'challenge_id': challenge_id,
                'destination': 'user@example.test',
                'channel': 'email',
                'purpose': 'login',
                'salt': salt,
                'code_hash': otp._code_digest(
                    self.pepper.encode(), salt, '123456'
                ),
                'expires_at': datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(minutes=5),
                'attempts': attempts,
                'consumed_at': None,
            }])
            connections.append(connection)
        with patch.object(otp, 'conn', ConnectionFactory(connections)):
            for attempt in range(4):
                with self.subTest(attempt=attempt), self.assertRaises(
                    otp.OTPInvalidError
                ):
                    service.verify_code(
                        challenge_id, 'user@example.test', 'login', '000000'
                    )
            with self.assertRaisesRegex(otp.OTPInvalidError, 'hết lượt'):
                service.verify_code(
                    challenge_id, 'user@example.test', 'login', '000000'
                )
        for expected_attempt, connection in enumerate(connections, start=1):
            update = next(call for call in connection.calls
                          if 'SET attempts=' in call[0])
            self.assertEqual(update[1][0], expected_attempt)
            self.assertEqual(
                update[1][1] is not None, expected_attempt == otp.MAX_ATTEMPTS
            )

    def test_expired_code_is_invalidated(self):
        challenge_id = 'e' * 64
        row = {
            'challenge_id': challenge_id,
            'destination': 'user@example.test',
            'channel': 'email',
            'purpose': 'password_reset',
            'salt': 'f' * 32,
            'code_hash': otp._code_digest(
                self.pepper.encode(), 'f' * 32, '123456'
            ),
            'expires_at': datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(seconds=1),
            'attempts': 0,
            'consumed_at': None,
        }
        connection = ScriptedConnection([row])
        service = otp.OTPService('email', MockProvider(), pepper=self.pepper)
        with patch.object(otp, 'conn', ConnectionFactory([connection])):
            with self.assertRaisesRegex(otp.OTPInvalidError, 'hết hạn'):
                service.verify_code(
                    challenge_id, 'user@example.test', 'password_reset', '123456'
                )
        self.assertIn('SET consumed_at=?', connection.calls[-1][0])

    def test_used_challenge_cannot_be_reused(self):
        connection = ScriptedConnection([{
            'challenge_id': '1' * 64,
            'destination': 'user@example.test',
            'channel': 'email',
            'purpose': 'login',
            'salt': '2' * 32,
            'code_hash': '3' * 64,
            'expires_at': datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(minutes=5),
            'attempts': 0,
            'consumed_at': datetime.now(timezone.utc).replace(tzinfo=None),
        }])
        service = otp.OTPService('email', MockProvider(), pepper=self.pepper)
        with patch.object(otp, 'conn', ConnectionFactory([connection])):
            with self.assertRaisesRegex(otp.OTPInvalidError, 'đã được sử dụng'):
                service.verify_code(
                    '1' * 64, 'user@example.test', 'login', '123456'
                )
        self.assertEqual(len(connection.calls), 1)

    def test_resend_interval_and_hourly_limit_are_enforced(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        provider = MockProvider()
        service = otp.OTPService(
            'sms', provider, pepper=self.pepper,
            code_generator=lambda: '123456',
        )
        resend_limited = ScriptedConnection([{
            'request_count': 1, 'latest_request': now,
        }])
        with patch.object(otp, 'conn', ConnectionFactory([resend_limited])):
            with self.assertRaisesRegex(otp.OTPRateLimitError, 'đợi'):
                service.request_code('0901234567', 'login')
        self.assertEqual(provider.sent, [])

        hourly_limited = ScriptedConnection([{
            'request_count': otp.MAX_REQUESTS_PER_HOUR,
            'latest_request': now - timedelta(seconds=otp.RESEND_INTERVAL.seconds + 1),
        }])
        with patch.object(otp, 'conn', ConnectionFactory([hourly_limited])):
            with self.assertRaisesRegex(otp.OTPRateLimitError, '5 mã'):
                service.request_code('0901234567', 'login')
        self.assertEqual(provider.sent, [])

    def test_missing_configuration_and_delivery_failure_are_not_success(self):
        with self.assertRaisesRegex(otp.OTPNotConfiguredError,
                                    'Chưa cấu hình dịch vụ gửi mã'):
            otp.OTPService(
                'email', otp.EmailOTPProvider(environ={}),
                pepper=self.pepper,
            ).request_code('user@example.test', 'login')
        self.assertFalse(otp.SMSOTPProvider(environ={
            'PIGSKIN_SMS_ENDPOINT': 'http://sms.example.test',
            'PIGSKIN_SMS_API_KEY': 'secret',
        }).configured)
        self.assertFalse(otp.EmailOTPProvider(environ={}).configured)

    def test_email_provider_rejects_invalid_port_and_sender_configuration(self):
        base = {
            'PIGSKIN_SMTP_HOST': 'smtp.example.test',
            'PIGSKIN_SMTP_USER': 'sender@example.test',
            'PIGSKIN_SMTP_PASSWORD': 'secret',
            'PIGSKIN_SMTP_FROM': 'sender@example.test',
        }
        self.assertTrue(otp.EmailOTPProvider(environ=base).configured)
        self.assertFalse(otp.EmailOTPProvider(environ={
            **base, 'PIGSKIN_SMTP_PORT': 'not-a-port',
        }).configured)
        self.assertFalse(otp.EmailOTPProvider(environ={
            **base, 'PIGSKIN_SMTP_FROM': 'invalid-address',
        }).configured)

    def test_delivery_failure_does_not_invalidate_the_previous_code(self):
        class FailingProvider(MockProvider):
            def send(self, destination, code):
                raise otp.OTPDeliveryError('delivery failed')

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        create = ScriptedConnection([{
            'request_count': 1,
            'latest_request': now - timedelta(seconds=otp.RESEND_INTERVAL.seconds + 1),
        }])
        cleanup = ScriptedConnection()
        service = otp.OTPService(
            'email', FailingProvider(), pepper=self.pepper,
            code_generator=lambda: '123456',
        )
        with patch.object(otp, 'conn', ConnectionFactory([create, cleanup])):
            with self.assertRaises(otp.OTPDeliveryError):
                service.request_code('user@example.test', 'login')
        self.assertFalse(any(
            'UPDATE dbo.auth_otp_challenges' in query
            for query, _ in create.calls
        ))
        self.assertTrue(any(
            'DELETE FROM dbo.auth_otp_challenges' in query
            for query, _ in cleanup.calls
        ))


if __name__ == '__main__':
    unittest.main()
