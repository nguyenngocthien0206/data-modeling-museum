"""Arrow schemas of the simulated source tables (design section 3.1)."""

from __future__ import annotations

import pyarrow as pa

TIMESTAMP = pa.timestamp("us")


def _field(name: str, kind: pa.DataType, nullable: bool = False) -> pa.Field:
    return pa.field(name, kind, nullable=nullable)


def _table(*fields: pa.Field) -> pa.Schema:
    audit = (_field("created_at", TIMESTAMP), _field("updated_at", TIMESTAMP))
    return pa.schema([*fields, *audit])


S, I64, I32, DATE, BOOL = pa.string(), pa.int64(), pa.int32(), pa.date32(), pa.bool_()

SCHEMAS: dict[str, pa.Schema] = {
    "province": _table(_field("province_code", S), _field("province_name", S)),
    "district": _table(
        _field("district_code", S), _field("province_code", S), _field("district_name", S)
    ),
    "ward": _table(_field("ward_code", S), _field("district_code", S), _field("ward_name", S)),
    "store": _table(
        _field("store_id", I64),
        _field("store_code", S),
        _field("store_name", S),
        _field("ward_code", S),
        _field("address_line", S),
        _field("opened_on", DATE),
        _field("closed_on", DATE, nullable=True),
        _field("status", S),
    ),
    "channel": _table(_field("channel_code", S), _field("channel_name", S)),
    "membership_tier": _table(
        _field("tier_code", S),
        _field("tier_name", S),
        _field("rank", I32),
        _field("min_spend_12m", I64),
    ),
    "customer": _table(
        _field("customer_id", I64),
        _field("full_name", S),
        _field("phone", S),
        _field("email", S),
        _field("date_of_birth", DATE),
        _field("gender", S),
        _field("address_line", S),
        _field("ward_code", S),
        _field("tier_code", S),
        _field("joined_at", TIMESTAMP),
    ),
    "product_category": _table(_field("category_id", I64), _field("category_name", S)),
    "product": _table(
        _field("product_id", I64),
        _field("sku", S),
        _field("product_name", S),
        _field("category_id", I64),
        _field("size", S, nullable=True),
        _field("list_price", I64),
        _field("is_active", BOOL),
    ),
    "promotion": _table(
        _field("promotion_id", I64),
        _field("promo_code", S),
        _field("promo_name", S),
        _field("promo_type", S),
        _field("promo_value", I64),
        _field("starts_on", DATE),
        _field("ends_on", DATE),
    ),
    "employee": _table(
        _field("employee_id", I64),
        _field("full_name", S),
        _field("home_store_id", I64),
        _field("role", S),
        _field("hired_on", DATE),
        _field("terminated_on", DATE, nullable=True),
    ),
    "shift": _table(
        _field("shift_id", I64),
        _field("store_id", I64),
        _field("employee_id", I64),
        _field("shift_start", TIMESTAMP),
        _field("shift_end", TIMESTAMP),
    ),
    "sales_order": _table(
        _field("order_id", I64),
        _field("store_id", I64),
        _field("customer_id", I64, nullable=True),
        _field("cashier_employee_id", I64),
        _field("channel_code", S),
        _field("ordered_at", TIMESTAMP),
        _field("status", S),
    ),
    "order_line": _table(
        _field("order_id", I64),
        _field("line_no", I32),
        _field("product_id", I64),
        _field("quantity", I32),
        _field("unit_price", I64),
        _field("line_amount", I64),
    ),
    "order_promotion": _table(
        _field("order_id", I64), _field("promotion_id", I64), _field("discount_amount", I64)
    ),
}

KEYS: dict[str, tuple[str, ...]] = {
    "province": ("province_code",),
    "district": ("district_code",),
    "ward": ("ward_code",),
    "store": ("store_id",),
    "channel": ("channel_code",),
    "membership_tier": ("tier_code",),
    "customer": ("customer_id",),
    "product_category": ("category_id",),
    "product": ("product_id",),
    "promotion": ("promotion_id",),
    "employee": ("employee_id",),
    "shift": ("shift_id",),
    "sales_order": ("order_id",),
    "order_line": ("order_id", "line_no"),
    "order_promotion": ("order_id", "promotion_id"),
}
