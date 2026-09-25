# GoodFind — a lost and found any place can run

GoodFind gives one organization — a college, an office, a hospital, a transport
hub — its own private lost and found. Members report what they lost, anyone can
log what they found, and a scoring engine pairs the two and alerts the owner.

This version is **multi-tenant**: every user, item, match, message and
notification carries an `org_id`, and every query is filtered by it. Data still
lives in memory (`mock_data.py`), so the app runs with no database at all.

## Run it

```bash
cd goodfind_app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

| Account | Login | Role |
|---|---|---|
| Member | `demo@vsbec.ac.in` / `demo1234` | reports items, claims matches |
| Front desk | `desk@vsbec.ac.in` / `desk1234` | approves claims, releases items |
| Admin | `admin@vsbec.ac.in` / `admin1234` | organization stats and settings |
| Other organization | `ravi@northgate.example` / `ravi1234` | proves the data is isolated |

Run `python smoke_test.py` to check every route and the tenant boundary.

## What is new compared with the single-tenant version

1. **Organizations.** `ORGANIZATIONS` is the tenant table. People join by email
   domain (`@vsbec.ac.in` → that college) or by a join code the admin shares.
   `/register-organization` lets a new place onboard itself.
2. **Three roles.** `member` reports and claims; `staff` runs the front desk;
   `admin` sees organization-wide stats and edits the collection desk.
3. **Photos on both sides.** The owner uploads a reference photo of what they
   lost; the finder uploads a photo of what they handed in. Both are saved to
   `static/uploads/` and fingerprinted at upload time.
4. **Real matching** (`matching.py`) over seven factors, 100 points in total:

   | Factor | Points | What it compares |
   |---|---|---|
   | Same category | 20 | hard filter — different categories never match |
   | Brand matches | 15 | exact brand |
   | Colour matches | 10 | exact colour |
   | Found soon after the loss | 15 | 0–14 day window, closer scores higher |
   | Same place | 10 | shared location words |
   | Descriptions agree | 10 | shared meaningful words in the two write-ups |
   | Photos look alike | 20 | image fingerprint similarity |

   The owner is then told in plain words: *"This looks like your item. The two
   photos are 61% alike."* with a **Contact the finder** button that opens a
   private thread. Every point is shown, so nothing is a black box.
5. **A real handover flow.** Owner submits an identifying detail → claim goes to
   the front desk → staff approves or rejects → item is released and marked
   returned, which closes the case for both sides.
6. **Isolation checks everywhere.** Matches never cross organizations, a user is
   never matched to their own found item, and opening another organization's
   match URL redirects away.

## Files

```
goodfind_app/
├── app.py                     # routes, auth, roles, org scoping, rate limiting
├── matching.py                # the scoring engine (7 factors, 100 pts)
├── image_ai.py                # photo fingerprints: aHash, dHash, colour histogram
├── seed_photos.py             # regenerates the demo photos
├── supabase_client.py         # Supabase connection & Supabase Storage upload
├── mock_data.py               # Supabase PostgreSQL data layer + fallback
├── seed_supabase.py           # populates Supabase with initial demo data
├── smoke_test.py              # route + tenant-isolation automated test
├── test_supabase_integration.py # integration test suite
├── supabase_schema.sql        # Supabase PostgreSQL schema with RLS
├── requirements.txt           # dependencies (Flask, Pillow, supabase, etc.)
├── templates/                 # base, app shell, and one file per page
└── static/css, static/js
```

## Connecting to Supabase

1. **Create a Supabase Project** at [supabase.com](https://supabase.com).
2. **Run SQL Schema**:
   Copy the contents of `supabase_schema.sql` into the Supabase SQL Editor and execute it.
3. **Configure `.env`**:
   Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-or-service-key
   SUPABASE_STORAGE_BUCKET=item-photos
   ```
4. **Create Storage Bucket**:
   In your Supabase dashboard, create a public bucket named `item-photos` (or the name in `.env`).
5. **Seed Demo Data** (optional):
   ```bash
   python seed_supabase.py
   ```
6. **Run Tests**:
   ```bash
   python smoke_test.py
   python test_supabase_integration.py
   ```

## How the photo analysis works

Two people photographing the same phone never produce identical files, so
`image_ai.py` does not compare pixels. It reduces each photo to a fingerprint:

- **aHash** — shrink to 8×8 grey, mark each pixel brighter or darker than the
  average. Captures overall shape.
- **dHash** — compare each pixel with its right-hand neighbour. Captures edges,
  and survives brightness changes.
- **Colour histogram** — a 4×4×4 RGB histogram, compared by intersection.

The three are blended into one 0–1 score, after removing chance agreement (two
random hashes already agree on about half their bits). On the shipped demo
photos — the same phone at two angles and two brightness levels — this scores
**0.61**, while a phone against a wallet scores **0.33**, below the 0.35 cut-off.

This is a classical computer-vision baseline: fast, no training data, easy to
explain. To upgrade it, replace `compare_fingerprints()` with CNN embeddings
(MobileNet features and cosine similarity, for example). Nothing that calls the
module changes, and the rules stay as the floor, so matching still works if the
model is unavailable.
