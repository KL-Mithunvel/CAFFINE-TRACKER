"""One-off dev utility: seed fake entries across the project's history so the
dashboard/stats code can be exercised with a realistic-looking dataset.

Does NOT touch existing rows — only appends new entries dated from the
project's first commit (2026-07-10) through today. Uses app.models.add_entry
so every dose is computed the normal way (volume_ml * caffeine_per_100ml / 100).

Run once, from the venv:
    .venv\\Scripts\\python scripts\\seed_fake_data.py
"""
import random
from datetime import date, timedelta

from app import db, models

START_DATE = date(2026, 7, 10)   # project start (git log)
END_DATE = date(2026, 8, 21)     # today
DOUBLE_START = date(2026, 8, 8)
DOUBLE_END = date(2026, 8, 18)

HIGH_DAY_PROBABILITY = 0.9  # 90% of days run higher than a normal day

REGULAR_MG_RANGE = (150, 300)     # a "normal" moderate day, under the 400mg limit
HIGH_MULTIPLIER_RANGE = (1.3, 1.8)   # higher-than-normal days
DOUBLE_MULTIPLIER_RANGE = (2.0, 2.3) # Aug 8-18: ~twice the regular amount

LIGHT_DRINKS = {"Black Tea", "Green Tea", "Coca-Cola"}
MEDIUM_DRINKS = {"Brewed Coffee", "Pepsi"}
STRONG_DRINKS = {"Espresso", "Red Bull", "Monster"}

rng = random.Random(20260810)


def day_target_mg(day: date) -> tuple[float, str]:
    baseline = rng.uniform(*REGULAR_MG_RANGE)
    if DOUBLE_START <= day <= DOUBLE_END:
        return baseline * rng.uniform(*DOUBLE_MULTIPLIER_RANGE), "double"
    if rng.random() < HIGH_DAY_PROBABILITY:
        return baseline * rng.uniform(*HIGH_MULTIPLIER_RANGE), "high"
    return baseline, "regular"


def pick_pool(day_kind: str, drinks_by_name: dict) -> list:
    if day_kind == "double":
        names = STRONG_DRINKS | MEDIUM_DRINKS
    elif day_kind == "high":
        names = MEDIUM_DRINKS | STRONG_DRINKS
    else:
        names = LIGHT_DRINKS | MEDIUM_DRINKS
    return [drinks_by_name[n] for n in names if n in drinks_by_name]


def entry_count_for(day_kind: str) -> int:
    if day_kind == "double":
        return rng.randint(3, 5)
    if day_kind == "high":
        return rng.randint(2, 3)
    return rng.randint(1, 2)


def random_times(n: int, day: date) -> list[str]:
    slots = list(range(7 * 60, 22 * 60 + 30, 15))  # 07:00 - 22:30, 15-min steps
    chosen = sorted(rng.sample(slots, k=min(n, len(slots))))
    times = []
    for minutes in chosen:
        h, m = divmod(minutes, 60)
        times.append(f"{day.isoformat()} {h:02d}:{m:02d}:00")
    return times


def main() -> None:
    conn = db.get_connection()
    db.init_db()

    drinks = models.list_drinks(conn, presets_only=True)
    drinks_by_name = {d["name"]: d for d in drinks}

    total_entries = 0
    day = START_DATE
    while day <= END_DATE:
        target_mg, day_kind = day_target_mg(day)
        pool = pick_pool(day_kind, drinks_by_name)
        n = entry_count_for(day_kind)
        times = random_times(n, day)

        weights = [rng.uniform(0.6, 1.4) for _ in range(len(times))]
        total_w = sum(weights)

        for consumed_at, w in zip(times, weights):
            drink = rng.choice(pool)
            share_mg = target_mg * w / total_w
            conc = drink["caffeine_per_100ml"]
            volume_ml = round(share_mg * 100 / conc / 5) * 5
            volume_ml = max(volume_ml, 15)
            models.add_entry(conn, drink["id"], volume_ml, consumed_at=consumed_at)
            total_entries += 1

        day += timedelta(days=1)

    print(f"Inserted {total_entries} fake entries from {START_DATE} to {END_DATE}.")


if __name__ == "__main__":
    main()
