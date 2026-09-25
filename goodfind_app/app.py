"""
GoodFind - Multi-tenant Lost & Found platform.

Every organization (college, workplace, hospital, transport hub...) gets its
own isolated space. Data operations flow through the database adapter
(mock_data.py) which connects to Supabase PostgreSQL or falls back to in-memory
storage when credentials are not configured.
"""
import os
import uuid
from functools import wraps
from datetime import datetime, date, timedelta

from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename

load_dotenv()

import mock_data as db
import matching
import image_ai
import supabase_client

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-secret-change-me")

# Rate Limiting configuration
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://"
)

UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024      # 6 MB per photo
os.makedirs(UPLOAD_DIR, exist_ok=True)


def save_photo(file_storage, org_id="global", kind="item"):
    """Save an uploaded photo and return (url, fingerprint).

    Computes the fingerprint once at upload time and uploads to Supabase
    Storage if configured, otherwise saving to local static/uploads.
    """
    if not file_storage or not file_storage.filename:
        return "", None
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
    if ext not in ALLOWED_EXT:
        return "", None

    # Validate image integrity locally with Pillow
    try:
        from PIL import Image
        img_check = Image.open(file_storage.stream)
        img_check.verify()
        file_storage.stream.seek(0)
    except Exception:
        return "", None

    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, name)
    file_storage.save(path)

    try:
        fp = image_ai.fingerprint(path)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        return "", None

    # Supabase Storage Integration
    if supabase_client.is_supabase_enabled():
        try:
            with open(path, "rb") as f:
                remote_url = supabase_client.upload_to_storage(
                    f, file_storage.filename, org_id=org_id, kind=kind
                )
                if remote_url:
                    return remote_url, fp
        except Exception as e:
            print(f"[Storage] Supabase upload failed, using local: {e}")

    return f"uploads/{name}", fp


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    """Allow only the listed roles. Usage: @roles_required('staff', 'admin')"""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("user_role") not in roles:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_org():
    return db.get_org(session.get("org_id"))


@app.template_filter("img_src")
def img_src_filter(url):
    """Render image URL properly whether local or remote Supabase Storage."""
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return url_for("static", filename=url)


@app.context_processor
def inject_globals():
    uid, oid = session.get("user_id"), session.get("org_id")
    return {
        "unread_count": db.unread_notification_count(uid, oid) if uid else 0,
        "org": current_org(),
        "role": session.get("user_role"),
        "now": datetime.now(),
        "img_src": img_src_filter,
    }


