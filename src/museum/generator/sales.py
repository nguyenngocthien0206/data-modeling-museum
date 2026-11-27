"""One day of sales: orders, order lines and stacked promotions, vectorized with numpy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pyarrow as pa

from museum.generator.config import Profile
from museum.generator.people import Members
from museum.generator.reference import Product, Promotion, Store
from museum.generator.schemas import SCHEMAS
from museum.generator.workforce import DayShifts, store_slots

SALES_TABLES = ("sales_order", "order_line", "order_promotion")

HOUR_WEIGHTS = np.array([3, 8, 10, 7, 5, 6, 8, 7, 5, 6, 7, 6, 5, 4, 3, 2], dtype=float)
FIRST_HOUR = 6
WEEKDAY_FACTOR = (0.95, 0.95, 0.95, 1.0, 1.05, 1.2, 1.15)  # Monday first
YEARLY_GROWTH = 0.10
DINE_IN_SHARE = 0.6
AWAY_FROM_HOME_STORE = 0.1
MAX_LINES = 5
QUANTITIES, QUANTITY_WEIGHTS = np.array([1, 2, 3]), np.array([0.8, 0.15, 0.05])
MAX_PROMOTIONS = 3


@dataclass
class Catalogue:
    product_id: np.ndarray
    list_price: np.ndarray
    log_weight: np.ndarray

    @classmethod
    def from_products(cls, products: list[Product]) -> Catalogue:
        return cls(
            product_id=np.array([p.product_id for p in products], dtype=np.int64),
            list_price=np.array([p.list_price for p in products], dtype=np.int64),
            log_weight=np.log(np.array([p.popularity for p in products])),
        )


def _top_k(rng: np.random.Generator, log_weight: np.ndarray, k: np.ndarray, width: int):
    """Weighted sampling without replacement per row (Gumbel top-k). Returns (row, column, pick)."""
    noise = -np.log(-np.log(rng.random((len(k), len(log_weight)))))
    ranked = np.argsort(-(log_weight[None, :] + noise), axis=1)[:, :width]
    mask = np.arange(width)[None, :] < k[:, None]
    rows, cols = np.nonzero(mask)
    return rows, cols, ranked[rows, cols]


def _pick_members(
    rng: np.random.Generator, pool: np.ndarray, members: Members, count: int
) -> np.ndarray:
    if count == 0 or len(pool) == 0:
        return np.full(count, -1, dtype=np.int64)
    weight = members.weight[pool]
    return members.customer_id[rng.choice(pool, size=count, p=weight / weight.sum())]


def build_day_sales(
    profile: Profile,
    day_index: int,
    stores: list[Store],
    catalogue: Catalogue,
    promotions: list[Promotion],
    members: Members,
    members_by_store: list[np.ndarray],
    shifts: DayShifts,
    rng: np.random.Generator,
) -> dict[str, dict]:
    today: date = profile.day(day_index)
    level = WEEKDAY_FACTOR[today.weekday()] * (1 + YEARLY_GROWTH * day_index / 365)
    active = members.active_on(day_index)
    everyone = np.flatnonzero(active)

    store_ids, seconds, customers, cashiers = [], [], [], []
    for store in stores:
        n = int(rng.poisson(profile.orders_per_store_day * store.size * level))
        if n == 0:
            continue
        hours = rng.choice(len(HOUR_WEIGHTS), size=n, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
        second = np.sort((FIRST_HOUR + hours) * 3600 + rng.integers(0, 3600, size=n))

        slot_ends = np.array([end for _, end in store_slots(profile, store)])
        slot = np.searchsorted(slot_ends, second, side="right")
        cashier = np.empty(n, dtype=np.int64)
        for s, staff in enumerate(shifts.slot_staff[store.index]):
            in_slot = slot == s
            cashier[in_slot] = staff[rng.integers(0, len(staff), size=int(in_slot.sum()))]

        is_member = rng.random(n) >= profile.guest_share
        away = rng.random(n) < AWAY_FROM_HOME_STORE
        customer = np.full(n, -1, dtype=np.int64)
        home_pool = members_by_store[store.index]
        home_pool = home_pool[active[home_pool]]
        at_home, elsewhere = is_member & ~away, is_member & away
        customer[at_home] = _pick_members(rng, home_pool, members, int(at_home.sum()))
        customer[elsewhere] = _pick_members(rng, everyone, members, int(elsewhere.sum()))

        store_ids.append(np.full(n, store.store_id, dtype=np.int64))
        seconds.append(second)
        customers.append(customer)
        cashiers.append(cashier)

    if not store_ids:
        return {name: {column: [] for column in SCHEMAS[name].names} for name in SALES_TABLES}

    store_id = np.concatenate(store_ids)
    second = np.concatenate(seconds)
    customer = np.concatenate(customers)
    cashier = np.concatenate(cashiers)
    n_orders = len(store_id)
    order_id = (day_index + 1) * 10_000_000 + np.arange(1, n_orders + 1, dtype=np.int64)
    midnight = np.datetime64(today, "us")
    ordered_at = midnight + second.astype("timedelta64[s]").astype("timedelta64[us]")
    channel = np.where(rng.random(n_orders) < DINE_IN_SHARE, "dine_in", "takeaway")

    # Lines: 1 to MAX_LINES distinct products per order, weighted by popularity.
    n_lines = 1 + np.minimum(rng.poisson(profile.extra_lines_per_order, n_orders), MAX_LINES - 1)
    row, col, pick = _top_k(rng, catalogue.log_weight, n_lines, MAX_LINES)
    quantity = rng.choice(QUANTITIES, size=len(row), p=QUANTITY_WEIGHTS)
    unit_price = catalogue.list_price[pick]
    line_amount = quantity * unit_price
    gross = np.bincount(row, weights=line_amount, minlength=n_orders).astype(np.int64)

    # Promotions: 0 to 3 distinct active promotions per order, discounts capped at gross.
    live = [p for p in promotions if p.starts_on <= today <= p.ends_on]
    promo_rows = _promotions(profile, rng, live, gross)
    promo_order, promo_id, discount = promo_rows

    return {
        "sales_order": {
            "order_id": order_id,
            "store_id": store_id,
            "customer_id": _nullable(customer),
            "cashier_employee_id": cashier,
            "channel_code": channel,
            "ordered_at": ordered_at,
            "status": np.full(n_orders, "completed"),
            "created_at": ordered_at,
            "updated_at": ordered_at,
        },
        "order_line": {
            "order_id": order_id[row],
            "line_no": (col + 1).astype(np.int32),
            "product_id": catalogue.product_id[pick],
            "quantity": quantity.astype(np.int32),
            "unit_price": unit_price,
            "line_amount": line_amount,
            "created_at": ordered_at[row],
            "updated_at": ordered_at[row],
        },
        "order_promotion": {
            "order_id": order_id[promo_order],
            "promotion_id": promo_id,
            "discount_amount": discount,
            "created_at": ordered_at[promo_order],
            "updated_at": ordered_at[promo_order],
        },
    }


def _promotions(
    profile: Profile, rng: np.random.Generator, live: list[Promotion], gross: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nothing = (np.empty(0, np.int64), np.empty(0, np.int64), np.empty(0, np.int64))
    if not live:
        return nothing
    u = rng.random(len(gross))
    p3, p2, p1 = profile.promo_three, profile.promo_two, profile.promo_one
    wanted = np.select([u < p3, u < p3 + p2, u < p3 + p2 + p1], [3, 2, 1], default=0)
    wanted = np.minimum(wanted, len(live))
    orders = np.flatnonzero(wanted)
    if len(orders) == 0:
        return nothing
    width = min(MAX_PROMOTIONS, len(live))
    flat = np.zeros(len(live))
    row, col, pick = _top_k(rng, flat, wanted[orders], width)

    kind = np.array([p.promo_type for p in live])[pick]
    value = np.array([p.promo_value for p in live], dtype=np.int64)[pick]
    base = gross[orders][row]
    raw = np.where(kind == "percent_off", base * value // 100 // 1000 * 1000, value)

    table = np.zeros((len(orders), width), dtype=np.int64)
    table[row, col] = raw
    capped = np.minimum(np.cumsum(table, axis=1), gross[orders][:, None])
    granted = np.diff(capped, axis=1, prepend=0)[row, col]

    keep = granted > 0
    ids = np.array([p.promotion_id for p in live], dtype=np.int64)
    return orders[row][keep], ids[pick][keep], granted[keep]


def _nullable(values: np.ndarray) -> pa.Array:
    """Guest orders carry -1 internally and a null customer_id in the source."""
    return pa.array(values, type=pa.int64(), mask=values < 0)
