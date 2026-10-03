import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from market_data import get_quote
from switchbot import send_component, validate_component

JST = ZoneInfo("Asia/Tokyo")


def in_window(now):
    local = now.astimezone(JST)
    minute = local.hour * 60 + local.minute
    return local.weekday() < 5 and 540 <= minute <= 930 and not 690 <= minute < 750


def format_component(quotes):
    if len(quotes) != 2:
        raise ValueError("Two quotes are required")
    def number(value):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    parts = []
    for label, unit, item in zip(("TDSE", "日経225"), ("円", ""), quotes):
        change = ("+" if item.change >= 0 else "-") + number(abs(item.change))
        parts.append(f"{label} {number(item.price)}{unit} {change}({item.change_percent:+.2f}%)")
    stamp = min(q.as_of for q in quotes).astimezone(JST).strftime("%m/%d %H:%M")
    text = " | ".join(parts) + f" | 最古{stamp} JST 遅延"
    if len(text) > 100:
        raise ValueError("Quote display exceeds 100 characters; nothing was sent")
    return text


def component_target():
    try:
        template_id = int(os.environ["TEMPLATE_ID"])
        component_id = int(os.environ["COMPONENT_ID"])
    except (KeyError, ValueError):
        raise ValueError("Set TEMPLATE_ID and COMPONENT_ID to positive integers") from None
    validate_component(template_id, component_id, "check")
    return template_id, component_id


def load_credentials():
    import boto3
    prefix = os.environ["SSM_PREFIX"].rstrip("/")
    names = [prefix + "/" + key for key in ("token", "secret", "device-id")]
    result = boto3.client("ssm").get_parameters(Names=names, WithDecryption=True)
    values = {p["Name"]: p["Value"] for p in result["Parameters"]}
    if any(not values.get(name, "").strip() for name in names):
        raise RuntimeError("Missing or empty SSM credentials")
    return [values[name].strip() for name in names]


def lambda_handler(event, context):
    event = event or {}
    now = datetime.now(timezone.utc)
    force = event.get("force") is True
    if not force and not in_window(now):
        return {"status": "skipped", "reason": "outside trading window"}
    quotes = [get_quote(symbol) for symbol in ("7046.T", "^N225")]
    # On holidays or missing current-session quotes preserve the existing page.
    if not force and any(q.as_of.astimezone(JST).date() != now.astimezone(JST).date() for q in quotes):
        return {"status": "skipped", "reason": "no current-session quotes"}
    text = format_component(quotes)
    template_id, component_id = component_target()
    if event.get("dry_run") is True:
        return {"status": "dry_run", "text": text}
    send_component(*load_credentials(), template_id, component_id, text)
    return {"status": "sent", "text": text}
