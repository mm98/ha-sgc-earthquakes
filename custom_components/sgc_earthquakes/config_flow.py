"""Set up SGC Earthquakes: pick a zone, a feed and which earthquakes to show."""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
	CONF_FEED,
	CONF_MAP_APP,
	CONF_MINIMUM_MAGNITUDE,
	CONF_MINIMUM_SHAKING,
	CONF_PERIOD_HOURS,
	CONF_REVIEWED_ONLY,
	CONF_ZONE,
	DEFAULT_FEED,
	DEFAULT_MINIMUM_MAGNITUDE,
	DOMAIN,
	FEED_URL,
	FEEDS,
	MAP_APP_GOOGLE,
	MAP_APPS,
	MAXIMUM_PERIOD_HOURS,
	MINIMUM_SHAKING_OPTIONS,
	MINIMUM_ZONE_RADIUS_M,
	SHAKING_ANY,
)
from .coordinator import FeedBlocked, FeedError, SgcConfigEntry, async_fetch_feed, zone_area

OPTIONS = (
	CONF_MINIMUM_MAGNITUDE,
	CONF_MINIMUM_SHAKING,
	CONF_PERIOD_HOURS,
	CONF_REVIEWED_ONLY,
	CONF_MAP_APP,
)

OPTION_FIELDS = {
	probatio.Required(
		CONF_MINIMUM_MAGNITUDE, default=DEFAULT_MINIMUM_MAGNITUDE
	): selector.NumberSelector(
		selector.NumberSelectorConfig(
			min=0, max=10, step=0.1, mode=selector.NumberSelectorMode.BOX
		)
	),
	probatio.Required(CONF_MINIMUM_SHAKING, default=SHAKING_ANY): selector.SelectSelector(
		selector.SelectSelectorConfig(
			options=list(MINIMUM_SHAKING_OPTIONS),
			translation_key=CONF_MINIMUM_SHAKING,
			mode=selector.SelectSelectorMode.DROPDOWN,
		)
	),
	# Left empty, the whole list is shown.
	probatio.Optional(CONF_PERIOD_HOURS): selector.NumberSelector(
		selector.NumberSelectorConfig(
			min=1,
			max=MAXIMUM_PERIOD_HOURS,
			step=1,
			mode=selector.NumberSelectorMode.BOX,
			unit_of_measurement="hours",
			translation_key=CONF_PERIOD_HOURS,
		)
	),
	probatio.Required(CONF_REVIEWED_ONLY, default=False): selector.BooleanSelector(),
	probatio.Required(CONF_MAP_APP, default=MAP_APP_GOOGLE): selector.SelectSelector(
		selector.SelectSelectorConfig(
			options=list(MAP_APPS),
			translation_key=CONF_MAP_APP,
			mode=selector.SelectSelectorMode.LIST,
		)
	),
}

SOURCE_SCHEMA = probatio.Schema(
	{
		probatio.Required(CONF_ZONE): selector.EntitySelector(
			selector.EntitySelectorConfig(
				filter=selector.EntityFilterSelectorConfig(domain="zone")
			)
		),
		probatio.Required(CONF_FEED, default=DEFAULT_FEED): selector.SelectSelector(
			selector.SelectSelectorConfig(
				options=list(FEEDS),
				translation_key=CONF_FEED,
				mode=selector.SelectSelectorMode.DROPDOWN,
			)
		),
	}
)

USER_SCHEMA = SOURCE_SCHEMA.extend(OPTION_FIELDS)

OPTIONS_SCHEMA = probatio.Schema(OPTION_FIELDS)


