from museum.generator.people import ascii_slug, unique_phones
from museum.generator.reference import PROVINCES, build_geography, build_products
from museum.generator.seeds import stream


def test_province_names_are_real_and_include_the_2025_merger_cases():
    names = {name for _, name, *_ in PROVINCES}
    assert {"Hà Nội", "Thành phố Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ"} <= names
    # Folded into another province in 2025: each must exist so the merger challenge can run.
    assert {"Bình Dương", "Bà Rịa - Vũng Tàu", "Hải Dương", "Quảng Nam", "Sóc Trăng"} <= names


def test_codes_are_unique_and_roll_up_to_one_parent():
    geo = build_geography()
    province_codes = [code for code, _ in geo.provinces]
    district_codes = [code for code, _, _ in geo.districts]
    ward_codes = [code for code, _, _ in geo.wards]
    for codes in (province_codes, district_codes, ward_codes):
        assert len(codes) == len(set(codes))
    assert {parent for _, parent, _ in geo.districts} <= set(province_codes)
    assert {parent for _, parent, _ in geo.wards} <= set(district_codes)
    assert all(geo.district_of_ward(w) == parent for w, parent, _ in geo.wards)


def test_products_have_unique_skus_and_positive_prices():
    products = build_products()
    assert len({p.sku for p in products}) == len(products)
    assert all(p.list_price > 0 and p.popularity > 0 for p in products)


def test_phones_are_unique_ten_digit_mobile_numbers():
    phones = unique_phones(stream(1, "test"), 5000)
    assert len(set(phones)) == 5000
    assert all(len(p) == 10 and p.startswith("0") for p in phones)


def test_ascii_slug_strips_vietnamese_marks():
    assert ascii_slug("Đặng Thị Hương") == "dang.thi.huong"
