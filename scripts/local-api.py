#!/usr/bin/env python3
"""Run the Lambda handlers locally behind a real HTTP server.

There is no "backend server" in this project — the backend is three Lambda
functions. This script gives you the dev loop anyway: it serves HTTP on
localhost and dispatches each request into the same handler code Lambda runs,
constructing the API Gateway v2 event shape by hand.

Downstream services are NOT mocked. DynamoDB, Athena, S3 and Secrets Manager
are the real dev resources, so what you see locally is what the deployed
function would do. That means you need working AWS credentials, and it means
writes here are real writes.

    ./scripts/local-api.py            # port 8000
    ./scripts/local-api.py --port 9000

Then point the frontend at it:
    echo "VITE_API_URL=http://localhost:8000" > frontend/.env.local
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))

TF_DIR = ROOT / "infrastructure" / "terraform" / "environments" / "dev"


def load_env_from_terraform() -> dict[str, str]:
    """Read resource names from terraform outputs rather than hardcoding them,
    so this cannot drift from what is actually deployed."""
    raw = subprocess.run(
        ["terraform", f"-chdir={TF_DIR}", "output", "-json"],
        capture_output=True, text=True, check=True,
    ).stdout
    out = {k: v["value"] for k, v in json.loads(raw).items()}
    tables = out["dynamodb_tables"]
    return {
        "LEDGERLY_ENV": "dev",
        "ITEMS_TABLE": tables["items"],
        "ACCOUNTS_TABLE": tables["accounts"],
        "RULES_TABLE": tables["rules"],
        "SYNC_RUNS_TABLE": tables["sync_runs"],
        "DATA_BUCKET": out["data_bucket"],
        "ATHENA_RESULTS_BUCKET": out["athena_results_bucket"],
        "ATHENA_WORKGROUP": out["athena_workgroup"],
        "GLUE_DATABASE": out["glue_database"],
        "PLAID_SECRET_ARN": "ledgerly/dev/plaid",
        "AUTH_SECRET_ARN": "ledgerly/dev/auth",
        "AWS_REGION": "us-east-1",
    }


class Handler(BaseHTTPRequestHandler):
    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length).decode() if length else ""

        # Route to the same Lambda that API Gateway would pick.
        from ledgerly.handlers import api, plaid_api, sync

        if parsed.path.startswith("/plaid/"):
            handler = plaid_api.handler
        elif parsed.path.startswith("/sync"):
            handler = sync.handler
        else:
            handler = api.handler

        event = {
            "requestContext": {"http": {"method": method, "path": parsed.path}},
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "queryStringParameters": {
                k: v[0] for k, v in parse_qs(parsed.query).items()
            } or None,
            "body": body or None,
            "isBase64Encoded": False,
        }

        try:
            result = handler(event, None)
            status = result.get("statusCode", 200)
            payload = result.get("body", "{}")
        except Exception as exc:  # noqa: BLE001 - surface it, do not swallow
            import traceback

            traceback.print_exc()
            status, payload = 500, json.dumps({"error": "handler_crashed", "detail": str(exc)})

        encoded = payload.encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        # Permissive CORS: this binds to localhost only and never runs deployed.
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-headers", "content-type,authorization")
        self.send_header("access-control-allow-methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-headers", "content-type,authorization")
        self.send_header("access-control-allow-methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"  {fmt % args}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import os

    try:
        env = load_env_from_terraform()
    except subprocess.CalledProcessError:
        sys.exit("Could not read terraform outputs. Run `terraform apply` in "
                 f"{TF_DIR} first.")
    os.environ.update(env)

    # macOS python.org builds do not read the system keychain, so outbound TLS
    # to Plaid fails without an explicit CA bundle. Harmless elsewhere.
    try:
        import certifi

        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass

    print(f"Ledgerly backend on http://localhost:{args.port}")
    print(f"  database   {env['GLUE_DATABASE']}")
    print(f"  data       {env['DATA_BUCKET']}")
    print("  NOTE: DynamoDB / Athena / S3 are the REAL dev resources — writes are real.\n")
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
