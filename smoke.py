import urllib.request, json
try:
    r = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/exams", timeout=5)
    body = json.load(r)
    reg = urllib.request.urlopen(urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/login",
        data=json.dumps({"email": "smoketest@example.com", "password": "smoketest123"}).encode(),
        headers={"Content-Type": "application/json"}), timeout=5)
    tok = json.load(reg)["token"]
    me = urllib.request.urlopen(urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/me", headers={"Authorization": "Bearer " + tok}), timeout=5)
    auth = json.load(me)
    dash = urllib.request.urlopen(urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/dashboard", headers={"Authorization": "Bearer " + tok}), timeout=5)
    out = f"exams HTTP {r.status} n={len(body)} | register OK role={auth['role']} email={auth['email']} | dashboard HTTP {dash.status}"
except Exception as e:
    out = "FAIL: " + repr(e)
open(r"C:\Users\brund\Downloads\trmi-windows-x64.exe\govtexammitra\health.txt", "w").write(out)
