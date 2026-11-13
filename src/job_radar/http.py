"""A small, polite HTTP client: timeouts, retries with backoff, identifying User-Agent."""
from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "job-radar/1.0 (personal job-search tool; github.com/shoaib-kk)"
TIMEOUT = 25


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


def get_json(session: requests.Session, url: str, **kw):
    r = session.get(url, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r.json()


def post_json(session: requests.Session, url: str, payload: dict, **kw):
    r = session.post(url, json=payload, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r.json()


def pause(seconds: float = 0.4) -> None:
    """Small delay between paginated requests to the same host."""
    time.sleep(seconds)
