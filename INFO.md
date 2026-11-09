# Casambi dakramen in Home Assistant

Eigen versie van de Casambi Bluetooth integratie voor Home Assistant, gemaakt voor de twee Illumy DNS dakramen van Luxlight in de keuken en de hal. Elk dakraam heeft verlichting, een plissé en een zonwering. Met deze versie zijn alle drie te bedienen vanuit Home Assistant en lopen de automations voor de zonwering weer.

De basis is de integratie van [Superkikim/casambi-bt-hass](https://github.com/Superkikim/casambi-bt-hass), versie `1.9.0.dev30` (commit `b4ab686` van 26 oktober 2026). Daar zijn twee bestanden aan aangepast. Al het andere is gelijk aan het origineel.

## Wat er is gedaan

Op 4 november 2026 werkten de dakramen ineens niet meer. Plissé, zonwering en verlichting stonden in Home Assistant op `unavailable`. Op 9 november is de oorzaak gevonden en opgelost.

### De oorzaak

Er speelden twee dingen tegelijk.

* **De eigen aanpassingen waren weg.** Tussen 3 en 4 november is Home Assistant bijgewerkt van 2026.10.1 naar 2026.10.4. Tegelijk heeft HACS de integratie bijgewerkt naar de nieuwste versie van Superkikim. Daarmee zijn de lokale aanpassingen overschreven die de plissé en zonwering als cover in Home Assistant zetten. De vier covers bleven als lege entiteit achter.
* **De library crashte op de dakramen.** De integratie gebruikt de Python library `casambi-bt-skk` om met Casambi te praten. Die library loopt vast op de schuifregelaars van de Illumy. Elke keer dat een dakraam zijn status stuurt, volgt de fout `ValueError: negative shift count`. Tussen 4 en 9 november stond die fout 328 keer in de log. Omdat de crash gebeurt voordat de library het dakraam als online markeert, bleef ook de verlichting onbereikbaar.

### De oplossing

* **Covers terug.** In `cover.py` is code toegevoegd die van elke schuifregelaar van de Illumy een cover maakt. De eerste wordt de plissé, de tweede de zonwering. De covers krijgen dezelfde unique ID als vroeger. Daardoor herkent Home Assistant ze als de oude entiteiten en blijven namen, ruimtes en automations gewoon werken.
* **Crash afgevangen.** Bovenin `cover.py` staat een kleine aanpassing van de library. Die vangt de fout op, zodat het dakraam toch online komt. De stand van de schuifregelaars leest de integratie zelf, op een manier die wel werkt.
* **Aanpassing vroeg laden.** Onderaan `__init__.py` staat een extra regel die `cover.py` direct laadt als de integratie start. Na de eerste herstart werkte de keuken wel en de hal niet. Het hal netwerk had binnen 0,2 seconde na het starten al verbinding, nog voordat de aanpassing actief was. Het eerste statusbericht crashte daardoor alsnog en de hal bleef offline tot een handmatige herlaadactie. Met deze regel is de aanpassing actief voordat er verbinding is.
* **Eigen naam.** In `manifest.json` en `hacs.json` heet de integratie nu *Casambi Bluetooth (dakramen)*, met deze repository als documentatie. De interne naam `casambi_bt` is bewust gelijk gebleven. Anders ziet Home Assistant het als een nieuwe integratie en zijn alle koppelingen en entiteiten weg.

### Getest

* De nieuwe code is getest met de echte library `casambi-bt-skk==0.4.0b5.post2` en een nagebootst dakraam, met schuifregelaars van 8 en van 16 bits. Er was geen crash meer, het uitlezen van de stand klopte en bij het verzetten van één scherm bleven het andere scherm en de verlichting ongemoeid.
* Op 9 november op de Larikslaan geplaatst. Na de herstart en een herlaadactie van de hal waren alle zes de entiteiten weer bereikbaar.
* De extra regel in `__init__.py` en de installatie via HACS vanuit deze repository zijn nog niet op een echte installatie getest. Na de eerstvolgende herstart moeten beide dakramen direct bereikbaar zijn, zonder herlaadactie. Dan is dat ook bevestigd.

## Hoe het in elkaar zit

### Hoe Home Assistant met de dakramen praat

Casambi werkt via Bluetooth. Home Assistant verbindt met één van de apparaten in een Casambi netwerk en kan via dat apparaat het hele netwerk bedienen. Elk dakraam is een eigen netwerk met één apparaat, dus er zijn twee koppelingen in Home Assistant: `Smits5511` voor de keuken en `Smits5511+` voor de hal.

Bij het toevoegen van een netwerk haalt de integratie eenmalig de opbouw van het netwerk op uit de Casambi cloud, met het wachtwoord van het netwerk. Daarin staat per apparaat welke bedieningen het heeft. Daarna gaat alles lokaal via Bluetooth.

Elk apparaat stuurt zijn status als een rijtje bytes. In die bytes zit elke bediening op een vaste plek, met een vaste lengte in bits. De Illumy DNS heeft zes bedieningen, in deze volgorde:

```
SENSOR       intern, niet gebruikt
SENSOR       intern, niet gebruikt
DIMMER       helderheid van de verlichting
TEMPERATURE  kleurtemperatuur van de verlichting
SLIDER       plissé      (schuifregelaar 0)
SLIDER       zonwering   (schuifregelaar 1)
```

### Waarom de library crasht

De library rekent elke schuifregelaar om naar een waarde van 8 bits. Dat doet hij door de ruwe waarde een aantal plaatsen naar links te schuiven, namelijk 8 min de lengte van de regelaar. Bij een regelaar van 8 bits of minder gaat dat goed. De schuifregelaars van de Illumy zijn langer dan 8 bits. Dan wordt dat getal negatief, en een negatieve schuif mag in Python niet:

```python
scale = UnitState.SLIDER_RESOLUTION - c.length   # 8 min een getal groter dan 8
self._state.slider = cInt << scale              # ValueError: negative shift count
```

Dit staat in `CasambiBt/_unit.py`, in `Unit.setStateFromBytes`, rond regel 729. De fout zit ook in de oudere versies 0.4.0b2 van de library.

Het vervelende is waar het misgaat. De library leest eerst de status, zet daarna het apparaat op online en laat daarna Home Assistant weten dat er iets veranderd is. De crash zit in de eerste stap. Daardoor gebeurt de rest nooit en blijft het hele dakraam offline, ook de verlichting.

### Wat de aanpassing van de library doet

De aanpassing vervangt `Unit.setStateFromBytes` door een versie die de originele aanroept en de `ValueError` opvangt. De bedieningen worden op volgorde gelezen en de schuifregelaars komen als laatste. Op het moment van de crash zijn de ruwe bytes, de helderheid en de kleurtemperatuur dus al opgeslagen. Alleen de schuifregelaars ontbreken, en die leest de cover zelf uit de ruwe bytes.

Een vlag `_casambi_illumy_patched` zorgt dat de aanpassing maar één keer wordt toegepast, ook als de integratie wordt herladen.

### Hoe de covers werken

Voor elk apparaat dat begint met `EXT/`, schuifregelaars heeft en geen aan/uit bediening, maakt de integratie per schuifregelaar een cover. Dat laatste is nodig om de Winsol Lamel buiten te houden. Die heeft ook schuifregelaars, maar krijgt eigen entiteiten in `lamel_controls.py`.

* **Uitlezen.** De cover pakt de ruwe bytes van het apparaat en haalt daar de bits van zijn eigen schuifregelaar uit. Waar die staan en hoe lang ze zijn, leest hij uit de opbouw van het apparaat. De code hoeft de exacte breedte van de schuifregelaars dus niet te kennen en werkt bij elke lengte.
* **Omrekenen.** De ruwe waarde wordt omgerekend naar 0 tot 100. De maximale waarde van de regelaar is 100, de minimale waarde is 0. Er wordt niets omgedraaid.
* **Verzetten.** De cover rekent de gewenste stand terug naar een ruwe waarde en stuurt die met `setControlValue` naar het dakraam. Die functie past alleen de bits van die ene schuifregelaar aan en laat de rest van de status staan. Een scherm verzetten verandert dus niets aan het andere scherm of aan de verlichting.
* **Dicht of open.** Home Assistant noemt een cover dicht bij stand 0. Dat is een afspraak in Home Assistant en zegt niets over het scherm zelf, zie de richting hieronder.
* **Unique ID.** Elke cover krijgt als unique ID `{netwerk ID}-unit-{apparaat UUID}-slider-cover-{0 of 1}`. Dat is gelijk aan de oude versie van vóór 4 november. Verander dit nooit, anders maakt Home Assistant nieuwe entiteiten aan en werken de automations niet meer.

### Richting van de schermen

De schermen melden hun stand niet allemaal op dezelfde manier.

* Bij beide plissés en bij de zonwering van de hal is stand 100 fysiek dicht en stand 0 open.
* Bij de zonwering van de keuken is het omgekeerd. Daar is stand 0 fysiek dicht en 100 open. Dat is een fabrieksfout in dat ene scherm.

De integratie draait niets om. De automation *Zonwering dakramen* stuurt beide zonweringen daarom in losse stappen aan, met tegengestelde waarden en drie seconden ertussen, zodat ze niet tegelijk over Bluetooth gaan.

### Bestanden

```
HACSdakramen/
├── custom_components/casambi_bt/
│   ├── __init__.py        opstart van de integratie, aangepast: één regel onderaan
│   ├── cover.py           covers, aangepast: library fix en covers voor de Illumy
│   ├── manifest.json      naam, eigenaar, link en versie aangepast
│   ├── light.py           verlichting, ongewijzigd
│   ├── lamel_controls.py  Winsol Lamel, ongewijzigd
│   └── ...                overige bestanden, ongewijzigd
├── hacs.json              naam in HACS aangepast
├── INFO.md                dit bestand
└── README.md              documentatie van Superkikim, met bovenaan een verwijzing hierheen
```

**cover.py** begint met de aanpassing van de library, direct onder `_LOGGER`. Daaronder staan `_SLIDER_NAMES` met de namen Plissé en Zonwering, `_slider_controls()` die bepaalt welke apparaten covers krijgen, en `_read_bits()` die bits uit de ruwe status haalt. In `async_setup_entry` staat een extra lus die de covers aanmaakt. Onderaan staat de class `CasambiSliderCover`. De Winsol code van Superkikim in hetzelfde bestand is niet veranderd.

**__init__.py** heeft als laatste regel `from . import cover as _illumy_patch`. Die moet echt onderaan staan. `cover.py` haalt `CasambiApi` uit `__init__.py`, en hoger in het bestand bestaat die nog niet. Dan start de integratie niet.

**manifest.json** heeft een nieuwe naam, eigenaar `@ReonSmits`, een link naar deze repository en versie `1.9.0.dev31`. De `domain` is nog `casambi_bt` en de library is nog `casambi-bt-skk==0.4.0b5.post2`. Houd die twee zo.

Alle aanpassingen in de code zijn terug te vinden door te zoeken op `Illumy`. Het volledige verschil met de versie van Superkikim zie je met:

```bash
git diff b4ab686 HEAD -- custom_components hacs.json
```

## Installeren

### Vooraf

* Home Assistant OS met HACS. Getest op Home Assistant 2026.10.4 met HACS 2.0.5.
* Een Bluetooth adapter of Bluetooth proxy binnen bereik van beide dakramen.
* Deze repository moet publiek zijn, anders kan HACS hem niet ophalen.
* Maak eerst een back-up via Instellingen, Systeem, Back-ups.

### Overstappen vanaf de versie van Superkikim

Dit is de situatie op de Larikslaan. De koppelingen, apparaten en entiteiten blijven staan. Alleen de code wordt vervangen.

1. Open HACS en zoek *Casambi Bluetooth (Superkikim fork)*. Kies via het menu met de drie puntjes voor verwijderen. Verwijder de integratie niet onder Instellingen, Apparaten en diensten. Dan ben je de koppelingen en apparaten kwijt.
2. Kies in HACS rechtsboven het menu met de drie puntjes en dan *Custom repositories*. Vul `https://github.com/ReonSmits/HACSdakramen` in, kies type *Integration* en klik op toevoegen.
3. Zoek in HACS *Casambi Bluetooth (dakramen)* en klik op downloaden.
4. Herstart Home Assistant via Instellingen, Systeem, het aan/uit menu.
5. Controleer of alles werkt, zie hieronder.

### Nieuwe installatie

1. Doe stap 2 tot en met 4 hierboven.
2. Ga naar Instellingen, Apparaten en diensten. Meestal staan de dakramen er al als ontdekt apparaat. Anders voeg je de integratie *Casambi Bluetooth (dakramen)* zelf toe.
3. Voeg beide netwerken toe, elk met het eigen wachtwoord. `Smits5511` is de keuken op adres `91:2F:EB:01:36:E1`. `Smits5511+` is de hal op adres `79:03:A8:4B:A9:79`. Hiervoor is eenmalig internet nodig.
4. Zet het apparaat van de keuken in de ruimte Keuken en dat van de hal in de ruimte Hal.
5. Hernoem de entiteiten naar de namen in de tabel hieronder. Home Assistant maakt zelf namen als `cover.illumy_dns_plisse_2`. Die kennen de automations niet.
6. Zet de automations terug uit een back-up. Die staan niet in deze repository.
7. Controleer of alles werkt.

### Zonder HACS

Download deze repository als zip via de knop Code op GitHub. Vervang in Studio Code Server de map `/config/custom_components/casambi_bt/` door de map `custom_components/casambi_bt/` uit de zip. Herstart daarna Home Assistant.

### Controleren of alles werkt

Binnen een minuut na de herstart moeten deze zes entiteiten een stand hebben en niet op `unavailable` staan.

| Entiteit | Wat |
|---|---|
| `light.illumy_dns` | verlichting keuken |
| `cover.keuken_illumy_dns_plisse` | plissé keuken |
| `cover.keuken_illumy_dns_zonwering` | zonwering keuken |
| `light.illumy_dns_2` | verlichting hal |
| `cover.illumy_dns_plisse` | plissé hal |
| `cover.illumy_dns_zonwering` | zonwering hal |

Zoek daarna in de log op `casambi`. Per dakraam hoort er een regel te staan die begint met `[CASAMBI_UNIT_PROFILE] id=1 name='Illumy DNS'`. De fout `negative shift count` mag niet meer voorkomen.

Zet tot slot de zonwering van de hal op 100. Die moet fysiek dicht gaan.

## Gegevens van de installatie

| | Keuken | Hal |
|---|---|---|
| Casambi netwerk | `Smits5511` | `Smits5511+` |
| Bluetooth adres | `91:2F:EB:01:36:E1` | `79:03:A8:4B:A9:79` |
| Config entry | `01M0NHRC8DX66JGR82C62HVHXQ` | `01M0NNCMXVE6M8QP6C69G1PYHW` |
| Netwerk ID | `BUPYNsWwwnIXV8uQeITsDdl6Quh4m6q3` | `Y00W32ihv2s5dtrvVVnnfqhzrztFdT0L` |
| Apparaat UUID | `1EBC7B8A-79BA-449C-B652-15D22D16597F` | `857AEF8A-28AD-49E8-A7DC-BD57FED495E0` |

Beide apparaten zijn een Illumy DNS van Luxlight met firmware 12290 en mode `EXT/2ch/Dim,TW[NoMix]`. Powercalc meet het verbruik van de verlichting in `sensor.dakraam_keuken_led_power` en `sensor.dakraam_hal_led_power`, met de bijbehorende `_energy` sensoren.

Deze automations hangen van de dakramen af:

* *Zonwering dakramen* stuurt de zonwering op basis van de weersverwachting van Met.no en de windstoten van Buienradar. Gebruikt de helper `input_datetime.zonwering_laatst_gesloten`, zodat de zonwering hooguit één keer per dag sluit.
* *Zonwering onbereikbaar waarschuwing*
* *Dakraam herstelpoging*
* *Dakraam hal volgt de verlichting* en *Dakraam woonkamer volgt de verlichting*
* *Plisse hal bij donker* en *Plisse woonkamer bij donker*
* *Kleuren herstellen na opstart*

Alleen *Zonwering dakramen* is bij het herstel inhoudelijk bekeken. Van de andere is alleen bekend dat ze naar de dakramen verwijzen.

## Problemen oplossen

* **Alles op `unavailable` en `negative shift count` in de log.** De aanpassing van de library is niet actief. Controleer of `cover.py` het woord `Illumy` bevat en of de laatste regel van `__init__.py` de import van `cover` is. Zo niet, dan heeft HACS een andere versie neergezet. Installeer opnieuw volgens de stappen hierboven.
* **Eén dakraam onbereikbaar, het andere werkt.** Meestal Bluetooth. Herlaad dat ene netwerk via Instellingen, Apparaten en diensten, Casambi, het netwerk, het menu met de drie puntjes. Meldingen als `Failed to connect` of `was not found` in de log wijzen op bereik of een storing. De keuken heeft dit af en toe.
* **Verlichting werkt, maar de covers ontbreken.** De covers in `cover.py` ontbreken. Installeer opnieuw.
* **Een scherm gaat de verkeerde kant op.** Kijk eerst bij de richting van de schermen. De zonwering van de keuken is bewust omgekeerd. Klopt het dan nog niet, pas dan de berekening in `CasambiSliderCover` aan en daarna de automations.
* **Na een update van Home Assistant werkt het niet meer.** Kijk eerst in HACS of de integratie is bijgewerkt of vervangen. Controleer daarna het eerste punt.

### De versie van vóór 4 november terughalen

De lokale versie die tot 3 november draaide staat niet in deze repository. Die is door HACS overschreven. Hij zit alleen nog in de back-up `d872567e` van 3 november, gemaakt op Home Assistant 2026.10.1. Die back-up is versleuteld met de back-upsleutel. Home Assistant kan niet één map uit een back-up terugzetten. Een volledige restore zet alles terug naar 3 november. Wil je alleen de oude bestanden, download de back-up dan, ontsleutel hem op een computer en haal de map `homeassistant/custom_components/casambi_bt/` eruit.

## Bijwerken

### Verbeteringen van Superkikim overnemen

```bash
git clone https://github.com/ReonSmits/HACSdakramen
cd HACSdakramen
git remote add upstream https://github.com/Superkikim/casambi-bt-hass
git fetch upstream
git merge upstream/main
```

Controleer na het samenvoegen of `cover.py` nog `_safe_set_state_from_bytes`, `_slider_controls` en `CasambiSliderCover` bevat, en of de laatste regel van `__init__.py` er nog staat. Controleer in `manifest.json` of de `domain` nog `casambi_bt` is en verhoog de versie, bijvoorbeeld naar `1.9.0.dev32`. Push naar `main`, werk bij in HACS en herstart Home Assistant.

### Wanneer de aanpassing van de library weg kan

Pas als `casambi-bt-skk` schuifregelaars van meer dan 8 bits zelf goed verwerkt. Zet de aanpassing dan tijdelijk uit en kijk of `negative shift count` terugkomt in de log.

## Aandachtspunten

* Installeer of update nooit meer de versie van Superkikim in HACS. Die overschrijft deze aanpassingen, net als op 4 november.
* De integratie gebruikt `via_device`, en dat geeft een waarschuwing in de log. Vanaf Home Assistant 2027.8 werkt dat niet meer. Vóór die update moet het in `entities.py` worden omgezet naar `via_device_id`, of overgenomen worden van Superkikim als die het heeft opgelost.
* De melding `casambi-bt-skk=unknown` bij het opstarten is onschuldig. Alleen het uitlezen van het versienummer mislukt. De library zelf laadt gewoon.
* De repository van Superkikim heeft geen licentiebestand. Houd deze repository daarom bij voorkeur voor eigen gebruik.
