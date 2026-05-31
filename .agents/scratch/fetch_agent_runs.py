#!/usr/bin/env python3
import urllib.request
import json

url = "https://hjwthysdzjqivrmrezdm.supabase.co/rest/v1/agent_runs?select=id,run_type,triggered_by,status,records_processed,error_log,started_at,completed_at&order=started_at.desc&limit=10"
headers = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhqd3RoeXNkempxaXZybXJlemRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTQwNTQsImV4cCI6MjA5MjUzMDA1NH0.MF_deA3cVMkgJCxmbKoTwrQs2SmfWlQwIOqSB0k3noc",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhqd3RoeXNkempxaXZybXJlemRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTQwNTQsImV4cCI6MjA5MjUzMDA1NH0.MF_deA3cVMkgJCxmbKoTwrQs2SmfWlQwIOqSB0k3noc"
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = response.read()
        runs = json.loads(data)
        print("FOUND AGENT RUNS:")
        for r in runs:
            print(f"- Run ID: {r.get('id')}")
            print(f"  Job: {r.get('run_type')}, Status: {r.get('status')}")
            print(f"  Triggered By: {r.get('triggered_by')}")
            print(f"  Processed: {r.get('records_processed')}")
            print(f"  Started At: {r.get('started_at')}")
            print(f"  Finished At: {r.get('completed_at')}")
            print(f"  Errors: {r.get('error_log')}")
            print("-" * 50)
except Exception as e:
    print(f"Error querying agent runs: {e}")
