"""People: name pools, unique phone numbers, and the member base.

Faker's vi_VN name formats put the given name first ("Nam Nguyễn"), which is not how
Vietnamese names are written. We only take Faker's lists of family, middle and given
names and compose them in Vietnamese order: family, middle, given. Faker is also too slow
to call once per person at the large scale, so it fills small pools once and numpy picks
from them.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from faker import Faker
from faker.providers.person.vi_VN import Provider as VietnameseNames

from museum.generator.config import Profile
from museum.generator.reference import Geography, Store

MOBILE_PREFIXES = (
    "032", "033", "034", "035", "036", "037", "038", "039",
    "070", "076", "077", "078", "079",
    "081", "082", "083", "084", "085", "086", "088", "089",
    "090", "091", "093", "094", "096", "097", "098",
)  # fmt: skip
EMAIL_DOMAINS = ("example.com", "example.net", "example.org")
STREET_POOL_SIZE = 2000

# Share of members who joined before the simulated period (the chain already exists).
PRIOR_MEMBER_SHARE = 0.3
PRIOR_MEMBER_DAYS = 730
MEAN_MEMBER_LIFETIME_DAYS = 420


@dataclass
class NamePools:
    family: tuple[str, ...]
    middle_male: tuple[str, ...]
    middle_female: tuple[str, ...]
    given_male: tuple[str, ...]
    given_female: tuple[str, ...]

    @classmethod
    def from_faker(cls) -> NamePools:
        middle = tuple(VietnameseNames.middle_names)
        unisex = tuple(VietnameseNames.first_names_unisex)
        return cls(
            family=tuple(VietnameseNames.last_names),
            middle_male=tuple(m for m in middle if m != "Thị"),
            middle_female=tuple(m for m in middle if m != "Văn"),
            given_male=tuple(VietnameseNames.first_names_male) + unisex,
            given_female=tuple(VietnameseNames.first_names_female) + unisex,
        )

    def full_names(self, rng: np.random.Generator, genders: np.ndarray) -> list[str]:
        n = len(genders)
        family = rng.choice(self.family, size=n)
        names = []
        for i, gender in enumerate(genders):
            middle_pool = self.middle_female if gender == "F" else self.middle_male
            given_pool = self.given_female if gender == "F" else self.given_male
            middle = middle_pool[rng.integers(len(middle_pool))]
            given = given_pool[rng.integers(len(given_pool))]
            names.append(f"{family[i]} {middle} {given}")
        return names


def street_pool(faker_seed: int) -> list[str]:
    faker = Faker("vi_VN")
    faker.seed_instance(faker_seed)
    return [faker.street_address() for _ in range(STREET_POOL_SIZE)]


def ascii_slug(text: str) -> str:
    plain = text.replace("Đ", "D").replace("đ", "d")
    plain = unicodedata.normalize("NFKD", plain)
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return ".".join(plain.lower().split())


def unique_phones(rng: np.random.Generator, n: int) -> list[str]:
    """n distinct Vietnamese mobile numbers (10 digits)."""
    space = len(MOBILE_PREFIXES) * 10_000_000
    chosen = np.empty(0, dtype=np.int64)
    while len(chosen) < n:
        draw = rng.integers(0, space, size=int((n - len(chosen)) * 1.1) + 10)
        merged = np.concatenate([chosen, draw])
        _, first = np.unique(merged, return_index=True)
        chosen = merged[np.sort(first)]
    chosen = chosen[:n]
    return [f"{MOBILE_PREFIXES[v // 10_000_000]}{v % 10_000_000:07d}" for v in chosen]


def emails(rng: np.random.Generator, names: list[str]) -> list[str]:
    numbers = rng.integers(1, 10_000, size=len(names))
    domains = rng.choice(EMAIL_DOMAINS, size=len(names))
    out = []
    for name, number, domain in zip(names, numbers, domains, strict=True):
        parts = ascii_slug(name).split(".")
        out.append(f"{parts[-1]}.{parts[0]}{number}@{domain}")
    return out


@dataclass
class Members:
    customer_id: np.ndarray
    join_day: np.ndarray  # day index; negative means before the simulated period
    churn_day: np.ndarray  # first day the member no longer buys
    home_store: np.ndarray  # store index
    weight: np.ndarray  # how often the member buys, relative to others
    columns: dict  # customer table rows, one per member, in customer_id order

    def landing_day(self) -> np.ndarray:
        return np.maximum(self.join_day, 0)

    def active_on(self, day: int) -> np.ndarray:
        """Members who can place an order on this day (joined on an earlier day, not churned)."""
        return (self.join_day < day) & (self.churn_day > day)


def build_members(
    profile: Profile,
    stores: list[Store],
    geo: Geography,
    pools: NamePools,
    streets: list[str],
    rng: np.random.Generator,
) -> Members:
    n = profile.members
    store_weight = np.array([s.size for s in stores])
    home_store = rng.choice(len(stores), size=n, p=store_weight / store_weight.sum())
    opened_index = np.array([(s.opened_on - profile.start).days for s in stores])

    prior = rng.random(n) < PRIOR_MEMBER_SHARE
    join_day = np.where(
        prior,
        rng.integers(-PRIOR_MEMBER_DAYS, 0, size=n),
        rng.integers(0, profile.n_days, size=n),
    )
    join_day = np.maximum(join_day, opened_index[home_store])
    join_second = rng.integers(7 * 3600, 21 * 3600, size=n)

    order = np.lexsort((join_second, join_day))
    home_store, join_day, join_second = home_store[order], join_day[order], join_second[order]

    lifetime = np.maximum(1, rng.exponential(MEAN_MEMBER_LIFETIME_DAYS, size=n).astype(np.int64))
    churn_day = join_day + 1 + lifetime
    weight = rng.gamma(0.7, 1.0, size=n)

    genders = np.where(rng.random(n) < 0.55, "F", "M")
    names = pools.full_names(rng, genders)
    start = datetime.combine(profile.start, datetime.min.time())
    joined_at = [
        start + timedelta(days=int(d), seconds=int(s))
        for d, s in zip(join_day, join_second, strict=True)
    ]
    ages_in_days = rng.integers(16 * 365, 60 * 365, size=n)
    birth_dates = [profile.start - timedelta(days=int(a)) for a in ages_in_days]
    wards = [str(rng.choice(geo.wards_by_province[stores[s].province_code])) for s in home_store]

    customer_id = np.arange(1, n + 1, dtype=np.int64)
    columns = {
        "customer_id": customer_id,
        "full_name": names,
        "phone": unique_phones(rng, n),
        "email": emails(rng, names),
        "date_of_birth": birth_dates,
        "gender": genders.tolist(),
        "address_line": rng.choice(streets, size=n).tolist(),
        "ward_code": wards,
        "tier_code": ["MEMBER"] * n,
        "joined_at": joined_at,
        "created_at": joined_at,
        "updated_at": joined_at,
    }
    return Members(customer_id, join_day, churn_day, home_store, weight, columns)
