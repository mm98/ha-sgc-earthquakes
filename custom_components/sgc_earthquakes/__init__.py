"""SGC Earthquakes: earthquakes from the Servicio Geologico Colombiano inside a zone."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .coordinator import SgcConfigEntry, SgcCoordinator

PLATFORMS: list[Platform] = [Platform.GEO_LOCATION, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SgcConfigEntry) -> bool:
	"""Start polling the feed and create the entities."""
	_remove_earthquake_entities(hass, entry)
	coordinator = SgcCoordinator(hass, entry)
	await coordinator.async_config_entry_first_refresh()
	entry.runtime_data = coordinator
	entry.async_on_unload(
		async_track_state_change_event(
			hass, coordinator.zone_entity_id, coordinator.async_zone_changed
		)
	)
	entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
	await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
	return True


async def _async_entry_updated(hass: HomeAssistant, entry: SgcConfigEntry) -> None:
	"""Apply new settings at once. Only another zone or list needs a reload.

	A reload recreates every earthquake entity, and automations would see each
	one as new.
	"""
	coordinator = entry.runtime_data
	if dict(entry.data) != coordinator.source:
		hass.config_entries.async_schedule_reload(entry.entry_id)
		return
	coordinator.async_apply_options(entry.options)


async def async_unload_entry(hass: HomeAssistant, entry: SgcConfigEntry) -> bool:
	"""Stop polling and remove the entities."""
	if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
		_remove_earthquake_entities(hass, entry)
	return unloaded


@callback
def _remove_earthquake_entities(hass: HomeAssistant, entry: SgcConfigEntry) -> None:
	"""Forget earthquake entities, which are created again from the feed.

	Without this, earthquakes that left the feed while Home Assistant was stopped
	would stay in the entity list for good.
	"""
	registry = er.async_get(hass)
	for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
		if entity.domain == Platform.GEO_LOCATION:
			registry.async_remove(entity.entity_id)
