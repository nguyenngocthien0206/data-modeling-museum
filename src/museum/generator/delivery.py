"""How one day's sales reach the landing: on time, late, and corrected later.

- Late: a store whose POS was offline syncs the whole day 1 to 3 days later. The rows keep
  `created_at` (the sale) and get `updated_at` = the sync time, so a watermark extract on
  `updated_at` picks them up on the sync day.
- Corrected: a share of orders change in a later extract: voided, a line quantity or unit
  price fixed, or a discount adjusted. Discounts stay capped at the order's gross.
- Nothing is ever hard-deleted (design section 4.4).

Each day worker buffers every row per (table, landing day) and writes each buffer once,
as `part-dNNNN.parquet` where NNNN is the day of the sales, so workers never collide.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pyarrow as pa

from museum.generator.config import Profile
from museum.generator.landing import LandingWriter
from museum.generator.sales import SalesBatch, capped_discounts
from museum.generator.workforce import DayShifts

LATE_LAG_DAYS = (1, 3)
SYNC_SECONDS = (7 * 3600, 10 * 3600)
CORRECTION_LAG_DAYS = (1, 10)
CORRECTION_KINDS = ("void", "quantity", "unit_price", "discount")
CORRECTION_WEIGHTS = (0.3, 0.4, 0.15, 0.15)
PRICE_FIXES = np.array([-2_000, -1_000, 1_000, 2_000])
DISCOUNT_FIXES = np.array([-2_000, -1_000, 1_000, 2_000])


@dataclass
class DayOutcome:
    day: int
    rows: dict[str, int] = field(default_factory=dict)
    spend_members: np.ndarray = field(default_factory=lambda: np.empty(0, np.int64))
    spend_amounts: np.ndarray = field(default_factory=lambda: np.empty(0, np.int64))
    landed_orders: int = 0
    completed_orders: int = 0
    voided_orders: int = 0
    late_orders: int = 0
    corrected_orders: int = 0
    net_revenue: int = 0


class Buffer:
    def __init__(self) -> None:
        self.parts: dict[tuple[str, int], list[dict]] = defaultdict(list)

    def add(self, table_name: str, landing_day: int, columns: dict) -> None:
        self.parts[(table_name, landing_day)].append(columns)

    def flush(self, profile: Profile, writer: LandingWriter, origin_day: int) -> None:
        for (table_name, landing_day), chunks in sorted(self.parts.items()):
            merged = {k: _concat([c[k] for c in chunks]) for k in chunks[0]}
            writer.write(table_name, profile.day(landing_day), merged, part=f"d{origin_day:04d}")


def _concat(values: list):
    if isinstance(values[0], pa.Array):
        return pa.concat_arrays(values)
    if isinstance(values[0], np.ndarray):
        return np.concatenate(values)
    return [v for chunk in values for v in chunk]


def _nullable(values: np.ndarray) -> pa.Array:
    """Guest orders carry -1 internally and a null customer_id in the source."""
    return pa.array(values, type=pa.int64(), mask=values < 0)


def _orders(b: SalesBatch, idx: np.ndarray, status: np.ndarray, updated: np.ndarray) -> dict:
    return {
        "order_id": b.order_id[idx],
        "store_id": b.store_id[idx],
        "customer_id": _nullable(b.customer_id[idx]),
        "cashier_employee_id": b.cashier[idx],
        "channel_code": b.channel[idx],
        "ordered_at": b.ordered_at[idx],
        "status": status,
        "created_at": b.ordered_at[idx],
        "updated_at": updated,
    }


def _lines(b: SalesBatch, idx, quantity, unit_price, updated) -> dict:
    order = b.line_order[idx]
    return {
        "order_id": b.order_id[order],
        "line_no": b.line_no[idx].astype(np.int32),
        "product_id": b.product_id[idx],
        "quantity": quantity.astype(np.int32),
        "unit_price": unit_price,
        "line_amount": quantity * unit_price,
        "created_at": b.ordered_at[order],
        "updated_at": updated,
    }


def _promos(b: SalesBatch, idx, discount, updated) -> dict:
    order = b.promo_order[idx]
    return {
        "order_id": b.order_id[order],
        "promotion_id": b.promotion_id[idx],
        "discount_amount": discount,
        "created_at": b.ordered_at[order],
        "updated_at": updated,
    }


def _stamp(profile: Profile, day: int, seconds) -> np.ndarray:
    midnight = np.datetime64(profile.day(day), "us")
    return midnight + (np.asarray(seconds, dtype=np.int64) * 1_000_000).astype("timedelta64[us]")


def _segments(positions: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Start and end of each order's rows, for rows sorted by order position."""
    starts = np.searchsorted(positions, np.arange(n), side="left")
    ends = np.searchsorted(positions, np.arange(n), side="right")
    return starts, ends


