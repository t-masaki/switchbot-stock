import base64
import hashlib
import hmac
import time
import uuid
from urllib.parse import quote
from http_client import request_json

BASE_URL = "https://api.switch-bot.com/v1.1"


def auth_headers(token, secret, timestamp=None, nonce=None):
    timestamp = str(timestamp if timestamp is not None else int(time.time() * 1000))
    nonce = nonce if nonce is not None else str(uuid.uuid4())
    signature = base64.b64encode(hmac.new(secret.encode(),
        (token + timestamp + nonce).encode(), hashlib.sha256).digest()).decode()
    return {"Authorization": token, "sign": signature, "t": timestamp,
            "nonce": nonce, "Content-Type": "application/json; charset=utf8"}


def api_call(token, secret, path, payload=None):
    result = request_json(BASE_URL + path, auth_headers(token, secret), payload)
    if result.get("statusCode") != 100:
        raise RuntimeError("SwitchBot rejected request (statusCode="
                           + str(result.get("statusCode")) + ")")
    return result.get("body", {})


def validate_component(template_id, component_id, text):
    for value in (template_id, component_id):
        if type(value) is not int or value <= 0:
            raise ValueError("Template and component IDs must be positive integers")
    if not isinstance(text, str) or not text or len(text) > 100:
        raise ValueError("Component text must contain 1-100 characters")


def send_component(token, secret, device_id, template_id, component_id, text):
    validate_component(template_id, component_id, text)
    return api_call(token, secret, "/devices/" + quote(device_id, safe="") + "/commands",
                    {"command": "customPutComponent", "commandType": "command",
                     "parameter": {"templateID": template_id,
                                   "componentID": component_id, "text": text}})
