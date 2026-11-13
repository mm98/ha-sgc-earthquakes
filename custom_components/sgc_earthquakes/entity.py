"""What the summary entities share: the device and the details of one earthquake."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_URL, MANUFACTURER, SGC_EARTHQUAKES_PAGE
from .coordinator import SgcCoordinator
from .models import NearbyEarthquake


def quake_details(coordinator: SgcCoordinator, nearby: NearbyEarthquake | None) -> dict[str, Any]:
	"""Where and when an earthquake happened, with its links."""
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
		# No latitude and longitude: the map would show the entity as a second marker.
		"external_id": quake.id,
		"url": EVENT_URL.format(id=quake.id),
		"map_url": coordinator.map_url(quake),
	}


class SgcEntity(CoordinatorEntity[SgcCoordinator]):
	"""An entity on the entry's device."""

	_attr_has_entity_name = True
	_attr_attribution = MANUFACTURER

	def __init__(self, coordinator: SgcCoordinator, description: EntityDescription) -> None:
		"""Attach the entity to the entry's device."""
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
