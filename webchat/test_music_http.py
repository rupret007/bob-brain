"""Retained music routes, isolated storage and no rendering/provider calls."""
import base64
import json
from unittest.mock import patch
import test_webchat as fixtures
import test_media_http as media_fixtures
import task_queue


class MusicHTTPTests(fixtures.Fixture):
    request=fixtures.HTTPTests.request
    login=fixtures.HTTPTests.login
    raw=media_fixtures.MediaHTTPTests.raw

    def setUp(self):
        import threading
        from app import Server
        super().setUp()
        self.server=Server(('127.0.0.1',0),self.chat)
        self.port=self.server.server_address[1]
        self.server_thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.server_thread.start()
        self.origin='http://127.0.0.1:'+str(self.port)
        self.cookie,self.csrf='',''
        self.login()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.server_thread.join(2)
        self.assertEqual(self.fake.calls,[])
        self.assertFalse(task_queue.tasks(self.root))
        super().tearDown()

    def test_song_roundtrip_and_access_boundaries(self):
        data=dict(title='Fixture song',lyrics='Synthetic words',chords='C G',notes='Fixture')
        self.assertEqual(self.request('POST','/api/song-projects',data,auth=False)[0],401)
        self.assertEqual(self.request('POST','/api/song-projects',data,headers={'X-CSRF-Token':'bad'})[0],403)
        code,_,body=self.request('POST','/api/song-projects',data)
        self.assertEqual(code,200);saved=json.loads(body)
        path='/api/song-projects/'+saved['id']
        self.assertEqual(json.loads(self.request('GET',path)[2])['lyrics'],data['lyrics'])
        self.assertEqual(self.request('GET',path,auth=False)[0],401)
        changed=dict(data,id=saved['id'],notes='Revised fixture')
        self.assertEqual(json.loads(self.request('POST','/api/song-projects',changed)[2])['id'],saved['id'])
        self.assertEqual(len(json.loads(self.request('GET','/api/song-projects')[2])['projects']),1)
        self.assertEqual(self.request('GET','/api/song-projects/not-an-id')[0],404)

    def test_audio_roundtrip_validation_and_access(self):
        raw=b'RIFF\x00\x01fixture'
        data=dict(filename='fixture.wav',data_base64=base64.b64encode(raw).decode())
        self.assertEqual(self.request('POST','/api/audio/upload',data,auth=False)[0],401)
        self.assertEqual(self.request('POST','/api/audio/upload',data,headers={'Origin':'https://invalid.example'})[0],403)
        code,_,body=self.request('POST','/api/audio/upload',data)
        self.assertEqual(code,201);saved=json.loads(body)
        route='/api/audio/'+saved['audio_id']
        code,_,body=self.raw('GET',route)
        self.assertEqual((code,body),(200,raw))
        self.assertEqual(self.raw('GET',route,auth=False)[0],401)
        self.assertEqual(self.raw('GET','/api/audio/missing')[0],404)
        self.assertEqual(self.request('POST','/api/audio/upload',dict(data,data_base64='!'))[0],400)
        self.assertEqual(self.request('POST','/api/audio/upload',dict(data,filename='fixture.exe'))[0],400)

    def test_demo_requires_matching_confirmation_and_dry_run_never_renders(self):
        data=dict(lyrics='Synthetic fixture words',style='Fixture style')
        with patch('app.generate_demo',side_effect=AssertionError('Unconfirmed rendering')):
            code,_,body=self.request('POST','/api/music/demo',data)
            self.assertEqual(code,200);receipt=json.loads(body)
            self.assertTrue(receipt['needs_confirm'])
            self.assertEqual(self.request('POST','/api/music/demo',dict(data,confirm=True,receipt=receipt['receipt'],lyrics='Changed'))[0],400)
        with patch('music_demo.render_sketch',side_effect=AssertionError('Dry run rendered')):
            code,_,body=self.request('POST','/api/music/demo',dict(data,confirm=True,receipt=receipt['receipt'],dry_run=True))
            self.assertEqual(code,200);self.assertTrue(json.loads(body)['dry_run'])
        with patch('app.music_budget_status',return_value={'fixture':True}):
            self.assertEqual(self.request('GET','/api/music/eligibility')[0],200)
        with patch('app.music_budget_status',side_effect=RuntimeError('Fixture unavailable')):
            self.assertEqual(self.request('GET','/api/music/eligibility')[0],503)
