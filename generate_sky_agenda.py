#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AstroCarnet DWARF - générateur gratuit de sky_agenda.json

Objectif : générer un agenda simple J+7, sans clé API et sans service payant.
L'app n'affiche pas les calculs techniques. Elle affiche seulement :
- Lune visible à partir de...
- Vénus visible à partir de...
- Pluie de météores : pic...
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from skyfield.api import Loader, wgs84
from skyfield import almanac
from zoneinfo import ZoneInfo


# ─────────────────────────────────────────────────────────────────────────────
# Configuration simple
# ─────────────────────────────────────────────────────────────────────────────

LOCATION_NAME = os.environ.get("ASTROCARNET_LOCATION_NAME", "Saint-Germain / Troyes")
LATITUDE = float(os.environ.get("ASTROCARNET_LATITUDE", "48.2564"))
LONGITUDE = float(os.environ.get("ASTROCARNET_LONGITUDE", "4.0296"))
TIMEZONE_NAME = os.environ.get("ASTROCARNET_TIMEZONE", "Europe/Paris")

DAYS_TO_GENERATE = int(os.environ.get("ASTROCARNET_DAYS", "7"))

# Planètes visibles à l'œil nu. Uranus/Neptune volontairement ignorées pour garder l'agenda simple.
PLANETS = [
    ("Mercure", ("mercury", "mercury barycenter")),
    ("Vénus", ("venus", "venus barycenter")),
    ("Mars", ("mars", "mars barycenter")),
    ("Jupiter", ("jupiter barycenter", "jupiter")),
    ("Saturne", ("saturn barycenter", "saturn")),
]

# Règles volontairement simples. Ces seuils servent seulement à décider "visible à partir de".
PLANET_MIN_ALTITUDE_DEG = float(os.environ.get("ASTROCARNET_PLANET_ALTITUDE_MIN", "5"))
SUN_MAX_ALTITUDE_FOR_PLANETS_DEG = float(os.environ.get("ASTROCARNET_SUN_ALTITUDE_MAX", "-4"))
MOON_MIN_ALTITUDE_DEG = float(os.environ.get("ASTROCARNET_MOON_ALTITUDE_MIN", "0"))

STEP_MINUTES = int(os.environ.get("ASTROCARNET_STEP_MINUTES", "5"))
OUTPUT_PATH = Path(os.environ.get("ASTROCARNET_OUTPUT", "sky_agenda.json"))


@dataclass(frozen=True)
class MeteorShower:
    name: str
    peak_month: int
    peak_day: int


# Pics approximatifs récurrents, suffisants pour un agenda simple.
# Les dates peuvent varier légèrement selon les années.
METEOR_SHOWERS = [
    MeteorShower("Quadrantides", 1, 3),
    MeteorShower("Lyrides", 4, 22),
    MeteorShower("Êta Aquarides", 5, 6),
    MeteorShower("Delta Aquarides", 7, 30),
    MeteorShower("Perséides", 8, 12),
    MeteorShower("Orionides", 10, 21),
    MeteorShower("Léonides", 11, 17),
    MeteorShower("Géminides", 12, 14),
    MeteorShower("Ursides", 12, 22),
]

WEEKDAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
    "septembre", "octobre", "novembre", "décembre",
]


def day_label(day: date) -> str:
    return f"{WEEKDAYS_FR[day.weekday()]} {day.day} {MONTHS_FR[day.month - 1]}"


def format_hhmm(dt: datetime) -> str:
    if dt.hour == 0 and dt.minute == 0:
        return "début de nuit"
    return f"{dt.hour:02d}:{dt.minute:02d}"


def visible_sort_key(value: str) -> int:
    if not value:
        return 9999
    if "début" in value.lower():
        return 0
    try:
        hour, minute = value.split(":")
        return int(hour) * 60 + int(minute)
    except Exception:
        return 9998


def get_body(eph, possible_names: Iterable[str]):
    last_error: Optional[Exception] = None
    for name in possible_names:
        try:
            return eph[name]
        except Exception as exc:  # pragma: no cover
            last_error = exc
    raise RuntimeError(f"Corps introuvable dans l'éphéméride : {tuple(possible_names)}") from last_error


def local_datetimes_for_day(day: date, tz: ZoneInfo) -> list[datetime]:
    start = datetime.combine(day, time(0, 0), tzinfo=tz)
    return [start + timedelta(minutes=m) for m in range(0, 24 * 60, STEP_MINUTES)]


