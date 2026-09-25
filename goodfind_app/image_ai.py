"""
GoodFind image analysis.

Two images of the same object, taken by two different people on two different
phones, will never be byte-identical. So we don't compare pixels -- we reduce
each photo to a small "fingerprint" and compare fingerprints.

Three signals, all computed with Pillow only (no heavy ML dependency):

1. aHash  - average hash. Shrink to 8x8 grey, mark each pixel as brighter or
            darker than the image average. Captures overall shape and layout.
2. dHash  - difference hash. Compare each pixel with its right-hand neighbour.
            Captures edges, and survives brightness changes well.
3. Colour - a 4x4x4 RGB histogram. Captures "this is a black object on a pale
            desk" independently of shape.

similarity() blends them into a single 0.0 - 1.0 score. This is a classical
computer-vision baseline, not a neural network: it is fast, needs no training
data, and is easy to explain in a review. Phase 3 can swap compare_fingerprints
for CNN embeddings (for example MobileNet features with cosine similarity)
without changing anything that calls this module.
"""
import json
from PIL import Image, ImageFilter

HASH_SIZE = 8
BINS = 4  # per RGB channel -> 64 histogram buckets


def _open(path):
    img = Image.open(path)
    img = img.convert("RGB")
    # EXIF-rotated phone photos would otherwise compare badly
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def _ahash(grey):
    small = grey.resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS)
    px = list(small.getdata())
    avg = sum(px) / len(px)
    return "".join("1" if p >= avg else "0" for p in px)


def _dhash(grey):
    small = grey.resize((HASH_SIZE + 1, HASH_SIZE), Image.LANCZOS)
    px = list(small.getdata())
    bits = []
    for row in range(HASH_SIZE):
        base = row * (HASH_SIZE + 1)
        for col in range(HASH_SIZE):
            bits.append("1" if px[base + col] > px[base + col + 1] else "0")
    return "".join(bits)


def _histogram(img):
    small = img.resize((64, 64), Image.LANCZOS)
    step = 256 // BINS
    buckets = [0] * (BINS ** 3)
    for r, g, b in small.getdata():
        idx = (r // step) * BINS * BINS + (g // step) * BINS + (b // step)
        buckets[idx] += 1
    total = sum(buckets) or 1
    return [round(c / total, 5) for c in buckets]


def fingerprint(path):
    """Reduce a photo on disk to a small JSON-serialisable fingerprint."""
    img = _open(path)
    grey = img.convert("L").filter(ImageFilter.SHARPEN)
    return {"ahash": _ahash(grey), "dhash": _dhash(grey), "hist": _histogram(img)}


def _hamming_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    same = sum(1 for x, y in zip(a, b) if x == y)
    return same / len(a)


def _hist_similarity(a, b):
    """Histogram intersection: sum of the smaller value in each bucket."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(min(x, y) for x, y in zip(a, b))


def compare_fingerprints(fp_a, fp_b):
    """Blend the three signals into one 0.0 - 1.0 similarity score."""
    if not fp_a or not fp_b:
        return 0.0
    a = _hamming_similarity(fp_a.get("ahash"), fp_b.get("ahash"))
    d = _hamming_similarity(fp_a.get("dhash"), fp_b.get("dhash"))
    h = _hist_similarity(fp_a.get("hist"), fp_b.get("hist"))

    # Chance agreement has to be removed or everything looks similar:
    # two random 64-bit hashes already agree on ~50% of bits, and two photos
    # taken in the same building share a lot of background colour.
    a = max(0.0, (a - 0.55) / 0.45)
    d = max(0.0, (d - 0.55) / 0.45)
    h = max(0.0, (h - 0.45) / 0.55)

    return round(0.35 * a + 0.40 * d + 0.25 * h, 4)


def similarity_from_paths(path_a, path_b):
    """Convenience wrapper for scripts and tests."""
    return compare_fingerprints(fingerprint(path_a), fingerprint(path_b))


def dumps(fp):
    return json.dumps(fp)


def loads(raw):
    return json.loads(raw) if raw else None
