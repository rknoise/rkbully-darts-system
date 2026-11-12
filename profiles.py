"""Játékosprofilok: név, profilkép (feltöltött JPG/PNG), szín. A beállításfájlban tárolva, a felülettől független.

A profilképet a program egy kis (256×256, négyzetre vágott) JPG-vé alakítja a `~/.rkbully/avatars` mappában, így a
nagy fényképek sem lassítják a felületet, és az eredeti fájl törlése nem rontja el a profilt.
"""
import uuid
from pathlib import Path

AVATAR_DIR = Path.home() / ".rkbully" / "avatars"
AVATAR_PX = 256
COLORS = ["#ff8a1f", "#3a9bff", "#38e07b", "#e05aff", "#ffd23f", "#ff5a7a", "#2fe0d0", "#9a7bff"]
MAX_PLAYERS = 8


def new_id():
    return uuid.uuid4().hex[:8]


def make_profile(name, used_colors=()):
    """Új profil: az első még nem használt színnel."""
    free = [c for c in COLORS if c not in used_colors]
    return {"id": new_id(), "name": name.strip(), "avatar": None, "color": (free or COLORS)[0]}


def clean(profile):
    """Hibás/hiányos bejegyzésből használható profil (a beállításfájl kézzel is szerkeszthető)."""
    name = str(profile.get("name", "")).strip()
    if not name:
        return None
    color = profile.get("color")
    out = {"id": str(profile.get("id") or new_id()), "name": name,
           "avatar": profile.get("avatar") or None, "color": color if color in COLORS else COLORS[0]}
    since = profile.get("stats_from")                   # a statisztika nullázásának ideje: ennél régebbi játékok nem számítanak
    if isinstance(since, (int, float)) and not isinstance(since, bool) and since > 0:
        out["stats_from"] = float(since)
    return out


def load(cfg):
    """(profilok, játékosok azonosítói) a beállításokból. A régi, csak neveket tároló fájlból profilokat készít."""
    profiles, seen = [], set()
    for raw in cfg.get("profiles") or []:
        pr = clean(raw) if isinstance(raw, dict) else None
        if pr and pr["id"] not in seen:
            seen.add(pr["id"])
            profiles.append(pr)
    by_id = {p["id"]: p for p in profiles}
    if profiles:
        players = [pid for pid in (cfg.get("players") or []) if pid in by_id][:MAX_PLAYERS]
        if not players:
            players = [p["id"] for p in profiles[:2]]
        return profiles, players
    names = [str(n).strip() for n in (cfg.get("names") or ["Játékos 1", "Játékos 2"]) if str(n).strip()][:MAX_PLAYERS]
    for name in names or ["Játékos 1", "Játékos 2"]:
        profiles.append(make_profile(name, [p["color"] for p in profiles]))
    return profiles, [p["id"] for p in profiles]


def dump(profiles, players):
    return {"profiles": profiles, "players": players}


def name_taken(profiles, name, except_id=None):
    n = name.strip().casefold()
    return any(p["name"].casefold() == n for p in profiles if p["id"] != except_id)


def unique_name(profiles, base):
    """"Játékos 3" típusú, még nem használt név."""
    k = len(profiles) + 1
    while name_taken(profiles, f"{base} {k}"):
        k += 1
    return f"{base} {k}"


def avatar_path(profile, folder=None):
    """A profilkép fájlja, ha van és létezik."""
    if not profile or not profile.get("avatar"):
        return None
    path = Path(folder or AVATAR_DIR) / profile["avatar"]
    return path if path.is_file() else None


def import_avatar(src, pid, folder=None):
    """Egy képfájlból (JPG/PNG/…) kis, négyzetes JPG profilkép. Visszaadja a fájlnevet; ValueError, ha nem kép."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    img = QImage(str(src))
    if img.isNull():
        raise ValueError("A fájl nem olvasható képként.")
    side = min(img.width(), img.height())
    img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
    img = img.scaled(AVATAR_PX, AVATAR_PX, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
    folder = Path(folder or AVATAR_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{pid}_{uuid.uuid4().hex[:4]}.jpg"            # új név: a régi kép gyorsítótára nem ragad be
    if not img.save(str(folder / name), "JPG", 90):
        raise ValueError("A profilkép mentése nem sikerült.")
    return name


def delete_avatar(profile, folder=None):
    path = avatar_path(profile, folder)
    if path:
        try:
            path.unlink()
        except OSError:
            pass
    profile["avatar"] = None