def find_visible_windows(*, eph, ts, observer, target, sun, day: date, tz: ZoneInfo, target_type: str) -> list[tuple[datetime, datetime]]:
    local_times = local_datetimes_for_day(day, tz)
    utc_times = [dt.astimezone(timezone.utc) for dt in local_times]
    t = ts.from_datetimes(utc_times)

    target_alt = observer.at(t).observe(target).apparent().altaz()[0].degrees

    if target_type == "moon":
        visible_flags = [alt >= MOON_MIN_ALTITUDE_DEG for alt in target_alt]
    else:
        sun_alt = observer.at(t).observe(sun).apparent().altaz()[0].degrees
        visible_flags = [
            obj_alt >= PLANET_MIN_ALTITUDE_DEG and sol_alt <= SUN_MAX_ALTITUDE_FOR_PLANETS_DEG
            for obj_alt, sol_alt in zip(target_alt, sun_alt)
        ]

    windows: list[tuple[datetime, datetime]] = []
    in_window = False
    start_time: Optional[datetime] = None

    for idx, is_visible in enumerate(visible_flags):
        if is_visible and not in_window:
            in_window = True
            start_time = local_times[idx]
        if in_window and (not is_visible or idx == len(visible_flags) - 1):
            end_time = local_times[idx]
            if start_time is not None:
                windows.append((start_time, end_time))
            in_window = False
            start_time = None

    return [
        (start, end)
        for start, end in windows
        if (end - start) >= timedelta(minutes=max(10, STEP_MINUTES))
    ]


def first_visible_from(windows: list[tuple[datetime, datetime]]) -> Optional[str]:
    if not windows:
        return None
    first_start = windows[0][0]
    if first_start.hour == 0 and first_start.minute == 0:
        return "début de nuit"
    return format_hhmm(first_start)


def moon_phase_label(eph, ts, day: date, tz: ZoneInfo) -> str:
    noon_local = datetime.combine(day, time(12, 0), tzinfo=tz)
    t = ts.from_datetime(noon_local.astimezone(timezone.utc))
    phase_deg = float(almanac.moon_phase(eph, t).degrees) % 360

    if phase_deg < 22 or phase_deg >= 338:
        return "Nouvelle Lune"
    if phase_deg < 67:
        return "Croissant lunaire"
    if phase_deg < 112:
        return "Premier quartier"
    if phase_deg < 157:
        return "Lune gibbeuse croissante"
    if phase_deg < 202:
        return "Pleine Lune"
    if phase_deg < 247:
        return "Lune gibbeuse décroissante"
    if phase_deg < 292:
        return "Dernier quartier"
    return "Dernier croissant"


def meteor_items_for_day(day: date, today: date) -> list[dict]:
    items: list[dict] = []
    for shower in METEOR_SHOWERS:
        peak = date(day.year, shower.peak_month, shower.peak_day)
        if shower.peak_month == 1 and today.month == 12:
            peak = date(today.year + 1, shower.peak_month, shower.peak_day)

        delta_from_day = (peak - day).days
        delta_from_today = (peak - today).days

        if delta_from_day == 0:
            items.append({"type": "meteor", "title": shower.name, "note": "Pic cette nuit."})
        elif day == today and 1 <= delta_from_today <= 7:
            note = "Pic demain." if delta_from_today == 1 else f"Pic dans {delta_from_today} jours."
            items.append({"type": "meteor", "title": shower.name, "note": note})
    return items


def build_agenda() -> dict:
    tz = ZoneInfo(TIMEZONE_NAME)

    loader = Loader(os.path.expanduser("~/.skyfield"))
    ts = loader.timescale()
    eph = loader("de421.bsp")

    earth = eph["earth"]
    sun = eph["sun"]
    moon = eph["moon"]
    observer = earth + wgs84.latlon(LATITUDE, LONGITUDE)

    now = datetime.now(tz)
    today = now.date()
    days: list[dict] = []

    for offset in range(DAYS_TO_GENERATE):
        day = today + timedelta(days=offset)
        items: list[dict] = []

        phase_label = moon_phase_label(eph, ts, day, tz)
        moon_windows = find_visible_windows(
            eph=eph, ts=ts, observer=observer, target=moon, sun=sun, day=day, tz=tz, target_type="moon"
        )
        moon_from = first_visible_from(moon_windows)
        if moon_from:
            items.append({"type": "moon", "title": phase_label, "visible_from": moon_from})
        elif phase_label == "Nouvelle Lune":
            items.append({"type": "moon", "title": phase_label, "note": "Lune très fine ou quasiment invisible."})

        planet_items: list[dict] = []
        for title, possible_names in PLANETS:
            target = get_body(eph, possible_names)
            windows = find_visible_windows(
                eph=eph, ts=ts, observer=observer, target=target, sun=sun, day=day, tz=tz, target_type="planet"
            )
            visible_from = first_visible_from(windows)
            if visible_from:
                planet_items.append({"type": "planet", "title": title, "visible_from": visible_from})

        planet_items.sort(key=lambda item: visible_sort_key(item.get("visible_from", "")))
        items.extend(planet_items)
        items.extend(meteor_items_for_day(day, today))

        days.append({
            "date": day.isoformat(),
            "label": day_label(day),
            "source": "AstroCarnet Auto · Skyfield",
            "items": items,
        })

    return {
        "updatedAt": now.isoformat(timespec="seconds"),
        "location": LOCATION_NAME,
        "source": "AstroCarnet Auto · Skyfield",
        "days": days,
    }


def main() -> None:
    agenda = build_agenda()
    OUTPUT_PATH.write_text(json.dumps(agenda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Agenda généré : {OUTPUT_PATH.resolve()}")
    print(f"Jours : {len(agenda['days'])}")
    print(f"Lieu : {agenda['location']}")


if __name__ == "__main__":
    main()
