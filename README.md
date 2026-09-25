# SGC Earthquakes for Home Assistant

See earthquakes from the Servicio Geológico Colombiano (SGC), Colombia's geological survey, in Home Assistant. You pick an area, and every earthquake inside it shows up on your map. Sensors tell you about the latest and the strongest earthquakes, and about how strongly each one was probably felt in your area.

It works like the USGS earthquake integration that comes with Home Assistant, but it uses SGC's earthquake lists, which cover Colombia in more detail.

Available in English, Danish and Spanish.

## Before you start: make a zone

The integration only shows earthquakes inside one of your Home Assistant zones, so you need a zone that covers the area you care about.

Make the zone big, because strong earthquakes are felt far away: 100 to 200 km is a good size. The zone must be at least 1 km. Your Home zone is usually only 100 meters, so make a new zone for this.

1. Go to **Settings > Areas, labels & zones**, open **Zones** and select **Create zone**.
2. Enter a **Name**, for example your city.
3. Drag the pin on the map to the center of the area.
4. Enter the **Radius** in meters, for example `200000` for 200 km.
5. Turn on **Passive**. Without it, someone who is away from home but inside this big zone shows as being in the zone, instead of away.
6. Select **Create**.

## Install

Requires Home Assistant 2026.9 or newer.

### With HACS

Select this button to open the integration in HACS, then select **Download**:

