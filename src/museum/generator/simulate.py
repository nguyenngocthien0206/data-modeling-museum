"""Run the simulation.

1. Build the world from its own random streams: geography, stores with their lifecycle,
   catalogue with its price history, promotions with their edits, members, workforce.
2. Write the slowly changing tables (stores, products, promotions, employees) day by day.
3. Generate sales day by day. Each day draws only from streams keyed by that day, so days
   are independent and can run in parallel processes with identical results.
4. Review member tiers monthly from the spend those sales produced, then write the
   customer table (joins, address moves and tier changes) and the truth manifest.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from museum import __version__
from museum.generator.config import Profile
from museum.generator.delivery import DayOutcome, deliver_day
from museum.generator.landing import LandingWriter
from museum.generator.people import (
    Change,
    Members,
    NamePools,
    address_moves,
    build_members,
    customer_extracts,
    month_of_day,
    street_pool,
    tier_changes,
)
from museum.generator.reference import (
    TIERS,
    Promotion,
    Store,
    VersionLog,
    build_geography,
    build_price_history,
    build_products,
    build_promotions,
    build_stores,
    static_extract,
)
from museum.generator.sales import Catalogue, build_day_sales
from museum.generator.seeds import int_seed, stream
from museum.generator.workforce import Workforce, build_day_shifts, build_workforce

MANIFEST_NAME = "truth_manifest.json"


@dataclass
class Summary:
    profile: str
    seed: int
    days: int
    workers: int
    rows: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0


@dataclass
class World:
    profile: Profile
    root: Path
    stores: list[Store]
    catalogue: Catalogue
    promotions: list[Promotion]
    members: Members
    pools: tuple[list[np.ndarray], list[np.ndarray]]
    workforce: Workforce


def landing_root(data_dir: Path, profile: Profile) -> Path:
    return data_dir / profile.name / "landing"


def manifest_path(data_dir: Path, profile: Profile) -> Path:
    return data_dir / profile.name / MANIFEST_NAME


def default_workers(profile: Profile) -> int:
    """One process for tiny runs (spawning costs more than it saves), several otherwise."""
    daily_orders = (profile.stores + profile.new_stores) * profile.orders_per_store_day
    if daily_orders < 100:
        return 1
    return max(1, min(8, (os.cpu_count() or 2) - 1))


def run_day(world: World, day: int) -> DayOutcome:
    profile, seed = world.profile, world.profile.seed
    shifts = build_day_shifts(
        profile, world.stores, world.workforce, day, stream(seed, "shifts", day)
    )
    batch = build_day_sales(
        profile,
        day,
        world.stores,
        world.catalogue,
        world.promotions,
        world.members,
        world.pools,
        shifts,
        stream(seed, "sales", day),
    )
    writer = LandingWriter(world.root)
    return deliver_day(profile, day, batch, shifts, writer, stream(seed, "delivery", day))


_WORLD: World | None = None


def _init_worker(world: World) -> None:
    global _WORLD
    _WORLD = world


def _run_day_in_worker(day: int) -> DayOutcome:
    assert _WORLD is not None
    return run_day(_WORLD, day)


def generate(profile: Profile, data_dir: Path, workers: int | None = None) -> Summary:
    started = time.perf_counter()
    seed = profile.seed
    root = landing_root(data_dir, profile)
    writer = LandingWriter(root)
    writer.reset()

    log = VersionLog()
    geo = build_geography()
    pools = NamePools.from_faker()
    streets = street_pool(int_seed(seed, "streets"))
    stores = build_stores(profile, geo, streets, log, stream(seed, "stores"))
    products = build_products()
    prices = build_price_history(profile, products, log, stream(seed, "prices"))
    promotions = build_promotions(profile, log, stream(seed, "promotions"))
    members = build_members(profile, stores, geo, pools, streets, stream(seed, "members"))
    workforce = build_workforce(profile, stores, pools, stream(seed, "workforce"))
    world = World(
        profile=profile,
        root=root,
        stores=stores,
        catalogue=Catalogue.build(products, prices),
        promotions=promotions,
        members=members,
        pools=members.pools(len(stores)),
        workforce=workforce,
    )

    for table_name, columns in static_extract(geo).items():
        writer.write(table_name, profile.start, columns)
    for d in range(profile.n_days):
        for table_name, columns in log.tables_on(d).items():
            writer.write(table_name, profile.day(d), columns)
        if d in workforce.rows_by_day:
            rows = workforce.rows_by_day[d]
            writer.write("employee", profile.day(d), {k: [r[k] for r in rows] for k in rows[0]})

    workers = workers or default_workers(profile)
    days = range(profile.n_days)
    if workers == 1:
        outcomes = [run_day(world, d) for d in days]
    else:
        with ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(world,)) as pool:
            outcomes = list(pool.map(_run_day_in_worker, days, chunksize=8))

    months = month_of_day(profile, profile.n_days - 1) + 1
    spend = np.zeros((months, len(members)), dtype=np.int64)
    for outcome in outcomes:
        spend[month_of_day(profile, outcome.day), outcome.spend_members] += outcome.spend_amounts
    tiers = tier_changes(profile, members, spend)
    moves = address_moves(profile, members, geo, streets, stream(seed, "moves"))
    for d, columns in customer_extracts(profile, members, tiers + moves):
        writer.write("customer", profile.day(d), columns)

    rows = dict(writer.rows)
    for outcome in outcomes:
        for table_name, count in outcome.rows.items():
            rows[table_name] = rows.get(table_name, 0) + count
    rows = dict(sorted(rows.items()))

    manifest = _manifest(profile, outcomes, tiers, moves, log, products, promotions, rows)
    manifest_path(data_dir, profile).write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    return Summary(
        profile=profile.name,
        seed=seed,
        days=profile.n_days,
        workers=workers,
        rows=rows,
        seconds=round(time.perf_counter() - started, 1),
    )


def _tier_moves(tiers: list[Change]) -> tuple[int, int]:
    rank = {t[0]: t[2] for t in TIERS}
    current: dict[int, int] = {}
    up = down = 0
    for change in sorted(tiers, key=lambda c: (c.day, c.member)):
        new = rank[change.tier_code]
        old = current.get(change.member, 1)
        up, down = up + (new > old), down + (new < old)
        current[change.member] = new
    return up, down


def _manifest(profile, outcomes, tiers, moves, log, products, promotions, rows) -> dict:
    """Facts the simulation knows about its own final state, used to check the oracles."""
    up, down = _tier_moves(tiers)
    by_day = {profile.day(o.day).isoformat(): o for o in outcomes if o.landed_orders}
    return {
        "profile": profile.name,
        "seed": profile.seed,
        "generator_version": __version__,
        "period": {
            "start": profile.start.isoformat(),
            "end": profile.end.isoformat(),
            "days": profile.n_days,
        },
        "orders": {
            "landed": sum(o.landed_orders for o in outcomes),
            "completed": sum(o.completed_orders for o in outcomes),
            "voided": sum(o.voided_orders for o in outcomes),
            "late": sum(o.late_orders for o in outcomes),
            "corrected": sum(o.corrected_orders for o in outcomes),
        },
        "net_revenue": {
            "total": sum(o.net_revenue for o in outcomes),
            "by_order_date": {day: o.net_revenue for day, o in by_day.items()},
        },
        "completed_orders_by_order_date": {day: o.completed_orders for day, o in by_day.items()},
        "history": {
            "tier_upgrades": up,
            "tier_downgrades": down,
            "address_moves": len(moves),
            "price_changes": len(log.versions("product")) - len(products),
            "promotion_edits": len(log.versions("promotion")) - len(promotions),
            "store_openings": profile.new_stores,
            "store_closings": profile.closed_stores,
        },
        "rows": rows,
    }
