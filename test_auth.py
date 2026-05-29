import requests

s = requests.Session()
res = s.post('http://localhost:8000/api/auth/login/', json={"username": "admin", "password": "breathe123"})
print("Login status:", res.status_code)
print("Login cookies:", s.cookies.get_dict())
print("Login response:", res.json())

res2 = s.get('http://localhost:8000/api/auth/me/')
print("Me status:", res2.status_code)
print("Me response:", res2.json())

res3 = s.post('http://localhost:8000/api/v1/ingestion/sap/upload/')
print("Upload status:", res3.status_code)
print("Upload response:", res3.text)
