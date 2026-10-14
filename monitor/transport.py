"""Bounded HTTP with per-host pacing, robots checks, and no restriction bypass."""
import hashlib
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import httpx

USER_AGENT = 'RussiaAutoPriceMonitor/1.0 (+public official price monitoring)'


@dataclass
class Document:
    url: str
    content: bytes
    content_type: str

    @property
    def text(self):
        return self.content.decode('utf-8', errors='strict')

    @property
    def sha256(self):
        return hashlib.sha256(self.content).hexdigest()


class Fetcher:
    def __init__(self, allowed_hosts, client=None):
        self.hosts = set(allowed_hosts)
        self.client = client or httpx.Client(timeout=httpx.Timeout(25, connect=10),
                                            headers={'User-Agent': USER_AGENT}, follow_redirects=False)
        self.robots = {}
        self.last_request = {}

    def check_url(self, url):
        p = urlparse(url)
        if p.scheme != 'https' or p.hostname not in self.hosts or p.username or p.port not in (None, 443):
            raise ValueError('Non-official or unsafe redirect/source URL')

    def _request(self, url):
        self.check_url(url)
        host = urlparse(url).hostname
        time.sleep(max(0, self.last_request.get(host, 0) + 1 - time.monotonic()))
        for attempt in range(3):
            self.last_request[host] = time.monotonic()
            try:
                # Stream to bound memory even if Content-Length is absent/wrong.
                with self.client.stream('GET', url) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 15_000_000:
                            raise ValueError('Document exceeds 15 MB safety limit')
                        chunks.append(chunk)
                    if response.status_code == 429 or response.status_code >= 500:
                        response.raise_for_status()
                    return response, b''.join(chunks)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError('Unreachable')

    def _allowed(self, url):
        origin = f'https://{urlparse(url).netloc}'
        if origin not in self.robots:
            response, body = self._request(origin + '/robots.txt')
            if response.status_code == 404:
                text = 'User-agent: *\nAllow: /'
            elif response.status_code == 200:
                text = body.decode('utf-8', errors='replace')
            else:
                raise ValueError(f'robots.txt unavailable: HTTP {response.status_code}; stop conservatively')
            parser = RobotFileParser()
            parser.parse(text.splitlines())
            self.robots[origin] = parser
        if not self.robots[origin].can_fetch(USER_AGENT, url):
            raise ValueError('robots.txt disallows this URL')

    def get(self, url):
        for _ in range(5):
            self.check_url(url)
            self._allowed(url)
            response, body = self._request(url)
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers['location'])
                continue
            response.raise_for_status()
            return Document(url, body, response.headers.get('content-type', ''))
        raise ValueError('Too many redirects')

    def close(self):
        self.client.close()
