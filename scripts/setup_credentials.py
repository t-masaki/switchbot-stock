"""Interactive setup: secrets never appear in command arguments or files."""
import argparse
from getpass import getpass
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))
from switchbot import api_call


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--prefix", default="/switchbot-stock")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    token = getpass("SwitchBot Token: ").strip()
    secret = getpass("SwitchBot Secret: ").strip()
    if not token or not secret:
        raise SystemExit("Token/Secret must not be empty")
    devices = api_call(token, secret, "/devices").get("deviceList", [])
    for device in devices:
        print(device.get("deviceId"), device.get("deviceType"), device.get("deviceName"))
    device_id = getpass("Daily Station Device ID: ").strip()
    if device_id not in {d.get("deviceId") for d in devices}:
        raise SystemExit("Device ID must match a device in the list")
    import boto3
    ssm = boto3.client("ssm", region_name=args.region)
    for key, value in (("token", token), ("secret", secret), ("device-id", device_id)):
        ssm.put_parameter(Name=args.prefix.rstrip("/") + "/" + key,
                          Value=value, Type="SecureString", Overwrite=args.overwrite)
    print("Saved three SecureString parameters. Values were not printed.")


if __name__ == "__main__":
    main()
