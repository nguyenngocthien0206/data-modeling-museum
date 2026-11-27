"""Run the simulation: build the world once, then write one extract per day.

The world (geography, stores, catalogue, promotions, members, workforce) is built first
from its own random streams. Each day then draws only from streams keyed by that day,
so a day's data does not depend on how many random numbers earlier days used.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from museum.generator.config import Profile
from museum.generator.landing import LandingWriter
from museum.generator.people import NamePools, build_members, street_pool
from museum.generator.reference import (
    build_geography,
    build_products,
    build_promotions,
    build_stores,
    initial_extract,
    promotion_columns,
)
from museum.generator.sales import Catalogue, build_day_sales
from museum.generator.seeds import int_seed, stream
from museum.generator.workforce import build_day_shifts, build_workforce


@dataclass
class Summary:
    profile: str
    seed: int
    days: int
    rows: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0


def landing_root(data_dir: Path, profile: Profile) -> Path:
    return data_dir / profile.name / "landing"


def _by_landing_day(values: np.ndarray) -> dict[int, np.ndarray]:
    order = np.argsort(values, kind="stable")
    days, starts = np.unique(values[order], return_index=True)
    return dict(zip(days.tolist(), np.split(order, starts[1:]), strict=True))


def generate(profile: Profile, data_dir: Path) -> Summary:
    started = time.perf_counter()
    seed = profile.seed
    writer = LandingWriter(landing_root(data_dir, profile))
    writer.reset()

    geo = build_geography()
    pools = NamePools.from_faker()
    streets = street_pool(int_seed(seed, "streets"))
    stores = build_stores(profile, geo, streets, stream(seed, "stores"))
    products = build_products()
    catalogue = Catalogue.from_products(products)
    promotions = build_promotions(profile, stream(seed, "promotions"))
    members = build_members(profile, stores, geo, pools, streets, stream(seed, "members"))
    workforce = build_workforce(profile, stores, pools, stream(seed, "workforce"))

    member_columns = {k: np.asarray(v, dtype=object) for k, v in members.columns.items()}
    members_landing = _by_landing_day(members.landing_day())
    members_by_store = [np.flatnonzero(members.home_store == s.index) for s in stores]
    promo_landing = _by_landing_day(
        np.array([max(0, (p.created_at.date() - profile.start).days) for p in promotions])
    )
    promo_columns = {
        k: np.asarray(v, dtype=object) for k, v in promotion_columns(promotions).items()
    }
    pending_shift_fixes: dict[int, list[dict]] = {}

    for d in range(profile.n_days):
        today = profile.day(d)
        if d == 0:
            for table_name, columns in initial_extract(geo, products, stores).items():
                writer.write(table_name, today, columns)
        if d in members_landing:
            idx = members_landing[d]
            writer.write("customer", today, {k: v[idx] for k, v in member_columns.items()})
        if d in promo_landing:
            idx = promo_landing[d]
            writer.write("promotion", today, {k: v[idx] for k, v in promo_columns.items()})
        if d in workforce.rows_by_day:
            writer.write("employee", today, _rows_to_columns(workforce.rows_by_day[d]))

        shifts = build_day_shifts(profile, stores, workforce, d, stream(seed, "shifts", d))
        for landing_day, row in shifts.corrections:
            pending_shift_fixes.setdefault(landing_day, []).append(row)
        shift_columns = shifts.columns
        if d in pending_shift_fixes:
            fixes = _rows_to_columns(pending_shift_fixes.pop(d))
            shift_columns = {k: list(v) + fixes[k] for k, v in shift_columns.items()}
        writer.write("shift", today, shift_columns)

        sales = build_day_sales(
            profile,
            d,
            stores,
            catalogue,
            promotions,
            members,
            members_by_store,
            shifts,
            stream(seed, "sales", d),
        )
        for table_name, columns in sales.items():
            writer.write(table_name, today, columns)

    return Summary(
        profile=profile.name,
        seed=seed,
        days=profile.n_days,
        rows=dict(sorted(writer.rows.items())),
        seconds=round(time.perf_counter() - started, 1),
    )


def _rows_to_columns(rows: list[dict]) -> dict[str, list]:
    return {key: [row[key] for row in rows] for key in rows[0]}
