# HACSdakramen: Casambi-integratie voor de Illumy DNS-dakramen

Eigen fork van [Superkikim/casambi-bt-hass](https://github.com/Superkikim/casambi-bt-hass)
(versie `1.9.0.dev30`, commit `b4ab686`) met de aanpassingen die nodig zijn voor de
twee Luxlight **Illumy DNS**-dakramen in Home Assistant (Larikslaan).

## Hardware en netwerken

| | Keuken | Hal |
|---|---|---|
| Casambi-netwerk | `Smits5511` | `Smits5511+` |
| Config entry | `01M0NHRC8DX66JGR82C62HVHXQ` | `01M0NNCMXVE6M8QP6C69G1PYHW` |
| Bluetooth-adres | `91:2F:EB:01:36:E1` | `79:03:A8:4B:A9:79` |
| Network ID | `BUPYNsWwwnIXV8uQeITsDdl6Quh4m6q3` | `Y00W32ihv2s5dtrvVVnnfqhzrztFdT0L` |
| Unit UUID | `1EBC7B8A-79BA-449C-B652-15D22D16597F` | `857AEF8A-28AD-49E8-A7DC-BD57FED495E0` |

Elk raam is één Casambi-unit:

- naam `Illumy DNS`, fabrikant Luxlight, firmware 12290
- mode `EXT/2ch/Dim,TW[NoMix]`
- controls, op volgorde: `SENSOR, SENSOR, DIMMER, TEMPERATURE, SLIDER, SLIDER`
  - DIMMER + TEMPERATURE = de LED-verlichting (lamp met kleurtemperatuur)
  - SLIDER 0 = **plissé**
  - SLIDER 1 = **zonwering**
- de SLIDER-controls zijn **breder dan 8 bits**, en dat is de oorzaak van de library-bug hieronder

## Entiteiten in Home Assistant

| Entiteit | Wat | Unique ID (einde) |
|---|---|---|
| `light.illumy_dns` | LED keuken | `…-unit-1EBC7B8A…-light` |
| `cover.keuken_illumy_dns_plisse` | plissé keuken | `…-slider-cover-0` |
| `cover.keuken_illumy_dns_zonwering` | zonwering keuken | `…-slider-cover-1` |
| `light.illumy_dns_2` | LED hal | |
| `cover.illumy_dns_plisse` | plissé hal | `…-slider-cover-0` |
| `cover.illumy_dns_zonwering` | zonwering hal | `…-slider-cover-1` |
| `sensor.dakraam_{keuken,hal}_led_{power,energy}` | Powercalc | |

Unique-ID-formaat: `{network_id}-unit-{unit_uuid}-slider-cover-{index}`. Verander dat
nooit, anders krijgen alle covers nieuwe entity_ids en breken de automations.

### Richting van de schermen (let op!)

De positie is de sliderwaarde, lineair geschaald naar 0–100 en **niet omgekeerd**
(slider op maximum = 100).

- Plissé keuken, plissé hal, zonwering hal: **100 = fysiek dicht**, 0 = open
- Zonwering keuken: **omgekeerd**, 0 = fysiek dicht, 100 = open (fabrieksfout in dat scherm)

De automations houden hier rekening mee met aparte stappen per scherm.

### Automations die van deze entiteiten afhangen

- `automation.zonwering_dakramen`: weer-gestuurde zonwering (Met.no + Buienradar)
- `automation.zonwering_onbereikbaar_waarschuwing`
- `automation.dakraam_herstelpoging`
- `automation.dakraam_hal_koppelen_aan_verlichting` / `automation.dakraam_woonkamer_koppelen_aan_verlichting`
- `automation.plisse_hal_bij_donker` / `automation.plisse_woonkamer_bij_donker`
- `automation.kleuren_herstellen_na_opstart`

## Aanpassingen ten opzichte van upstream

### 1. Covers voor de SLIDER-controls (`cover.py`)

Upstream maakt alleen covers voor `EXT/1ch/Dim`-units (Winsol). Voor de Illumy maakt deze
fork per SLIDER een `CasambiSliderCover` (`_slider_controls()`, `CasambiSliderCover`):

- detectie: mode begint met `EXT/`, heeft een SLIDER en **geen** ONOFF (dat sluit de
  Winsol Lamel uit, die zit in `lamel_controls.py`)
- lezen: bits direct uit `unit.state.raw_state` (`_read_bits`), werkt bij elke bitbreedte
- schrijven: `casa.setControlValue(unit, ctrl, raw)`, die alleen de bits van die slider
  wijzigt en de rest van de state (lamp!) intact laat
- namen: index 0 = `Plissé`, index 1 = `Zonwering`, device_class `blind`

### 2. Workaround voor de library-bug (`cover.py`, bovenaan)

`casambi-bt-skk==0.4.0b5.post2` (en ook 0.4.0b2.x) doet in `Unit.setStateFromBytes`:

```python
scale = UnitState.SLIDER_RESOLUTION - c.length   # 8 - 16 = negatief
self._state.slider = cInt << scale              # ValueError: negative shift count
```

Die fout gebeurt in `_dataCallback` **voordat** `u._online` wordt gezet. Daardoor bleef
de hele unit offline en stonden ook de lampen op `unavailable`. De fork vervangt
`Unit.setStateFromBytes` door een wrapper die deze `ValueError` opvangt. `raw_state` en
alle controls vóór de sliders zijn dan al geparsed, en de covers lezen de sliders zelf.

### 3. Patch vroeg laden (`__init__.py`, onderaan)

```python
from . import cover as _illumy_patch  # noqa: E402,F401
```

Zonder deze regel wordt de patch pas actief als het cover-platform laadt. Bij een herstart
verbond het hal-netwerk 0,2 s eerder, waardoor het eerste statuspakket alsnog crashte en
de hal `unavailable` bleef tot een reload. Deze regel moet **onderaan** staan, anders
krijg je een circular import (`cover.py` importeert `CasambiApi` uit `__init__.py`).

### 4. Manifest

`name`, `documentation`, `codeowners` en `version` (`1.9.0.dev31`) aangepast. De
`requirements` zijn ongewijzigd (`casambi-bt-skk==0.4.0b5.post2`). Het domein blijft
`casambi_bt`, zodat bestaande config entries en entiteiten gewoon doorwerken.

## Geschiedenis van de storing (november 2026)

- Tot 3 november werkte alles, op HA 2026.10.1 met een lokaal aangepaste versie.
- Tussen 3 en 4 november: update naar HA 2026.10.4 (Python 3.14.9). Tegelijk heeft HACS
  de upstream-versie `b4ab686` geïnstalleerd, waarmee de lokale aanpassingen weg waren.
  De laatste back-up met de oude versie is `d872567e` (3 november, 2026.10.1, versleuteld).
- Vanaf 4 november: alle covers stonden op "stale restored / unavailable", de lampen ook,
  met 328× `negative shift count` in de log.
- 9 november: hersteld met de aanpassingen hierboven. Na de herstart moest het hal-netwerk
  nog één keer herladen worden (aanpassing 3 voorkomt dat voortaan).

## Installatie via HACS

1. HACS → Integraties → ⋮ → *Custom repositories* → `https://github.com/ReonSmits/HACSdakramen`, categorie *Integration*.
2. Verwijder in HACS de oude repository `Superkikim/casambi-bt-hass` (alleen uit HACS, **niet**
   de integratie in Instellingen → Apparaten, want de config entries moeten blijven).
3. Download *Casambi Bluetooth (dakramen)* en herstart Home Assistant.
4. Controleer dat alle zes de entiteiten hierboven beschikbaar zijn.

Update **niet** meer vanuit de Superkikim-repo: die overschrijft deze aanpassingen.

## Bekende openstaande punten

- Warning `via_device` is deprecated (in `entities.py`, `DeviceInfo(via_device=…)`).
  Stopt met werken in **HA 2027.8**, dus vóór die update ombouwen naar `via_device_id`
  of laten oplossen door upstream.
- `[CASAMBI_STARTUP] casambi-bt-skk=unknown`: alleen de versiemelding faalt, de library
  zelf laadt wel. Onschuldig.
- Bluetooth-verbindingsfouten (`Failed to connect`, `device disconnected`) op
  `91:2F:EB:01:36:E1` komen af en toe voor. `automation.dakraam_herstelpoging` vangt dat op.
- Upstream bijwerken: `git fetch upstream && git merge upstream/main` en daarna controleren
  dat `cover.py` en de regel onderaan `__init__.py` er nog in staan.

## Testen zonder Home Assistant

De slider-logica is getest met de echte `casambi-bt-skk==0.4.0b5.post2` en een
nagebootste Illumy-unit (sliders van 8 en 16 bits): geen crash, lezen 25/100 %,
schrijven 60 % geeft de juiste ruwe waarde, en de andere slider en de lamp blijven
ongewijzigd.
