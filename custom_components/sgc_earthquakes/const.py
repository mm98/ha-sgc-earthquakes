"""Constants for SGC Earthquakes."""

from datetime import timedelta
from typing import Final

from homeassistant.const import __version__ as HA_VERSION

DOMAIN: Final = "sgc_earthquakes"

CONF_ZONE: Final = "zone"
CONF_FEED: Final = "feed"
CONF_MINIMUM_MAGNITUDE: Final = "minimum_magnitude"
CONF_MINIMUM_SHAKING: Final = "minimum_shaking"
CONF_PERIOD_HOURS: Final = "period_hours"
CONF_REVIEWED_ONLY: Final = "reviewed_only"
CONF_MAP_APP: Final = "map_app"

MAP_APP_GOOGLE: Final = "google_maps"
MAP_APP_APPLE: Final = "apple_maps"
MAP_APPS: Final = (MAP_APP_GOOGLE, MAP_APP_APPLE)

# The lists the SGC earthquake page (https://www.sgc.gov.co/sismos) offers.
FEEDS: Final = (
	"five_days_2",
	"five_days_all",
	"thirty_days_important",
	"sixty_days_4",
	"international",
)
DEFAULT_FEED: Final = "five_days_2"
FEED_URL: Final = "https://archive.sgc.gov.co/feed/v1.0.1/summary/{feed}.json"

# A 200 km zone around Ibague holds about 150 earthquakes of magnitude 3 or more
# in five days during a swarm, and every one becomes an entity and a map marker.
DEFAULT_MINIMUM_MAGNITUDE: Final = 3.0

# Levels the "minimum shaking at zone center" filter offers. Higher ones mean
# damage, and those earthquakes already pass the lower settings.
SHAKING_ANY: Final = "any"
MINIMUM_SHAKING_OPTIONS: Final = (SHAKING_ANY, "weak", "light", "moderate", "strong")

# The longest SGC list covers 60 days.
MAXIMUM_PERIOD_HOURS: Final = 60 * 24

# SGC places each earthquake automatically first. An analyst then checks it and
# often moves it (by up to 140 km in the samples) or changes the magnitude.
STATUS_REVIEWED: Final = "manual"

# Earthquakes count only when their center is inside the zone, so a zone the
# size of a house would never show anything.
MINIMUM_ZONE_RADIUS_M: Final = 1000

# The feed changes every 2 to 10 minutes during a swarm and new earthquakes
# appear about 3 minutes after they happen.
UPDATE_INTERVAL: Final = timedelta(minutes=5)
REQUEST_TIMEOUT: Final = 30

# The SGC server (CloudFront) refuses Home Assistant's own User-Agent, because
# it contains "Python". It accepts a browser-style one of at least 40 characters.
USER_AGENT: Final = (
	f"Mozilla/5.0 (compatible; HomeAssistant/{HA_VERSION}; +https://www.home-assistant.io)"
)

ATTRIBUTION: Final = "Servicio Geológico Colombiano"
MANUFACTURER: Final = "Servicio Geológico Colombiano"
SGC_EARTHQUAKES_PAGE: Final = "https://www.sgc.gov.co/sismos"
EVENT_URL: Final = "https://www.sgc.gov.co/detallesismo/{id}/resumen"
# Google's documented Maps URL: opens the app on phones, the web page elsewhere.
# Five decimals is about 1 m, the precision Home Assistant keeps for locations.
GOOGLE_MAPS_URL: Final = (
	"https://www.google.com/maps/search/?api=1&query={latitude:.5f},{longitude:.5f}"
)
# Apple's unified Maps URL (iOS 18.4 and macOS 15.4 or newer). The name labels
# the pin; Google's URL has no such option.
APPLE_MAPS_URL: Final = (
	"https://maps.apple.com/place?coordinate={latitude:.5f},{longitude:.5f}&name={name}"
)