def deliver_day(
    profile: Profile,
    day: int,
    batch: SalesBatch,
    shifts: DayShifts,
    writer: LandingWriter,
    rng: np.random.Generator,
) -> DayOutcome:
    buffer = Buffer()
    outcome = DayOutcome(day=day)
    n = len(batch)

    # Shifts land on time; their corrections were planned when the shifts were built.
    buffer.add("shift", day, shifts.columns)
    for landing_day, row in shifts.corrections:
        buffer.add("shift", landing_day, {k: [v] for k, v in row.items()})

    if n:
        _deliver_sales(profile, day, batch, buffer, outcome, rng)
    buffer.flush(profile, writer, day)
    outcome.rows = dict(writer.rows)
    return outcome


def _deliver_sales(profile, day, batch, buffer, outcome, rng) -> None:
    n = len(batch)
    # Offline store-days: every order of that store and day syncs later.
    stores_today = np.unique(batch.store_index)
    offline = rng.random(len(stores_today)) < profile.late_store_day_share
    lag_of_store = np.zeros(int(batch.store_index.max()) + 1, dtype=np.int64)
    lag_of_store[stores_today[offline]] = rng.integers(
        *LATE_LAG_DAYS, size=int(offline.sum()), endpoint=True
    )
    lag = lag_of_store[batch.store_index]
    landing = day + lag
    sync = rng.integers(*SYNC_SECONDS, size=n)
    first_updated = batch.ordered_at.copy()
    for late_day in np.unique(landing[lag > 0]):
        hit = landing == late_day
        first_updated[hit] = _stamp(profile, int(late_day), sync[hit])
    line_landing, promo_landing = landing[batch.line_order], landing[batch.promo_order]

    line_start, line_end = _segments(batch.line_order, n)
    promo_start, promo_end = _segments(batch.promo_order, n)
    status = np.full(n, "completed", dtype=object)
    quantity, unit_price, discount = (
        batch.quantity.copy(),
        batch.unit_price.copy(),
        batch.discount.copy(),
    )

    # Spend at the till, for the monthly tier review (the source computes tiers from its own sales).
    gross0 = np.bincount(batch.line_order, weights=quantity * unit_price, minlength=n)
    disc0 = np.bincount(batch.promo_order, weights=discount, minlength=n)
    members = batch.member_index >= 0
    if members.any():
        ids, inverse = np.unique(batch.member_index[members], return_inverse=True)
        outcome.spend_members = ids
        outcome.spend_amounts = np.bincount(inverse, weights=(gross0 - disc0)[members]).astype(
            np.int64
        )

    landed = landing < profile.n_days
    for landing_day in np.unique(landing[landed]).tolist():
        orders = np.flatnonzero(landing == landing_day)
        lines = np.flatnonzero(line_landing == landing_day)
        promos = np.flatnonzero(promo_landing == landing_day)
        line_updated = first_updated[batch.line_order[lines]]
        promo_updated = first_updated[batch.promo_order[promos]]
        buffer.add(
            "sales_order",
            landing_day,
            _orders(batch, orders, status[orders], first_updated[orders]),
        )
        buffer.add(
            "order_line",
            landing_day,
            _lines(batch, lines, quantity[lines], unit_price[lines], line_updated),
        )
        buffer.add(
            "order_promotion",
            landing_day,
            _promos(batch, promos, discount[promos], promo_updated),
        )

    # Corrections, applied to the final state and landed after the original version.
    fixed_day = landing + rng.integers(*CORRECTION_LAG_DAYS, size=n, endpoint=True)
    chosen = np.flatnonzero(
        landed & (rng.random(n) < profile.correction_share) & (fixed_day < profile.n_days)
    )
    kinds = rng.choice(len(CORRECTION_KINDS), size=len(chosen), p=CORRECTION_WEIGHTS)
    fixed_second = rng.integers(8 * 3600, 20 * 3600, size=len(chosen))
    touched: dict[int, dict[str, set]] = defaultdict(
        lambda: {"order": set(), "line": set(), "promo": set()}
    )
    when_by_order: dict[int, int] = {}
    for o, kind, second in zip(chosen.tolist(), kinds.tolist(), fixed_second.tolist(), strict=True):
        kind = CORRECTION_KINDS[kind]
        lines = np.arange(line_start[o], line_end[o])
        promos = np.arange(promo_start[o], promo_end[o])
        if kind == "discount" and len(promos) == 0:
            kind = "quantity"
        bucket = touched[int(fixed_day[o])]
        when_by_order[o] = second
        if kind == "void":
            status[o] = "voided"
            bucket["order"].add(o)
            continue
        if kind == "quantity":
            j = int(lines[rng.integers(len(lines))])
            step = -1 if quantity[j] > 1 and rng.random() < 0.5 else 1
            quantity[j] += step
            bucket["line"].add(j)
        elif kind == "unit_price":
            j = int(lines[rng.integers(len(lines))])
            unit_price[j] = max(1_000, unit_price[j] + int(rng.choice(PRICE_FIXES)))
            bucket["line"].add(j)
        else:
            k = int(promos[rng.integers(len(promos))])
            discount[k] = max(1_000, discount[k] + int(rng.choice(DISCOUNT_FIXES)))
            bucket["promo"].add(k)
        if len(promos):
            gross = int((quantity[lines] * unit_price[lines]).sum())
            capped = capped_discounts(discount[promos][None, :], np.array([gross]))[0]
            for k, value in zip(promos.tolist(), capped.tolist(), strict=True):
                if value != discount[k] or k in bucket["promo"]:
                    discount[k] = value
                    bucket["promo"].add(k)

    for fix_day, bucket in sorted(touched.items()):
        if bucket["order"]:
            idx = np.array(sorted(bucket["order"]), dtype=np.int64)
            when = _stamp(profile, fix_day, [when_by_order[o] for o in idx])
            buffer.add("sales_order", fix_day, _orders(batch, idx, status[idx], when))
        if bucket["line"]:
            idx = np.array(sorted(bucket["line"]), dtype=np.int64)
            when = _stamp(profile, fix_day, [when_by_order[int(o)] for o in batch.line_order[idx]])
            buffer.add(
                "order_line", fix_day, _lines(batch, idx, quantity[idx], unit_price[idx], when)
            )
        if bucket["promo"]:
            idx = np.array(sorted(bucket["promo"]), dtype=np.int64)
            when = _stamp(profile, fix_day, [when_by_order[int(o)] for o in batch.promo_order[idx]])
            buffer.add("order_promotion", fix_day, _promos(batch, idx, discount[idx], when))

    # The final state, as the source will hold it at the end of the period.
    gross = np.bincount(batch.line_order, weights=quantity * unit_price, minlength=n)
    disc = np.bincount(batch.promo_order, weights=discount, minlength=n)
    completed = landed & (status == "completed")
    outcome.landed_orders = int(landed.sum())
    outcome.completed_orders = int(completed.sum())
    outcome.voided_orders = int((landed & (status == "voided")).sum())
    outcome.late_orders = int((landed & (lag > 0)).sum())
    outcome.corrected_orders = len(chosen)
    outcome.net_revenue = int((gross - disc)[completed].sum())
