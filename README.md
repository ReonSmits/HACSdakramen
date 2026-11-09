# Casambi skylights in Home Assistant

A custom version of the Casambi Bluetooth integration for Home Assistant, made for the two Luxlight Illumy DNS skylights in the kitchen and the hall. Each skylight has lighting, a pleated blind (plissé) and a sunscreen (zonwering). With this version all three can be controlled from Home Assistant and the sunscreen automations run again.

It is based on the integration by [Superkikim/casambi-bt-hass](https://github.com/Superkikim/casambi-bt-hass), version `1.9.0.dev30` (commit `b4ab686` of 26 October 2026). Two code files were changed. Everything else is the same as the original. The original documentation is in [UPSTREAM_README.md](UPSTREAM_README.md).

## What was done

On 4 November 2026 the skylights suddenly stopped working. Blinds, sunscreens and lighting all showed `unavailable` in Home Assistant. On 9 November the cause was found and fixed.

### The cause

Two things happened at the same time.

* **Our own changes were gone.** Between 3 and 4 November Home Assistant was updated from 2026.10.1 to 2026.10.4. At the same time HACS updated the integration to the latest Superkikim version. That overwrote the local changes that turned the blind and sunscreen into covers in Home Assistant. The four covers were left behind as empty entities.
* **The library crashed on the skylights.** The integration uses the Python library `casambi-bt-skk` to talk to Casambi. That library breaks on the sliders of the Illumy. Every time a skylight sends its status, it fails with `ValueError: negative shift count`. Between 4 and 9 November that error was logged 328 times. Because the crash happens before the library marks the skylight as online, the lighting stayed unreachable as well.

### The fix

* **Covers restored.** Code was added to `cover.py` that turns each slider of the Illumy into a cover. The first one becomes the blind, the second one the sunscreen. The covers get the same unique ID as before. Home Assistant therefore recognises them as the old entities, and names, areas and automations keep working.
* **Crash caught.** At the top of `cover.py` there is a small patch to the library. It catches the error so the skylight still comes online. The integration reads the slider positions itself, in a way that does work.
* **Patch loaded early.** At the bottom of `__init__.py` there is one extra line that loads `cover.py` as soon as the integration starts. After the first restart the kitchen worked but the hall did not. The hall network connected within 0.2 seconds of starting, before the patch was active. Its first status message still crashed, and the hall stayed offline until it was reloaded by hand. With this line the patch is active before any connection is made.
* **Own name.** In `manifest.json` and `hacs.json` the integration is now called *Casambi Bluetooth (dakramen)*, with this repository as its documentation. The internal name `casambi_bt` was deliberately kept. Otherwise Home Assistant would see it as a new integration, and all connections and entities would be lost.

### Tested

* The new code was tested with the real library `casambi-bt-skk==0.4.0b5.post2` and a simulated skylight, with sliders of both 8 and 16 bits. There was no crash, the positions were read correctly, and moving one screen left the other screen and the lighting untouched.
* Installed at the Larikslaan on 9 November. After the restart and a reload of the hall, all six entities were reachable again.
* The extra line in `__init__.py` and installing via HACS from this repository have not yet been tested on a real installation. After the next restart both skylights should be reachable straight away, without a reload. That will confirm it.

## How it works

### How Home Assistant talks to the skylights

Casambi works over Bluetooth. Home Assistant connects to one of the devices in a Casambi network and can control the whole network through that device. Each skylight is its own network with one device, so there are two connections in Home Assistant: `Smits5511` for the kitchen and `Smits5511+` for the hall.

When a network is added, the integration fetches the network layout once from the Casambi cloud, using the network password. The layout lists which controls each device has. After that everything runs locally over Bluetooth.

Each device sends its status as a short row of bytes. Every control sits at a fixed position in those bytes, with a fixed length in bits. The Illumy DNS has six controls, in this order:

```
SENSOR       internal, not used
SENSOR       internal, not used
DIMMER       brightness of the lighting
TEMPERATURE  colour temperature of the lighting
SLIDER       blind      (slider 0)
SLIDER       sunscreen  (slider 1)
```

### Why the library crashes

The library converts every slider to an 8 bit value. It does that by shifting the raw value to the left by 8 minus the length of the slider. For a slider of 8 bits or less that works. The sliders of the Illumy are longer than 8 bits. The number then becomes negative, and Python does not allow a negative shift:

```python
scale = UnitState.SLIDER_RESOLUTION - c.length   # 8 minus a number larger than 8
self._state.slider = cInt << scale              # ValueError: negative shift count
```

This is in `CasambiBt/_unit.py`, in `Unit.setStateFromBytes`, around line 729. The older 0.4.0b2 versions of the library have the same bug.

The problem is where it fails. The library first reads the status, then marks the device as online, and then tells Home Assistant that something changed. The crash is in the first step. The rest never happens, so the whole skylight stays offline, lighting included.

### What the library patch does

The patch replaces `Unit.setStateFromBytes` with a version that calls the original and catches the `ValueError`. The controls are read in order and the sliders come last. When the crash happens, the raw bytes, the brightness and the colour temperature have already been stored. Only the sliders are missing, and the covers read those from the raw bytes themselves.

A flag `_casambi_illumy_patched` makes sure the patch is applied only once, also when the integration is reloaded.

### How the covers work

For every device whose mode starts with `EXT/`, that has sliders and no on/off control, the integration creates one cover per slider. The on/off rule keeps the Winsol Lamel out. That device also has sliders, but gets its own entities in `lamel_controls.py`.

* **Reading.** The cover takes the raw bytes of the device and extracts the bits of its own slider. Where those bits are and how long they are comes from the device layout. The code therefore does not need to know the exact width of the sliders and works for any length.
* **Converting.** The raw value is scaled to 0 to 100. The maximum value of the slider is 100, the minimum is 0. Nothing is reversed.
* **Moving.** The cover converts the requested position back to a raw value and sends it to the skylight with `setControlValue`. That function changes only the bits of that one slider and leaves the rest of the status as it is. Moving one screen therefore changes nothing on the other screen or the lighting.
* **Open or closed.** Home Assistant calls a cover closed at position 0. That is a Home Assistant convention and says nothing about the screen itself, see the direction below.
* **Unique ID.** Each cover gets the unique ID `{network ID}-unit-{device UUID}-slider-cover-{0 or 1}`. That is the same as the old version from before 4 November. Never change it, or Home Assistant creates new entities and the automations stop working.

### Direction of the screens

The screens do not all report their position the same way.

* For both blinds and for the hall sunscreen, position 100 is physically closed and position 0 is open.
* For the kitchen sunscreen it is the other way round. There, position 0 is physically closed and 100 is open. That is a factory fault in that one screen.

The integration does not reverse anything. The *Zonwering dakramen* automation therefore controls the two sunscreens in separate steps, with opposite values and three seconds in between, so they do not go over Bluetooth at the same time.

### Files

```
HACSdakramen/
├── custom_components/casambi_bt/
│   ├── __init__.py        start of the integration, changed: one line at the bottom
│   ├── cover.py           covers, changed: library patch and covers for the Illumy
│   ├── manifest.json      name, owner, link and version changed
│   ├── light.py           lighting, unchanged
│   ├── lamel_controls.py  Winsol Lamel, unchanged
│   └── ...                other files, unchanged
├── hacs.json              name in HACS changed
├── README.md              this file
└── UPSTREAM_README.md     original documentation by Superkikim
```

**cover.py** starts with the library patch, directly below `_LOGGER`. Below that are `_SLIDER_NAMES` with the names Plissé and Zonwering, `_slider_controls()` which decides which devices get covers, and `_read_bits()` which extracts bits from the raw status. `async_setup_entry` has an extra loop that creates the covers. The class `CasambiSliderCover` is at the bottom. The Winsol code by Superkikim in the same file was not changed.

**__init__.py** has `from . import cover as _illumy_patch` as its last line. It really has to be at the bottom. `cover.py` imports `CasambiApi` from `__init__.py`, and higher up in the file that class does not exist yet. The integration would then fail to start.

**manifest.json** has a new name, owner `@ReonSmits`, a link to this repository and version `1.9.0.dev31`. The `domain` is still `casambi_bt` and the library is still `casambi-bt-skk==0.4.0b5.post2`. Keep both as they are.

All changes in the code can be found by searching for `Illumy`. The full difference with the Superkikim version is shown by:

```bash
git diff b4ab686 HEAD -- custom_components hacs.json
```

## Installation

### Before you start

* Home Assistant OS with HACS. Tested on Home Assistant 2026.10.4 with HACS 2.0.5.
* A Bluetooth adapter or Bluetooth proxy within range of both skylights.
* This repository must be public, otherwise HACS cannot fetch it.
* Make a backup first via Settings, System, Backups.

### Switching from the Superkikim version

This is the situation at the Larikslaan. Connections, devices and entities stay in place. Only the code is replaced.

1. Open HACS and look up *Casambi Bluetooth (Superkikim fork)*. Choose remove from the three dot menu. Do not remove the integration under Settings, Devices and services. That would delete the connections and devices.
2. In HACS, open the three dot menu at the top right and choose *Custom repositories*. Enter `https://github.com/ReonSmits/HACSdakramen`, choose type *Integration* and click add.
3. Look up *Casambi Bluetooth (dakramen)* in HACS and click download.
4. Restart Home Assistant via Settings, System, the power menu.
5. Check that everything works, see below.

### New installation

1. Do steps 2 to 4 above.
2. Go to Settings, Devices and services. Usually the skylights are already listed as discovered. Otherwise add the integration *Casambi Bluetooth (dakramen)* yourself.
3. Add both networks, each with its own password. `Smits5511` is the kitchen at address `91:2F:EB:01:36:E1`. `Smits5511+` is the hall at address `79:03:A8:4B:A9:79`. This needs internet once.
4. Put the kitchen device in the Keuken area and the hall device in the Hal area.
5. Rename the entities to the names in the table below. Home Assistant makes up names such as `cover.illumy_dns_plisse_2`, which the automations do not know.
6. Restore the automations from a backup. They are not in this repository.
7. Check that everything works.

### Without HACS

Download this repository as a zip via the Code button on GitHub. In Studio Code Server, replace the folder `/config/custom_components/casambi_bt/` with the folder `custom_components/casambi_bt/` from the zip. Then restart Home Assistant.

### Check that everything works

Within a minute of the restart these six entities must have a state and must not be `unavailable`.

| Entity | What |
|---|---|
| `light.illumy_dns` | kitchen lighting |
| `cover.keuken_illumy_dns_plisse` | kitchen blind |
| `cover.keuken_illumy_dns_zonwering` | kitchen sunscreen |
| `light.illumy_dns_2` | hall lighting |
| `cover.illumy_dns_plisse` | hall blind |
| `cover.illumy_dns_zonwering` | hall sunscreen |

Then search the log for `casambi`. For each skylight there should be a line starting with `[CASAMBI_UNIT_PROFILE] id=1 name='Illumy DNS'`. The error `negative shift count` must not appear any more.

Finally, set the hall sunscreen to 100. It should physically close.

## Installation details

| | Kitchen | Hall |
|---|---|---|
| Casambi network | `Smits5511` | `Smits5511+` |
| Bluetooth address | `91:2F:EB:01:36:E1` | `79:03:A8:4B:A9:79` |
| Config entry | `01M0NHRC8DX66JGR82C62HVHXQ` | `01M0NNCMXVE6M8QP6C69G1PYHW` |
| Network ID | `BUPYNsWwwnIXV8uQeITsDdl6Quh4m6q3` | `Y00W32ihv2s5dtrvVVnnfqhzrztFdT0L` |
| Device UUID | `1EBC7B8A-79BA-449C-B652-15D22D16597F` | `857AEF8A-28AD-49E8-A7DC-BD57FED495E0` |

Both devices are a Luxlight Illumy DNS with firmware 12290 and mode `EXT/2ch/Dim,TW[NoMix]`. Powercalc measures the power use of the lighting in `sensor.dakraam_keuken_led_power` and `sensor.dakraam_hal_led_power`, with the matching `_energy` sensors.

These automations depend on the skylights:

* *Zonwering dakramen* controls the sunscreens based on the Met.no forecast and the Buienradar wind gusts. It uses the helper `input_datetime.zonwering_laatst_gesloten`, so the sunscreens close at most once a day.
* *Zonwering onbereikbaar waarschuwing*
* *Dakraam herstelpoging*
* *Dakraam hal volgt de verlichting* and *Dakraam woonkamer volgt de verlichting*
* *Plisse hal bij donker* and *Plisse woonkamer bij donker*
* *Kleuren herstellen na opstart*

Only *Zonwering dakramen* was reviewed in detail during the repair. For the others it is only known that they refer to the skylights.

## Troubleshooting

* **Everything `unavailable` and `negative shift count` in the log.** The library patch is not active. Check that `cover.py` contains the word `Illumy` and that the last line of `__init__.py` is the import of `cover`. If not, HACS has installed a different version. Install again using the steps above.
* **One skylight unreachable, the other works.** Usually Bluetooth. Reload that one network via Settings, Devices and services, Casambi, the network, the three dot menu. Messages like `Failed to connect` or `was not found` in the log point to range or interference. The kitchen has this now and then.
* **Lighting works, but the covers are missing.** The covers in `cover.py` are missing. Install again.
* **A screen moves the wrong way.** First check the direction of the screens. The kitchen sunscreen is reversed on purpose. If it is still wrong, change the calculation in `CasambiSliderCover` and then the automations.
* **It stops working after a Home Assistant update.** First check in HACS whether the integration was updated or replaced. Then check the first point.

### Getting back the version from before 4 November

The local version that ran until 3 November is not in this repository. HACS overwrote it. It only exists in backup `d872567e` of 3 November, made on Home Assistant 2026.10.1. That backup is encrypted with the backup key. Home Assistant cannot restore a single folder from a backup. A full restore takes everything back to 3 November. If you only want the old files, download the backup, decrypt it on a computer and take out the folder `homeassistant/custom_components/casambi_bt/`.

## Updating

### Taking over improvements from Superkikim

```bash
git clone https://github.com/ReonSmits/HACSdakramen
cd HACSdakramen
git remote add upstream https://github.com/Superkikim/casambi-bt-hass
git fetch upstream
git merge upstream/main
```

After merging, check that `cover.py` still contains `_safe_set_state_from_bytes`, `_slider_controls` and `CasambiSliderCover`, and that the last line of `__init__.py` is still there. Upstream will change its own `README.md`; keep ours and put theirs in `UPSTREAM_README.md`. Check that the `domain` in `manifest.json` is still `casambi_bt` and raise the version, for example to `1.9.0.dev32`. Push to `main`, update in HACS and restart Home Assistant.

### When the library patch can go

Only when `casambi-bt-skk` handles sliders longer than 8 bits itself. Then disable the patch for a while and check whether `negative shift count` comes back in the log.

## Points of attention

* Never install or update the Superkikim version in HACS again. It overwrites these changes, just like on 4 November.
* The integration uses `via_device`, which gives a warning in the log. From Home Assistant 2027.8 that stops working. Before that update it has to be changed to `via_device_id` in `entities.py`, or taken over from Superkikim if they have fixed it.
* The message `casambi-bt-skk=unknown` at startup is harmless. Only reading the version number fails. The library itself loads normally.
* The Superkikim repository has no licence file. Keep this repository for personal use where possible.
