"""People: name pools, unique phone numbers, and the member base with its history.

Faker's vi_VN name formats put the given name first ("Nam Nguyễn"), which is not how
Vietnamese names are written. We only take Faker's lists of family, middle and given
names and compose them in Vietnamese order: family, middle, given. Faker is also too slow
to call once per person at the large scale, so it fills small pools once and numpy picks
from them.

The customer table is overwritten in place by the source: an address move or a tier
change replaces the row. Each change lands in the extract of its day, and several changes
on the same day land as one row (the end-of-day state).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
from faker import Faker
from faker.providers.person.vi_VN import Provider as VietnameseNames

from museum.generator.config import Profile
from museum.generator.reference import TIERS, Geography, Store, at

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
MOVE_ACROSS_PROVINCES = 0.2
TIER_REVIEW_SECOND = 3 * 3600  # tiers are recomputed at 03:00 on the first of the month


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
    weight: np.ndarray  # how often the member buys, relative to others
    home_store: np.ndarray  # store index where the member usually buys
    later_home: np.ndarray  # store index after the home store closed (same if never)
    home_switch_day: np.ndarray  # day the member moves to later_home
    columns: dict  # customer rows as at joining, in customer_id order

    def __len__(self) -> int:
        return len(self.customer_id)

    def landing_day(self) -> np.ndarray:
        return np.maximum(self.join_day, 0)

    def active_on(self, day: int) -> np.ndarray:
        """Members who can place an order on this day (joined on an earlier day, not churned)."""
        return (self.join_day < day) & (self.churn_day > day)

    def pools(self, n_stores: int) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """Per store: members who start there, and members who arrive after a closure."""
        before = [np.flatnonzero(self.home_store == s) for s in range(n_stores)]
        moved = self.later_home != self.home_store
        after = [np.flatnonzero(moved & (self.later_home == s)) for s in range(n_stores)]
        return before, after


def build_members(
    profile: Profile,
    stores: list[Store],
    geo: Geography,
    pools: NamePools,
    streets: list[str],
    rng: np.random.Generator,
) -> Members:
    n = profile.members
    prior = rng.random(n) < PRIOR_MEMBER_SHARE
    join_day = np.where(
        prior,
        rng.integers(-PRIOR_MEMBER_DAYS, 0, size=n),
        rng.integers(0, profile.n_days, size=n),
    )
    join_day = np.maximum(join_day, min(s.open_day for s in stores))
    join_second = rng.integers(7 * 3600, 21 * 3600, size=n)
    order = np.lexsort((join_second, join_day))
    join_day, join_second = join_day[order], join_second[order]

    size = np.array([s.size for s in stores])
    home_store = np.empty(n, dtype=np.int64)
    for day in np.unique(join_day):
        joining = np.flatnonzero(join_day == day)
        weight = size * np.array([s.trades_on(int(day)) for s in stores])
        home_store[joining] = rng.choice(len(stores), size=len(joining), p=weight / weight.sum())

    later_home = home_store.copy()
    switch_day = np.full(n, profile.n_days, dtype=np.int64)
    for store in stores:
        if store.close_day >= profile.n_days:
            continue
        leaving = np.flatnonzero(home_store == store.index)
        open_after = [s for s in stores if s.trades_on(store.close_day)]
        nearby = [s for s in open_after if s.province_code == store.province_code] or open_after
        weight = np.array([s.size for s in nearby])
        picks = rng.choice(len(nearby), size=len(leaving), p=weight / weight.sum())
        later_home[leaving] = np.array([nearby[p].index for p in picks], dtype=np.int64)
        switch_day[leaving] = store.close_day

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

    columns = {
        "customer_id": np.arange(1, n + 1, dtype=np.int64),
        "full_name": names,
        "phone": unique_phones(rng, n),
        "email": emails(rng, names),
        "date_of_birth": birth_dates,
        "gender": genders.tolist(),
        "address_line": rng.choice(streets, size=n).tolist(),
        "ward_code": wards,
        "tier_code": [TIERS[0][0]] * n,
        "joined_at": joined_at,
        "created_at": joined_at,
        "updated_at": joined_at,
    }
    return Members(
        customer_id=columns["customer_id"],
        join_day=join_day,
        churn_day=churn_day,
        weight=weight,
        home_store=home_store,
        later_home=later_home,
        home_switch_day=switch_day,
        columns=columns,
    )


@dataclass
class Change:
    member: int
    day: int
    when: datetime
    ward_code: str | None = None
    address_line: str | None = None
    tier_code: str | None = None


def address_moves(
    profile: Profile,
    members: Members,
    geo: Geography,
    streets: list[str],
    rng: np.random.Generator,
) -> list[Change]:
    daily = profile.address_move_monthly / 30
    first = np.maximum(members.join_day + 1, 1)
    last = np.minimum(members.churn_day, profile.n_days)
    span = np.maximum(last - first, 0)
    counts = rng.poisson(daily * span)
    province_codes = [code for code, _ in geo.provinces]
    ward = list(members.columns["ward_code"])
    moves: list[Change] = []
    for member in np.flatnonzero(counts):
        days = np.unique(rng.integers(first[member], last[member], size=counts[member]))
        for day in days:
            province = ward[member][:2]
            if rng.random() < MOVE_ACROSS_PROVINCES:
                province = str(rng.choice(province_codes))
            ward[member] = str(rng.choice(geo.wards_by_province[province]))
            moves.append(
                Change(
                    member=int(member),
                    day=int(day),
                    when=at(profile.day(int(day)), int(rng.integers(8 * 3600, 22 * 3600))),
                    ward_code=ward[member],
                    address_line=str(rng.choice(streets)),
                )
            )
    return moves


def month_starts(profile: Profile) -> list[tuple[int, int]]:
    """(month number since the period start, day index) for each first-of-month after day 0."""
    out = []
    day = date(profile.start.year, profile.start.month, 1)
    month = 0
    while day <= profile.end:
        if day > profile.start:
            out.append((month, (day - profile.start).days))
        day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        month += 1
    return out


def month_of_day(profile: Profile, day_index: int) -> int:
    d = profile.day(day_index)
    return (d.year - profile.start.year) * 12 + d.month - profile.start.month


def tier_changes(profile: Profile, members: Members, spend: np.ndarray) -> list[Change]:
    """Monthly tier review from trailing 12-month net spend (spend is months x members)."""
    thresholds = np.array([t[3] for t in TIERS])
    codes = [t[0] for t in TIERS]
    current = np.zeros(len(members), dtype=np.int64)
    changes: list[Change] = []
    for month, day in month_starts(profile):
        window = spend[max(0, month - 12) : month].sum(axis=0)
        tier = np.searchsorted(thresholds, window, side="right") - 1
        eligible = members.join_day < day
        changed = np.flatnonzero(eligible & (tier != current))
        when = at(profile.day(day), TIER_REVIEW_SECOND)
        changes.extend(Change(int(m), day, when, tier_code=codes[tier[m]]) for m in changed)
        current[changed] = tier[changed]
    return changes


def customer_extracts(profile: Profile, members: Members, changes: list[Change]):
    """Yield (day, columns) for the customer table: joins plus merged daily changes."""
    columns = {k: np.asarray(v, dtype=object) for k, v in members.columns.items()}
    state = {k: columns[k].copy() for k in ("ward_code", "address_line", "tier_code", "updated_at")}
    joins_by_day: dict[int, np.ndarray] = {}
    landing = members.landing_day()
    for day in np.unique(landing):
        joins_by_day[int(day)] = np.flatnonzero(landing == day)
    changes_by_day: dict[int, list[Change]] = {}
    for change in sorted(changes, key=lambda c: (c.day, c.member, c.when)):
        changes_by_day.setdefault(change.day, []).append(change)

    for day in sorted(set(joins_by_day) | set(changes_by_day)):
        touched = set(joins_by_day.get(day, np.empty(0, dtype=np.int64)).tolist())
        for change in changes_by_day.get(day, []):
            for field_name in ("ward_code", "address_line", "tier_code"):
                value = getattr(change, field_name)
                if value is not None:
                    state[field_name][change.member] = value
            state["updated_at"][change.member] = max(
                state["updated_at"][change.member], change.when
            )
            touched.add(change.member)
        idx = np.array(sorted(touched), dtype=np.int64)
        out = {k: v[idx] for k, v in columns.items()}
        out.update({k: v[idx] for k, v in state.items()})
        yield day, out
