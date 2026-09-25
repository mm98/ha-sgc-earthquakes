"""Sensors that sum up the earthquakes inside the zone, now and since setup."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
	SensorEntity,
	SensorEntityDescription,
	SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_URL, MANUFACTURER, SGC_EARTHQUAKES_PAGE
from .coordinator import SgcConfigEntry, SgcCoordinator
from .models import Earthquake, NearbyEarthquake, quake_from_dict, quake_to_dict

# Nothing is polled per entity, the coordinator pushes every update.
PARALLEL_UPDATES = 0

type Rank = Callable[[NearbyEarthquake], tuple[Any, ...]]


def _time_rank(nearby: NearbyEarthquake) -> tuple[Any, ...]:
	return (nearby.quake.time,)


def _magnitude_rank(nearby: NearbyEarthquake) -> tuple[Any, ...]:
	return (nearby.quake.magnitude, nearby.quake.time)


def _shaking_rank(nearby: NearbyEarthquake) -> tuple[Any, ...]:
	return (nearby.intensity, nearby.quake.time)


def _magnitude(nearby: NearbyEarthquake) -> float:
	return nearby.quake.magnitude


def _shaking(nearby: NearbyEarthquake) -> float:
	return round(nearby.intensity, 1)


def _details(coordinator: SgcCoordinator, nearby: NearbyEarthquake | None) -> dict[str, Any]:
	if nearby is None:
		return {}
	quake = nearby.quake
	return {
		"place": quake.place,
		"magnitude": quake.magnitude,
		"shaking": nearby.shaking,
		"shaking_mmi": round(nearby.intensity, 1),
		"color": nearby.color,
		"time": quake.time,
		"time_source": quake.time_source,
		"distance_km": round(nearby.distance_km, 1),
		"depth_km": quake.depth_km,
		# No latitude and longitude: the map would show the sensor as a second marker.
		"external_id": quake.id,
		"url": EVENT_URL.format(id=quake.id),
		"map_url": coordinator.map_url(quake),
	}


@dataclass(frozen=True, kw_only=True)
class SgcSensorEntityDescription(SensorEntityDescription):
	"""A summary sensor and how it reads the earthquakes."""

	# Which earthquake the sensor is about, for example the strongest one. None
	# for the count.
	rank: Rank | None = None
	value: Callable[[NearbyEarthquake], float] = _magnitude
	# Keep the best earthquake ever shown, not only among those shown now.
	historic: bool = False


SENSORS: tuple[SgcSensorEntityDescription, ...] = (
	SgcSensorEntityDescription(
		key="earthquakes",
		translation_key="earthquakes",
		state_class=SensorStateClass.MEASUREMENT,
	),
	SgcSensorEntityDescription(
		key="latest_magnitude",
		translation_key="latest_magnitude",
		rank=_time_rank,
		suggested_display_precision=1,
	),
	SgcSensorEntityDescription(
		key="strongest_magnitude",
		translation_key="strongest_magnitude",
		rank=_magnitude_rank,
		suggested_display_precision=1,
	),
	SgcSensorEntityDescription(
		key="strongest_magnitude_historic",
		translation_key="strongest_magnitude_historic",
		rank=_magnitude_rank,
		historic=True,
		suggested_display_precision=1,
	),
	SgcSensorEntityDescription(
		key="strongest_shaking",
		translation_key="strongest_shaking",
		rank=_shaking_rank,
		value=_shaking,
		native_unit_of_measurement="MMI",
		suggested_display_precision=1,
	),
	SgcSensorEntityDescription(
		key="strongest_shaking_historic",
		translation_key="strongest_shaking_historic",
		rank=_shaking_rank,
		value=_shaking,
		historic=True,
		native_unit_of_measurement="MMI",
		suggested_display_precision=1,
	),
)


async def async_setup_entry(
	hass: HomeAssistant,
	entry: SgcConfigEntry,
	async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
	"""Add the summary sensors."""
	coordinator = entry.runtime_data
	async_add_entities(
		(SgcHistoricSensor if description.historic else SgcSensor)(coordinator, description)
		for description in SENSORS
	)


class SgcSensor(CoordinatorEntity[SgcCoordinator], SensorEntity):
	"""A number about the earthquakes shown now."""

	_attr_has_entity_name = True
	_attr_attribution = MANUFACTURER
	entity_description: SgcSensorEntityDescription

	def __init__(
		self, coordinator: SgcCoordinator, description: SgcSensorEntityDescription
	) -> None:
		"""Attach the sensor to the entry's device."""
		super().__init__(coordinator)
		self.entity_description = description
		entry = coordinator.config_entry
		self._attr_unique_id = f"{entry.entry_id}_{description.key}"
		self._attr_device_info = DeviceInfo(
			identifiers={(DOMAIN, entry.entry_id)},
			entry_type=DeviceEntryType.SERVICE,
			manufacturer=MANUFACTURER,
			model="Earthquake feed",
			name=f"SGC Earthquakes {entry.title}",
			configuration_url=SGC_EARTHQUAKES_PAGE,
		)

	def _picked(self) -> NearbyEarthquake | None:
		rank = self.entity_description.rank
		return max(self.coordinator.data.values(), key=rank, default=None) if rank else None

	@property
	def native_value(self) -> float | int | None:
		"""The count, or the magnitude or shaking of the picked earthquake."""
		if self.entity_description.rank is None:
			return len(self.coordinator.data)
		nearby = self._picked()
		return self.entity_description.value(nearby) if nearby else None

	@property
	def extra_state_attributes(self) -> dict[str, Any] | None:
		"""Where and when the picked earthquake happened."""
		if self.entity_description.rank is None:
			return None
		return _details(self.coordinator, self._picked())