def _sign_in(user):
    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_role"] = user["role"]
    session["org_id"] = user["org_id"]      # <-- the tenant key


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def landing():
    return render_template("landing.html", orgs=db.get_all_orgs())


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("15 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        errors = {}
        if not email:
            errors["email"] = "Enter your email."
        if not password:
            errors["password"] = "Enter your password."

        user = db.get_user_by_email(email)
        if not errors and (not user or not db.verify_user_password(user, password)):
            errors["form"] = "That email and password don't match an account."

        if errors:
            return render_template("login.html", errors=errors, email=email), 400

        _sign_in(user)
        flash(f"Welcome back, {user['name']}.", "success")
        return redirect(url_for("staff_desk") if user["role"] in ("staff", "admin")
                        else url_for("dashboard"))

    return render_template("login.html", errors={}, email="")


@app.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def signup():
    """Join an existing organization by email domain or join code."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        code = request.form.get("join_code", "").strip()
        errors = {}

        if not name:
            errors["name"] = "Enter your full name."
        elif len(name) > 80:
            errors["name"] = "Name must be under 80 characters."

        if not email or "@" not in email:
            errors["email"] = "Enter a valid email address."
        elif db.get_user_by_email(email):
            errors["email"] = "An account with this email already exists."

        if not password or len(password) < 6:
            errors["password"] = "Use at least 6 characters."
        if confirm != password:
            errors["confirm_password"] = "The two passwords don't match."

        # Tenant resolution: domain rule first, join code as fallback
        org = db.get_org_by_domain(email) if "@" in email else None
        if not org and code:
            org = db.get_org_by_code(code)
        if not org and not errors.get("email"):
            errors["join_code"] = ("We can't tell which organization you belong to. "
                                   "Use your work or college email, or enter a join code.")

        if errors:
            return render_template("signup.html", errors=errors, name=name,
                                   email=email, join_code=code), 400

        db.create_user(name, email, password, org["id"], role="member")
        flash(f"Account created for {org['name']}. Log in to continue.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html", errors={}, name="", email="", join_code="")


@app.route("/register-organization", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def register_org():
    """Self-serve onboarding for new organizations."""
    if request.method == "POST":
        f = request.form
        errors = {}
        for field, label in [("name", "Organization name"), ("email_domain", "Email domain"),
                             ("join_code", "Join code"), ("collection_desk", "Collection desk"),
                             ("admin_name", "Your name"), ("admin_email", "Your email"),
                             ("admin_password", "Password")]:
            val = f.get(field, "").strip()
            if not val:
                errors[field] = f"{label} is required."

        admin_email = f.get("admin_email", "").strip().lower()
        if admin_email and db.get_user_by_email(admin_email):
            errors["admin_email"] = "An account with this email already exists."
        if db.get_org_by_code(f.get("join_code", "")):
            errors["join_code"] = "That join code is already taken."
        if len(f.get("admin_password", "")) < 6:
            errors["admin_password"] = "Use at least 6 characters."

        if errors:
            return render_template("register_org.html", errors=errors, form=f,
                                   org_types=db.ORG_TYPES), 400

        org = db.create_org(f["name"], f.get("type", "Other"), f["email_domain"],
                            f["join_code"], f["collection_desk"],
                            admin_email)
        db.create_user(f["admin_name"].strip(), admin_email,
                       f["admin_password"], org["id"], role="admin")

        flash(f"{org['name']} is set up. Share the join code {org['join_code']} "
              "with your members.", "success")
        return redirect(url_for("login"))

    return render_template("register_org.html", errors={}, form={}, org_types=db.ORG_TYPES)


@app.route("/logout")
def logout():
    session.clear()
    flash("You're logged out.", "info")
    return redirect(url_for("landing"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    uid, oid = session["user_id"], session["org_id"]
    lost = db.get_user_lost_reports(uid, oid)
    found = db.get_user_found_reports(uid, oid)
    returned = db.get_user_returned_reports(uid, oid)
    matches = db.get_matches_for_user(uid, oid)

    activity = []
    for i in lost:
        activity.append({"icon": "search", "text": f"Reported lost: {i['name']}",
                         "meta": i["status"], "time": i["created_at"]})
    for i in found:
        activity.append({"icon": "hand", "text": f"Handed in: {i['name']}",
                         "meta": i["location"], "time": i["created_at"]})
    for i in returned:
        activity.append({"icon": "done", "text": f"Returned: {i['name']}",
                         "meta": "Case closed", "time": i["created_at"]})
    activity.sort(key=lambda a: str(a["time"]), reverse=True)

    top = None
    if matches:
        m = matches[0]
        top = {"match": m, "lost": db.get_item(m["lost_item_id"]),
               "found": db.get_item(m["found_item_id"])}

    return render_template("dashboard.html", active_nav="dashboard",
                           lost_count=len(lost), found_count=len(found),
                           match_count=len(matches), returned_count=len(returned),
                           top_match=top, activity=activity[:5])


# ---------------------------------------------------------------------------
# Report lost / found
# ---------------------------------------------------------------------------
def _validate_item_form(form):
    errors = {}
    name = form.get("name", "").strip()
    if not name:
        errors["name"] = "Name the item."
    elif len(name) < 2 or len(name) > 100:
        errors["name"] = "Name should be between 2 and 100 characters."

    cat = form.get("category")
    if not cat:
        errors["category"] = "Pick a category."
    elif cat not in db.CATEGORIES:
        errors["category"] = "Choose a valid category."

    loc = form.get("location", "").strip()
    if not loc:
        errors["location"] = "Where was it lost or found?"
    elif len(loc) > 150:
        errors["location"] = "Location must be under 150 characters."

    d_str = form.get("date")
    if not d_str:
        errors["date"] = "Pick a date."
    else:
        try:
            d_val = datetime.strptime(d_str, "%Y-%m-%d").date()
            if d_val > date.today():
                errors["date"] = "Date cannot be in the future."
            elif d_val < (date.today() - timedelta(days=365)):
                errors["date"] = "Date cannot be older than one year."
        except ValueError:
            errors["date"] = "Invalid date format."

    desc = form.get("description", "").strip()
    if not desc:
        errors["description"] = "Add a short description."
    elif len(desc) < 5:
        errors["description"] = "Description is too short (at least 5 characters)."
    elif len(desc) > 1500:
        errors["description"] = "Description must be under 1500 characters."

    return errors


def _build_item(form, prefix, photo=None):
    org_id = session["org_id"]
    image_url, image_fp = save_photo(photo, org_id=org_id, kind=prefix)
    return {
        "id": db.next_id(prefix), "org_id": org_id,
        "user_id": session["user_id"], "name": form["name"].strip(),
        "category": form["category"], "brand": form.get("brand", "").strip(),
        "model": form.get("model", "").strip(), "color": form.get("color", "").strip(),
        "location": form["location"].strip(), "date": form["date"],
        "time": form.get("time", ""), "description": form["description"].strip(),
        "image_url": image_url, "image_fp": image_fp,
        "status": "Searching", "created_at": datetime.now(),
    }


def _alert_owner(lost, found, score, notes):
    """Notify the owner that a potential match has been identified."""
    finder = db.get_user_by_id(found["user_id"])
    finder_name = finder["name"] if finder else "A finder"
    db.add_notification(
        lost["org_id"], lost["user_id"], "match",
        f"{matching.verdict(score, notes)} ({score}% match)",
        f"{found['name']} was handed in at {found['location']} on {found['date']} "
        f"by {finder_name}. Open the match to compare the photos and contact them.")


def _match_new_lost(item):
    """Run scorer against organization's open found reports and alert on hits."""
    hits = matching.run_matching(item, db.org_found_items(item["org_id"]))
    for found, score, factors, notes in hits:
        db.add_match(item, found, score, factors, notes)
        item["status"] = "Possible Match"
        db.update_item_status(item["id"], "Possible Match")
        found["status"] = "Possible Match"
        db.update_item_status(found["id"], "Possible Match")
        _alert_owner(item, found, score, notes)
    return len(hits)


def _match_new_found(item):
    """Run scorer against organization's open lost reports."""
    count = 0
    for lost in db.org_lost_items(item["org_id"]):
        if lost["status"] in ("Returned", "Closed"):
            continue
        score, factors, notes = matching.score_match(lost, item)
        if score >= matching.THRESHOLD:
            db.add_match(lost, item, score, factors, notes)
            lost["status"] = "Possible Match"
            db.update_item_status(lost["id"], "Possible Match")
            item["status"] = "Possible Match"
            db.update_item_status(item["id"], "Possible Match")
            _alert_owner(lost, item, score, notes)
            count += 1
    return count


@app.route("/lost", methods=["GET", "POST"])
@login_required
@limiter.limit("15 per 10 minutes", methods=["POST"])
def report_lost():
    if request.method == "POST":
        errors = _validate_item_form(request.form)
        if errors:
            return render_template("report_item.html", active_nav="report", mode="lost",
                                   errors=errors, form=request.form,
                                   categories=db.CATEGORIES), 400

        item = _build_item(request.form, "lost", request.files.get("photo"))
        db.add_lost_report(item)
        hits = _match_new_lost(item)
        flash(f"Report saved. {hits} possible match found." if hits == 1 else
              f"Report saved. {hits} possible matches found." if hits else
              "Report saved. We'll alert you the moment something similar is handed in.",
              "success")
        return redirect(url_for("matches") if hits else url_for("items"))

    return render_template("report_item.html", active_nav="report", mode="lost",
                           errors={}, form={}, categories=db.CATEGORIES)


@app.route("/found", methods=["GET", "POST"])
@login_required
@limiter.limit("15 per 10 minutes", methods=["POST"])
def report_found():
    if request.method == "POST":
        errors = _validate_item_form(request.form)
        if errors:
            return render_template("report_item.html", active_nav="report", mode="found",
                                   errors=errors, form=request.form,
                                   categories=db.CATEGORIES), 400

        item = _build_item(request.form, "found", request.files.get("photo"))
        db.add_found_report(item)
        hits = _match_new_found(item)
        org = current_org()
        desk = org["collection_desk"] if org else "the collection desk"
        flash(f"Thank you. Please hand the item in at {desk}."
              + (f" {hits} owner has been alerted." if hits == 1 else
                 f" {hits} owners have been alerted." if hits else ""), "success")
        return redirect(url_for("items", tab="found"))

    return render_template("report_item.html", active_nav="report", mode="found",
                           errors={}, form={}, categories=db.CATEGORIES)


# ---------------------------------------------------------------------------
# Matches + ownership verification
# ---------------------------------------------------------------------------
@app.route("/matches")
@login_required
def matches():
    uid, oid = session["user_id"], session["org_id"]
    rows = [{"match": m, "lost": db.get_item(m["lost_item_id"]),
             "found": db.get_item(m["found_item_id"])}
            for m in db.get_matches_for_user(uid, oid)]
    return render_template("matches.html", active_nav="matches", rows=rows)


@app.route("/matches/<match_id>", methods=["GET", "POST"])
@login_required
def match_details(match_id):
    match = db.get_match(match_id)
    if not match or match["org_id"] != session["org_id"]:
        flash("That match isn't available.", "error")
        return redirect(url_for("matches"))

    lost = db.get_item(match["lost_item_id"])
    found = db.get_item(match["found_item_id"])

    if request.method == "POST":
        detail = request.form.get("unique_detail", "").strip()
        if len(detail) < 10:
            flash("Describe a detail only the owner would know (at least 10 characters).",
                  "error")
        else:
            db.submit_ownership_claim(match_id, lost["id"], session["user_id"], detail)
            for staff in db.org_members(session["org_id"]):
                if staff["role"] in ("staff", "admin"):
                    db.add_notification(session["org_id"], staff["id"], "claim",
                                        f"Claim to review: {found['name']}",
                                        f"{session['user_name']} says this item is theirs.")
            flash("Claim sent. The front desk will review it.", "success")
            return redirect(url_for("items"))

    finder = db.get_user_by_id(found["user_id"])
    return render_template("match_details.html", active_nav="matches",
                            match=match, lost=lost, found=found, finder=finder,
                            verdict=matching.verdict(match["score"], match.get("notes")))


@app.route("/matches/<match_id>/contact", methods=["POST"])
@login_required
def contact_finder(match_id):
    """Open a private thread between the owner and finder."""
    match = db.get_match(match_id)
    if not match or match["org_id"] != session["org_id"]:
        flash("That match isn't available.", "error")
        return redirect(url_for("matches"))

    lost, found = db.get_item(match["lost_item_id"]), db.get_item(match["found_item_id"])
    if lost["user_id"] != session["user_id"]:
        flash("Only the person who reported the loss can start this thread.", "error")
        return redirect(url_for("matches"))

    conv = db.start_conversation(
        session["org_id"], session["user_id"], found["user_id"], found["name"],
        opening=f"Hi, I think the {found['name']} you handed in is my "
                f"{lost['name']}. I lost it at {lost['location']} on {lost['date']}.")
    db.add_notification(session["org_id"], found["user_id"], "message",
                        f"{session['user_name']} may be the owner of {found['name']}",
                        "They opened a thread about the item you handed in.",
                        link_id=conv["id"])
    flash("Thread opened with the finder.", "success")
    return redirect(url_for("messages", conv=conv["id"]))


# ---------------------------------------------------------------------------
# Staff desk: approve or reject claims, mark items returned
# ---------------------------------------------------------------------------
@app.route("/desk")
@login_required
@roles_required("staff", "admin")
def staff_desk():
    oid = session["org_id"]
    claims = []
    for m in db.get_claims_for_staff(oid):
        l_item = db.get_item(m["lost_item_id"])
        f_item = db.get_item(m["found_item_id"])
        claimant = db.get_user_by_id(l_item["user_id"]) if l_item else None
        claims.append({"match": m, "lost": l_item, "found": f_item, "claimant": claimant})

    holding = [i for i in db.org_found_items(oid) if i["status"] != "Returned"]
    return render_template("desk.html", active_nav="desk", claims=claims, holding=holding)


@app.route("/desk/claims/<match_id>/<decision>", methods=["POST"])
@login_required
@roles_required("staff", "admin")
def decide_claim(match_id, decision):
    match = db.get_match(match_id)
    if not match or match["org_id"] != session["org_id"]:
        flash("That claim isn't available.", "error")
        return redirect(url_for("staff_desk"))

    lost, found = db.get_item(match["lost_item_id"]), db.get_item(match["found_item_id"])
    org = current_org()
    desk = org["collection_desk"] if org else "the collection desk"

    if decision == "approve":
        db.decide_ownership_claim(match_id, "approve", reviewer_id=session["user_id"])
        db.add_notification(session["org_id"], lost["user_id"], "claim",
                            f"Your claim for {found['name']} was approved",
                            f"Collect it from {desk}. Bring your ID.")
        flash("Claim approved. The owner has been told where to collect it.", "success")
    elif decision == "reject":
        db.decide_ownership_claim(match_id, "reject", reviewer_id=session["user_id"])
        db.add_notification(session["org_id"], lost["user_id"], "claim",
                            f"Claim for {found['name']} was not approved",
                            "The identifying detail didn't match. Your report is still open.")
        flash("Claim rejected. The report stays open.", "info")
    return redirect(url_for("staff_desk"))


@app.route("/desk/items/<item_id>/returned", methods=["POST"])
@login_required
@roles_required("staff", "admin")
def mark_returned(item_id):
    found = db.get_item(item_id)
    if not found or found["org_id"] != session["org_id"]:
        flash("That item isn't available.", "error")
        return redirect(url_for("staff_desk"))

    db.mark_item_returned(item_id)
    # Notify matching lost owners
    for m in db.MATCHES:
        if m["found_item_id"] == item_id and m.get("claim_status") == "approved":
            lost = db.get_item(m["lost_item_id"])
            if lost:
                db.add_notification(lost["org_id"], lost["user_id"], "returned",
                                    f"{lost['name']} returned", "Case closed. Glad you got it back.")
    flash("Marked as returned.", "success")
    return redirect(url_for("staff_desk"))


# ---------------------------------------------------------------------------
# My reports
# ---------------------------------------------------------------------------
@app.route("/items")
@login_required
def items():
    uid, oid = session["user_id"], session["org_id"]
    tab = request.args.get("tab", "lost")
    return render_template(
        "items.html", active_nav="items", tab=tab,
        lost=db.get_user_lost_reports(uid, oid),
        found=db.get_user_found_reports(uid, oid),
        returned=db.get_user_returned_reports(uid, oid),
        match_count=db.match_count_for_item)


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------
@app.route("/messages")
@login_required
def messages():
    uid, oid = session["user_id"], session["org_id"]
    convs = db.get_conversations_for_user(uid, oid)
    active_id = request.args.get("conv", convs[0]["id"] if convs else None)
    active_conv = db.get_conversation(active_id) if active_id else None
    if active_conv and active_conv["org_id"] != oid:
        active_conv = None
    return render_template("messages.html", active_nav="messages",
                           conversations=convs, active_conv=active_conv,
                           other_name=db.other_participant_name)


@app.route("/messages/<conv_id>/send", methods=["POST"])
@login_required
@limiter.limit("30 per minute", methods=["POST"])
def send_message(conv_id):
    conv = db.get_conversation(conv_id)
    text = request.form.get("text", "").strip()
    if conv and conv["org_id"] == session["org_id"] and session["user_id"] in conv["participants"] and text:
        db.add_message(conv_id, session["user_id"], text)
    return redirect(url_for("messages", conv=conv_id))


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@app.route("/notifications")
@login_required
def notifications():
    uid, oid = session["user_id"], session["org_id"]
    notes = sorted(db.get_notifications_for_user(uid, oid),
                   key=lambda n: str(n["created_at"]), reverse=True)
    return render_template("notifications.html", active_nav="notifications",
                           notifications=notes)


@app.route("/notifications/<notif_id>/dismiss", methods=["POST"])
@login_required
def dismiss_notification(notif_id):
    db.dismiss_notification(notif_id)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(url_for("notifications"))


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = db.get_user_by_id(session["user_id"])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Your name can't be empty.", "error")
        elif len(name) > 80:
            flash("Name must be under 80 characters.", "error")
        else:
            db.update_user_name(session["user_id"], name)
            session["user_name"] = name
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
    return render_template("profile.html", active_nav="profile", user=user)


# ---------------------------------------------------------------------------
# Organization admin
# ---------------------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_dashboard():
    oid = session["org_id"]
    org = current_org()

    if request.method == "POST":
        desk = request.form.get("collection_desk", "").strip()
        if desk:
            db.update_org_collection_desk(oid, desk)
            flash("Collection desk updated.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin.html", active_nav="admin", stats=db.admin_stats(oid),
                           lost_items=db.org_lost_items(oid),
                           found_items=db.org_found_items(oid),
                           members=db.org_members(oid))


def bootstrap_photos():
    """Fingerprint any seed photo that doesn't have one yet."""
    for item in db.LOST_ITEMS + db.FOUND_ITEMS + db.RETURNED_ITEMS:
        if item.get("image_url") and not item.get("image_fp"):
            path = os.path.join(app.static_folder, item["image_url"])
            if os.path.exists(path):
                item["image_fp"] = image_ai.fingerprint(path)


def bootstrap_matches():
    """Score the seed data once at startup so the demo opens with real matches."""
    for org in db.get_all_orgs():
        org_id = org["id"]
        found_pool = db.org_found_items(org_id)
        for lost in db.org_lost_items(org_id):
            for found, score, factors, notes in matching.run_matching(lost, found_pool):
                db.add_match(lost, found, score, factors, notes)
                lost["status"] = "Possible Match"
                found["status"] = "Possible Match"


bootstrap_photos()
bootstrap_matches()


if __name__ == "__main__":
    app.run(debug=True)
