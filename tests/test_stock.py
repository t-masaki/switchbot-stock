import base64
import os
from datetime import datetime, timezone
import hashlib
import hmac
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lambda'))
import lambda_function as app
import market_data as market
import switchbot


class StockTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"TEMPLATE_ID": "5874", "COMPONENT_ID": "801332647"})
        env.start()
        self.addCleanup(env.stop)

    def test_window_boundaries(self):
        for clock, expected in [('08:59', False), ('09:00', True), ('11:29', True),
                                ('11:30', False), ('12:29', False), ('12:30', True),
                                ('15:30', True), ('15:31', False)]:
            with self.subTest(clock=clock):
                self.assertEqual(app.in_window(datetime.fromisoformat('2026-10-02T'+clock+':45+09:00')), expected)
        self.assertFalse(app.in_window(datetime.fromisoformat('2026-10-03T09:00:00+09:00')))
        self.assertTrue(app.in_window(datetime.fromisoformat('2026-10-02T00:00:00+00:00')))

    def fixture(self, **changes):
        meta = dict(symbol='7046.T', currency='JPY', regularMarketPrice=1234,
                    chartPreviousClose=1200, regularMarketTime=1790902800)
        meta.update(changes)
        return {'chart': {'error': None, 'result': [{'meta': meta}]}}

    def test_quote_math(self):
        q = market.parse_quote('7046.T', self.fixture())
        self.assertEqual(q.change, 34)
        self.assertAlmostEqual(q.change_percent, 34/1200*100)
        q = market.parse_quote('7046.T', self.fixture(regularMarketPrice=1190))
        self.assertEqual(q.change, -10)

    def test_invalid_quotes(self):
        for change in [dict(chartPreviousClose=0), dict(regularMarketPrice=float('nan')),
                       dict(currency='USD'), dict(symbol='OTHER'), dict(regularMarketTime=None)]:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                market.parse_quote('7046.T', self.fixture(**change))
        with self.assertRaises(RuntimeError):
            market.parse_quote('7046.T', {'chart': {'error': {'code': 'Not Found'}}})

    def test_signature(self):
        headers = switchbot.auth_headers('token', 'secret', 1234567890123, 'nonce')
        expected = base64.b64encode(hmac.new(b'secret', b'token1234567890123nonce', hashlib.sha256).digest()).decode()
        self.assertEqual(headers['sign'], expected)

    def test_payload_and_limit(self):
        q = market.parse_quote('7046.T', self.fixture())
        text = app.format_component([q, q])
        self.assertLessEqual(len(text), 100)
        self.assertNotIn('\n', text)
        with patch('switchbot.request_json', return_value={'statusCode': 100, 'body': {}}) as send:
            switchbot.send_component('token', 'secret', 'id', 5874, 801332647, text)
            self.assertEqual(send.call_args.args[2], {'command': 'customPutComponent', 'parameter': {'templateID': 5874, 'componentID': 801332647, 'text': text}, 'commandType': 'command'})
        for bad in ['あ'*101, 'a'*101, '']:
            with self.assertRaises(ValueError):
                switchbot.send_component('token', 'secret', 'id', 5874, 801332647, bad)

    def test_exact_100_characters_and_id_validation(self):
        switchbot.validate_component(5874, 801332647, 'あ' * 100)
        for invalid in (0, -1, True, '5874', 1.5):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                switchbot.validate_component(invalid, 801332647, 'text')
        with patch.dict(os.environ, {"TEMPLATE_ID": "invalid"}), self.assertRaises(ValueError):
            app.component_target()

    def test_oversize_display_not_truncated(self):
        q = market.parse_quote('7046.T', self.fixture(regularMarketPrice=1e50))
        with self.assertRaises(ValueError):
            app.format_component([q, q])

    def test_handler_passes_configured_ids(self):
        q = market.parse_quote('7046.T', self.fixture())
        with patch.object(app, 'get_quote', return_value=q), patch.object(app, 'load_credentials', return_value=['t', 's', 'd']), patch.object(app, 'send_component') as send:
            result = app.lambda_handler({'force': True}, None)
            self.assertEqual(result['status'], 'sent')
            self.assertEqual(send.call_args.args, ('t', 's', 'd', 5874, 801332647, result['text']))

    def test_api_failure(self):
        with patch('switchbot.request_json', return_value={'statusCode': 190}), self.assertRaises(RuntimeError):
            switchbot.api_call('token', 'secret', '/devices')

    def test_dry_run_never_loads_secrets_or_sends(self):
        q = market.parse_quote('7046.T', self.fixture())
        with patch.object(app, 'get_quote', return_value=q), patch.object(app, 'load_credentials') as creds, patch.object(app, 'send_component') as send:
            result = app.lambda_handler({'force': True, 'dry_run': True}, None)
            self.assertEqual(result['status'], 'dry_run')
            creds.assert_not_called()
            send.assert_not_called()

    def test_old_quotes_preserve_page(self):
        q = market.Quote('7046.T', 1234, 1200, datetime(2000, 1, 1, tzinfo=timezone.utc))
        with patch.object(app, 'in_window', return_value=True), patch.object(app, 'get_quote', return_value=q), patch.object(app, 'send_component') as send:
            self.assertEqual(app.lambda_handler({}, None)['status'], 'skipped')
            send.assert_not_called()

    def test_closed_window_does_not_fetch(self):
        with patch.object(app, 'in_window', return_value=False), patch.object(app, 'get_quote') as fetch:
            self.assertEqual(app.lambda_handler({}, None)['status'], 'skipped')
            fetch.assert_not_called()

    def test_one_quote_failure_does_not_send_partial_page(self):
        with patch.object(app, 'get_quote', side_effect=RuntimeError('unavailable')), patch.object(app, 'send_component') as send:
            with self.assertRaises(RuntimeError):
                app.lambda_handler({'force': True}, None)
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
