"""Az ikonfájlok (assets/rkbully.png és assets/rkbully.ico) újragyártása a forrásképből.

Csak ehhez kell a Pillow (pip install pillow); a programnak és a kész ikonfájloknak nem.
Használat:  python tools/make_icons.py [forraskep.png]
Ha másik logót szeretnél, írd felül az assets/rkbully_forras.png fájlt (négyzet alakú, átlátszó háttérrel a legjobb),
vagy add meg a képet argumentumként, majd futtasd újra.
"""
import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def square(im):
    """Négyzetre egészíti ki a képet (átlátszó szegéllyel), hogy a torzítás nélkül skálázódjon."""
    side = max(im.size)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return out


def main(src):
    im = square(Image.open(src).convert("RGBA"))
    ASSETS.mkdir(exist_ok=True)
    png = im.resize((512, 512), Image.LANCZOS)
    png.save(ASSETS / "rkbully.png", optimize=True)
    big = im.resize((512, 512), Image.LANCZOS)
    big.save(ASSETS / "rkbully.ico", format="ICO", sizes=[(s, s) for s in SIZES])
    print("kész:", ASSETS / "rkbully.png", "és", ASSETS / "rkbully.ico")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ASSETS / "rkbully_forras.png")
