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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .coordinator import SgcConfigEntry, SgcCoordinator
from .entity import SgcEntity, quake_details
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
	async_add_entities([SgcWarningMagnitudeSensor(coordinator, WARNING_MAGNITUDE)])


class SgcSensor(SgcEntity, SensorEntity):
	"""A number about the earthquakes shown now."""

	entity_description: SgcSensorEntityDescription

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
		return quake_details(self.coordinator, self._picked())


WARNING_MAGNITUDE = SensorEntityDescription(
	key="warning_magnitude",
	translation_key="warning_magnitude",
	entity_category=EntityCategory.DIAGNOSTIC,
	suggested_display_precision=1,
)


class SgcWarningMagnitudeSensor(SgcEntity, SensorEntity):
	"""The warning magnitude from the settings, to compare with in automations."""

	@property
	def available(self) -> bool:
		"""A setting is known also while the list cannot be downloaded."""
		return True

	@property
	def native_value(self) -> float:
		"""The magnitude from which an earthquake counts as a warning."""
		return self.coordinator.warning_magnitude


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
		return quake_details(self.coordinator, self._record_nearby())

	@property
	def extra_restore_state_data(self) -> _HistoricData:
		"""The record, saved with the state so it survives restarts."""
		return _HistoricData(
			source=self.coordinator.source,
			quake=quake_to_dict(self._record) if self._record else None,
		)
