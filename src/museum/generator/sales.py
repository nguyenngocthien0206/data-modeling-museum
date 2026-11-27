"""One day of sales as first rung up at the till: orders, lines and stacked promotions.

Everything is vectorized with numpy. Late arrival and later corrections are applied on
top of this batch in `delivery.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from museum.generator.config import Profile
from museum.generator.people import Members
from museum.generator.reference import PriceBook, Product, Promotion, Store
from museum.generator.workforce import DayShifts, store_slots

HOUR_WEIGHTS = np.array([3, 8, 10, 7, 5, 6, 8, 7, 5, 6, 7, 6, 5, 4, 3, 2], dtype=float)
FIRST_HOUR = 6
WEEKDAY_FACTOR = (0.95, 0.95, 0.95, 1.0, 1.05, 1.2, 1.15)  # Monday first
YEARLY_GROWTH = 0.10
DINE_IN_SHARE = 0.6
AWAY_FROM_HOME_STORE = 0.1
MAX_LINES = 5
QUANTITIES, QUANTITY_WEIGHTS = np.array([1, 2, 3]), np.array([0.8, 0.15, 0.05])
MAX_PROMOTIONS = 3
OVERRIDE_DISCOUNTS = np.array([2_000, 5_000])


@dataclass
class Catalogue:
    products: list[Product]
    prices: PriceBook
    product_id: np.ndarray
    log_weight: np.ndarray

    @classmethod
    def build(cls, products: list[Product], prices: PriceBook) -> Catalogue:
        return cls(
            products=products,
            prices=prices,
            product_id=np.array([p.product_id for p in products], dtype=np.int64),
            log_weight=np.log(np.array([p.popularity for p in products])),
        )


@dataclass
class SalesBatch:
    """Orders of one day, before late arrival and corrections. Indexes are positions."""

    order_id: np.ndarray
    store_index: np.ndarray
    store_id: np.ndarray
    customer_id: np.ndarray  # -1 for guests
    member_index: np.ndarray  # -1 for guests
    cashier: np.ndarray
    channel: np.ndarray
    ordered_at: np.ndarray  # datetime64[us]
    line_order: np.ndarray  # order position of each line
    line_no: np.ndarray
    product_id: np.ndarray
    quantity: np.ndarray
    unit_price: np.ndarray
    promo_order: np.ndarray  # order position of each order-promotion row
    promotion_id: np.ndarray
    discount: np.ndarray

    def __len__(self) -> int:
        return len(self.order_id)


def _top_k(rng: np.random.Generator, log_weight: np.ndarray, k: np.ndarray, width: int):
    """Weighted sampling without replacement per row (Gumbel top-k). Returns (row, column, pick)."""
    noise = -np.log(-np.log(rng.random((len(k), len(log_weight)))))
    ranked = np.argsort(-(log_weight[None, :] + noise), axis=1)[:, :width]
    mask = np.arange(width)[None, :] < k[:, None]
    rows, cols = np.nonzero(mask)
    return rows, cols, ranked[rows, cols]


def _pick(rng: np.random.Generator, pool: np.ndarray, members: Members, count: int) -> np.ndarray:
    if count == 0 or len(pool) == 0:
        return np.full(count, -1, dtype=np.int64)
    weight = members.weight[pool]
    return rng.choice(pool, size=count, p=weight / weight.sum())


def home_pool(members: Members, before: np.ndarray, after: np.ndarray, day: int) -> np.ndarray:
    """Members whose usual store, on this day, is the store the two arrays belong to."""
    stayed = before[members.home_switch_day[before] > day]
    arrived = after[members.home_switch_day[after] <= day]
    pool = np.concatenate([stayed, arrived])
    return pool[members.active_on(day)[pool]]


def build_day_sales(
    profile: Profile,
    day_index: int,
    stores: list[Store],
    catalogue: Catalogue,
    promotions: list[Promotion],
    members: Members,
    pools: tuple[list[np.ndarray], list[np.ndarray]],
    shifts: DayShifts,
    rng: np.random.Generator,
) -> SalesBatch:
    today: date = profile.day(day_index)
    level = WEEKDAY_FACTOR[today.weekday()] * (1 + YEARLY_GROWTH * day_index / 365)
    everyone = np.flatnonzero(members.active_on(day_index))

    parts: dict[str, list[np.ndarray]] = {k: [] for k in ("store", "second", "member", "cashier")}
    for store in stores:
        if not store.trades_on(day_index):
            continue
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
        member = np.full(n, -1, dtype=np.int64)
        local = home_pool(members, pools[0][store.index], pools[1][store.index], day_index)
        at_home, elsewhere = is_member & ~away, is_member & away
        member[at_home] = _pick(rng, local, members, int(at_home.sum()))
        member[elsewhere] = _pick(rng, everyone, members, int(elsewhere.sum()))

        parts["store"].append(np.full(n, store.index, dtype=np.int64))
        parts["second"].append(second)
        parts["member"].append(member)
        parts["cashier"].append(cashier)

    empty = np.empty(0, dtype=np.int64)
    if not parts["store"]:
        stamps = np.empty(0, dtype="datetime64[us]")
        return SalesBatch(*(empty,) * 7, stamps, *(empty,) * 8)

    store_index = np.concatenate(parts["store"])
    second = np.concatenate(parts["second"])
    member = np.concatenate(parts["member"])
    n_orders = len(store_index)
    ordered_at = np.datetime64(today, "us") + (second * 1_000_000).astype("timedelta64[us]")

    # Lines: 1 to MAX_LINES distinct products per order, weighted by popularity, priced at
    # the list price in effect at the order time, except a few manual overrides.
    n_lines = 1 + np.minimum(rng.poisson(profile.extra_lines_per_order, n_orders), MAX_LINES - 1)
    row, col, pick = _top_k(rng, catalogue.log_weight, n_lines, MAX_LINES)
    quantity = rng.choice(QUANTITIES, size=len(row), p=QUANTITY_WEIGHTS)
    unit_price = catalogue.prices.price_array(catalogue.products, ordered_at[row], pick)
    override = rng.random(len(row)) < profile.price_override_share
    cut = rng.choice(OVERRIDE_DISCOUNTS, size=len(row))
    unit_price = np.where(override, np.maximum(1_000, unit_price - cut), unit_price)
    gross = np.bincount(row, weights=quantity * unit_price, minlength=n_orders).astype(np.int64)

    live = [p for p in promotions if p.starts_on <= today <= p.ends_on]
    promo_order, promotion_id, discount = _promotions(profile, rng, live, gross)

    return SalesBatch(
        order_id=(day_index + 1) * 10_000_000 + np.arange(1, n_orders + 1, dtype=np.int64),
        store_index=store_index,
        store_id=np.array([s.store_id for s in stores], dtype=np.int64)[store_index],
        customer_id=np.where(member >= 0, members.customer_id[np.maximum(member, 0)], -1),
        member_index=member,
        cashier=np.concatenate(parts["cashier"]),
        channel=np.where(rng.random(n_orders) < DINE_IN_SHARE, "dine_in", "takeaway"),
        ordered_at=ordered_at,
        line_order=row,
        line_no=(col + 1).astype(np.int64),
        product_id=catalogue.product_id[pick],
        quantity=quantity.astype(np.int64),
        unit_price=unit_price,
        promo_order=promo_order,
        promotion_id=promotion_id,
        discount=discount,
    )


def capped_discounts(raw: np.ndarray, gross: np.ndarray) -> np.ndarray:
    """Apply stacked discounts in order, never letting their total exceed gross."""
    capped = np.minimum(np.cumsum(raw, axis=1), gross[:, None])
    return np.diff(capped, axis=1, prepend=0)


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
    row, col, pick = _top_k(rng, np.zeros(len(live)), wanted[orders], width)

    kind = np.array([p.promo_type for p in live])[pick]
    value = np.array([p.promo_value for p in live], dtype=np.int64)[pick]
    base = gross[orders][row]
    raw = np.where(kind == "percent_off", base * value // 100 // 1000 * 1000, value)

    table = np.zeros((len(orders), width), dtype=np.int64)
    table[row, col] = raw
    granted = capped_discounts(table, gross[orders])[row, col]

    keep = granted > 0
    ids = np.array([p.promotion_id for p in live], dtype=np.int64)
    return orders[row][keep], ids[pick][keep], granted[keep]
