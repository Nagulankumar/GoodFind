"""Quick smoke test: every page loads, and data does not leak between orgs."""
from app import app
import mock_data as db

c = app.test_client()
fails = []


def check(label, resp, expect=200):
    code = resp.status_code
    ok = code == expect
    if not ok:
        fails.append(f"{label}: got {code}, expected {expect}")
    print(f"{'PASS' if ok else 'FAIL'}  {label} [{code}]")


check("landing", c.get("/"))
check("login page", c.get("/login"))
check("signup page", c.get("/signup"))
check("register org page", c.get("/register-organization"))
check("dashboard while logged out redirects", c.get("/dashboard"), 302)

# --- member login -----------------------------------------------------------
c.post("/login", data={"email": "demo@vsbec.ac.in", "password": "demo1234"})
for path in ["/dashboard", "/lost", "/found", "/items", "/matches",
             "/messages", "/notifications", "/profile"]:
    check(f"member {path}", c.get(path))
check("member blocked from /desk", c.get("/desk"), 302)
check("member blocked from /admin", c.get("/admin"), 302)

# report a lost item that should match found-005 (Brown Leather Wallet)
r = c.post("/lost", data={"name": "Brown wallet", "category": "Wallet",
                          "color": "Brown", "location": "Cafeteria",
                          "date": "2026-09-15", "description": "Bifold, brown leather."},
           follow_redirects=True)
check("report lost + auto-match", r)
print("   matches now stored:", len(db.MATCHES))
assert db.MATCHES, "matching engine produced no matches"

# photo pipeline: seeded phone match must use the image factor
phone = next(m for m in db.MATCHES
             if db.get_item(m["found_item_id"])["name"] == "Black Android Phone")
print("   phone match score:", phone["score"], phone["factors"])
assert "Photos look alike" in phone["factors"], "image factor did not fire"
assert phone["notes"]["image_similarity"] > 50

# uploading a photo through the form
import io
from PIL import Image
buf = io.BytesIO()
Image.open("static/uploads/seed/phone_owner.png").save(buf, "PNG")
buf.seek(0)
r = c.post("/lost", data={"name": "Dark phone", "category": "Mobile Phone",
                          "color": "Black", "location": "Library",
                          "date": "2026-09-17", "description": "Black phone, cracked protector.",
                          "photo": (buf, "myphone.png")},
           content_type="multipart/form-data", follow_redirects=True)
check("upload a reference photo", r)
uploaded = db.LOST_ITEMS[-1]
assert uploaded["image_url"].startswith("uploads/"), uploaded["image_url"]
assert uploaded["image_fp"], "no fingerprint computed on upload"
print("   uploaded photo saved as", uploaded["image_url"])

m = next(mm for mm in db.MATCHES if db.get_item(mm["lost_item_id"])["name"] == "Brown wallet")
check("match details", c.get(f"/matches/{m['id']}"))
check("submit claim", c.post(f"/matches/{m['id']}",
                             data={"unique_detail": "There is a torn bus pass inside it."},
                             follow_redirects=True))
assert m["claim_status"] == "pending", m["claim_status"]

# --- staff approves ---------------------------------------------------------
c.get("/logout")
c.post("/login", data={"email": "desk@vsbec.ac.in", "password": "desk1234"})
check("staff desk", c.get("/desk"))
check("approve claim", c.post(f"/desk/claims/{m['id']}/approve", follow_redirects=True))
assert m["claim_status"] == "approved", m["claim_status"]
check("mark returned", c.post(f"/desk/items/{m['found_item_id']}/returned",
                              follow_redirects=True))

# contacting the finder opens a thread
c.get("/logout")
c.post("/login", data={"email": "demo@vsbec.ac.in", "password": "demo1234"})
check("contact the finder", c.post(f"/matches/{phone['id']}/contact", follow_redirects=True))
assert any(conv["item_summary"] == "Black Android Phone" for conv in db.CONVERSATIONS)

# --- admin ------------------------------------------------------------------
c.get("/logout")
c.post("/login", data={"email": "admin@vsbec.ac.in", "password": "admin1234"})
check("admin dashboard", c.get("/admin"))

# --- tenant isolation -------------------------------------------------------
c.get("/logout")
c.post("/login", data={"email": "ravi@northgate.example", "password": "ravi1234"})
body = c.get("/items").get_data(as_text=True)
leak = "Samsung" in body or "Brown Leather Wallet" in body
print(f"{'FAIL' if leak else 'PASS'}  other org sees no VSB items")
if leak:
    fails.append("tenant leak on /items")
check("cross-org match blocked", c.get(f"/matches/{m['id']}"), 302)

# --- signup by join code ----------------------------------------------------
c.get("/logout")
r = c.post("/signup", data={"name": "New Student", "email": "new@gmail.com",
                            "join_code": "VSB2026", "password": "pass1234",
                            "confirm_password": "pass1234"}, follow_redirects=True)
check("signup via join code", r)
assert db.USERS["new@gmail.com"]["org_id"] == "org-001"

print("\n" + ("ALL PASSED" if not fails else "FAILURES:\n" + "\n".join(fails)))
