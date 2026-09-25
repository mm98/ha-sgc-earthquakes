"""Fetches the SGC feed and keeps the earthquakes inside the chosen zone."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout, hdrs

from homeassistant.components.zone import ATTR_RADIUS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance

from .const import (
	APPLE_MAPS_URL,
	CONF_FEED,
	CONF_MAP_APP,
	CONF_MINIMUM_MAGNITUDE,
	CONF_MINIMUM_SHAKING,
	CONF_PERIOD_HOURS,
	CONF_REVIEWED_ONLY,
	CONF_ZONE,
	DEFAULT_MINIMUM_MAGNITUDE,
	DOMAIN,
	FEED_URL,
	GOOGLE_MAPS_URL,
	MAP_APP_APPLE,
	MAP_APP_GOOGLE,
	REQUEST_TIMEOUT,
	SHAKING_ANY,
	STATUS_REVIEWED,
	UPDATE_INTERVAL,
	USER_AGENT,
)
from .models import (
	Earthquake,
	NearbyEarthquake,
	estimated_intensity,
	level_start,
	parse_feed,
)

_LOGGER = logging.getLogger(__name__)

type SgcConfigEntry = ConfigEntry[SgcCoordinator]


class FeedError(Exception):
	"""The feed could not be read."""


class FeedBlocked(FeedError):
	"""The SGC server refused the request."""


@dataclass(frozen=True, slots=True)
class ZoneArea:
	"""The center and radius of the zone the earthquakes must be inside."""

	name: str
	latitude: float
	longitude: float
	radius_m: float


def zone_area(state: State | None) -> ZoneArea | None:
	"""Read a zone's center and radius, or None when it is not a usable zone."""
	if state is None or state.domain != "zone":
		return None
	try:
		return ZoneArea(
			name=state.name,
			latitude=float(state.attributes[ATTR_LATITUDE]),
			longitude=float(state.attributes[ATTR_LONGITUDE]),
			radius_m=float(state.attributes[ATTR_RADIUS]),
		)
	except (KeyError, TypeError, ValueError):
		return None


def _measure(area: ZoneArea, quake: Earthquake) -> NearbyEarthquake | None:
	meters = distance(area.latitude, area.longitude, quake.latitude, quake.longitude)
	if meters is None:
		return None
	distance_km = meters / 1000
	return NearbyEarthquake(
		quake=quake,
		distance_km=distance_km,
		intensity=estimated_intensity(quake.magnitude, distance_km, quake.depth_km),
	)


async def async_fetch_feed(
	session: ClientSession, url: str, etag: str | None = None
) -> tuple[dict[str, Earthquake] | None, str | None]:
	"""Download and read the feed. Returns None instead of earthquakes when unchanged."""
	# Home Assistant's session sets its own User-Agent, which the server blocks,
	# so it is replaced on each request.
	headers = {hdrs.USER_AGENT: USER_AGENT}
	if etag:
		headers[hdrs.IF_NONE_MATCH] = etag
	try:
		async with session.get(
			url, headers=headers, timeout=ClientTimeout(total=REQUEST_TIMEOUT)
		) as response:
			if response.status == HTTPStatus.NOT_MODIFIED:
				return None, etag
			# The firewall answers with an HTML page. A wrong feed name gives a
			# 403 too, but as XML from the storage behind it.
			if response.status == HTTPStatus.FORBIDDEN and response.content_type == "text/html":
				raise FeedBlocked
			response.raise_for_status()
			payload = await response.json(content_type=None)
			new_etag = response.headers.get(hdrs.ETAG)
	except FeedError:
		raise
	except (ClientError, TimeoutError, ValueError) as err:
		raise FeedError(str(err) or type(err).__name__) from err
	try:
		return parse_feed(payload), new_etag
	except ValueError as err:
		raise FeedError(str(err)) from err


