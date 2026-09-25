"""Earthquakes as the SGC feed describes them, kept free of Home Assistant imports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta, timezone
import logging
import math
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Colombia has no daylight saving time, so a fixed offset is exact.
COLOMBIA_TIME = timezone(timedelta(hours=-5))

# Intensity prediction equation of Allen, Wald and Worden (2012), "Intensity
# attenuation for active crustal regions", J. Seismology 16: 409-433, in the
# hypocentral distance version, with the coefficients of OpenQuake's
# AllenEtAl2012Rhypo. It estimates the Modified Mercalli Intensity (MMI) at a
# place from the magnitude and the distance to the hypocenter.
_C0, _C1, _C2, _C4, _M1, _M2 = 2.085, 1.428, -1.402, 0.078, -0.209, 2.042
# Automatic solutions often give a depth of 0 km, and at almost no distance the
# equation gives unrealistic values for small earthquakes.
MINIMUM_HYPOCENTRAL_KM = 5.0

# Upper limits of the Modified Mercalli levels, named with the USGS ShakeMap
# words. Damage per ShakeMap: none up to IV, very light at V, light at VI,
# moderate at VII, and heavier above.
SHAKING_LEVELS: tuple[tuple[float, str], ...] = (
	(1.5, "not_felt"),
	(3.5, "weak"),
	(4.5, "light"),
	(5.5, "moderate"),
	(6.5, "strong"),
	(7.5, "very_strong"),
	(8.5, "severe"),
	(9.5, "violent"),
)
SHAKING_EXTREME = "extreme"
# Green: hardly noticed. Yellow: clearly felt, at most very light damage.
# Orange: light damage possible. Red: damage likely. The names work both as CSS
# colors and as Home Assistant card colors.
SHAKING_COLORS = {
	"not_felt": "green",
	"weak": "green",
	"light": "yellow",
	"moderate": "yellow",
	"strong": "orange",
}
SHAKING_COLOR_DAMAGE = "red"


def estimated_intensity(magnitude: float, distance_km: float, depth_km: float | None) -> float:
	"""The estimated shaking (MMI, 1 to 12) at a place this far from the earthquake."""
	hypocentral = max(math.hypot(distance_km, depth_km or 0.0), MINIMUM_HYPOCENTRAL_KM)
	near_source = _M1 + _M2 * math.exp(magnitude - 5)
	intensity = _C0 + _C1 * magnitude + _C2 * math.log(math.hypot(hypocentral, near_source))
	if hypocentral > 50:
		intensity += _C4 * math.log(hypocentral / 50)
	return min(max(intensity, 1.0), 12.0)


def shaking_level(intensity: float) -> str:
	"""The ShakeMap word for an intensity, for example "weak" for 2.0."""
	return next((level for limit, level in SHAKING_LEVELS if intensity < limit), SHAKING_EXTREME)


def level_start(level: str) -> float:
	"""The lowest intensity that counts as this level, for example 1.5 for "weak"."""
	starts = [1.0] + [limit for limit, _ in SHAKING_LEVELS]
	levels = [name for _, name in SHAKING_LEVELS] + [SHAKING_EXTREME]
	return starts[levels.index(level)]


def shaking_color(level: str) -> str:
	"""Green, yellow, orange or red for a level."""
	return SHAKING_COLORS.get(level, SHAKING_COLOR_DAMAGE)


@dataclass(frozen=True, kw_only=True, slots=True)
class Earthquake:
	"""One earthquake from the feed."""

	id: str
	latitude: float
	longitude: float
	depth_km: float | None
	magnitude: float
	magnitude_type: str | None
	place: str
	nearby_towns: str | None
	time: datetime
	updated: datetime | None
	status: str | None
	agency: str | None
	felt_reports: int | None
	intensity: int | None

	@property
	def title(self) -> str:
		"""The name shown in Home Assistant, like the USGS integration writes it."""
		return f"M {self.magnitude:.1f} - {self.place}"

	@property
	def intensity_level(self) -> str | None:
		"""SGC's measured intensity as a ShakeMap word, for example "weak" for 3."""
		return shaking_level(self.intensity) if self.intensity else None

	@property
	def time_source(self) -> str:
		"""The time in Colombia, as SGC shows it, for example "2026/09/23 04:04 AM".

		Year first like ISO, but with slashes on purpose: the frontend treats text
		that starts with yyyy-MM-dd as a date and converts it to the viewer's time
		zone, and this must stay Colombian time. AM and PM are written out, since
		strftime's %p depends on the system locale.
		"""
		local = self.time.astimezone(COLOMBIA_TIME)
		hour = local.hour % 12 or 12
		half = "AM" if local.hour < 12 else "PM"
		return f"{local:%Y/%m/%d} {hour:02d}:{local:%M} {half}"


