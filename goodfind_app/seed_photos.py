"""
Generate the demo photos shipped with the seed data.

These stand in for two people photographing the same object: same phone, but
different angle, crop and lighting -- exactly the case image_ai.py has to
handle. Re-run with `python seed_photos.py` if you delete them.
"""
import os
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

OUT = os.path.join("static", "uploads", "seed")
os.makedirs(OUT, exist_ok=True)


def phone(desk=(206, 200, 188), body=(28, 30, 33), screen=(58, 62, 70)):
    img = Image.new("RGB", (480, 480), desk)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([150, 90, 330, 400], radius=26, fill=body)
    d.rounded_rectangle([162, 108, 318, 382], radius=18, fill=screen)
    d.rounded_rectangle([196, 118, 284, 130], radius=6, fill=(20, 22, 24))
    d.ellipse([170, 124, 186, 140], fill=(46, 48, 52))       # camera bump
    return img


def wallet():
    img = Image.new("RGB", (480, 480), (222, 218, 205))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([110, 160, 370, 330], radius=12, fill=(104, 66, 38))
    d.line([110, 245, 370, 245], fill=(78, 48, 26), width=4)
    d.rounded_rectangle([150, 180, 250, 235], radius=4, fill=(198, 190, 172))
    return img


def variant(img, angle, brightness, crop):
    out = img.rotate(angle, resample=Image.BICUBIC, fillcolor=(200, 196, 184))
    out = ImageEnhance.Brightness(out).enhance(brightness)
    w, h = out.size
    out = out.crop((crop, crop, w - crop, h - crop)).resize((480, 480))
    return out.filter(ImageFilter.GaussianBlur(0.4))


base_phone = phone()
# The owner's old reference photo: straight on, bright.
variant(base_phone, 0, 1.06, 10).save(os.path.join(OUT, "phone_owner.png"))
# The finder's photo at the desk: tilted, dimmer, cropped closer.
variant(base_phone, -7, 0.88, 34).save(os.path.join(OUT, "phone_finder.png"))
# A different object, to prove the scorer doesn't pair everything.
wallet().save(os.path.join(OUT, "wallet_finder.png"))

print("Wrote demo photos to", OUT)
