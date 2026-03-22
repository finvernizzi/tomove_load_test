from simulator.config import GeoBounds
from simulator.geo import GeoSampler


def test_geo_sampler_within_bounds() -> None:
    bounds = GeoBounds(min_lat=45.0, max_lat=46.0, min_lng=7.0, max_lng=8.0)
    sampler = GeoSampler(bounds, seed=123)

    for _ in range(100):
        point = sampler.sample()
        assert 45.0 <= point.lat <= 46.0
        assert 7.0 <= point.lng <= 8.0