@dataclass
class _HistoricData(ExtraStoredData):
	"""The record earthquake, and the zone and list it was recorded for."""

	source: dict[str, Any]
	quake: dict[str, Any] | None

	def as_dict(self) -> dict[str, Any]:
		return {"source": self.source, "quake": self.quake}


class SgcHistoricSensor(SgcSensor, RestoreEntity):
	"""The strongest earthquake shown since setup, kept across restarts."""

	_record: Earthquake | None = None

	async def async_added_to_hass(self) -> None:
		"""Take the record back from before the restart, unless the zone or list changed."""
		await super().async_added_to_hass()
		if (stored := await self.async_get_last_extra_data()) is not None:
			data = stored.as_dict()
			if data.get("source") == self.coordinator.source and data.get("quake"):
				try:
					self._record = quake_from_dict(data["quake"])
				except (KeyError, TypeError, ValueError):
					self._record = None
		self._update_record()

	@callback
	def _handle_coordinator_update(self) -> None:
		self._update_record()
		super()._handle_coordinator_update()

	def _update_record(self) -> None:
		rank = self.entity_description.rank
		assert rank is not None
		shown = self.coordinator.data or {}
		record = None
		if self._record is not None:
			# While SGC still lists it, take its revised magnitude and location.
			record = shown.get(self._record.id) or self.coordinator.nearby(self._record)
			if record is None:
				return
		best = self._picked()
		if best is not None and (record is None or rank(best) > rank(record)):
			record = best
		self._record = record.quake if record else None

	def _record_nearby(self) -> NearbyEarthquake | None:
		return self.coordinator.nearby(self._record) if self._record else None

	@property
	def available(self) -> bool:
		"""A record stays readable while the list cannot be downloaded."""
		return self._record is not None or super().available

	@property
	def native_value(self) -> float | None:
		"""The magnitude or shaking of the record earthquake."""
		nearby = self._record_nearby()
		return self.entity_description.value(nearby) if nearby else None

	@property
	def extra_state_attributes(self) -> dict[str, Any] | None:
		"""Where and when the record earthquake happened."""
		return _details(self.coordinator, self._record_nearby())

	@property
	def extra_restore_state_data(self) -> _HistoricData:
		"""The record, saved with the state so it survives restarts."""
		return _HistoricData(
			source=self.coordinator.source,
			quake=quake_to_dict(self._record) if self._record else None,
		)