class SgcCoordinator(DataUpdateCoordinator[dict[str, NearbyEarthquake]]):
	"""Polls one SGC feed and selects the earthquakes inside one zone."""

	config_entry: SgcConfigEntry

	def __init__(self, hass: HomeAssistant, entry: SgcConfigEntry) -> None:
		"""Set up the coordinator for a config entry."""
		super().__init__(
			hass,
			_LOGGER,
			config_entry=entry,
			name=f"{DOMAIN} {entry.title}",
			update_interval=UPDATE_INTERVAL,
		)
		self._session = async_get_clientsession(hass)
		# The zone and list this coordinator was built for. Another zone or list
		# needs a reload, other settings apply at once.
		self.source: dict[str, Any] = dict(entry.data)
		self.feed_url = FEED_URL.format(feed=entry.data[CONF_FEED])
		self.zone_entity_id: str = entry.data[CONF_ZONE]
		self._read_options(entry.options)
		self.area: ZoneArea | None = None
		self.feed: dict[str, Earthquake] = {}
		self._etag: str | None = None

	async def _async_update_data(self) -> dict[str, NearbyEarthquake]:
		area = self._area()
		try:
			# Only ask for "unchanged" when there is something to reuse.
			quakes, etag = await async_fetch_feed(
				self._session, self.feed_url, self._etag if self.feed else None
			)
		except FeedBlocked as err:
			raise UpdateFailed(
				translation_domain=DOMAIN,
				translation_key="blocked",
				translation_placeholders={"url": self.feed_url},
			) from err
		except FeedError as err:
			raise UpdateFailed(
				translation_domain=DOMAIN,
				translation_key="cannot_connect",
				translation_placeholders={"url": self.feed_url, "error": str(err)},
			) from err
		if quakes is not None:
			self.feed = quakes
			self._etag = etag
		# Selected on every poll, also when the list is unchanged, so earthquakes
		# drop out once they are older than the period.
		return self._select(area)

	def _area(self) -> ZoneArea:
		area = zone_area(self.hass.states.get(self.zone_entity_id))
		if area is None:
			raise UpdateFailed(
				translation_domain=DOMAIN,
				translation_key="zone_not_found",
				translation_placeholders={"zone": self.zone_entity_id},
			)
		self.area = area
		return area

	def _select(self, area: ZoneArea) -> dict[str, NearbyEarthquake]:
		oldest = dt_util.utcnow() - self.period if self.period else None
		selected: dict[str, NearbyEarthquake] = {}
		for quake in self.feed.values():
			if (
				quake.magnitude < self.minimum_magnitude
				or (oldest is not None and quake.time < oldest)
				or (self.reviewed_only and quake.status != STATUS_REVIEWED)
			):
				continue
			nearby = _measure(area, quake)
			if nearby is None or nearby.distance_km * 1000 > area.radius_m:
				continue
			if self.minimum_intensity is not None and nearby.intensity < self.minimum_intensity:
				continue
			selected[quake.id] = nearby
		return selected

	def nearby(self, quake: Earthquake) -> NearbyEarthquake | None:
		"""Distance and estimated shaking at the zone center, also for a stored earthquake."""
		return _measure(self.area, quake) if self.area else None

	def _read_options(self, options: Mapping[str, Any]) -> None:
		self.minimum_magnitude: float = options.get(
			CONF_MINIMUM_MAGNITUDE, DEFAULT_MINIMUM_MAGNITUDE
		)
		shaking = options.get(CONF_MINIMUM_SHAKING, SHAKING_ANY)
		self.minimum_intensity: float | None = (
			None if shaking == SHAKING_ANY else level_start(shaking)
		)
		period_hours = options.get(CONF_PERIOD_HOURS)
		self.period: timedelta | None = timedelta(hours=period_hours) if period_hours else None
		self.reviewed_only: bool = options.get(CONF_REVIEWED_ONLY, False)
		self.map_app: str = options.get(CONF_MAP_APP, MAP_APP_GOOGLE)

	@callback
	def async_apply_options(self, options: Mapping[str, Any]) -> None:
		"""Use new settings at once, without downloading or recreating entities.

		Earthquakes that stay shown keep their entity, so automations do not see
		them as new. Ones a changed filter adds or hides still enter or leave.
		"""
		self._read_options(options)
		# After a failed download the next successful one applies them.
		if self.area is None or not self.last_update_success:
			return
		self.data = self._select(self.area)
		self.async_update_listeners()

	def map_url(self, quake: Earthquake) -> str:
		"""A link that opens the earthquake in the map app picked in the settings."""
		if self.map_app == MAP_APP_APPLE:
			return APPLE_MAPS_URL.format(
				latitude=quake.latitude,
				longitude=quake.longitude,
				name=quote(f"M {quake.magnitude:.1f}", safe=""),
			)
		return GOOGLE_MAPS_URL.format(latitude=quake.latitude, longitude=quake.longitude)

	@callback
	def async_zone_changed(self, event: Event[EventStateChangedData]) -> None:
		"""Select again when the zone is moved or resized, without downloading."""
		area = zone_area(event.data["new_state"])
		# A zone's state also changes when people enter or leave it.
		if area is None or area == self.area or not self.last_update_success:
			return
		self.area = area
		self.async_set_updated_data(self._select(area))
