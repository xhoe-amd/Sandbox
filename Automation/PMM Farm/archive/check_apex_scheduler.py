import requests

url = "http://apexlegacy.amd.com/farm/83/jobs/active"

response = requests.get(url)

print(response.status_code)
print(response.text)