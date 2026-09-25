"""
GoodFind matching engine.

This is the core of the product: when someone hands in an item, the engine
compares it against every open lost report in the same organization and decides
whether to tell an owner "this looks like yours".

Seven factors, 100 points in total:

    Category          20   hard filter -- categories must match at all
    Brand             15   exact match on brand
    Colour            10   exact match on colour
    Date closeness    15   found on or shortly after the loss
    Location          10   shared place words
    Description       10   shared meaningful words in the two write-ups
    Photo             20   image fingerprint similarity (image_ai.py)

Every factor is reported back so the owner and the front desk can see *why* the
two items were paired. That explainability is the reason rules come before a
neural network; image_ai.py can be upgraded to CNN embeddings later and this
file does not change.
"""
from datetime import datetime

import image_ai

THRESHOLD = 50          # below this we don't surface a match at all
STRONG = 75             # at or above this we call it a strong match
MAX_DAY_GAP = 14        # a phone found 3 weeks later is probably another phone

WEIGHTS = {
    "category": 20,
    "brand": 15,
    "color": 10,
    "date": 15,
    "location": 10,
    "description": 10,
    "image": 20,
}

_STOP = {
    "the", "a", "an", "and", "or", "with", "without", "of", "in", "on", "at",
    "is", "it", "its", "was", "has", "have", "had", "my", "i", "for", "to",
    "near", "by", "from", "that", "this", "there", "some", "very", "one",
    "floor", "block", "room", "side", "inside", "colour", "color",
}


def _parse(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _tokens(text):
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in (text or ""))
    return {w for w in cleaned.split() if len(w) > 2 and w not in _STOP}


def _text_similarity(a, b):
    """Jaccard overlap: shared words divided by all distinct words."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def score_match(lost, found):
    """Compare one lost report with one found item.

    Returns (score 0-100, factors dict, notes dict). `notes` holds the raw
    similarity values so the UI can say "the photos are 81% alike".
    """
    factors, notes = {}, {}

    # Hard rules first -- these are disqualifiers, not soft signals.
    if lost["org_id"] != found["org_id"]:
        return 0, {}, {}                    # never match across organizations
    if lost["user_id"] == found["user_id"]:
        return 0, {}, {}                    # don't match a user to themselves
    if lost["category"] != found["category"]:
        return 0, {}, {}

    score = WEIGHTS["category"]
    factors["Same category"] = WEIGHTS["category"]

    lb, fb = lost.get("brand", "").strip().lower(), found.get("brand", "").strip().lower()
    if lb and fb and lb == fb:
        score += WEIGHTS["brand"]
        factors["Brand matches"] = WEIGHTS["brand"]

    lc, fc = lost.get("color", "").strip().lower(), found.get("color", "").strip().lower()
    if lc and fc and lc == fc:
        score += WEIGHTS["color"]
        factors["Colour matches"] = WEIGHTS["color"]

    d1, d2 = _parse(lost.get("date")), _parse(found.get("date"))
    if d1 and d2:
        gap = (d2 - d1).days
        if 0 <= gap <= MAX_DAY_GAP:
            pts = round(WEIGHTS["date"] * (1 - gap / MAX_DAY_GAP))
            if pts:
                score += pts
                factors["Found soon after the loss"] = pts
                notes["day_gap"] = gap

    if _tokens(lost.get("location")) & _tokens(found.get("location")):
        score += WEIGHTS["location"]
        factors["Same place"] = WEIGHTS["location"]

    # --- description: what the owner wrote vs what the finder wrote ----------
    text_sim = _text_similarity(
        f"{lost.get('name','')} {lost.get('description','')}",
        f"{found.get('name','')} {found.get('description','')}")
    if text_sim >= 0.12:
        pts = round(WEIGHTS["description"] * min(text_sim * 2, 1.0))
        if pts:
            score += pts
            factors["Descriptions agree"] = pts
            notes["text_similarity"] = round(text_sim * 100)

    # --- photo: the owner's reference photo vs the finder's photo ------------
    img_sim = image_ai.compare_fingerprints(lost.get("image_fp"), found.get("image_fp"))
    if img_sim:
        notes["image_similarity"] = round(img_sim * 100)
        if img_sim >= 0.35:
            pts = round(WEIGHTS["image"] * img_sim)
            score += pts
            factors["Photos look alike"] = pts

    return min(score, 100), factors, notes


def verdict(score, notes=None):
    """One plain sentence for the owner, in the interface's voice."""
    notes = notes or {}
    if score >= STRONG:
        line = "This looks like your item."
    elif score >= 60:
        line = "This could well be your item."
    else:
        line = "This is worth a look."
    if notes.get("image_similarity", 0) >= 60:
        line += f" The two photos are {notes['image_similarity']}% alike."
    return line


def run_matching(lost_item, found_pool, threshold=THRESHOLD):
    """Score one lost report against a pool of found items, best first."""
    results = []
    for f in found_pool:
        if f["status"] in ("Returned", "Closed"):
            continue
        s, factors, notes = score_match(lost_item, f)
        if s >= threshold:
            results.append((f, s, factors, notes))
    return sorted(results, key=lambda r: r[1], reverse=True)
