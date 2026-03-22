from __future__ import annotations

import random
from dataclasses import dataclass

from simulator.config import GeoBounds


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float


class GeoSampler:
    def __init__(self, bounds: GeoBounds, seed: int | None = None) -> None:
        self._bounds = bounds
        self._rng = random.Random(seed)

    def sample(self) -> GeoPoint:
        lat = self._rng.uniform(self._bounds.min_lat, self._bounds.max_lat)
        lng = self._rng.uniform(self._bounds.min_lng, self._bounds.max_lng)
        return GeoPoint(lat=lat, lng=lng)
