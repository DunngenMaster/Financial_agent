import requests

url = "http://localhost:8000/process/pdf"

try:
    resp = requests.post(url, headers={"accept": "application/json"})
    print("Status:", resp.status_code)
    print("Response:")
    print(resp.json())
except Exception as e:
    print("Error calling /process/pdf:", e)
