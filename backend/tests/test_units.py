from app.services.units import canonical_unit, resolve_category_unit, same_unit


def test_synonym_units_match():
    assert same_unit("kWh", "kilowatt hour")
    assert same_unit("kilowatt-hour", "kWh")
    assert same_unit("kilogram", "kg")
    assert canonical_unit("kg·km") == canonical_unit("kg*km")
    assert not same_unit("kWh", "kg")


def test_resolve_category_unit_from_datasets():
    assert resolve_category_unit("kg", ["kWh", "kilowatt hour"], energy=True) == "kWh"
    assert resolve_category_unit("kg", ["kWh", "MJ"], energy=True) == "kg"
    assert resolve_category_unit("kg", [], energy=True) == "kWh"
    assert resolve_category_unit("MJ", [], energy=True) == "MJ"
    assert resolve_category_unit("kg", [], energy=False) == "kg"
