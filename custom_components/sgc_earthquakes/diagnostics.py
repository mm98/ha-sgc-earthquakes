"""Diagnostics for SGC Earthquakes: settings, the zone size and the selected earthquakes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_ZONE
from .coordinator import SgcConfigEntry

# The zone's entity id (like zone.ibague) often names where the user lives.
TO_REDACT = {CONF_ZONE}


async def async_get_config_entry_diagnostics(
	hass: HomeAssistant, entry: SgcConfigEntry
) -> dict[str, Any]:
	"""Settings, the zone radius (not its location) and what the feed gave."""
	coordinator = entry.runtime_data
	area = coordinator.area
	return {
		"data": async_redact_data(entry.data, TO_REDACT),
		"options": dict(entry.options),
		"feed_url": coordinator.feed_url,
		"zone_radius_km": round(area.radius_m / 1000, 1) if area else None,
		"last_update_success": coordinator.last_update_success,
		"earthquakes_in_feed": len(coordinator.feed),
		# Without the distance to the zone center, or the shaking that follows
		# from it: three earthquakes with their distances pin the center down.
		"earthquakes_in_zone": [
			asdict(nearby.quake) for nearby in (coordinator.data or {}).values()
		],
	}


async def async_get_device_diagnostics(
	hass: HomeAssistant, entry: SgcConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
	"""The same, offered on the device page."""
	return await async_get_config_entry_diagnostics(hass, entry)
