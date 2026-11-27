"""Employees over time, and the daily shifts that staff each store.

Shift rows have one employee each. Every order's cashier is drawn from the shift that
covers the order time, so shift corrections may only extend a shift: a later clock-out
fixed after the fact never leaves an order without a covering shift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from museum.generator.config import Profile
from museum.generator.people import NamePools
from museum.generator.reference import INITIAL_LOAD_AT, Store

OPEN_SECOND, CLOSE_SECOND = 6 * 3600, 22 * 3600
TWO_SLOTS = ((6 * 3600, 14 * 3600), (14 * 3600, 22 * 3600))
THREE_SLOTS = ((6 * 3600, 12 * 3600), (12 * 3600, 17 * 3600), (17 * 3600, 22 * 3600))
BUSY_STORE_ORDERS = 120  # stores expecting this many orders a day run three shifts
EXTRA_STAFF = 2
CORRECTION_LAG_DAYS = (1, 5)
CORRECTION_MINUTES = (15, 30, 45, 60)


def store_slots(profile: Profile, store: Store) -> tuple[tuple[int, int], ...]:
    busy = profile.orders_per_store_day * store.size >= BUSY_STORE_ORDERS
    return THREE_SLOTS if busy else TWO_SLOTS


def daily_rate(monthly: float) -> float:
    return 1 - (1 - monthly) ** (1 / 30)


def _office_hours(day: date, rng: np.random.Generator) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(
        seconds=int(rng.integers(9 * 3600, 17 * 3600))
    )


@dataclass
class Workforce:
    rows_by_day: dict[int, list[dict]] = field(default_factory=dict)  # employee versions
    roster: list[list[list[int]]] = field(default_factory=list)  # [day][store] -> ids
    hired_on: dict[int, date] = field(default_factory=dict)
    terminated_on: dict[int, date] = field(default_factory=dict)
    transfers: int = 0

    def land(self, day: int, row: dict) -> None:
        self.rows_by_day.setdefault(day, []).append(dict(row))


def build_workforce(
    profile: Profile, stores: list[Store], pools: NamePools, rng: np.random.Generator
) -> Workforce:
    workforce = Workforce()
    employees: dict[int, dict] = {}
    hires_due: dict[int, list[tuple[int, str]]] = {}

    def hire(store: int, role: str, hired_on: date, landing_day: int, at: datetime) -> None:
        gender = "F" if rng.random() < 0.5 else "M"
        employee_id = len(employees) + 1
        row = {
            "employee_id": employee_id,
            "full_name": pools.full_names(rng, np.array([gender]))[0],
            "home_store_id": stores[store].store_id,
            "role": role,
            "hired_on": hired_on,
            "terminated_on": None,
            "created_at": at,
            "updated_at": at,
        }
        employees[employee_id] = {"row": row, "store": store}
        workforce.hired_on[employee_id] = hired_on
        workforce.land(landing_day, row)

    for store in stores:
        staff = len(store_slots(profile, store)) * profile.staff_per_slot + EXTRA_STAFF
        roles = ["store_manager"] + ["barista"] * (staff // 2) + ["cashier"] * staff
        for role in roles[:staff]:
            earliest = (store.opened_on - date(2019, 1, 1)).days
            hired_on = date(2019, 1, 1) + timedelta(
                days=int(rng.integers(earliest, (profile.start - date(2019, 1, 1)).days))
            )
            hire(store.index, role, hired_on, 0, INITIAL_LOAD_AT)

    p_leave = daily_rate(profile.monthly_turnover)
    p_move = daily_rate(profile.monthly_transfer) if len(stores) > 1 else 0.0
    active = sorted(employees)
    for d in range(profile.n_days):
        today = profile.day(d)
        for store, role in hires_due.pop(d, []):
            hire(store, role, today, d, _office_hours(today, rng))
            active.append(len(employees))
        settled = [e for e in active if workforce.hired_on[e] < today]
        leave = rng.random(len(settled)) < p_leave
        move = rng.random(len(settled)) < p_move
        leaving = set()
        for employee_id, quits, moves in zip(settled, leave, move, strict=True):
            record = employees[employee_id]
            if quits:
                record["row"]["terminated_on"] = today
                record["row"]["updated_at"] = _office_hours(today, rng)
                workforce.terminated_on[employee_id] = today
                workforce.land(d, record["row"])
                leaving.add(employee_id)
                gap = int(rng.integers(3, 15))
                hires_due.setdefault(d + gap, []).append((record["store"], record["row"]["role"]))
            elif moves:
                others = [s.index for s in stores if s.index != record["store"]]
                record["store"] = int(rng.choice(others))
                record["row"]["home_store_id"] = stores[record["store"]].store_id
                record["row"]["updated_at"] = _office_hours(today, rng)
                workforce.land(d, record["row"])
                workforce.transfers += 1
        roster: list[list[int]] = [[] for _ in stores]
        for employee_id in active:
            roster[employees[employee_id]["store"]].append(employee_id)
        workforce.roster.append(roster)
        active = [e for e in active if e not in leaving]
    return workforce


@dataclass
class DayShifts:
    columns: dict
    slot_staff: list[list[np.ndarray]]  # [store][slot] -> employee ids on that slot
    corrections: list[tuple[int, dict]]  # (landing day, corrected row)


def build_day_shifts(
    profile: Profile,
    stores: list[Store],
    workforce: Workforce,
    day_index: int,
    rng: np.random.Generator,
) -> DayShifts:
    today = profile.day(day_index)
    midnight = datetime.combine(today, datetime.min.time())
    rows: dict[str, list] = {k: [] for k in ("shift_id", "store_id", "employee_id")}
    rows.update(shift_start=[], shift_end=[])
    slot_staff: list[list[np.ndarray]] = []
    corrections: list[tuple[int, dict]] = []
    for store in stores:
        slots = store_slots(profile, store)
        roster = np.array(workforce.roster[day_index][store.index], dtype=np.int64)
        if len(roster) == 0:
            raise RuntimeError(f"store {store.store_code} has no staff on {today}")
        wanted = len(slots) * profile.staff_per_slot
        on_duty = rng.permutation(roster)[:wanted]
        per_slot = [on_duty[i :: len(slots)] for i in range(len(slots))]
        per_slot = [s if len(s) else rng.choice(roster, size=1) for s in per_slot]
        slot_staff.append(per_slot)
        counter = 0
        for (start, end), staff in zip(slots, per_slot, strict=True):
            for employee_id in staff:
                counter += 1
                shift_id = (day_index + 1) * 100_000 + store.index * 100 + counter
                begins = midnight + timedelta(seconds=start)
                ends = midnight + timedelta(seconds=end)
                rows["shift_id"].append(shift_id)
                rows["store_id"].append(store.store_id)
                rows["employee_id"].append(int(employee_id))
                rows["shift_start"].append(begins)
                rows["shift_end"].append(ends)
                if rng.random() < profile.shift_correction_rate:
                    lag = int(rng.integers(*CORRECTION_LAG_DAYS, endpoint=True))
                    if day_index + lag < profile.n_days:
                        fixed_on = profile.day(day_index + lag)
                        extra = timedelta(minutes=int(rng.choice(CORRECTION_MINUTES)))
                        row = {
                            "shift_id": shift_id,
                            "store_id": store.store_id,
                            "employee_id": int(employee_id),
                            "shift_start": begins,
                            "shift_end": ends + extra,
                            "created_at": begins,
                            "updated_at": _office_hours(fixed_on, rng),
                        }
                        corrections.append((day_index + lag, row))
    starts = rows["shift_start"]
    rows["created_at"] = list(starts)
    rows["updated_at"] = list(starts)
    return DayShifts(rows, slot_staff, corrections)