class SgcEarthquakesConfigFlow(ConfigFlow, domain=DOMAIN):
	"""Add a zone to watch for earthquakes."""

	VERSION = 1

	@staticmethod
	@callback
	def async_get_options_flow(config_entry: SgcConfigEntry) -> SgcEarthquakesOptionsFlow:
		"""Change which earthquakes are shown."""
		return SgcEarthquakesOptionsFlow()

	async def async_step_user(
		self, user_input: dict[str, Any] | None = None
	) -> ConfigFlowResult:
		"""Pick the zone, the feed and which earthquakes to show."""
		errors: dict[str, str] = {}
		placeholders: dict[str, str] = {}
		if user_input is not None:
			errors, placeholders, title = await self._async_validate(user_input)
			if not errors:
				await self.async_set_unique_id(_unique_id(user_input))
				self._abort_if_unique_id_configured()
				return self.async_create_entry(
					title=title,
					data={CONF_ZONE: user_input[CONF_ZONE], CONF_FEED: user_input[CONF_FEED]},
					options={key: user_input[key] for key in OPTIONS if key in user_input},
				)
		return self.async_show_form(
			step_id="user",
			data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
			errors=errors,
			description_placeholders=placeholders,
		)

	async def async_step_reconfigure(
		self, user_input: dict[str, Any] | None = None
	) -> ConfigFlowResult:
		"""Swap the zone or the feed."""
		entry = self._get_reconfigure_entry()
		errors: dict[str, str] = {}
		placeholders: dict[str, str] = {}
		if user_input is not None:
			errors, placeholders, title = await self._async_validate(user_input)
			unique_id = _unique_id(user_input)
			if not errors and any(
				other.unique_id == unique_id and other.entry_id != entry.entry_id
				for other in self._async_current_entries(include_ignore=False)
			):
				errors["base"] = "already_configured"
			if not errors:
				# The entry's update listener reloads it when the zone or list changed.
				return self.async_update_and_abort(
					entry,
					unique_id=unique_id,
					title=title,
					data={CONF_ZONE: user_input[CONF_ZONE], CONF_FEED: user_input[CONF_FEED]},
				)
		return self.async_show_form(
			step_id="reconfigure",
			data_schema=self.add_suggested_values_to_schema(
				SOURCE_SCHEMA, user_input or dict(entry.data)
			),
			errors=errors,
			description_placeholders=placeholders,
		)

	async def _async_validate(
		self, user_input: dict[str, Any]
	) -> tuple[dict[str, str], dict[str, str], str]:
		"""Check the zone is usable and the feed can be read. Returns errors, placeholders and a title."""
		zone_id = user_input[CONF_ZONE]
		# The picker shows only zones, but a flow can also be driven without it.
		area = zone_area(self.hass.states.get(zone_id)) if zone_id.startswith("zone.") else None
		if area is None:
			return {CONF_ZONE: "zone_not_found"}, {}, ""
		placeholders = {"zone": area.name, "radius": f"{area.radius_m:.0f}"}
		if area.radius_m < MINIMUM_ZONE_RADIUS_M:
			return {CONF_ZONE: "zone_too_small"}, placeholders, ""
		try:
			await async_fetch_feed(
				async_get_clientsession(self.hass),
				FEED_URL.format(feed=user_input[CONF_FEED]),
			)
		except FeedBlocked:
			return {"base": "blocked"}, placeholders, ""
		except FeedError:
			return {"base": "cannot_connect"}, placeholders, ""
		return {}, placeholders, area.name


class SgcEarthquakesOptionsFlow(OptionsFlow):
	"""Change the filters and the map app. They apply at once, without a reload."""

	async def async_step_init(
		self, user_input: dict[str, Any] | None = None
	) -> ConfigFlowResult:
		"""Show the filters."""
		if user_input is not None:
			return self.async_create_entry(data=user_input)
		return self.async_show_form(
			step_id="init",
			data_schema=self.add_suggested_values_to_schema(
				OPTIONS_SCHEMA, dict(self.config_entry.options)
			),
		)


def _unique_id(user_input: dict[str, Any]) -> str:
	return f"{user_input[CONF_ZONE]}_{user_input[CONF_FEED]}"
