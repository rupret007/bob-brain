"""Direct Google Drive reads: one pointed-at Doc or plain text file.

Uses the same protected Google OAuth/HTTPS boundary as Calendar: owner-only
authorized-user JSON, fixed hosts, no proxies, redirects, or retries. Drive
credentials are dedicated and explicit; Calendar and ADC files are never used.
Merely constructing this module never contacts Google.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import urllib.error
import urllib.parse
import urllib.request

import chat_intent

NEEDS_AUTH = 'needs Google auth'
HELP = ('Try “read drive FILE_ID” or “read google doc https://docs.google.com/document/d/FILE_ID/edit”. '
        'Only a Google Doc or plain text file is returned, as a bounded excerpt with title, '
        'modified time, and source link. No Drive search, folders, binaries, sharing, or edits.')
PREFIX = r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
READ = re.compile(PREFIX + r'(?:read|show|open|fetch|get)\s+(?:the\s+)?'
                  r'(?:(?:google\s+)?drive(?:\s+(?:doc(?:ument)?|file))?|'
                  r'google\s+doc(?:ument)?)\b\s*(.*)$', re.I | re.S)
FILE_ID = re.compile(r'^[A-Za-z0-9_-]{10,128}$')
DOC_MIME = 'application/vnd.google-apps.document'
TEXT_MIME = 'text/plain'
EXCERPT_LIMIT = 8 * 1024
BODY_LIMIT = 2 * 1024 * 1024
HOSTS = ('oauth2.googleapis.com', 'www.googleapis.com')
DRIVE_PREFIX = '/drive/v3/files/'
UNSUPPORTED = re.compile(r'/drive/folders/|/spreadsheets/|/presentation/', re.I)
WRITE_PATH = re.compile(r'/permissions|/copy|/comments|/watch|/create')


class DriveError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise DriveError('Google Drive redirected the request; no content was verified.')


def request(url, *, data=None, headers=None, form=False, as_json=True):
    """Fixed Google hosts, no proxies, redirects, retries, or Drive writes."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc not in HOSTS:
        raise DriveError('Invalid Drive endpoint.')
    if parsed.netloc == 'oauth2.googleapis.com':
        if parsed.path != '/token' or data is None:
            raise DriveError('Invalid Drive endpoint.')
    elif not parsed.path.startswith(DRIVE_PREFIX) or WRITE_PATH.search(parsed.path) or data is not None:
        raise DriveError('Invalid Drive endpoint.')
    body = (urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json', **(headers or {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=10) as response:
            raw = response.read(BODY_LIMIT + 1)
        if len(raw) > BODY_LIMIT:
            raise ValueError('large response')
        if as_json:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError('invalid response')
            return result
        return raw.decode('utf-8')
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403) or form and exc.code == 400:
            raise DriveError(NEEDS_AUTH) from None
        if exc.code == 404:
            raise DriveError('That Drive file could not be read; no content was returned.') from None
        raise DriveError('Google Drive rejected the request; no content was verified.') from None
    except (OSError, ValueError, UnicodeError):
        raise DriveError('Google Drive is unavailable or returned invalid data; no content was verified.') from None


class GoogleDrive:
    """Read-only Drive client using an explicitly configured OAuth file."""

    def __init__(self, credentials=None, transport=None):
        self.credentials = credentials
        self.transport = transport or request

    def configured(self):
        self._credentials()

    def _credentials(self):
        configured = self.credentials or os.environ.get('BOB_GOOGLE_DRIVE_CREDENTIALS')
        path = Path(configured).expanduser() if configured else Path.home() / '.config/webbob/google-drive.json'
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd) as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 24000:
                    raise ValueError('private credentials required')
                value = json.load(handle)
            if not isinstance(value, dict) or value.get('type', 'authorized_user') != 'authorized_user':
                raise ValueError('authorized user required')
            if any(not isinstance(value.get(k), str) or not value[k].strip() for k in ('client_id', 'client_secret', 'refresh_token')):
                raise ValueError('missing OAuth credentials')
            return value
        except (OSError, ValueError, UnicodeError):
            raise DriveError(NEEDS_AUTH) from None

    def _headers(self):
        cfg = self._credentials()
        token = self.transport('https://oauth2.googleapis.com/token', form=True, as_json=True,
                               data={k: cfg[k] for k in ('client_id', 'client_secret', 'refresh_token')} |
                               {'grant_type': 'refresh_token'})
        access = token.get('access_token')
        if not isinstance(access, str) or not access or any(c.isspace() for c in access):
            raise DriveError(NEEDS_AUTH)
        return {'Authorization': 'Bearer ' + access}

    def _file_url(self, file_id, query):
        return 'https://www.googleapis.com/drive/v3/files/' + urllib.parse.quote(file_id, safe='') + '?' + query

    def metadata(self, file_id):
        query = urllib.parse.urlencode(dict(
            fields='id,name,mimeType,modifiedTime,webViewLink', supportsAllDrives='true'))
        return self.transport(self._file_url(file_id, query), headers=self._headers(), as_json=True)

    def export_text(self, file_id):
        query = urllib.parse.urlencode(dict(mimeType='text/plain', supportsAllDrives='true'))
        return self.transport(self._file_url(file_id, query).replace('?', '/export?'),
                              headers=self._headers(), as_json=False)

    def download_text(self, file_id):
        query = urllib.parse.urlencode(dict(alt='media', supportsAllDrives='true'))
        return self.transport(self._file_url(file_id, query), headers=self._headers(), as_json=False)


