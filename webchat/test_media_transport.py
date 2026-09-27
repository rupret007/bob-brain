"""Round-trip vision transport and isolation without making a model request."""
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from api_call import split_transport
from chat_media import public_attachment, store_media
from providers import Providers, Redactor
from test_chat_media import png_fixture


class MediaTransportTests(unittest.TestCase):
    def test_json_round_trip_preserves_old_delimiter_unicode_and_quotes(self):
        prompt = 'Before\n---BOB_VISION_JSON---\nAfter "quotes" and 📎\n{"vision": []}'
        vision = [{'mime': 'image/jpeg', 'data_base64': 'YQ==', 'caption': 'photo'}]
        self.assertEqual(split_transport(json.dumps({'prompt': prompt, 'vision': vision})), (prompt, vision))
        self.assertEqual(split_transport(json.dumps({'prompt': prompt, 'vision': []})), (prompt, []))
        for raw in ('text', '[]', '{}', '{"prompt": 4}', '{"prompt":"a", "vision":{}}',
                    '{"prompt":"a", "vision":[{"mime":"text/html","data_base64":"x"}]}',
                    '{"prompt":"a", "vision":[{"mime":"image/jpeg","data_base64":"not!valid*base64"}]}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                split_transport(raw)

    def test_simultaneous_conversations_keep_their_own_vision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured, errors = {}, []
            gate = threading.Barrier(3)
            def runner(argv, **kwargs):
                payload = json.loads(kwargs['prompt'])
                captured[threading.current_thread().name] = payload
                return 0, 'A sufficiently long offline fixture answer.', ''
            provider = Providers(root, Redactor(root, 'fixture-password'), runner)
            def bundle(_root, metas, **kwargs):
                name = metas[0]['filename']
                return {'text': name, 'vision': [{'mime': 'image/jpeg', 'data_base64': name}], 'warnings': []}
            def work(name):
                try:
                    cid = str(uuid.uuid4())
                    msg = {'role': 'user', 'status': 'done', 'content': 'Before\n---BOB_VISION_JSON---\nAfter'}
                    if name != 'text':
                        meta = store_media(root, png_fixture(), name + '.png', conversation_id=cid)
                        msg['attachments'] = [public_attachment(meta)]
                    prompt = provider.prompt({'id': cid, 'messages': [msg]})
                    gate.wait(timeout=5)
                    provider.call('gemini', prompt, None, threading.Event())
                except Exception as exc:
                    errors.append(exc)
            with patch('chat_media.enrich_for_model', side_effect=bundle), patch.object(provider, 'snapshot', return_value=[]):
                threads = [threading.Thread(target=work, args=(name,), name=name) for name in ('first', 'second', 'text')]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(7)
                    self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            for name in ('first', 'second'):
                self.assertEqual(captured[name]['vision'][0]['data_base64'], name + '.png')
            self.assertEqual(captured['text']['vision'], [])
            self.assertIn('---BOB_VISION_JSON---', captured['first']['prompt'])

    def test_media_failures_and_text_only_provider_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provider = Providers(root, Redactor(root, 'fixture-password'))
            cid = str(uuid.uuid4())
            meta = store_media(root, png_fixture(), 'photo.png', conversation_id=cid)
            conversation = {'id': cid, 'preferred_provider': 'minimax', 'messages': [
                {'role': 'user', 'status': 'done', 'content': 'Describe this', 'attachments': [public_attachment(meta)]}]}
            bundle = {'text': 'File could not be read.', 'vision': [{'mime': 'image/jpeg', 'data_base64': 'YQ=='}],
                      'warnings': ['One attachment failed to decode.']}
            with patch('chat_media.enrich_for_model', return_value=bundle), patch.object(provider, 'snapshot', return_value=[]), patch.object(provider, 'call', return_value=('A useful offline answer.', None)):
                answer = provider.reply(conversation, threading.Event(), lambda *_: None)
            self.assertIn('failed to decode', answer['content'])
            self.assertIn('extracted text only', answer['content'])
            captured = []
            provider.run = lambda argv, **kw: (captured.append(json.loads(kw['prompt'])) or 0, 'Text only fixture answer.', '')
            provider.call('minimax', 'Question', None, threading.Event())
            self.assertEqual(captured[0]['vision'], [])
            self.assertIn('not images or video frames', captured[0]['prompt'])
            conversation['preferred_provider'] = 'auto'
            self.assertEqual(provider.route_order(conversation)[0], 'gemini')


if __name__ == '__main__':
    unittest.main()
