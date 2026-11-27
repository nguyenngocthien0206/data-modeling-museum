"""Reference data: geography, tiers, channels, catalogue, stores and promotions.

Province names and codes are real (pre-2025 administrative units), including every
province that the 2025 merger challenge folds into another one. Districts and wards are
simulated: realistic shape, made-up names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from museum.generator.config import Profile

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

PROMO_THEMES = ("Chào hè", "Tết", "Cuối tuần", "Thành viên mới", "Ngày đôi", "Mùa mưa")


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


@dataclass
class Product:
    product_id: int
    sku: str
    name: str
    category_id: int
    size: str | None
    list_price: int
    popularity: float


def build_products() -> list[Product]:
    products: list[Product] = []
    for prefix, name, category, price, popularity, sized in MENU:
        variants = SIZES if sized else ((None, 0, 1.0),)
        for size, surcharge, share in variants:
            sku = f"{prefix}-{size}" if size else prefix
            products.append(
                Product(
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
class Store:
    index: int
    store_id: int
    store_code: str
    store_name: str
    ward_code: str
    address_line: str
    opened_on: date
    size: float

    @property
    def province_code(self) -> str:
        return self.ward_code[:2]


def build_stores(
    profile: Profile, geo: Geography, streets: list[str], rng: np.random.Generator
) -> list[Store]:
    weights = np.array([p[3] for p in PROVINCES])
    province_codes = [p[0] for p in PROVINCES]
    picks = rng.choice(len(PROVINCES), size=profile.stores, p=weights / weights.sum())
    sizes = rng.lognormal(0.0, 0.35, size=profile.stores)
    sizes = sizes / sizes.mean()
    first_open, last_open = date(2019, 1, 1), date(2023, 12, 1)
    span = (last_open - first_open).days
    stores = []
    for i, pick in enumerate(picks):
        province = province_codes[pick]
        ward = str(rng.choice(geo.wards_by_province[province]))
        district = geo.district_name[ward[:4]]
        code = f"S{i + 1:03d}"
        stores.append(
            Store(
                index=i,
                store_id=i + 1,
                store_code=code,
                store_name=f"{CHAIN} {district}, {geo.province_name[province]} ({code})",
                ward_code=ward,
                address_line=str(rng.choice(streets)),
                opened_on=first_open + timedelta(days=int(rng.integers(0, span))),
                size=float(sizes[i]),
            )
        )
    return stores


@dataclass
class Promotion:
    promotion_id: int
    promo_code: str
    promo_name: str
    promo_type: str
    promo_value: int
    starts_on: date
    ends_on: date
    created_at: datetime


def build_promotions(profile: Profile, rng: np.random.Generator) -> list[Promotion]:
    promotions: list[Promotion] = []
    month = date(profile.start.year, profile.start.month, 1)
    while month <= profile.end:
        count = max(1, int(rng.poisson(profile.promotions_per_month)))
        days_in_month = ((month.replace(day=28) + timedelta(days=4)).replace(day=1) - month).days
        for _ in range(count):
            starts_on = month + timedelta(days=int(rng.integers(0, days_in_month)))
            ends_on = starts_on + timedelta(days=int(rng.integers(5, 22)))
            if rng.random() < 0.6:
                kind, value = "percent_off", int(rng.choice([10, 15, 20, 25, 30]))
                label = f"Giảm {value}%"
            else:
                kind, value = "amount_off", int(rng.choice([10_000, 15_000, 20_000, 25_000]))
                label = f"Giảm {value // 1000}k"
            theme = str(rng.choice(PROMO_THEMES))
            lead = timedelta(days=int(rng.integers(3, 11)), hours=9)
            promotions.append(
                Promotion(
                    promotion_id=len(promotions) + 1,
                    promo_code=f"PROMO{len(promotions) + 1:03d}",
                    promo_name=f"{label} {theme}",
                    promo_type=kind,
                    promo_value=value,
                    starts_on=starts_on,
                    ends_on=ends_on,
                    created_at=datetime.combine(starts_on, datetime.min.time()) - lead,
                )
            )
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    return promotions


def _audit(n: int) -> dict:
    return {"created_at": [INITIAL_LOAD_AT] * n, "updated_at": [INITIAL_LOAD_AT] * n}


def initial_extract(
    geo: Geography, products: list[Product], stores: list[Store]
) -> dict[str, dict]:
    """Every reference table as it stands in the first (full) extract."""

    def columns(names: tuple[str, ...], rows: list[tuple]) -> dict:
        data = {name: [row[i] for row in rows] for i, name in enumerate(names)}
        return {**data, **_audit(len(rows))}

    return {
        "province": columns(("province_code", "province_name"), geo.provinces),
        "district": columns(("district_code", "province_code", "district_name"), geo.districts),
        "ward": columns(("ward_code", "district_code", "ward_name"), geo.wards),
        "membership_tier": columns(("tier_code", "tier_name", "rank", "min_spend_12m"), TIERS),
        "channel": columns(("channel_code", "channel_name"), CHANNELS),
        "product_category": columns(("category_id", "category_name"), CATEGORIES),
        "product": columns(
            ("product_id", "sku", "product_name", "category_id", "size", "list_price", "is_active"),
            [
                (p.product_id, p.sku, p.name, p.category_id, p.size, p.list_price, True)
                for p in products
            ],
        ),
        "store": columns(
            (
                "store_id",
                "store_code",
                "store_name",
                "ward_code",
                "address_line",
                "opened_on",
                "closed_on",
                "status",
            ),
            [
                (
                    s.store_id,
                    s.store_code,
                    s.store_name,
                    s.ward_code,
                    s.address_line,
                    s.opened_on,
                    None,
                    "open",
                )
                for s in stores
            ],
        ),
    }


def promotion_columns(promotions: list[Promotion]) -> dict:
    return {
        "promotion_id": [p.promotion_id for p in promotions],
        "promo_code": [p.promo_code for p in promotions],
        "promo_name": [p.promo_name for p in promotions],
        "promo_type": [p.promo_type for p in promotions],
        "promo_value": [p.promo_value for p in promotions],
        "starts_on": [p.starts_on for p in promotions],
        "ends_on": [p.ends_on for p in promotions],
        "created_at": [p.created_at for p in promotions],
        "updated_at": [p.created_at for p in promotions],
    }
