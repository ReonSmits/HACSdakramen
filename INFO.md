# HACSdakramen: Casambi-integratie voor de Illumy DNS-dakramen

Eigen fork van [Superkikim/casambi-bt-hass](https://github.com/Superkikim/casambi-bt-hass),
gebaseerd op upstream-versie `1.9.0.dev30` (commit `b4ab686`, 26 oktober 2026), met de
aanpassingen die nodig zijn om de twee Luxlight **Illumy DNS**-dakramen (keuken en hal)
in Home Assistant te laten werken: lamp, plissé en zonwering.

Inhoud:

1. [Snel overzicht: wat is er aangepast](#1-snel-overzicht-wat-is-er-aangepast)
2. [Installatie van A tot Z](#2-installatie-van-a-tot-z)
3. [Controleren of alles werkt](#3-controleren-of-alles-werkt)
4. [Alle aanpassingen in detail](#4-alle-aanpassingen-in-detail)
5. [Hardware, netwerken en entiteiten](#5-hardware-netwerken-en-entiteiten)
6. [Problemen oplossen](#6-problemen-oplossen)
7. [Onderhoud: upstream bijwerken en HA-updates](#7-onderhoud-upstream-bijwerken-en-ha-updates)
8. [Geschiedenis van de storing (november 2026)](#8-geschiedenis-van-de-storing-november-2026)

---

## 1. Snel overzicht: wat is er aangepast

Ten opzichte van upstream `b4ab686` zijn precies deze bestanden gewijzigd. Al het andere
is ongewijzigd upstream.

| # | Bestand | Wat | Waarom |
|---|---|---|---|
| A | `custom_components/casambi_bt/cover.py` | Workaround voor de crash `negative shift count` (bovenaan het bestand) | Zonder deze workaround blijven de Illumy-units offline, en staan lamp én schermen op `unavailable` |
| B | `custom_components/casambi_bt/cover.py` | Nieuwe covers voor de SLIDER-controls: `_slider_controls()`, `_read_bits()`, `CasambiSliderCover`, en een extra lus in `async_setup_entry` | Upstream kent de plissé en zonwering van de Illumy niet |
| C | `custom_components/casambi_bt/__init__.py` | Eén import-regel helemaal onderaan | Zorgt dat workaround A actief is vóórdat Bluetooth verbindt |
| D | `custom_components/casambi_bt/manifest.json` | `name`, `codeowners`, `documentation`, `version` → `1.9.0.dev31` | Herkenbaar als eigen versie; `domain` en `requirements` zijn **niet** veranderd |
| E | `hacs.json` | `name` → `Casambi Bluetooth (dakramen)` | Naam in HACS |
| F | `INFO.md`, `README.md` | Deze documentatie en een verwijzing bovenaan de README | Terugvindbaarheid |

Zoek in de code op **`Illumy`** om alle aanpassingen in de code terug te vinden.
Het volledige verschil met upstream zie je met:

```bash
git diff b4ab686 HEAD -- custom_components hacs.json
```

> **Let op: dit is níet de oude versie van vóór 4 november.** De lokaal aangepaste versie
> die tot 3 november op Home Assistant draaide (met de toen gemaakte aanpassingen aan onder
> meer `__init__.py`) is bij de update van 4 november door HACS overschreven en bestaat niet
> meer op de HA-installatie. Deze repo is een **nieuwe** uitwerking op basis van upstream
> `b4ab686`, die hetzelfde resultaat geeft: dezelfde entiteiten met dezelfde unique IDs.
> De oude bestanden zitten alleen nog in back-up `d872567e` (zie §6.6).

---

## 2. Installatie van A tot Z

### A. Vooraf

- Home Assistant OS met HACS (getest op HA **2026.10.4**, Python 3.14.9, HACS 2.0.5).
- Een Bluetooth-adapter of Bluetooth-proxy binnen bereik van beide dakramen.
- Het wachtwoord van beide Casambi-netwerken (`Smits5511` en `Smits5511+`). Dat heb je
  alleen nodig bij een **nieuwe** installatie, niet bij het overstappen (B).
- Deze GitHub-repo moet **publiek** zijn, anders kan HACS hem niet ophalen.
- Maak voor de zekerheid eerst een back-up: *Instellingen → Systeem → Back-ups → Back-up maken*.

### B. Overstappen vanaf de Superkikim-versie (de situatie op de Larikslaan)

De bestaande koppelingen (config entries), apparaten en entiteiten blijven gewoon
staan. Je vervangt alleen de code.

1. **HACS openen**: *HACS* in de zijbalk.
2. **Oude repo uit HACS halen** (alleen de code, niet de koppeling):
   zoek *Casambi Bluetooth (Superkikim fork)* → ⋮ → **Verwijderen** / *Remove*.
   - Ga **niet** naar *Instellingen → Apparaten & diensten* om daar *Casambi* te verwijderen.
     Dan ben je de koppeling, de apparaten en de koppelingen in automations kwijt.
3. **Eigen repo toevoegen**: HACS → ⋮ (rechtsboven) → *Custom repositories*
   - Repository: `https://github.com/ReonSmits/HACSdakramen`
   - Type / Category: **Integration**
   - *Add*.
4. **Downloaden**: zoek in HACS *Casambi Bluetooth (dakramen)* → *Download* → kies de
   nieuwste versie (`main`) → *Download*.
5. **Home Assistant herstarten**: *Instellingen → Systeem → ⏻ → Home Assistant herstarten*.
6. **Controleren**: doe de checks uit [§3](#3-controleren-of-alles-werkt).

### C. Nieuwe installatie (bijvoorbeeld na een herinstallatie van HA)

1. Doe stap **B.3 t/m B.5** (repo toevoegen, downloaden, herstarten).
2. *Instellingen → Apparaten & diensten*. Meestal verschijnen de dakramen vanzelf als
   **Ontdekt** (via Bluetooth). Anders: *+ Integratie toevoegen* → *Casambi Bluetooth (dakramen)*.
3. Voeg **beide** netwerken toe, elk met het eigen wachtwoord:
   - `Smits5511` (keuken), adres `91:2F:EB:01:36:E1`
   - `Smits5511+` (hal), adres `79:03:A8:4B:A9:79`
4. Wijs de apparaten toe aan de ruimtes **Keuken** en **Hal**.
5. Controleer de entity_ids (zie [§5](#5-hardware-netwerken-en-entiteiten)). Wijken ze af,
   hernoem ze dan naar de namen uit de tabel, anders werken de automations niet.
6. Doe de checks uit [§3](#3-controleren-of-alles-werkt).

### D. Handmatig installeren (zonder HACS, noodgeval)

1. Download deze repo als zip: GitHub → *Code* → *Download ZIP*.
2. Open in HA **Studio Code Server** (of *Terminal & SSH*).
3. Vervang de hele map `/config/custom_components/casambi_bt/` door de map
   `custom_components/casambi_bt/` uit de zip.
4. Herstart Home Assistant en doe de checks uit §3.

### E. Na de installatie

- **Nooit meer** de Superkikim-repo in HACS installeren of updaten: die overschrijft deze
  aanpassingen (precies wat er op 4 november gebeurde).
- Updates van deze repo komen via HACS binnen als er iets naar `main` is gepusht.

---

## 3. Controleren of alles werkt

Binnen ongeveer een minuut na de herstart moeten **alle zes** de entiteiten een waarde
hebben (niet `unavailable`):

| Entiteit | Verwacht |
|---|---|
| `light.illumy_dns` | `on` / `off` |
| `cover.keuken_illumy_dns_plisse` | `open` / `closed` + positie |
| `cover.keuken_illumy_dns_zonwering` | `open` / `closed` + positie |
| `light.illumy_dns_2` | `on` / `off` |
| `cover.illumy_dns_plisse` | `open` / `closed` + positie |
| `cover.illumy_dns_zonwering` | `open` / `closed` + positie |

In de log (*Instellingen → Systeem → Logboeken*, zoek op `casambi`):

- **Goed**: `[CASAMBI_UNIT_PROFILE] id=1 name='Illumy DNS' … controls=['SENSOR', 'SENSOR', 'DIMMER', 'TEMPERATURE', 'SLIDER', 'SLIDER']`, één per netwerk.
- **Fout**: `ValueError: negative shift count`. Die mag **niet** meer verschijnen. Zie je
  hem wel, dan ontbreekt aanpassing A of C (zie §6.1).

Test daarna één raam met de hand: zet de zonwering van de hal op 100. Die moet fysiek
**dicht** gaan (zie de richting in §5).

---

## 4. Alle aanpassingen in detail

### A. Workaround voor de library-crash (`cover.py`, bovenaan)

**Probleem.** De library `casambi-bt-skk==0.4.0b5.post2` (en ook de oudere 0.4.0b2.x)
doet in `CasambiBt/_unit.py`, `Unit.setStateFromBytes()`, rond regel 729:

```python
scale = UnitState.SLIDER_RESOLUTION - c.length   # 8 - (breedte > 8) = negatief
self._state.slider = cInt << scale              # ValueError: negative shift count
```

De SLIDER-controls van de Illumy DNS zijn breder dan 8 bits, dus elk statuspakket crasht.
Dat gebeurt in `Casambi._dataCallback()` **vóór** `u._online = …` en vóór de
change-callbacks. Daardoor blijft de unit voor altijd offline en staan **alle**
entiteiten van het raam op `unavailable`, ook de lamp.

**Oplossing.** `Unit.setStateFromBytes` wordt vervangen door een wrapper die deze
`ValueError` opvangt. Op dat moment zijn `raw_state` en alle controls vóór de sliders
(dimmer, kleurtemperatuur) al ingelezen; de sliders zelf leest aanpassing B direct uit
`raw_state`.

```python
_orig_set_state_from_bytes = Unit.setStateFromBytes

def _safe_set_state_from_bytes(self: Unit, value: bytes) -> None:
    try:
        _orig_set_state_from_bytes(self, value)
    except ValueError as err:
        _LOGGER.debug("Ignored state parse error for unit %s: %s", self.name, err)

if not getattr(Unit.setStateFromBytes, "_casambi_illumy_patched", False):
    _safe_set_state_from_bytes._casambi_illumy_patched = True
    Unit.setStateFromBytes = _safe_set_state_from_bytes
```

De vlag `_casambi_illumy_patched` voorkomt dubbel patchen bij een reload.

**Wanneer kan dit weg?** Pas als de library SLIDER-controls van meer dan 8 bits zelf
goed afhandelt. Controleer dat door de workaround tijdelijk uit te zetten en in de log
te kijken of `negative shift count` terugkomt.

### B. Covers voor plissé en zonwering (`cover.py`)

**Probleem.** Upstream maakt alleen covers voor units met mode `EXT/1ch/Dim` (Winsol).
De Illumy heeft mode `EXT/2ch/Dim,TW[NoMix]` met twee SLIDER-controls; upstream maakt
daar niets van.

**Oplossing.** Nieuw in `cover.py`:

- `_SLIDER_NAMES = ("Plissé", "Zonwering")`: index 0 = Plissé, index 1 = Zonwering.
- `_slider_controls(unit)`: geeft de SLIDER-controls (gesorteerd op bit-offset) van units
  waarvan de mode met `EXT/` begint, die een SLIDER hebben en **geen** ONOFF. Zo vallen
  de Winsol Lamel (die heeft ONOFF en eigen entiteiten in `lamel_controls.py`) en
  gewone Winsol-covers erbuiten.
- `_read_bits(raw, offset, length)`: leest een bitveld uit `raw_state`, voor elke breedte.
- `CasambiSliderCover`:
  - `unique_id` = `{network_id}-unit-{unit_uuid}-slider-cover-{index}`, exact gelijk aan
    de oude versie, zodat de bestaande entiteiten, ruimtes en automations blijven werken
  - `entity_type = f"slider-cover-{index}"`, `device_class = blind`
  - functies: openen, sluiten, positie zetten
  - **positie** = `round(raw * 100 / max)`, met `max = 2**length - 1`: lineair, **niet omgekeerd**
  - `is_closed` = positie 0 (HA-conventie)
  - schrijven via `casa.setControlValue(unit, ctrl, raw)`: dat wijzigt alleen de bits van
    die ene slider, dus de lamp en het andere scherm blijven ongemoeid
- In `async_setup_entry` een extra lus die voor elke niet-Winsol-unit een
  `CasambiSliderCover` per SLIDER toevoegt.

### C. Workaround vroeg laden (`__init__.py`, allerlaatste regels)

```python
# Illumy DNS dakramen: import the cover module as soon as the integration loads,
# so its library workaround (see cover.py) is active before the first Bluetooth
# state packet arrives. Must stay at the bottom to avoid a circular import.
from . import cover as _illumy_patch  # noqa: E402,F401
```

**Waarom.** Zonder deze regel wordt `cover.py`, en daarmee workaround A, pas geladen als HA
het cover-platform opzet. Dat gebeurt ná het verbinden. Op 9 november verbond het
hal-netwerk 0,2 seconde vóór dat moment; het eerste statuspakket crashte alsnog en de hal
bleef `unavailable` tot een handmatige reload.

**Waarom onderaan.** `cover.py` importeert `CasambiApi` uit `__init__.py`. Staat de regel
hoger, dan bestaat `CasambiApi` nog niet en krijg je een circular-import-fout.

### D. `manifest.json`

```diff
-  "name": "Casambi Bluetooth (Superkikim fork)",
+  "name": "Casambi Bluetooth (dakramen)",
-  "codeowners": ["@Superkikim"],
+  "codeowners": ["@ReonSmits"],
-  "documentation": "https://github.com/Superkikim/casambi-bt-hass",
+  "documentation": "https://github.com/ReonSmits/HACSdakramen",
-  "version": "1.9.0.dev30"
+  "version": "1.9.0.dev31"
```

**Niet veranderd, en dat moet zo blijven:**
- `"domain": "casambi_bt"`: anders ziet HA het als een andere integratie en zijn alle
  koppelingen en entiteiten weg.
- `"requirements": ["casambi-bt-skk==0.4.0b5.post2"]`: de library waarop de workaround
  getest is.

### E. `hacs.json`

Alleen `"name"` → `"Casambi Bluetooth (dakramen)"`.

### Getest

De slider-logica is getest met de echte `casambi-bt-skk==0.4.0b5.post2` en een
nagebootste Illumy-unit, met sliders van zowel 8 als 16 bits:

- geen crash meer
- lezen geeft 25 % en 100 %
- 60 % zetten geeft de juiste ruwe waarde
- de andere slider en de lamp blijven ongewijzigd

Op 9 november daarna live bevestigd: alle zes de entiteiten weer beschikbaar.

---

## 5. Hardware, netwerken en entiteiten

### Netwerken

| | Keuken | Hal |
|---|---|---|
| Casambi-netwerk | `Smits5511` | `Smits5511+` |
| Config entry | `01M0NHRC8DX66JGR82C62HVHXQ` | `01M0NNCMXVE6M8QP6C69G1PYHW` |
| Bluetooth-adres | `91:2F:EB:01:36:E1` | `79:03:A8:4B:A9:79` |
| Network ID | `BUPYNsWwwnIXV8uQeITsDdl6Quh4m6q3` | `Y00W32ihv2s5dtrvVVnnfqhzrztFdT0L` |
| Unit UUID | `1EBC7B8A-79BA-449C-B652-15D22D16597F` | `857AEF8A-28AD-49E8-A7DC-BD57FED495E0` |

### De unit (beide ramen gelijk)

- naam `Illumy DNS`, fabrikant Luxlight, firmware 12290, device_id 1
- mode `EXT/2ch/Dim,TW[NoMix]`
- controls, op volgorde: `SENSOR, SENSOR, DIMMER, TEMPERATURE, SLIDER, SLIDER`
  - DIMMER + TEMPERATURE = de LED-verlichting
  - SLIDER 0 = plissé, SLIDER 1 = zonwering (beide breder dan 8 bits)

### Entiteiten

| Entiteit | Wat | Ruimte | Unique ID (einde) |
|---|---|---|---|
| `light.illumy_dns` | LED keuken | Keuken | `…-light` |
| `cover.keuken_illumy_dns_plisse` | plissé keuken | Keuken | `…-slider-cover-0` |
| `cover.keuken_illumy_dns_zonwering` | zonwering keuken | Keuken | `…-slider-cover-1` |
| `light.illumy_dns_2` | LED hal | Hal | `…-light` |
| `cover.illumy_dns_plisse` | plissé hal | Hal | `…-slider-cover-0` |
| `cover.illumy_dns_zonwering` | zonwering hal | Hal | `…-slider-cover-1` |
| `sensor.dakraam_keuken_led_power` / `_energy` | Powercalc keuken | | |
| `sensor.dakraam_hal_led_power` / `_energy` | Powercalc hal | | |

### Richting van de schermen (let op!)

| Scherm | Positie 100 | Positie 0 |
|---|---|---|
| Plissé keuken | dicht | open |
| Plissé hal | dicht | open |
| Zonwering hal | dicht | open |
| **Zonwering keuken** | **open** | **dicht** (omgekeerd, fabrieksfout in dat scherm) |

De automations houden hier rekening mee met aparte stappen per scherm. Verander de
schaal in `CasambiSliderCover` dus niet zonder ook de automations aan te passen.

### Automations die hiervan afhangen

- `automation.zonwering_dakramen`: weer-gestuurde zonwering (Met.no + Buienradar)
- `automation.zonwering_onbereikbaar_waarschuwing`
- `automation.dakraam_herstelpoging`
- `automation.dakraam_hal_koppelen_aan_verlichting`
- `automation.dakraam_woonkamer_koppelen_aan_verlichting`
- `automation.plisse_hal_bij_donker`, `automation.plisse_woonkamer_bij_donker`
- `automation.kleuren_herstellen_na_opstart`
- helper `input_datetime.zonwering_laatst_gesloten`

---

## 6. Problemen oplossen

### 6.1 Alles `unavailable` en `negative shift count` in de log

Workaround A is niet actief.

- Controleer dat `/config/custom_components/casambi_bt/cover.py` het woord `Illumy` bevat
  (helemaal bovenaan, bij `_safe_set_state_from_bytes`).
- Controleer dat de laatste regel van `__init__.py` `from . import cover as _illumy_patch`
  is (aanpassing C).
- Ontbreekt een van beide, dan heeft HACS waarschijnlijk een andere versie geïnstalleerd.
  Installeer opnieuw volgens §2B.

### 6.2 Eén raam `unavailable`, het andere werkt

Meestal Bluetooth. Herlaad alleen dat netwerk: *Instellingen → Apparaten & diensten →
Casambi → het netwerk → ⋮ → Herladen*. Helpt dat niet, dan:

- staat het raam aan (stroom), en is de adapter/proxy binnen bereik?
- in de log: `Failed to connect` / `device disconnected` / `was not found` = bereik of
  storing. `automation.dakraam_herstelpoging` probeert dit automatisch.

### 6.3 Lamp werkt, maar plissé/zonwering-entiteiten ontbreken

Aanpassing B ontbreekt (cover.py zonder `CasambiSliderCover`). Herinstalleer volgens §2B.

### 6.4 Scherm beweegt de verkeerde kant op

Controleer eerst de tabel *Richting van de schermen* in §5; de keuken-zonwering is
bewust omgekeerd. Klopt het daarna nog niet, pas dan de positieberekening in
`CasambiSliderCover.current_cover_position` / `_set_position` aan (`100 - …`) én de
automations.

### 6.5 Na een update van HA werkt het niet meer

Kijk eerst of HACS de integratie heeft bijgewerkt of vervangen (HACS → de integratie →
versie / repository). Controleer daarna §6.1.

### 6.6 De oude versie van vóór 4 november terughalen

Die zit in de HA-back-up **`d872567e`** (3 november 2026, HA 2026.10.1). De back-up is
versleuteld met de back-upsleutel. HA kan niet één map terugzetten; een volledige
restore zet de hele configuratie terug naar 3 november. Alleen doen als laatste redmiddel,
bij voorkeur door de back-up te downloaden en lokaal te ontsleutelen om er
`homeassistant/custom_components/casambi_bt/` uit te halen.

### 6.7 Terug naar de officiële Superkikim-versie

HACS → *Casambi Bluetooth (dakramen)* verwijderen → Superkikim-repo downloaden → herstarten.
Dan werken de dakramen **niet**, zolang upstream deze ondersteuning niet heeft.

---

## 7. Onderhoud: upstream bijwerken en HA-updates

### Upstream-verbeteringen overnemen

```bash
git clone https://github.com/ReonSmits/HACSdakramen
cd HACSdakramen
git remote add upstream https://github.com/Superkikim/casambi-bt-hass
git fetch upstream
git merge upstream/main
```

Controleer na de merge:

1. `cover.py` bevat nog `_safe_set_state_from_bytes`, `_slider_controls` en `CasambiSliderCover`.
2. De laatste regel van `__init__.py` is nog `from . import cover as _illumy_patch`.
3. `manifest.json`: `domain` is nog `casambi_bt`, `name` is nog *(dakramen)*. Hoog
   `version` op (bijvoorbeeld `1.9.0.dev32`).
4. Push naar `main`, update in HACS en herstart. Doe daarna de checks uit §3.

### Openstaande punten

- **`via_device` is deprecated** (warning in de log, `entities.py` en daardoor `light.py`
  en `cover.py`). Stopt met werken in **HA 2027.8**. Vóór die HA-update ombouwen naar
  `via_device_id`, of eerst kijken of upstream het al heeft opgelost en mergen.
- `[CASAMBI_STARTUP] casambi-bt-skk=unknown` in de log: alleen de versiemelding faalt,
  de library laadt gewoon. Onschuldig.
- Af en toe Bluetooth-verbindingsfouten op `91:2F:EB:01:36:E1` (keuken). Die worden
  opgevangen door `automation.dakraam_herstelpoging`.

---

## 8. Geschiedenis van de storing (november 2026)

| Datum | Wat |
|---|---|
| t/m 3 nov | Alles werkt, op HA 2026.10.1 met een lokaal aangepaste versie van de integratie. Laatste back-up daarvan: `d872567e`. |
| 3–4 nov | Update naar HA 2026.10.4 (Python 3.14.9). Tegelijk installeert HACS upstream-versie `b4ab686`, waarmee de lokale aanpassingen overschreven zijn. |
| 4–9 nov | Alle vier de covers "stale restored" / `unavailable`, beide Illumy-lampen ook. 328× `ValueError: negative shift count` in de log. |
| 9 nov | Oorzaak gevonden. Nieuwe `cover.py` (aanpassingen A + B) geplaatst en HA herstart: keuken werkt, hal pas na een reload. Daarom aanpassing C toegevoegd. Alles in deze repo gezet. |
