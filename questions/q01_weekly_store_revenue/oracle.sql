-- Q01 reference answer, straight from the raw landing (no staging, no model).
with orders as (
    select *
    from landing_sales_order
    qualify row_number() over (
        partition by order_id order by _load_date desc, updated_at desc
    ) = 1
),

lines as (
    select *
    from landing_order_line
    qualify row_number() over (
        partition by order_id, line_no order by _load_date desc, updated_at desc
    ) = 1
),

promotions as (
    select *
    from landing_order_promotion
    qualify row_number() over (
        partition by order_id, promotion_id order by _load_date desc, updated_at desc
    ) = 1
),

gross as (
    select order_id, sum(line_amount) as amount
    from lines
    group by order_id
),

discount as (
    select order_id, sum(discount_amount) as amount
    from promotions
    group by order_id
)

select
    o.store_id,
    cast(date_trunc('week', o.ordered_at) as date) as week_start,
    cast(sum(g.amount - coalesce(d.amount, 0)) as bigint) as net_revenue
from orders as o
inner join gross as g on g.order_id = o.order_id
left join discount as d on d.order_id = o.order_id
where o.status = 'completed'
group by o.store_id, week_start
order by o.store_id, week_start
