# SGC Earthquakes for Home Assistant

Shows earthquakes from the Servicio Geológico Colombiano (SGC) that happen
inside one of your zones. It works like the built-in USGS earthquake
integration: every earthquake becomes a `geo_location` entity, so it shows on
the map and works with the geo_location trigger. The difference is the source
(the SGC lists at https://www.sgc.gov.co/sismos) and that the area is a normal
Home Assistant zone, set up in the UI instead of YAML.

The texts are in English, Danish and Spanish (`es` and `es-419`, the
Latin American Spanish most people in Colombia pick in Home Assistant).

## Installation

Requires Home Assistant 2026.9 or newer.

1. Copy this folder to `custom_components/sgc_earthquakes` in your Home
   Assistant configuration folder, including the `translations` and `brand`
   folders inside it. Without `translations` every form shows raw keys like
   `period_hours`, and without `brand` the integration has no icon.
2. Restart Home Assistant.
3. Make a large zone for the area you care about under
   **Settings > Areas, labels & zones > Zones**, for example 200 km around
   Ibagué.
4. Go to **Settings > Devices & services > Add integration** and pick
   **SGC Earthquakes**.

## Settings

| Setting | What it does |
|---|---|
| Zone | Earthquakes count when their center is inside this zone. The zone's own radius is used. Move or resize the zone later and the list follows, without a restart. |
| Earthquake list | Which SGC list to read (see below). |
| Minimum magnitude | Smaller earthquakes are left out. Default 3.0. |
| Minimum shaking at zone center | Leaves out earthquakes that would be felt less than this at the zone center (see **Estimated shaking** below). Any (the default), Weak, Light, Moderate or Strong. Unlike the magnitude, it weighs in distance and depth, so a strong earthquake far away can pass while a small one nearby does not. |
| Only earthquakes from the last (hours) | For example 24 for the last day. Empty shows the whole list. An earthquake drops off within 5 minutes after it gets older than this. |
| Only earthquakes checked by SGC | Waits until an SGC analyst has checked the earthquake. The first automatic location can be far off (one moved 140 km on review), so this avoids alerts for the wrong place. The check usually takes under half an hour, but some small earthquakes wait a day or more. |
| Map links open in | Google Maps (the default) works on any device. Apple Maps opens the Maps app on iPhone, iPad and Mac (iOS 18.4 or macOS 15.4 and newer) and labels the pin with the magnitude, for example M 4.2. Google's links cannot label the pin. |

Everything after the list can be changed later under **Configure**, and the
change applies at once, without a reload. **Reconfigure** swaps the zone or
the list, which reloads the integration. You can add the same zone more than
once with different lists.

The lists, as the SGC website offers them:

| List | Holds |
|---|---|
| Last 5 days, magnitude 2.0 and up | The default, and what the SGC site shows first |
| Last 5 days, all magnitudes | Down to about magnitude 0.5 |
| Last 30 days, notable earthquakes | About 150 picked earthquakes |
| Last 60 days, magnitude 4.0 and up | Also far outside Colombia |
| International earthquakes | Worldwide |

## Entities

One `geo_location` entity per earthquake, named like USGS names them, for
example `M 4.2 - Chaparral - Tolima, Colombia`. The entity id is SGC's own id
for the earthquake, for example `geo_location.sgc2026snqtlv`. Names repeat (a
swarm near Chaparral gave 50 earthquakes named `M 2.5 - Chaparral - Tolima,
Colombia` in 5 days) and SGC's review can change them, but the id stays the
same. SGC builds its ids from the time, so sorting by entity id also sorts by
time. The state is the distance from
the zone center in km. Attributes: magnitude, magnitude type, place, nearby
towns, depth in km, time, the time in Colombia (`time_source`), when SGC last
changed it, status (automatic or reviewed), reporting agency, felt reports,
the estimated shaking at the zone center (`shaking_mmi` as a number,
`shaking` as a word, and `color`), the shaking SGC measured at the earthquake
when it has a value (`intensity` as a number, `intensity_level` as a word), a
link to the SGC page for the earthquake, and a map link (`map_url`) that
opens the earthquake's location in Google Maps or Apple Maps, whichever you picked. Both
links are clickable in the entity dialog. Like the USGS entities, each one
also has `icon: mdi:pulse`, so a map card with `label_mode: icon` shows the
pulse icon.

About the times: **Time** and **Last changed by SGC** are stored in UTC and
the entity dialog shows them in your own time zone. **Time in Colombia** is
text, as SGC shows it, for example `2026/09/23 04:04 AM`, so it always stays
Colombian time (UTC-5, no summer time). It uses slashes because the dialog
treats text starting with `2026-09-23` as a date and converts it. In
templates, `time` is UTC: use `as_local(trigger.to_state.attributes.time)`
for your own time.

SGC reviews automatic earthquakes after a few minutes to a few hours. The
magnitude and location can change, and the entity is updated in place. If a
review moves an earthquake out of the zone or below the minimum magnitude, the
entity is removed. With **Only earthquakes checked by SGC** on, an earthquake
only appears after the review.

Sensors on the **SGC Earthquakes <zone>** device:

| Sensor | Shows |
|---|---|
| Earthquakes in zone | How many earthquakes are shown, after the filters |
| Magnitude of latest earthquake | With place, time, distance, estimated shaking, color and both links as attributes |
| Magnitude of strongest earthquake | The same for the highest magnitude among the earthquakes shown now |
| Magnitude of strongest earthquake (historic) | The highest magnitude since setup, also after that earthquake has left the list |
| Strongest shaking at zone center | The highest estimated shaking (MMI) among the earthquakes shown now |
| Strongest shaking at zone center (historic) | The highest estimated shaking since setup, kept the same way |

The sensors without "(historic)" follow your filters, for example only the
last 24 hours.
The historic sensors keep their record across restarts, and follow SGC's
corrections while the earthquake is still in the list. They start over when
you pick another zone or list under **Reconfigure**.

## Estimated shaking

Magnitude alone says little about what you feel: an M7.7 200 km away shakes
the zone center more than an M4 right below it. The integration therefore
estimates the shaking at the zone center on the Modified Mercalli Intensity
(MMI) scale, which USGS and SGC also use. It uses the intensity prediction
equation of Allen, Wald and Worden (2012) for active crustal regions, with the
coefficients from OpenQuake:

```
R   = sqrt(distance^2 + depth^2)          distance to the hypocenter, in km
Rm  = -0.209 + 2.042 * exp(M - 5)
MMI = 2.085 + 1.428*M - 1.402*ln(sqrt(R^2 + Rm^2)) + 0.078*ln(R/50)   (last term only when R > 50 km)
```

The number is named with the USGS ShakeMap words, and the color follows the
damage ShakeMap expects:

| MMI | Shaking | Damage | Color |
|---|---|---|---|
| I | Not felt | None | green |
| II to III | Weak | None | green |
| IV | Light | None | yellow |
| V | Moderate | Very light | yellow |
| VI | Strong | Light | orange |
| VII | Very strong | Moderate | red |
| VIII and up | Severe, Violent, Extreme | Moderate to very heavy | red |

The colors are plain names that work in Home Assistant cards and in CSS.

Keep in mind:

- It is an estimate, usually within one step of what is measured. Checked
  against the 13 earthquakes in a sample where SGC measured an intensity, the
  estimate for the earthquake's own location was 0.4 higher on average and
  never more than 1.0 off.
- It is for the zone center only. Places nearer the earthquake shake more.
- Local ground is not included. Soft soil can add a step: the 1999 Armenia
  earthquake was M6.2 but reached IX in the city.
- The equation is made for shallow earthquakes. Depth still counts, but it is
  less exact for deep ones, such as those around 150 km below Bucaramanga.
- SGC's own **Measured shaking at the earthquake** (`intensity`) is the
  strongest shaking its stations recorded where the earthquake happened. It
  is filled in for only a few earthquakes, and it is not the shaking at your
  zone center.

## Map

The map panel shows the earthquakes by itself. For a map card, use the source
`sgc_earthquakes`, and label the markers with the magnitude if you like:

```yaml
type: map
geo_location_sources:
  - source: sgc_earthquakes
    label_mode: attribute
    attribute: magnitude
```

## Notify on an earthquake

```yaml
triggers:
  - trigger: geo_location
    source: sgc_earthquakes
    zone: zone.ibague
    event: enter
conditions:
  # Only earthquakes you would feel at the zone center (Weak or more).
  - condition: template
    value_template: "{{ trigger.to_state.attributes.shaking_mmi >= 1.5 }}"
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
        # Tapping the notification in the companion app opens the map
        # (url on iPhone, clickAction on Android).
        url: "{{ trigger.to_state.attributes.map_url }}"
        clickAction: "{{ trigger.to_state.attributes.map_url }}"
```

Things to know:

- `leave` is not useful here. Earthquakes leave when they get older than the
  period or drop out of the list.
- Saving settings under **Configure** keeps the earthquake entities, so the
  trigger does not fire again for them, for example when you switch the map
  app. An earthquake that a changed filter lets through does count as
  entering, and one it hides as leaving.
- **Reconfigure** and reloading the integration recreate every earthquake, so
  the trigger then sees them all as new. A Home Assistant restart does not do
  this. To be safe, you can add a condition on the earthquake's time, for
  example `{{ now() - trigger.to_state.attributes.time < timedelta(hours=6) }}`.
  With **Only earthquakes checked by SGC**, allow more time, since it holds
  earthquakes back until SGC has checked them.
- If the download fails, the earthquakes stay as they were (the sensors show
  unavailable), so a network problem does not look like earthquakes leaving.

## How it reads the SGC list

- The SGC server refuses Home Assistant's normal User-Agent, so the
  integration sends a browser-style one.
- SGC writes coordinates as latitude, longitude, depth. Standard GeoJSON is
  the other way round, so generic GeoJSON tools put these earthquakes in the
  wrong place.
- The list is checked every 5 minutes, and only downloaded again when it
  changed.

## Diagnostics

**Download diagnostics** on the integration or device page gives the settings,
the zone radius (not its location) and the earthquakes found.
