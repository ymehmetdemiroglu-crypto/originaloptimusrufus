#!/usr/bin/env python3
import urllib.request
import json

url = "http://localhost:8000/api/agent/status"
headers = {
    "X-Admin-Key": "optimus_secret_key_2026"
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = response.read()
        status = json.loads(data)
        print("AGENT STATUS:")
        print(json.dumps(status, indent=2))
except Exception as e:
    print(f"Error querying agent status: {e}")
