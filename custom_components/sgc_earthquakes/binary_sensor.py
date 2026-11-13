"""A warning while a strong earthquake from the last hour is inside the zone."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
	BinarySensorDeviceClass,
	BinarySensorEntity,
	BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SgcConfigEntry
from .entity import SgcEntity, quake_details

# Nothing is polled per entity, the coordinator pushes every update.
PARALLEL_UPDATES = 0

WARNING = BinarySensorEntityDescription(
	key="warning",
	translation_key="warning",
	device_class=BinarySensorDeviceClass.SAFETY,
)


async def async_setup_entry(
	hass: HomeAssistant,
	entry: SgcConfigEntry,
	async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
	"""Add the warning."""
	async_add_entities([SgcWarningBinarySensor(entry.runtime_data, WARNING)])


class SgcWarningBinarySensor(SgcEntity, BinarySensorEntity):
	"""On for an hour after an earthquake at or above the warning magnitude.

	The list is read every 2 minutes meanwhile, so it also turns off within a
	2 minutes after the hour.
	"""

	@property
	def is_on(self) -> bool:
		"""Whether such an earthquake happened in the last hour."""
		return self.coordinator.warning is not None

	@property
	def extra_state_attributes(self) -> dict[str, Any]:
		"""The warning magnitude, and the strongest such earthquake."""
		return {
			"warning_magnitude": self.coordinator.warning_magnitude,
			**quake_details(self.coordinator, self.coordinator.warning),
		}
