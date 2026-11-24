"""Envía una lectura ficticia usando el mismo endpoint que el dispositivo."""

import argparse
import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("litros", help="Litros despachados, por ejemplo 10.50")
    parser.add_argument("--url", default="http://127.0.0.1:58000")
    args = parser.parse_args()

    payload = {
        "uid": "DEMO-NFC-01",
        "pistola": "DEMO-N1",
        "litros": args.litros,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    request = Request(
        args.url.rstrip("/") + "/api/iot/proxy/",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-IoT-Token": os.environ["IOT_SECRET_TOKEN"],
        },
    )
    with urlopen(request, timeout=10) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()
