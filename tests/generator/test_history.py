"""History in the source: overwrite-style changes, late arrival, corrections, truth manifest."""

import json

import pytest

from museum.generator import load_profile
from museum.generator.config import ProfileError
from museum.generator.schemas import KEYS

from ..helpers import scalar

PROFILE = load_profile("small")

FIRST_VERSION = "qualify row_number() over (partition by {keys} order by _load_date) = 1"


def first(table_name: str) -> str:
    keys = ", ".join(KEYS[table_name])
    return f"(select * from {table_name} {FIRST_VERSION.format(keys=keys)})"


def test_member_tiers_move_both_ways(small):
    moves = small.execute(
        """
        with versions as (
            select c.customer_id, t.rank,
                   lag(t.rank) over (partition by c.customer_id order by c._load_date) as before
            from customer c join membership_tier_final t using (tier_code)
        )
        select sum((rank > before)::int), sum((rank < before)::int) from versions"""
    ).fetchone()
    upgrades, downgrades = moves
    assert upgrades > 0 and downgrades > 0


def test_members_move_house(small):
    moved = """
        select count(*) from (
            select customer_id from customer group by 1 having count(distinct ward_code) > 1
        )"""
    assert scalar(small, moved) > 0


def test_some_product_changes_price_at_least_twice(small):
    sql = """
        select max(prices) from (
            select product_id, count(distinct list_price) as prices from product group by 1
        )"""
    assert scalar(small, sql) >= 3


def test_stores_open_and_close_during_the_period(small):
    histories = {
        row[0]
        for row in small.execute(
            "select string_agg(status, '>' order by _load_date) from store group by store_id"
        ).fetchall()
    }
    assert "planned>open" in histories
    assert "open>closed" in histories


def test_no_order_outside_the_store_open_interval(small):
    outside = """
        select count(*) from sales_order o join store_final s using (store_id)
        where o.ordered_at::date < s.opened_on
           or (s.closed_on is not null and o.ordered_at::date >= s.closed_on)"""
    assert scalar(small, outside) == 0


def test_lines_follow_the_list_price_in_effect_except_overrides(small):
    sql = f"""
        with line as (select * from {first("order_line")}),
             header as (select order_id, ordered_at from {first("sales_order")}),
             priced as (
                 select l.unit_price,
                        (select p.list_price from product p
                         where p.product_id = l.product_id and p.updated_at <= h.ordered_at
                         order by p.updated_at desc limit 1) as list_price
                 from line l join header h using (order_id)
             )
        select avg((unit_price <> list_price)::int), sum((unit_price > list_price)::int)
        from priced"""
    override_share, above_list = small.execute(sql).fetchone()
    assert above_list == 0
    assert 0.5 * PROFILE.price_override_share < override_share < 2 * PROFILE.price_override_share


def test_late_share_matches_the_profile(small):
    sql = f"select avg((_load_date > ordered_at::date)::int) from {first('sales_order')}"
    share = scalar(small, sql)
    expected = PROFILE.late_store_day_share
    assert 0.5 * expected < share < 1.5 * expected


def test_late_rows_keep_the_sale_time_and_carry_the_sync_time(small):
    bad = f"""
        select count(*) from {first("sales_order")}
        where _load_date > ordered_at::date
          and (created_at <> ordered_at or updated_at::date <> _load_date)"""
    assert scalar(small, bad) == 0


def test_corrected_share_matches_the_profile(small):
    sql = """
        with corrected as (
            select order_id from sales_order group by 1 having count(*) > 1
            union select order_id from order_line group by order_id, line_no having count(*) > 1
            union select order_id from order_promotion
                  group by order_id, promotion_id having count(*) > 1
        )
        select count(distinct order_id) * 1.0 / (select count(*) from sales_order_final)
        from corrected"""
    share = scalar(small, sql)
    expected = PROFILE.correction_share
    assert 0.5 * expected < share < 1.5 * expected
    assert scalar(small, "select count(*) from sales_order_final where status = 'voided'") > 0


@pytest.mark.parametrize("table_name", sorted(KEYS))
def test_the_latest_extract_holds_the_latest_update(small, table_name):
    keys = ", ".join(KEYS[table_name])
    sql = f"""
        select count(*) from (
            select _load_date, updated_at,
                   max(updated_at) over (partition by {keys}) as newest_update,
                   max(_load_date) over (partition by {keys}) as newest_load
            from {table_name}
        )
        where _load_date = newest_load and updated_at <> newest_update"""
    assert scalar(small, sql) == 0


def test_manifest_matches_a_recount_of_the_final_rows(small, small_manifest):
    manifest = json.loads(small_manifest.read_text(encoding="utf-8"))
    recount = small.execute(
        """
        with gross as (
                 select order_id, sum(line_amount) as amount
                 from order_line_final group by 1
             ),
             discount as (
                 select order_id, sum(discount_amount) as amount
                 from order_promotion_final group by 1
             )
        select o.ordered_at::date as day, count(*) as orders,
               sum(gross.amount - coalesce(discount.amount, 0)) as net
        from sales_order_final o
        join gross using (order_id) left join discount using (order_id)
        where o.status = 'completed'
        group by 1 order by 1"""
    ).fetchall()
    by_day = {day.isoformat(): (orders, net) for day, orders, net in recount}
    assert manifest["orders"]["completed"] == sum(orders for orders, _ in by_day.values())
    assert manifest["net_revenue"]["total"] == sum(net for _, net in by_day.values())
    assert {d: v[1] for d, v in by_day.items()} == manifest["net_revenue"]["by_order_date"]
    landed = scalar(small, "select count(*) from sales_order_final")
    assert manifest["orders"]["landed"] == landed
    for table_name, rows in manifest["rows"].items():
        assert scalar(small, f"select count(*) from {table_name}") == rows, table_name


def test_manifest_records_the_history_it_simulated(small_manifest):
    history = json.loads(small_manifest.read_text(encoding="utf-8"))["history"]
    assert history["tier_upgrades"] > 0 and history["tier_downgrades"] > 0
    assert history["price_changes"] > 0 and history["address_moves"] > 0
    assert history["store_openings"] == PROFILE.new_stores
    assert history["store_closings"] == PROFILE.closed_stores


def test_short_periods_cannot_open_or_close_stores():
    with pytest.raises(ProfileError, match="period"):
        PROFILE.with_changes(end=PROFILE.start.replace(month=3))