def parse_target(text):
    value = text.strip().strip('\'"')
    if not value:
        raise DriveError('I need a Google Drive file ID or Drive URL. ' + HELP)
    if UNSUPPORTED.search(value):
        raise DriveError('Drive folders, spreadsheets, and slides are not supported. Point at a Google Doc or plain text file.')
    match = re.search(r'https://(?:docs\.google\.com/document/d/|drive\.google\.com/file/d/)([A-Za-z0-9_-]{10,128})',
                      value, re.I)
    if match:
        return match[1]
    match = re.search(r'https://drive\.google\.com/(?:open|uc)\?[^\s#]*\bid=([A-Za-z0-9_-]{10,128})', value, re.I)
    if match:
        return match[1]
    parsed = urllib.parse.urlsplit(value.split()[-1].strip('\'".,'))
    if parsed.scheme or parsed.netloc:
        raise DriveError('I need a Google Drive file ID or Drive URL. ' + HELP)
    token = value.split()[-1].strip('\'".,')
    if FILE_ID.fullmatch(token):
        return token
    raise DriveError('I need a Google Drive file ID or Drive URL. ' + HELP)


def verified_metadata(result, file_id):
    if not isinstance(result, dict) or result.get('id') != file_id:
        raise DriveError('Google Drive returned invalid file metadata; no content was verified.')
    name, mime, modified = result.get('name'), result.get('mimeType'), result.get('modifiedTime')
    if not isinstance(name, str) or not name.strip() or not isinstance(mime, str):
        raise DriveError('Google Drive returned invalid file metadata; no content was verified.')
    if not isinstance(modified, str) or not modified:
        raise DriveError('Google Drive returned invalid file metadata; no content was verified.')
    try:
        datetime.fromisoformat(modified.replace('Z', '+00:00'))
    except ValueError:
        raise DriveError('Google Drive returned invalid file metadata; no content was verified.') from None
    link = result.get('webViewLink')
    if link is not None and (not isinstance(link, str) or not link.startswith('https://')):
        raise DriveError('Google Drive returned invalid file metadata; no content was verified.')
    return dict(id=file_id, name=name.strip(), mimeType=mime, modifiedTime=modified,
                webViewLink=link if isinstance(link, str) else None)


def receipt(meta, text):
    excerpt = text if isinstance(text, str) else ''
    truncated = len(excerpt) > EXCERPT_LIMIT
    if truncated:
        excerpt = excerpt[:EXCERPT_LIMIT]
    link = meta.get('webViewLink') or ('https://drive.google.com/file/d/' + meta['id'] + '/view')
    body = excerpt if excerpt else 'No text in this file.'
    note = '\n[Excerpt truncated.]' if truncated else ''
    return (f'Google Drive: {meta["name"][:500]}\nModified: {meta["modifiedTime"]}\n'
            f'Source: {link}\n\n{body}{note}')


class DriveRead:
    def __init__(self, client=None):
        self.client = client if client is not None else GoogleDrive()

    def matches(self, text):
        text = text.strip()
        return bool(READ.fullmatch(text) or text.lower() == 'drive help')

    def handle(self, text, cid, request_id, intent_state):
        if not self.matches(text):
            return None
        try:
            if text.strip().lower() == 'drive help':
                return HELP
            scopes = chat_intent.blocked_scopes(intent_state, chat_intent.projects(text))
            if scopes:
                return chat_intent.hold_reply(scopes)
            file_id = parse_target(READ.fullmatch(text.strip())[1])
            self.client.configured()
            meta = verified_metadata(self.client.metadata(file_id), file_id)
            if meta['mimeType'] == DOC_MIME:
                content = self.client.export_text(file_id)
            elif meta['mimeType'] == TEXT_MIME:
                content = self.client.download_text(file_id)
            else:
                raise DriveError('This Drive file is not a Google Doc or plain text; no content was returned.')
            if not isinstance(content, str):
                raise DriveError('Google Drive returned invalid file data; no content was verified.')
            return receipt(meta, content)
        except DriveError as exc:
            return str(exc)
        except (OSError, ValueError, TypeError, KeyError):
            return 'Google Drive request could not finish; no content was verified.'
