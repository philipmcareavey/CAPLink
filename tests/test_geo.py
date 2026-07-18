from app.services.geo import haversine_distance_miles


def test_distance_to_self_is_zero():
    assert haversine_distance_miles(53.4808, -2.2426, 53.4808, -2.2426) == 0.0


def test_distance_is_symmetric():
    a = (53.4808, -2.2426)  # Manchester
    b = (51.5074, -0.1278)  # London
    d1 = haversine_distance_miles(*a, *b)
    d2 = haversine_distance_miles(*b, *a)
    assert abs(d1 - d2) < 1e-9


def test_manchester_to_london_is_roughly_correct():
    # Known real-world distance is ~163 miles as the crow flies — assert a
    # generous range rather than an exact figure to avoid brittle precision assumptions.
    distance = haversine_distance_miles(53.4808, -2.2426, 51.5074, -0.1278)
    assert 150 < distance < 175


def test_short_distance_within_a_city():
    # University of Manchester campus to Manchester city centre — roughly 1-2 miles
    distance = haversine_distance_miles(53.4668, -2.2339, 53.4794, -2.2453)
    assert 0.5 < distance < 3.0
