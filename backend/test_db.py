import requests

url = "http://localhost:8000/orgs/default/repos/94428abf-b09a-4d63-9c15-08370609b0f1/branches/merge"
payload = {"source_branch": "test", "target_branch": "main"}

try:
    response = requests.post(url, json=payload)
    print("Status:", response.status_code)
    print("Response:", response.text[:500])
except Exception as e:
    print("Error:", e)
