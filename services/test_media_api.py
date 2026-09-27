"""Inspect media HTTP request construction using a stubbed transport."""
import os
import unittest
from unittest.mock import patch

import api


class MediaAPITests(unittest.TestCase):
    def test_gemini_vision_and_header_auth(self):
        parts = [{'mime': 'image/jpeg', 'data_base64': 'YQ=='}]
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'offline-fixture-key'}), patch.object(api, 'http_json', return_value='fixture answer') as http:
            self.assertEqual(api.model_call('gemini', 'fixture prompt', vision=parts), 'fixture answer')
        url, method, body, headers = http.call_args.args[:4]
        self.assertNotIn('key=', url)
        self.assertNotIn('offline-fixture-key', url)
        self.assertEqual(headers['x-goog-api-key'], 'offline-fixture-key')
        self.assertEqual(method, 'POST')
        self.assertEqual(body['contents'][0]['parts'][0]['inline_data'], {'mime_type': 'image/jpeg', 'data': 'YQ=='})
        self.assertEqual(body['contents'][0]['parts'][-1], {'text': 'fixture prompt'})

    def test_minimax_configured_text_model_cannot_silently_take_images(self):
        with patch.dict(os.environ, {'MINIMAX_API_KEY': 'offline-fixture-key'}), patch.object(api, 'http_json') as http:
            with self.assertRaisesRegex(ValueError, 'text only'):
                api.model_call('minimax', 'fixture', vision=[{'mime': 'image/jpeg', 'data_base64': 'YQ=='}])
            http.assert_not_called()


if __name__ == '__main__':
    unittest.main()
