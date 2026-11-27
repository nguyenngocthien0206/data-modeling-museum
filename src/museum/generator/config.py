"""Scale profiles: how big the simulated coffee chain is and how it behaves."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import resources
from pathlib import Path

import yaml

PROFILE_NAMES = ("small", "medium", "large")
MIN_DAYS_FOR_STORE_CHANGES = 150  # openings fall in [60, n-60], closings in [90, n-30]


class ProfileError(ValueError):
    """A profile file is missing a value or has one out of range."""


@dataclass(frozen=True)
class Profile:
    name: str
    seed: int
    start: date
    end: date
    stores: int  # open on the first day
    new_stores: int  # opened during the period
    closed_stores: int  # closed during the period
    orders_per_store_day: float
    extra_lines_per_order: float
    members: int
    guest_share: float
    promo_one: float
    promo_two: float
    promo_three: float
    promotions_per_month: float
    staff_per_slot: int
    monthly_turnover: float
    monthly_transfer: float
    shift_correction_rate: float
    address_move_monthly: float
    price_changes: int  # individual product price changes, on top of chain-wide rounds
    price_override_share: float
    promotion_edit_share: float
    late_store_day_share: float
    correction_share: float
    expect_orders: tuple[int, int]
    expect_lines: tuple[int, int]

    @property
    def n_days(self) -> int:
        return (self.end - self.start).days + 1

    def day(self, index: int) -> date:
        return self.start + timedelta(days=index)

    def with_changes(self, **changes) -> Profile:
        profile = dataclasses.replace(self, **changes)
        profile.validate()
        return profile

    def validate(self) -> None:
        if self.end <= self.start:
            raise ProfileError("period end must be after period start")
        for name in ("stores", "members", "staff_per_slot"):
            if getattr(self, name) < 1:
                raise ProfileError(f"{name} must be at least 1")
        for name in ("new_stores", "closed_stores", "price_changes"):
            if getattr(self, name) < 0:
                raise ProfileError(f"{name} cannot be negative")
        if self.closed_stores >= self.stores:
            raise ProfileError("closed_stores must leave at least one original store open")
        if (self.new_stores or self.closed_stores) and self.n_days < MIN_DAYS_FOR_STORE_CHANGES:
            raise ProfileError(
                f"opening or closing stores needs a period of {MIN_DAYS_FOR_STORE_CHANGES} days"
            )
        if self.orders_per_store_day <= 0:
            raise ProfileError("orders_per_store_day must be positive")
        rates = (
            "guest_share",
            "promo_one",
            "promo_two",
            "promo_three",
            "monthly_turnover",
            "monthly_transfer",
            "shift_correction_rate",
            "address_move_monthly",
            "price_override_share",
            "promotion_edit_share",
            "late_store_day_share",
            "correction_share",
        )
        for name in rates:
            if not 0 <= getattr(self, name) <= 1:
                raise ProfileError(f"{name} must be between 0 and 1")
        if self.promo_one + self.promo_two + self.promo_three > 1:
            raise ProfileError("promotion shares must add up to at most 1")
        for name in ("expect_orders", "expect_lines"):
            low, high = getattr(self, name)
            if low > high:
                raise ProfileError(f"{name} range is reversed")


def _require(raw: dict, *keys: str):
    value = raw
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ProfileError(f"profile is missing {'.'.join(keys)}")
        value = value[key]
    return value


def parse_profile(raw: dict) -> Profile:
    def number(kind, *keys):
        return kind(_require(raw, *keys))

    profile = Profile(
        name=str(_require(raw, "name")),
        seed=number(int, "seed"),
        start=_require(raw, "period", "start"),
        end=_require(raw, "period", "end"),
        stores=number(int, "stores", "at_start"),
        new_stores=number(int, "stores", "opened"),
        closed_stores=number(int, "stores", "closed"),
        orders_per_store_day=number(float, "orders_per_store_day"),
        extra_lines_per_order=number(float, "extra_lines_per_order"),
        members=number(int, "members"),
        guest_share=number(float, "guest_share"),
        promo_one=number(float, "promotion_shares", "one"),
        promo_two=number(float, "promotion_shares", "two"),
        promo_three=number(float, "promotion_shares", "three"),
        promotions_per_month=number(float, "promotions_per_month"),
        staff_per_slot=number(int, "workforce", "staff_per_slot"),
        monthly_turnover=number(float, "workforce", "monthly_turnover"),
        monthly_transfer=number(float, "workforce", "monthly_transfer"),
        shift_correction_rate=number(float, "workforce", "shift_correction_rate"),
        address_move_monthly=number(float, "history", "address_move_monthly"),
        price_changes=number(int, "history", "price_changes"),
        price_override_share=number(float, "history", "price_override_share"),
        promotion_edit_share=number(float, "history", "promotion_edit_share"),
        late_store_day_share=number(float, "delivery", "late_store_day_share"),
        correction_share=number(float, "delivery", "correction_share"),
        expect_orders=tuple(_require(raw, "expect", "orders")),
        expect_lines=tuple(_require(raw, "expect", "order_lines")),
    )
    if not isinstance(profile.start, date) or not isinstance(profile.end, date):
        raise ProfileError("period start and end must be dates (YYYY-MM-DD)")
    profile.validate()
    return profile


def load_profile(name_or_path: str | Path, seed: int | None = None) -> Profile:
    """Load a bundled profile by name, or a profile file by path."""
    if str(name_or_path) in PROFILE_NAMES:
        files = resources.files("museum.generator") / "profiles" / f"{name_or_path}.yaml"
        text = files.read_text(encoding="utf-8")
    else:
        text = Path(name_or_path).read_text(encoding="utf-8")
    profile = parse_profile(yaml.safe_load(text))
    return profile if seed is None else profile.with_changes(seed=seed)