[![Open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mm98&repository=ha_sgc_earthquakes&category=integration)

Or add it yourself:

1. Open **HACS**, select the three dots at the top right and pick **Custom repositories**.
2. Enter `https://github.com/mm98/ha_sgc_earthquakes`, choose the type **Integration** and select **Add**.
3. Search HACS for **SGC Earthquakes**, open it and select **Download**.
4. Restart Home Assistant.

### Without HACS

1. Copy the `custom_components/sgc_earthquakes` folder from this repository into the `custom_components` folder of your Home Assistant configuration.
2. Restart Home Assistant.

## Set up

Go to **Settings > Devices & services**, select **Add integration** and pick **SGC Earthquakes**. Or select this button:

[![Add the SGC Earthquakes integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=sgc_earthquakes)

Then pick your zone and choose which earthquakes to show:

| Setting | What it does |
|---|---|
| Zone | The area to watch. |
| Earthquake list | Which SGC list to use. See the lists below. |
| Minimum magnitude | Leaves out smaller earthquakes. The default is 3.0. |
| Minimum shaking at zone center | Only shows earthquakes that are felt at least this much at the center of your zone: Any (the default), Weak, Light, Moderate or Strong. See **How strongly was it felt?** below. |
| Only earthquakes from the last | For example 24 hours for the last day. Leave it empty to show the whole list. |
| Only earthquakes checked by SGC | Waits until an SGC expert has checked the earthquake. The first, automatic location can be wrong, sometimes by more than 100 km. The check usually takes less than half an hour, but small earthquakes can wait a day or more. |
| Map links open in | Google Maps works everywhere. Apple Maps opens the Maps app on iPhone, iPad and Mac (iOS 18.4 or macOS 15.4 and newer) and shows the magnitude on the pin. |

You can change these settings later with **Configure** on the integration. To use another zone or list, pick **Reconfigure**. You can also add the integration more than once, for example for two different zones.

The lists are the same as on the SGC website:

| List | What is in it |
|---|---|
| Last 5 days, magnitude 2.0 and up | The default, and the list the SGC website shows first |
| Last 5 days, all magnitudes | Also the very small earthquakes |
| Last 30 days, notable earthquakes | About 150 earthquakes that SGC picked out |
| Last 60 days, magnitude 4.0 and up | Also earthquakes far outside Colombia |
| International earthquakes | Earthquakes around the world |

## What you get

### Earthquakes on the map

Every earthquake in your zone shows on the Home Assistant map, with a name like `M 4.2 - Chaparral - Tolima, Colombia`: the magnitude and the place. Its value is the distance from your zone center in km. Select an earthquake to see:

- the magnitude, the place and the nearby towns
- the depth
- the time in your own time zone, and the time in Colombia
- whether SGC has checked it yet
- how strongly it was probably felt at your zone center, as a word, a number and a color
- how strongly SGC measured it where it happened, when SGC has that
- how many people reported feeling it
- links to the earthquake on the SGC website and on a map

When SGC corrects an earthquake, for example its magnitude or place, the map follows. An earthquake disappears again when it gets older than your time limit or leaves SGC's list.

### Sensors

| Sensor | Shows |
|---|---|
| Earthquakes in zone | How many earthquakes are shown right now |
| Magnitude of latest earthquake | The newest earthquake, with its place, time and links |
| Magnitude of strongest earthquake | The highest magnitude among the earthquakes shown now |
| Magnitude of strongest earthquake (historic) | The highest magnitude since you set up the integration, also after that earthquake is gone |
| Strongest shaking at zone center | The strongest shaking among the earthquakes shown now |
| Strongest shaking at zone center (historic) | The strongest shaking since you set up the integration |

The historic sensors keep their record when Home Assistant restarts. They start over when you pick another zone or list.

## How strongly was it felt?

The magnitude alone does not tell you how much an earthquake shook your area. A big earthquake far away can shake more than a small one right below you. So for every earthquake, the integration estimates the shaking at the center of your zone from the magnitude, the distance and the depth. It uses the 1 to 12 scale (Modified Mercalli) that SGC and the USGS also use:

| Scale | Shaking | Possible damage | Color |
|---|---|---|---|
| 1 | Not felt | None | Green |
| 2 to 3 | Weak | None | Green |
| 4 | Light | None | Yellow |
| 5 | Moderate | Very light | Yellow |
| 6 | Strong | Light | Orange |
| 7 | Very strong | Moderate | Red |
| 8 to 12 | Severe, violent or extreme | Moderate to very heavy | Red |

Keep in mind:

- It is an estimate. It is usually within one step of what is really measured.
- It is for the center of your zone. Places closer to the earthquake shake more.
- Soft ground can make the shaking a step stronger.
- **Measured shaking at the earthquake** is SGC's own measurement where the earthquake happened, not in your zone. SGC only has it for some earthquakes.

## Examples

### A map card

The **Map** in the sidebar shows the earthquakes by itself. To put them on a dashboard, add a **Map** card, open its code editor and paste this. It shows the magnitude on each earthquake:

```yaml
type: map
geo_location_sources:
  - source: sgc_earthquakes
    label_mode: attribute
    attribute: magnitude
```

### A notification for each earthquake you would feel

Create a new automation, open the three dots at the top right, pick **Edit in YAML** and paste this. Change `zone.ibague` to your own zone.

```yaml
triggers:
  - trigger: geo_location
    source: sgc_earthquakes
    zone: zone.ibague
    event: enter
conditions:
  # Only earthquakes that are felt at the zone center (Weak or stronger).
  - condition: template
    value_template: "{{ trigger.to_state.attributes.shaking_mmi >= 1.5 }}"
  # Skip earthquakes older than 6 hours.
  - condition: template
    value_template: "{{ now() - trigger.to_state.attributes.time < timedelta(hours=6) }}"
actions:
  - action: notify.notify
    data:
      message: >
        {{ trigger.to_state.name }},
        {{ trigger.to_state.state }} km from {{ trigger.zone.name }},
        at {{ trigger.to_state.attributes.time_source }} in Colombia.
        Estimated shaking there:
        {{ trigger.to_state.attributes.shaking | replace('_', ' ') }}.
      data:
        # Tapping the notification opens the map.
        url: "{{ trigger.to_state.attributes.map_url }}"
        clickAction: "{{ trigger.to_state.attributes.map_url }}"
```

Why skip old earthquakes? After **Reconfigure**, every earthquake in the list counts as new once. The time check stops a notification for each of them. If you turned on **Only earthquakes checked by SGC**, use 24 hours instead of 6, because the check can take a while. Changing settings with **Configure** or restarting Home Assistant does not make earthquakes count as new.

## Good to know

- New earthquakes show up about 3 to 8 minutes after they happen.
- If your internet or the SGC website is down, the earthquakes stay on the map, and the sensors show as unavailable until it works again.
- Times are shown in your own time zone. **Time in Colombia** always shows the Colombian time, as SGC gives it.

## Problems and ideas

Tell us on [GitHub](https://github.com/mm98/ha_sgc_earthquakes/issues). It helps to add the diagnostics: on the integration's page, open the three dots and pick **Download diagnostics**. They contain your settings and the earthquakes found, but not where your zone is.

## Credits

The earthquake data comes from the [Servicio Geológico Colombiano](https://www.sgc.gov.co/sismos). This integration is not made by SGC or connected to it.

## License

MIT, see [LICENSE](LICENSE).
