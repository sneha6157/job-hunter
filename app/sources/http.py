"""Shared HTTP session with retry + backoff for all sources."""
import time, random, requests, urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def make_session(retries: int = 2, backoff: float = 1.0) -> requests.Session:
    s       = requests.Session()
    retry   = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://",  adapter)
    s.mount("https://", adapter)
    return s


def safe_get(url: str, *, headers: dict, params: dict = None,
             timeout: int = 14, verify: bool = False,
             retries: int = 2) -> requests.Response | None:
    """GET with retry + jitter. Returns None on all failures."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url, headers=headers, params=params,
                timeout=timeout, verify=verify,
            )
            return resp
        except Exception as e:
            if attempt < retries:
                time.sleep(random.uniform(0.3, 0.8))
            else:
                raise e
    return None
