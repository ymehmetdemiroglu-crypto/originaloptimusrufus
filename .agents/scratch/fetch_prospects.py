#!/usr/bin/env python3
import urllib.request
import json

url = "https://hjwthysdzjqivrmrezdm.supabase.co/rest/v1/prospects?select=asin,brand,category,rufus_score,rufus_citation_probability&rufus_score=not.is.null&limit=10"
headers = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhqd3RoeXNkempxaXZybXJlemRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTQwNTQsImV4cCI6MjA5MjUzMDA1NH0.MF_deA3cVMkgJCxmbKoTwrQs2SmfWlQwIOqSB0k3noc",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhqd3RoeXNkempxaXZybXJlemRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTQwNTQsImV4cCI6MjA5MjUzMDA1NH0.MF_deA3cVMkgJCxmbKoTwrQs2SmfWlQwIOqSB0k3noc"
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = response.read()
        prospects = json.loads(data)
        print("FOUND PROSPECTS:")
        for p in prospects:
            print(f"- ASIN: {p.get('asin')}, Brand: {p.get('brand')}, Score: {p.get('rufus_score')}, Citation Prob: {p.get('rufus_citation_probability')}")
except Exception as e:
    print(f"Error querying prospects: {e}")
