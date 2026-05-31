#!/usr/bin/env python3
import urllib.request
import json

url = "https://hjwthysdzjqivrmrezdm.supabase.co/rest/v1/rufus_calc_submissions?select=id,asin,email&limit=5"
headers = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhqd3RoeXNkempxaXZybXJlemRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTQwNTQsImV4cCI6MjA5MjUzMDA1NH0.MF_deA3cVMkgJCxmbKoTwrQs2SmfWlQwIOqSB0k3noc",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhqd3RoeXNkempxaXZybXJlemRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTQwNTQsImV4cCI6MjA5MjUzMDA1NH0.MF_deA3cVMkgJCxmbKoTwrQs2SmfWlQwIOqSB0k3noc"
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = response.read()
        submissions = json.loads(data)
        print("FOUND SUBMISSIONS:")
        for s in submissions:
            print(f"- ID: {s.get('id')}, ASIN: {s.get('asin')}, Email: {s.get('email')}")
except Exception as e:
    print(f"Error querying submissions: {e}")
