"""Diagnostics for SGC Earthquakes: settings, the zone size and the selected earthquakes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .coordinator import SgcConfigEntry


async def async_get_config_entry_diagnostics(
	hass: HomeAssistant, entry: SgcConfigEntry
) -> dict[str, Any]:
	"""Settings, the zone radius (not its location) and what the feed gave."""
	coordinator = entry.runtime_data
	area = coordinator.area
	return {
		"data": dict(entry.data),
		"options": dict(entry.options),
		"feed_url": coordinator.feed_url,
		"zone_radius_km": round(area.radius_m / 1000, 1) if area else None,
		"last_update_success": coordinator.last_update_success,
		"earthquakes_in_feed": len(coordinator.feed),
		"earthquakes_in_zone": [
			{
				**asdict(nearby.quake),
				"distance_km": round(nearby.distance_km, 1),
				"shaking_mmi": round(nearby.intensity, 2),
			}
			for nearby in (coordinator.data or {}).values()
		],
	}


async def async_get_device_diagnostics(
	hass: HomeAssistant, entry: SgcConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
	"""The same, offered on the device page."""
	return await async_get_config_entry_diagnostics(hass, entry)
