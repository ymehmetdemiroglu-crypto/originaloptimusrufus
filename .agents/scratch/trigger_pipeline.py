#!/usr/bin/env python3
import urllib.request
import json

url = "http://localhost:8000/api/agent/run-pipeline"
headers = {
    "X-Admin-Key": "optimus_secret_key_2026",
    "Content-Type": "application/json"
}
data = json.dumps({"triggered_by": "manual"}).encode("utf-8")

req = urllib.request.Request(url, data=data, headers=headers, method="POST")
try:
    print("Triggering agent pipeline (this may take a few seconds to initialize/run)...")
    with urllib.request.urlopen(req) as response:
        res_data = response.read()
        res_json = json.loads(res_data)
        print("PIPELINE RUN RESULTS:")
        print(json.dumps(res_json, indent=2))
except Exception as e:
    print(f"Error triggering pipeline: {e}")
