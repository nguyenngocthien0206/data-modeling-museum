"""Reference data: geography, tiers, channels, catalogue, stores and promotions.

Province names and codes are real (pre-2025 administrative units), including every
province that the 2025 merger challenge folds into another one. Districts and wards are
simulated: realistic shape, made-up names.

Stores, products and promotions change over time. Every version goes into a VersionLog,
which lands it in the extract of the day it happened (one version per key per day: the
state at the end of that day, as a watermark extract would see it).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from museum.generator.config import Profile
from museum.generator.schemas import KEYS

CHAIN = "Museum Coffee"

# Rows in the first extract (an initial full load) carry this audit time.
INITIAL_LOAD_AT = datetime(2023, 12, 31, 22, 0)

# (code, name, is_city, store weight, number of districts)
PROVINCES = (
    ("01", "Hà Nội", True, 0.22, 8),
    ("79", "Thành phố Hồ Chí Minh", True, 0.28, 8),
    ("48", "Đà Nẵng", True, 0.08, 6),
    ("31", "Hải Phòng", True, 0.06, 6),
    ("92", "Cần Thơ", True, 0.05, 5),
    ("74", "Bình Dương", False, 0.07, 5),
    ("75", "Đồng Nai", False, 0.05, 5),
    ("77", "Bà Rịa - Vũng Tàu", False, 0.04, 4),
    ("30", "Hải Dương", False, 0.03, 4),
    ("49", "Quảng Nam", False, 0.03, 4),
    ("56", "Khánh Hòa", False, 0.04, 4),
    ("58", "Ninh Thuận", False, 0.01, 3),
    ("70", "Bình Phước", False, 0.01, 3),
    ("93", "Hậu Giang", False, 0.01, 3),
    ("94", "Sóc Trăng", False, 0.02, 3),
)
WARDS_PER_DISTRICT = 6

TIERS = (
    ("MEMBER", "Thành viên", 1, 0),
    ("SILVER", "Bạc", 2, 2_000_000),
    ("GOLD", "Vàng", 3, 5_000_000),
    ("DIAMOND", "Kim cương", 4, 12_000_000),
)
CHANNELS = (("dine_in", "Tại quầy"), ("takeaway", "Mang đi"))
CATEGORIES = ((1, "Cà phê"), (2, "Trà"), (3, "Đá xay"), (4, "Bánh"), (5, "Nước ép"))

# (sku prefix, name, category, base price in VND, popularity, sold in sizes)
MENU = (
    ("CF01", "Cà phê đen đá", 1, 29_000, 8, True),
    ("CF02", "Cà phê sữa đá", 1, 35_000, 12, True),
    ("CF03", "Bạc xỉu", 1, 39_000, 9, True),
    ("CF04", "Americano", 1, 45_000, 4, True),
    ("CF05", "Latte", 1, 55_000, 5, True),
    ("CF06", "Cappuccino", 1, 55_000, 4, True),
    ("TE01", "Trà đào cam sả", 2, 49_000, 8, True),
    ("TE02", "Trà sen vàng", 2, 49_000, 6, True),
    ("TE03", "Trà vải", 2, 45_000, 4, True),
    ("TE04", "Trà sữa trân châu", 2, 45_000, 6, True),
    ("FR01", "Matcha đá xay", 3, 59_000, 3, True),
    ("FR02", "Cookie đá xay", 3, 59_000, 3, True),
    ("BK01", "Bánh mì que", 4, 19_000, 4, False),
    ("BK02", "Croissant", 4, 29_000, 3, False),
    ("BK03", "Bánh tiramisu", 4, 35_000, 2, False),
    ("JC01", "Nước cam ép", 5, 45_000, 2, False),
)
SIZES = (("S", 0, 0.3), ("M", 6_000, 0.5), ("L", 10_000, 0.2))

# Chain-wide price rounds: (date, hour, categories affected, increase in VND).
PRICE_ROUNDS = (
    (date(2024, 7, 1), 6, (1,), 2_000),
    (date(2025, 2, 1), 6, (1, 2, 3), 3_000),
)
MIN_PRICE = 15_000

PROMO_THEMES = ("Chào hè", "Tết", "Cuối tuần", "Thành viên mới", "Ngày đôi", "Mùa mưa")
STORE_PLANNING_DAYS = 30


def at(day: date, seconds: int) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(seconds=int(seconds))


class VersionLog:
    """Rows to land, grouped by landing day and table, at most one version per key per day."""

    def __init__(self) -> None:
        self._rows: dict[int, dict[str, dict[tuple, dict]]] = defaultdict(lambda: defaultdict(dict))

    def add(self, day: int, table_name: str, row: dict) -> None:
        key = tuple(row[k] for k in KEYS[table_name])
        self._rows[max(day, 0)][table_name][key] = dict(row)

    def tables_on(self, day: int) -> dict[str, dict[str, list]]:
        out = {}
        for table_name, rows in sorted(self._rows.get(day, {}).items()):
            ordered = [rows[k] for k in sorted(rows)]
            out[table_name] = {c: [r[c] for r in ordered] for c in ordered[0]}
        return out

    def versions(self, table_name: str) -> list[tuple[int, dict]]:
        return [
            (day, row)
            for day in sorted(self._rows)
            for row in self._rows[day].get(table_name, {}).values()
        ]


@dataclass
class Geography:
    provinces: list[tuple[str, str]]
    districts: list[tuple[str, str, str]]
    wards: list[tuple[str, str, str]]
    wards_by_province: dict[str, list[str]] = field(default_factory=dict)
    district_name: dict[str, str] = field(default_factory=dict)
    province_name: dict[str, str] = field(default_factory=dict)

    def province_of_ward(self, ward_code: str) -> str:
        return ward_code[:2]

    def district_of_ward(self, ward_code: str) -> str:
        return ward_code[:4]


def build_geography() -> Geography:
    geo = Geography(provinces=[], districts=[], wards=[])
    for code, name, is_city, _, n_districts in PROVINCES:
        geo.provinces.append((code, name))
        geo.province_name[code] = name
        geo.wards_by_province[code] = []
        for i in range(1, n_districts + 1):
            district_code = f"{code}{i:02d}"
            district_name = f"Quận {i}" if is_city else f"Huyện {i}"
            geo.districts.append((district_code, code, district_name))
            geo.district_name[district_code] = district_name
            for j in range(1, WARDS_PER_DISTRICT + 1):
                ward_code = f"{district_code}{j:02d}"
                ward_name = f"Phường {j}" if is_city else f"Xã {j}"
                geo.wards.append((ward_code, district_code, ward_name))
                geo.wards_by_province[code].append(ward_code)
    return geo


def static_extract(geo: Geography) -> dict[str, dict]:
    """Tables that never change, as they stand in the first (full) extract."""

    def columns(names: tuple[str, ...], rows) -> dict:
        data = {name: [row[i] for row in rows] for i, name in enumerate(names)}
        audit = [INITIAL_LOAD_AT] * len(rows)
        return {**data, "created_at": audit, "updated_at": list(audit)}

    return {
        "province": columns(("province_code", "province_name"), geo.provinces),
        "district": columns(("district_code", "province_code", "district_name"), geo.districts),
        "ward": columns(("ward_code", "district_code", "ward_name"), geo.wards),
        "membership_tier": columns(("tier_code", "tier_name", "rank", "min_spend_12m"), TIERS),
        "channel": columns(("channel_code", "channel_name"), CHANNELS),
        "product_category": columns(("category_id", "category_name"), CATEGORIES),
    }


@dataclass
class Product:
    index: int
    product_id: int
    sku: str
    name: str
    category_id: int
    size: str | None
    list_price: int  # price on the first day
    popularity: float


def build_products() -> list[Product]:
    products: list[Product] = []
    for prefix, name, category, price, popularity, sized in MENU:
        variants = SIZES if sized else ((None, 0, 1.0),)
        for size, surcharge, share in variants:
            sku = f"{prefix}-{size}" if size else prefix
            products.append(
                Product(
                    index=len(products),
                    product_id=len(products) + 1,
                    sku=sku,
                    name=name,
                    category_id=category,
                    size=size,
                    list_price=price + surcharge,
                    popularity=popularity * share,
                )
            )
    return products


@dataclass
class PriceBook:
    """List price of every product over time, as the POS applies it."""

    changes: dict[int, list[tuple[datetime, int]]]  # product index -> (effective at, price)

    def price_array(self, products: list[Product], ordered_at: np.ndarray, product_index):
        """List price in effect at each order time (ordered_at as datetime64[us])."""
        prices = np.array([p.list_price for p in products], dtype=np.int64)[product_index]
        for index, changes in self.changes.items():
            hit = product_index == index
            if not hit.any():
                continue
            for effective, price in changes:
                after = hit & (ordered_at >= np.datetime64(effective, "us"))
                prices[after] = price
        return prices


def build_price_history(
    profile: Profile, products: list[Product], log: VersionLog, rng: np.random.Generator
) -> PriceBook:
    current = {p.index: p.list_price for p in products}
    changes: dict[int, list[tuple[datetime, int]]] = defaultdict(list)
    changed_on: set[tuple[int, int]] = set()

    def row(product: Product, price: int, when: datetime) -> dict:
        return {
            "product_id": product.product_id,
            "sku": product.sku,
            "product_name": product.name,
            "category_id": product.category_id,
            "size": product.size,
            "list_price": price,
            "is_active": True,
            "created_at": INITIAL_LOAD_AT,
            "updated_at": when,
        }

    events: list[tuple[datetime, Product, int]] = []
    for round_day, hour, categories, increase in PRICE_ROUNDS:
        if profile.start < round_day <= profile.end:
            for product in products:
                if product.category_id in categories:
                    events.append((at(round_day, hour * 3600), product, increase))
    for _ in range(profile.price_changes):
        product = products[int(rng.integers(len(products)))]
        day = int(rng.integers(1, profile.n_days))
        when = at(profile.day(day), int(rng.integers(6 * 3600, 22 * 3600)))
        step = int(rng.choice([-3_000, -2_000, 2_000, 3_000, 5_000]))
        events.append((when, product, step))

    for product in products:
        log.add(0, "product", row(product, product.list_price, INITIAL_LOAD_AT))
    for when, product, step in sorted(events, key=lambda e: (e[0], e[1].index)):
        day = (when.date() - profile.start).days
        if (product.index, day) in changed_on:
            continue  # one version per key per extract, and every price stays visible
        changed_on.add((product.index, day))
        current[product.index] = max(MIN_PRICE, current[product.index] + step)
        changes[product.index].append((when, current[product.index]))
        log.add(day, "product", row(product, current[product.index], when))
    return PriceBook(dict(changes))


@dataclass
class Store:
    index: int
    store_id: int
    store_code: str
    store_name: str
    ward_code: str
    address_line: str
    opened_on: date
    open_day: int  # first trading day as a day index (negative: before the period)
    close_day: int  # first day without trading (n_days if it never closes)
    size: float

    @property
    def province_code(self) -> str:
        return self.ward_code[:2]

    def trades_on(self, day: int) -> bool:
        return self.open_day <= day < self.close_day


def build_stores(
    profile: Profile,
    geo: Geography,
    streets: list[str],
    log: VersionLog,
    rng: np.random.Generator,
) -> list[Store]:
    total = profile.stores + profile.new_stores
    weights = np.array([p[3] for p in PROVINCES])
    province_codes = [p[0] for p in PROVINCES]
    picks = rng.choice(len(PROVINCES), size=total, p=weights / weights.sum())
    sizes = rng.lognormal(0.0, 0.35, size=total)
    sizes = sizes / sizes.mean()
    first_open = date(2019, 1, 1)
    span_before = (date(2023, 12, 1) - first_open).days
    new_open_days = np.sort(rng.integers(60, profile.n_days - 60, size=profile.new_stores))
    closing = rng.choice(profile.stores, size=profile.closed_stores, replace=False)
    close_days = dict(
        zip(
            closing.tolist(),
            rng.integers(90, profile.n_days - 30, size=len(closing)).tolist(),
            strict=True,
        )
    )

    stores = []
    for i, pick in enumerate(picks):
        province = province_codes[pick]
        ward = str(rng.choice(geo.wards_by_province[province]))
        code = f"S{i + 1:03d}"
        if i < profile.stores:
            opened_on = first_open + timedelta(days=int(rng.integers(0, span_before)))
        else:
            opened_on = profile.day(int(new_open_days[i - profile.stores]))
        place = f"{geo.district_name[ward[:4]]}, {geo.province_name[province]}"
        store = Store(
            index=i,
            store_id=i + 1,
            store_code=code,
            store_name=f"{CHAIN} {place} ({code})",
            ward_code=ward,
            address_line=str(rng.choice(streets)),
            opened_on=opened_on,
            open_day=(opened_on - profile.start).days,
            close_day=close_days.get(i, profile.n_days),
            size=float(sizes[i]),
        )
        stores.append(store)
        _log_store_lifecycle(profile, store, log)
    return stores


def _log_store_lifecycle(profile: Profile, store: Store, log: VersionLog) -> None:
    def row(status: str, closed_on: date | None, created: datetime, updated: datetime) -> dict:
        return {
            "store_id": store.store_id,
            "store_code": store.store_code,
            "store_name": store.store_name,
            "ward_code": store.ward_code,
            "address_line": store.address_line,
            "opened_on": store.opened_on,
            "closed_on": closed_on,
            "status": status,
            "created_at": created,
            "updated_at": updated,
        }

    if store.open_day <= 0:
        created = INITIAL_LOAD_AT
        log.add(0, "store", row("open", None, created, created))
    else:
        plan_day = max(1, store.open_day - STORE_PLANNING_DAYS)
        created = at(profile.day(plan_day), 10 * 3600)
        log.add(plan_day, "store", row("planned", None, created, created))
        log.add(store.open_day, "store", row("open", None, created, at(store.opened_on, 5 * 3600)))
    if store.close_day < profile.n_days:
        closed_on = profile.day(store.close_day)
        log.add(
            store.close_day, "store", row("closed", closed_on, created, at(closed_on, 5 * 3600))
        )


@dataclass
class Promotion:
    promotion_id: int
    promo_code: str
    promo_name: str
    promo_type: str
    promo_value: int
    starts_on: date
    ends_on: date  # final end date, after any edit
    created_at: datetime


def build_promotions(
    profile: Profile, log: VersionLog, rng: np.random.Generator
) -> list[Promotion]:
    promotions: list[Promotion] = []
    month = date(profile.start.year, profile.start.month, 1)
    while month <= profile.end:
        count = max(1, int(rng.poisson(profile.promotions_per_month)))
        next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        for _ in range(count):
            starts_on = month + timedelta(days=int(rng.integers(0, (next_month - month).days)))
            ends_on = starts_on + timedelta(days=int(rng.integers(5, 22)))
            if rng.random() < 0.6:
                kind, value = "percent_off", int(rng.choice([10, 15, 20, 25, 30]))
                label = f"Giảm {value}%"
            else:
                kind, value = "amount_off", int(rng.choice([10_000, 15_000, 20_000, 25_000]))
                label = f"Giảm {value // 1000}k"
            lead = timedelta(days=int(rng.integers(3, 11)), hours=9)
            promotion = Promotion(
                promotion_id=len(promotions) + 1,
                promo_code=f"PROMO{len(promotions) + 1:03d}",
                promo_name=f"{label} {rng.choice(PROMO_THEMES)}",
                promo_type=kind,
                promo_value=value,
                starts_on=starts_on,
                ends_on=ends_on,
                created_at=at(starts_on, 0) - lead,
            )
            created_day = (promotion.created_at.date() - profile.start).days
            log.add(created_day, "promotion", _promotion_row(promotion, promotion.created_at))
            # Some campaigns are extended or cut short a few days before they start.
            edit_day = (starts_on - profile.start).days - int(rng.integers(1, 4))
            if rng.random() < profile.promotion_edit_share and edit_day > max(created_day, 0):
                shift = int(rng.choice([-3, -2, 2, 3, 5]))
                promotion.ends_on = max(starts_on, ends_on + timedelta(days=shift))
                edited = at(profile.day(edit_day), int(rng.integers(9 * 3600, 17 * 3600)))
                log.add(edit_day, "promotion", _promotion_row(promotion, edited))
            promotions.append(promotion)
        month = next_month
    return promotions


def _promotion_row(p: Promotion, updated_at: datetime) -> dict:
    return {
        "promotion_id": p.promotion_id,
        "promo_code": p.promo_code,
        "promo_name": p.promo_name,
        "promo_type": p.promo_type,
        "promo_value": p.promo_value,
        "starts_on": p.starts_on,
        "ends_on": p.ends_on,
        "created_at": p.created_at,
        "updated_at": updated_at,
    }
