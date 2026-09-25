"""One map entity per earthquake inside the zone."""

from __future__ import annotations

from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import Platform, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import ATTRIBUTION, DOMAIN, EVENT_URL
from .coordinator import SgcConfigEntry, SgcCoordinator
from .models import NearbyEarthquake

# Nothing is polled per entity, the coordinator pushes every update.
PARALLEL_UPDATES = 0


async def async_setup_entry(
	hass: HomeAssistant,
	entry: SgcConfigEntry,
	async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
	"""Add, update and remove earthquake entities as the feed changes."""
	coordinator = entry.runtime_data
	entities: dict[str, SgcEarthquakeEvent] = {}

	@callback
	def _sync() -> None:
		# After a failed download the earthquakes stay as they were, so the
		# geo_location trigger does not see them all leave the zone.
		if not coordinator.last_update_success:
			return
		current = coordinator.data
		for quake_id in entities.keys() - current.keys():
			entities.pop(quake_id).async_forget()
		new_entities: list[SgcEarthquakeEvent] = []
		for quake_id, nearby in current.items():
			if (entity := entities.get(quake_id)) is None:
				entities[quake_id] = entity = SgcEarthquakeEvent(coordinator, nearby)
				new_entities.append(entity)
			else:
				entity.async_update_from(nearby)
		if new_entities:
			async_add_entities(new_entities)

	_sync()
	# This listener also keeps the coordinator polling while no earthquake exists.
	entry.async_on_unload(coordinator.async_add_listener(_sync))


class SgcEarthquakeEvent(GeolocationEvent):
	"""An earthquake on the map, with the distance from the zone center as state."""

	_attr_should_poll = False
	_attr_source = DOMAIN
	_attr_attribution = ATTRIBUTION
	_attr_unit_of_measurement = UnitOfLength.KILOMETERS
	_attr_translation_key = "earthquake"
	# Set on the entity rather than in icons.json, so the state carries an icon
	# attribute for templates and cards, as the USGS integration's does.
	_attr_icon = "mdi:pulse"

	def __init__(self, coordinator: SgcCoordinator, nearby: NearbyEarthquake) -> None:
		"""Create the entity from its first feed reading."""
		quake_id = nearby.quake.id
		self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{quake_id}"
		# The entity id comes from SGC's id, not the title: a swarm repeats one
		# title many times, and a review can change it, while the id never
		# changes. SGC builds its ids from the time, so they also sort by time.
		self.entity_id = f"{Platform.GEO_LOCATION}.{slugify(quake_id)}"
		self._coordinator = coordinator
		self._nearby = nearby
		self._map_url = coordinator.map_url(nearby.quake)
		self._apply(nearby, self._map_url)

	def _apply(self, nearby: NearbyEarthquake, map_url: str) -> None:
		quake = nearby.quake
		self._attr_name = quake.title
		self._attr_distance = nearby.distance_km
		self._attr_latitude = quake.latitude
		self._attr_longitude = quake.longitude
		attributes: dict[str, Any] = {
			"external_id": quake.id,
			"magnitude": quake.magnitude,
			"magnitude_type": quake.magnitude_type,
			"place": quake.place,
			"nearby_towns": quake.nearby_towns,
			"depth_km": quake.depth_km,
			"time": quake.time,
			"time_source": quake.time_source,
			"updated": quake.updated,
			"status": quake.status,
			"agency": quake.agency,
			"felt_reports": quake.felt_reports,
			"intensity": quake.intensity,
			"intensity_level": quake.intensity_level,
			"shaking": nearby.shaking,
			"shaking_mmi": round(nearby.intensity, 1),
			"color": nearby.color,
			"url": EVENT_URL.format(id=quake.id),
			"map_url": map_url,
		}
		self._attr_extra_state_attributes = {
			key: value for key, value in attributes.items() if value is not None
		}

	@callback
	def async_update_from(self, nearby: NearbyEarthquake) -> None:
		"""Take a revised reading (SGC may move or resize it) or another map app."""
		map_url = self._coordinator.map_url(nearby.quake)
		if nearby == self._nearby and map_url == self._map_url:
			return
		self._nearby = nearby
		self._map_url = map_url
		self._apply(nearby, map_url)
		if self.hass is not None:
			self.async_write_ha_state()

	@callback
	def async_forget(self) -> None:
		"""Remove the entity and its registry entry once the earthquake is gone."""
		if self.hass is None:
			return
		registry = er.async_get(self.hass)
		if self.registry_entry is not None and registry.async_get(self.entity_id):
			# Removing the registry entry also removes the entity.
			registry.async_remove(self.entity_id)
		else:
			self.hass.async_create_task(self.async_remove(force_remove=True))
