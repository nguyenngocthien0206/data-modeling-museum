"""End-to-end checks of the generated source data.

Determinism runs on a tiny profile; the behavioural checks run once on the small profile.
"""

import hashlib

import pyarrow as pa
import pyarrow.parquet as pq

from museum.generator import generate, load_profile
from museum.generator.schemas import KEYS, SCHEMAS

from ..helpers import scalar, tiny_profile


def file_hashes(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*.parquet"))
    }


def test_same_seed_gives_byte_identical_files(tmp_path):
    first = generate(tiny_profile(), tmp_path / "a")
    second = generate(tiny_profile(), tmp_path / "b")
    assert first.rows == second.rows
    a = file_hashes(tmp_path / "a" / "tiny" / "landing")
    b = file_hashes(tmp_path / "b" / "tiny" / "landing")
    assert a and a == b


def test_parallel_run_gives_the_same_files(tmp_path):
    generate(tiny_profile(), tmp_path / "a", workers=1)
    generate(tiny_profile(), tmp_path / "b", workers=2)
    a = file_hashes(tmp_path / "a" / "tiny" / "landing")
    b = file_hashes(tmp_path / "b" / "tiny" / "landing")
    assert a == b


def test_different_seed_gives_different_data(tmp_path):
    generate(tiny_profile(), tmp_path / "a")
    generate(tiny_profile(seed=99), tmp_path / "b")
    a = file_hashes(tmp_path / "a" / "tiny" / "landing")
    b = file_hashes(tmp_path / "b" / "tiny" / "landing")
    assert a != b


def test_every_file_matches_its_table_schema(small_landing):
    load_date = pa.field("_load_date", pa.date32(), nullable=False)
    for table_name, schema in SCHEMAS.items():
        files = sorted((small_landing / table_name).rglob("*.parquet"))
        assert files, f"no extracts for {table_name}"
        expected = schema.append(load_date)
        for path in files:
            assert pq.read_schema(path).equals(expected, check_metadata=False), path


def test_every_reference_table_lands_on_the_first_day(small_landing):
    for table_name in ("province", "district", "ward", "store", "product", "channel"):
        assert (small_landing / table_name / "load_date=2024-01-01").is_dir()


def test_volumes_fall_inside_the_profile_ranges(small):
    profile = load_profile("small")
    orders = scalar(small, "select count(*) from sales_order_final")
    lines = scalar(small, "select count(*) from order_line_final")
    assert profile.expect_orders[0] <= orders <= profile.expect_orders[1]
    assert profile.expect_lines[0] <= lines <= profile.expect_lines[1]
    assert scalar(small, "select count(*) from customer_final") == profile.members


ORPHANS = {
    "line to product": "order_line anti join product using (product_id)",
    "line to order": "order_line anti join sales_order using (order_id)",
    "order to store": "sales_order anti join store using (store_id)",
    "order to member": """sales_order o where customer_id is not null
        and not exists (select 1 from customer c where c.customer_id = o.customer_id)""",
    "promotion to order": "order_promotion anti join sales_order using (order_id)",
    "promotion exists": "order_promotion anti join promotion using (promotion_id)",
    "store ward": "store anti join ward using (ward_code)",
    "member ward": "customer anti join ward using (ward_code)",
}


def test_references_resolve(small):
    for label, from_clause in ORPHANS.items():
        assert scalar(small, f"select count(*) from {from_clause}") == 0, label


def test_guests_and_members_both_order(small):
    share = scalar(small, "select avg((customer_id is not null)::int) from sales_order_final")
    assert 0.45 < share < 0.65


def test_orders_stack_promotions_without_exceeding_gross(small):
    stacked = """
        select count(*) from (
            select order_id from order_promotion_final group by 1 having count(*) >= 2
        )"""
    over = """
        with gross as (
            select order_id, sum(line_amount) as amount from order_line_final group by 1
        ),
        discount as (
            select order_id, sum(discount_amount) as amount from order_promotion_final group by 1
        )
        select count(*)
        from discount join gross using (order_id)
        where discount.amount > gross.amount"""
    assert scalar(small, stacked) > 0
    assert scalar(small, over) == 0


def test_lines_are_priced_and_distinct_within_an_order(small):
    mispriced = "select count(*) from order_line where line_amount <> quantity * unit_price"
    duplicates = """
        select count(*) from (
            select order_id, product_id from order_line_final group by all having count(*) > 1
        )"""
    assert scalar(small, mispriced) == 0
    assert scalar(small, duplicates) == 0


def test_every_cashier_is_on_a_covering_shift(small):
    uncovered = """
        select count(*) from sales_order_final o
        where not exists (
            select 1 from shift_final s
            where s.employee_id = o.cashier_employee_id and s.store_id = o.store_id
              and o.ordered_at >= s.shift_start and o.ordered_at < s.shift_end
        )"""
    assert scalar(small, uncovered) == 0


def test_no_shift_after_termination(small):
    late = """
        with leaver as (
            select employee_id, max(terminated_on) as left_on from employee group by 1
        )
        select count(*) from shift join leaver using (employee_id)
        where left_on is not null and shift_start::date > left_on"""
    assert scalar(small, late) == 0
    assert scalar(small, "select count(*) from employee where terminated_on is not null") > 0


def test_transfers_and_shift_corrections_exist(small):
    transfers = """
        select count(*) from (
            select employee_id from employee group by 1
            having count(distinct home_store_id) > 1
        )"""
    corrected = """
        select count(*) from (select shift_id from shift group by 1 having count(*) > 1)"""
    assert scalar(small, transfers) > 0
    assert scalar(small, corrected) > 0


def test_corrections_only_extend_shifts_and_land_later(small):
    bad = """
        with versions as (
            select shift_id, shift_end, _load_date,
                   lag(shift_end) over w as previous_end,
                   lag(_load_date) over w as previous_load
            from shift
            window w as (partition by shift_id order by _load_date)
        )
        select count(*) from versions
        where previous_end is not null
          and (shift_end <= previous_end or _load_date <= previous_load)"""
    assert scalar(small, bad) == 0


def test_a_key_appears_at_most_once_per_extract(small):
    for table_name, columns in KEYS.items():
        key = ", ".join(columns)
        sql = f"""
            select count(*) from (
                select {key}, _load_date from {table_name} group by all having count(*) > 1
            )"""
        assert scalar(small, sql) == 0, table_name


def test_member_phones_are_unique(small):
    sql = "select count(*) - count(distinct phone) from customer_final"
    assert scalar(small, sql) == 0
