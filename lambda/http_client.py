import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def request_json(url, headers=None, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=headers or {})
    try:
        with urlopen(request, timeout=12) as response:
            return json.load(response)
    except HTTPError as exc:
        # Never expose request URLs (device IDs), headers, or response bodies.
        raise RuntimeError(f"Remote HTTP failure: {exc.code}") from None
    except (URLError, TimeoutError, ValueError):
        raise RuntimeError("Remote connection or JSON failure") from None
