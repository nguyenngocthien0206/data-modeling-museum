from datetime import date

import pytest

from museum.generator.config import PROFILE_NAMES, ProfileError, load_profile


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_bundled_profiles_load_and_cover_the_base_period(name):
    profile = load_profile(name)
    assert profile.name == name
    assert profile.start == date(2024, 1, 1)
    assert profile.end == date(2025, 6, 30)
    assert profile.n_days == 547


def test_profiles_grow_with_scale():
    small, medium, large = (load_profile(n) for n in PROFILE_NAMES)
    assert small.stores < medium.stores < large.stores
    assert small.expect_lines[1] < medium.expect_lines[0] < large.expect_lines[0]


def test_seed_override():
    assert load_profile("small", seed=7).seed == 7


@pytest.mark.parametrize(
    "change",
    [
        {"guest_share": 1.5},
        {"stores": 0},
        {"promo_one": 0.6, "promo_two": 0.3, "promo_three": 0.2},
        {"end": date(2023, 1, 1)},
        {"expect_orders": (10, 1)},
    ],
)
def test_invalid_values_are_rejected(change):
    with pytest.raises(ProfileError):
        load_profile("small").with_changes(**change)


def test_missing_key_is_reported(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("name: broken\nseed: 1\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="period.start"):
        load_profile(path)