@dataclass(frozen=True, kw_only=True, slots=True)
class NearbyEarthquake:
	"""An earthquake inside the zone, with its distance and estimated shaking at the zone center."""

	quake: Earthquake
	distance_km: float
	intensity: float

	@property
	def shaking(self) -> str:
		"""The estimated shaking at the zone center as a ShakeMap level."""
		return shaking_level(self.intensity)

	@property
	def color(self) -> str:
		"""Green, yellow, orange or red for the estimated shaking."""
		return shaking_color(self.shaking)


def quake_to_dict(quake: Earthquake) -> dict[str, Any]:
	"""An earthquake as plain JSON data, to keep it across restarts."""
	data = asdict(quake)
	data["time"] = quake.time.isoformat()
	data["updated"] = quake.updated.isoformat() if quake.updated else None
	return data


def quake_from_dict(data: Mapping[str, Any]) -> Earthquake:
	"""The earthquake saved by quake_to_dict. Raises on data it cannot read."""
	known = {field.name for field in fields(Earthquake)}
	values = {key: value for key, value in data.items() if key in known}
	values["time"] = datetime.fromisoformat(values["time"])
	if values.get("updated"):
		values["updated"] = datetime.fromisoformat(values["updated"])
	return Earthquake(**values)


def parse_feed(payload: Any) -> dict[str, Earthquake]:
	"""Read every usable earthquake from the feed, keyed by its id.

	A feature that cannot be read is skipped, so one bad row does not hide the rest.
	"""
	if not isinstance(payload, Mapping) or not isinstance(
		features := payload.get("features"), list
	):
		raise ValueError("The feed is not a GeoJSON FeatureCollection")
	quakes: dict[str, Earthquake] = {}
	skipped = 0
	for feature in features:
		try:
			quake = _parse_feature(feature)
		except (KeyError, IndexError, TypeError, ValueError):
			skipped += 1
			continue
		quakes[quake.id] = quake
	if skipped:
		_LOGGER.debug("Skipped %s of %s features that could not be read", skipped, len(features))
	return quakes


def _parse_feature(feature: Mapping[str, Any]) -> Earthquake:
	"""Read one feature, raising on anything the integration depends on."""
	props = feature["properties"]
	quake_id = feature["id"]
	if not isinstance(quake_id, str) or not quake_id:
		raise ValueError("Missing id")
	# The SGC feed stores [latitude, longitude, depth in km], the reverse of the
	# GeoJSON standard. The SGC web page reads them in this order too.
	coordinates = feature["geometry"]["coordinates"]
	latitude = _number(coordinates[0])
	longitude = _number(coordinates[1])
	if latitude is None or longitude is None:
		raise ValueError("Missing coordinates")
	if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
		raise ValueError("Coordinates out of range")
	magnitude = _number(props["mag"])
	if magnitude is None:
		raise ValueError("Missing magnitude")
	intensity = _integer(props.get("mmi"))
	return Earthquake(
		id=quake_id,
		latitude=latitude,
		longitude=longitude,
		depth_km=_number(coordinates[2]) if len(coordinates) > 2 else None,
		magnitude=magnitude,
		magnitude_type=_text(props.get("magType")),
		place=_text(props.get("place")) or "Unknown place",
		nearby_towns=_text(props.get("closerTowns")),
		# utcTime is UTC and has no seconds, for example "2026-09-23 09:23".
		time=_time(props["utcTime"], UTC),
		# updated is Colombia time, for example "2026-09-23 04:32:21".
		updated=_optional_time(props.get("updated"), COLOMBIA_TIME),
		status=_text(props.get("status")),
		agency=_text(props.get("agency")),
		felt_reports=_integer(props.get("felt")),
		# The feed writes 0 when no intensity was measured.
		intensity=intensity or None,
	)


def _number(value: Any) -> float | None:
	if isinstance(value, bool) or not isinstance(value, int | float):
		return None
	return float(value)


def _integer(value: Any) -> int | None:
	if isinstance(value, bool) or not isinstance(value, int):
		return None
	return value


def _text(value: Any) -> str | None:
	"""Tidy the spacing the feed sometimes has, as in "Ecuador - Colombia , Region"."""
	if not isinstance(value, str):
		return None
	text = " ".join(value.split()).replace(" ,", ",")
	return text or None


def _time(value: Any, zone: timezone) -> datetime:
	if not isinstance(value, str):
		raise ValueError("Missing time")
	parsed = datetime.fromisoformat(value.strip())
	if parsed.tzinfo is None:
		parsed = parsed.replace(tzinfo=zone)
	return parsed.astimezone(UTC)


def _optional_time(value: Any, zone: timezone) -> datetime | None:
	try:
		return _time(value, zone)
	except ValueError:
		return None
