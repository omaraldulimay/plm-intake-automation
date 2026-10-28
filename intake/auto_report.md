# Alltagslauf 2026-10-28 09:26 (AUSGEFUEHRT)

Neu: 15 Dokument-Dateien, 343 Ereignis-Dateien

## Lieferanten
- LIEFERANT_J TEKSTİL SAN.VE TİC.LTD.ŞTİ.: MENSCH ALIAS_PRUEFEN [('Lieferant J', 1.0)]

PO-Nummern per Browser nachgeladen: 72

## Neue Produkte (Stylenummer des Lieferanten als vorlaeufige SKU, Tag SKU-OFFEN)
- BF_26069 | BF_26069 Hoodie | Groessen XS,S,M,L,XL,2XL,3XL | Farben Black

- Farben: {'Black': 'vorhanden'}

WARNUNG Produktanlage fehlgeschlagen: CSV-Import gescheitert: locator.waitFor: Timeout 60000ms exceeded.
Call log:
  - waiting for locator('button[aria-label="Import CSV"]') to be visible

    at /home/runner/work/Dashboard-Produktion/Dashboard-Produktion/plm_intake/browser/import_csv.js:16:19
. Neue Bestellungen warten auf den naechsten Lauf, Rest laeuft weiter. Stand im PLM pruefen.
## Neue Bestellungen (CREATE)
- keine

## Preis-Nachtrag (Beleg mit Stueckpreisen zu Order mit Preis 0)
- keine

## Belege zu bestehenden Bestellungen
# Belege zu bestehenden Bestellungen

| Datei | Art | PO | gehoert zu |
|---|---|---|---|
| 1a0a957bca78ab0b_1.json | SERVICE_DOC | SI_2026_06_0047 | keine Warenpositionen (Fracht/Zoll/Spedition) |
| 1a0a96031405ab96_1.json | SERVICE_DOC | 247606 | keine Warenpositionen (Fracht/Zoll/Spedition) |
| 1a0a9c85d2b85dfb_1.json | SERVICE_DOC | 247606 | keine Warenpositionen (Fracht/Zoll/Spedition) |
| 1a0f19e1626c8806_1.json | SKIP | - | #25 PO-LIEFERANT_D-ALI20260821 |
| 1a0f2f5c1a0e0aa7_1.json | SKIP | - | #25 PO-LIEFERANT_D-ALI20260821 |
| 1a13103fd472a81b_1.json | ORPHAN_DOC | 62092211 | - |
| 1a1538b5bb3f6600_1.json | AMBIGUOUS_DOC | - | passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08 |
| 1a1538b5bb3f6600_2.json | AMBIGUOUS_DOC | - | passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08 |
| 1a1682ab9dcc2d5a_1.json | ORPHAN_DOC | - | - |
| 1a1685b25906026e_1.json | NONE | TBC / DRAFT | - |
| 1a168c1bddb1726c_1.json | BLOCKER | - | Lieferant unbekannt: None (nicht gefunden) |
| 1a176dd5eaeba732_1.json | BLOCKER | - | Lieferant unbekannt: LIEFERANT_J TEKSTİL SAN.VE TİC.LTD.ŞTİ. (nicht gefunden) |
| 1a177ba249af249a_1.json | AMBIGUOUS_DOC | 561874_2510 | passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08 |
| 1a17c5576c0d951e_1.json | REORDER_QUESTION | JM1020-JM260704 | #4 PO-LIEFERANT_X-JM260704 |
| 1a17dcd1b307e869_1.json | AMBIGUOUS_DOC | SPR2026000000445 | passt zu mehreren Orders: PO-LIEFERANT_I-SPR2026000000438, PO-LIEFERANT_I-SPR2026000000422, PO-LIEFERANT_I-SPR2026000000409 |

## Beleg ohne Bestell-PO im PLM (erst PI/PO anlegen, dann Beleg zuordnen)
- 1a13103fd472a81b_1.json (62092211)
- 1a1682ab9dcc2d5a_1.json (None)

## Dienstleister-Belege ohne Warenpositionen (Spedition, Zoll): kein PO-Bezug, nur zur Info
- 1a0a957bca78ab0b_1.json (SI_2026_06_0047)
- 1a0a96031405ab96_1.json (247606)
- 1a0a9c85d2b85dfb_1.json (247606)

## Beleg passt zu mehreren Orders (Mensch waehlt, per overrides.json oder PO-Nummer im Beleg klaeren)
- 1a1538b5bb3f6600_1.json (None): passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a1538b5bb3f6600_2.json (None): passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a177ba249af249a_1.json (561874_2510): passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a17dcd1b307e869_1.json (SPR2026000000445): passt zu mehreren Orders: PO-LIEFERANT_I-SPR2026000000438, PO-LIEFERANT_I-SPR2026000000422, PO-LIEFERANT_I-SPR2026000000409

## Entscheidung noetig (Reorder oder Teil derselben Bestellung?)
Per overrides.json: NOTE = nur Notiz an vorhandene PO, CREATE = neue PO, SKIP = ignorieren:
- 1a17c5576c0d951e_1.json -> vorhanden: #4 PO-LIEFERANT_X-JM260704

## Notizen/Ereignisse
# Ereignisse -> PLM

## #21 PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-12 18:46 ev:0ac8ea77] PAYMENT: Die lokalen FOB-Gebühren am Abgangshafen wurden noch nicht beglichen, weshalb die Freigabeerklärung noch nicht erteilt werden kann. (Mail 1a13101dad0031e3) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:46 ev:3be0b98e] SHIPMENT: Container GAOU 642 138-0 wurde entladen. (Mail 1a131027b11eec6e) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561872'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:46 ev:57ebac9f] SHIPMENT: Container EGHU 914 348-0 wurde entladen. (Mail 1a131027b11eec6e) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561876'; Notiz in allen 2 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:47 ev:9464e018] SHIPMENT: Container EGHU9143480 wurde durch das Hauptzollamt Hamburg überlassen (Zollanmeldung und Einfuhrabgabenbescheid erstellt). (Mail 1a13102a9494f5ce) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 2 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:47 ev:f65349d3] SHIPMENT: Container GAOU6421380 aus Ningbo (Versender Lieferant A, Pakistan) wurde am 12.10.2026 customs-cleared / überlassen in Hamburg. (Mail 1a13102b09ae44fe) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:14 ev:cf9a5875] SCHEDULE: Alpha hat den Zeitplan für das KUNDE_X-Polyester-Programm mitgeteilt: 50-60% Ex Factory am 20. Oktober, Rest bis 30. Oktober 2026. (Mail 1a134c1d5d3594a0) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:15 ev:d8b037d5] SCHEDULE: Confirmed EXW dates for KUNDE_X Polystyles Alpha: 50-60% on 20th Oct ex-fty and the rest until 30th Oct. (Mail 1a134c2f942e1864) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:46 ev:a4549cae] SHIPMENT: Vessel planning updated with CMA CGM FIGARO 0019, ETD 2026-10-26, ETA 2023-11-23. (Mail 1a134df4bb6116c1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-14 08:16 ev:b9b9e1e7] SCHEDULE: Lieferant A bittet um Schiffsplanung auf Basis eines Ex-Factory-Termins am 20.10.2026, da der Cut-off 22.10.2026 nicht eingehalten werden kann. (Mail 1a1390dcabd171b8) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-14 08:16 ev:fe051ca3] SHIPMENT: Schiffsplanung laut Zia Hussain (Quellzitat aus Verlauf): Reederei CMA, Cut-off 22.10.2026, ETD 26.10.2026, ETA 23.11.2026, Schiff CMA CGM FIGARO 0019. Die Mail fragt zudem nach 40'/20'-Container fuer die CRO. (Mail 1a1390dcabd171b8) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-18 12:37 ev:d07e3999] SCHEDULE: Request for production status update and ex-factory confirmation for the KUNDE_X polyester program as the 20.10. ex-factory date approaches. (Mail 1a14e968104ce5cf) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 11:43 ev:7ea8fb84] SCHEDULE: Ex-factory planned for tomorrow with 32-33k pcs (1 container, 53.48 CBM) as brown color is behind schedule while black is in excess. (Mail 1a1538b5bb3f6600) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 12:09 ev:16abe61f] SCHEDULE: Handover of goods at Karachi must be completed by 22.10.2026 to catch the CMA vessel. (Mail 1a153a24ac7870b5) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 17:15 ev:b9108646] SCHEDULE: Cut-off date for the first shipment batch of approx. 35,000 pcs (55 CBM) extended from 22nd to 23rd October on CMA vessel. (Mail 1a154bb35d1a0ed1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 17:15 ev:65a9a229] SCHEDULE: Remaining quantities are expected to be completed by 30th October. (Mail 1a154bb35d1a0ed1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:53bb666d] SCHEDULE: KUNDE_X Polyester: Ex-mill ~115 CBM planned for 30.10.2026, sailing from Karachi on 03.11.2026 and ETA Hamburg on 02.12.2026. (Mail 1a163038333c6ecb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:ba660989] SHIPMENT: KUNDE_X Polyester: 51 CBM dispatched yesterday (21.10.2026). (Mail 1a163038333c6ecb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-26 11:20 ev:dfa4dc48] SHIPMENT: Commercial invoice, packing list, bill of lading draft and CRO issued for container TXGU-410959-6. (Mail 1a177ba249af249a) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561874'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-26 13:00 ev:b8e8e94d] SCHEDULE: Revised plan for KUNDE_X Polyester: 1st 40ft HQ ex-mill 30.10, sailing Karachi 05.11. (Mail 1a17815b1851bebb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
## #22 PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11
- [2026-10-12 18:46 ev:0ac8ea77] PAYMENT: Die lokalen FOB-Gebühren am Abgangshafen wurden noch nicht beglichen, weshalb die Freigabeerklärung noch nicht erteilt werden kann. (Mail 1a13101dad0031e3) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:46 ev:3be0b98e] SHIPMENT: Container GAOU 642 138-0 wurde entladen. (Mail 1a131027b11eec6e) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561872'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:46 ev:57ebac9f] SHIPMENT: Container EGHU 914 348-0 wurde entladen. (Mail 1a131027b11eec6e) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561876'; Notiz in allen 2 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:47 ev:9464e018] SHIPMENT: Container EGHU9143480 wurde durch das Hauptzollamt Hamburg überlassen (Zollanmeldung und Einfuhrabgabenbescheid erstellt). (Mail 1a13102a9494f5ce) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 2 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:47 ev:f65349d3] SHIPMENT: Container GAOU6421380 aus Ningbo (Versender Lieferant A, Pakistan) wurde am 12.10.2026 customs-cleared / überlassen in Hamburg. (Mail 1a13102b09ae44fe) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:14 ev:cf9a5875] SCHEDULE: Alpha hat den Zeitplan für das KUNDE_X-Polyester-Programm mitgeteilt: 50-60% Ex Factory am 20. Oktober, Rest bis 30. Oktober 2026. (Mail 1a134c1d5d3594a0) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:15 ev:d8b037d5] SCHEDULE: Confirmed EXW dates for KUNDE_X Polystyles Alpha: 50-60% on 20th Oct ex-fty and the rest until 30th Oct. (Mail 1a134c2f942e1864) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:46 ev:a4549cae] SHIPMENT: Vessel planning updated with CMA CGM FIGARO 0019, ETD 2026-10-26, ETA 2023-11-23. (Mail 1a134df4bb6116c1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-14 08:16 ev:b9b9e1e7] SCHEDULE: Lieferant A bittet um Schiffsplanung auf Basis eines Ex-Factory-Termins am 20.10.2026, da der Cut-off 22.10.2026 nicht eingehalten werden kann. (Mail 1a1390dcabd171b8) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-14 08:16 ev:fe051ca3] SHIPMENT: Schiffsplanung laut Zia Hussain (Quellzitat aus Verlauf): Reederei CMA, Cut-off 22.10.2026, ETD 26.10.2026, ETA 23.11.2026, Schiff CMA CGM FIGARO 0019. Die Mail fragt zudem nach 40'/20'-Container fuer die CRO. (Mail 1a1390dcabd171b8) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-18 12:37 ev:d07e3999] SCHEDULE: Request for production status update and ex-factory confirmation for the KUNDE_X polyester program as the 20.10. ex-factory date approaches. (Mail 1a14e968104ce5cf) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 11:43 ev:7ea8fb84] SCHEDULE: Ex-factory planned for tomorrow with 32-33k pcs (1 container, 53.48 CBM) as brown color is behind schedule while black is in excess. (Mail 1a1538b5bb3f6600) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 12:09 ev:16abe61f] SCHEDULE: Handover of goods at Karachi must be completed by 22.10.2026 to catch the CMA vessel. (Mail 1a153a24ac7870b5) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 17:15 ev:b9108646] SCHEDULE: Cut-off date for the first shipment batch of approx. 35,000 pcs (55 CBM) extended from 22nd to 23rd October on CMA vessel. (Mail 1a154bb35d1a0ed1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 17:15 ev:65a9a229] SCHEDULE: Remaining quantities are expected to be completed by 30th October. (Mail 1a154bb35d1a0ed1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:53bb666d] SCHEDULE: KUNDE_X Polyester: Ex-mill ~115 CBM planned for 30.10.2026, sailing from Karachi on 03.11.2026 and ETA Hamburg on 02.12.2026. (Mail 1a163038333c6ecb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:ba660989] SHIPMENT: KUNDE_X Polyester: 51 CBM dispatched yesterday (21.10.2026). (Mail 1a163038333c6ecb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-26 11:20 ev:dfa4dc48] SHIPMENT: Commercial invoice, packing list, bill of lading draft and CRO issued for container TXGU-410959-6. (Mail 1a177ba249af249a) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561874'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-26 13:00 ev:b8e8e94d] SCHEDULE: Revised plan for KUNDE_X Polyester: 1st 40ft HQ ex-mill 30.10, sailing Karachi 05.11. (Mail 1a17815b1851bebb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
## #23 PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11
- [2026-10-12 18:46 ev:0ac8ea77] PAYMENT: Die lokalen FOB-Gebühren am Abgangshafen wurden noch nicht beglichen, weshalb die Freigabeerklärung noch nicht erteilt werden kann. (Mail 1a13101dad0031e3) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:46 ev:3be0b98e] SHIPMENT: Container GAOU 642 138-0 wurde entladen. (Mail 1a131027b11eec6e) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561872'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-12 18:47 ev:f65349d3] SHIPMENT: Container GAOU6421380 aus Ningbo (Versender Lieferant A, Pakistan) wurde am 12.10.2026 customs-cleared / überlassen in Hamburg. (Mail 1a13102b09ae44fe) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:14 ev:cf9a5875] SCHEDULE: Alpha hat den Zeitplan für das KUNDE_X-Polyester-Programm mitgeteilt: 50-60% Ex Factory am 20. Oktober, Rest bis 30. Oktober 2026. (Mail 1a134c1d5d3594a0) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:15 ev:d8b037d5] SCHEDULE: Confirmed EXW dates for KUNDE_X Polystyles Alpha: 50-60% on 20th Oct ex-fty and the rest until 30th Oct. (Mail 1a134c2f942e1864) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-13 12:46 ev:a4549cae] SHIPMENT: Vessel planning updated with CMA CGM FIGARO 0019, ETD 2026-10-26, ETA 2023-11-23. (Mail 1a134df4bb6116c1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-14 08:16 ev:b9b9e1e7] SCHEDULE: Lieferant A bittet um Schiffsplanung auf Basis eines Ex-Factory-Termins am 20.10.2026, da der Cut-off 22.10.2026 nicht eingehalten werden kann. (Mail 1a1390dcabd171b8) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-14 08:16 ev:fe051ca3] SHIPMENT: Schiffsplanung laut Zia Hussain (Quellzitat aus Verlauf): Reederei CMA, Cut-off 22.10.2026, ETD 26.10.2026, ETA 23.11.2026, Schiff CMA CGM FIGARO 0019. Die Mail fragt zudem nach 40'/20'-Container fuer die CRO. (Mail 1a1390dcabd171b8) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-18 12:37 ev:d07e3999] SCHEDULE: Request for production status update and ex-factory confirmation for the KUNDE_X polyester program as the 20.10. ex-factory date approaches. (Mail 1a14e968104ce5cf) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 11:43 ev:7ea8fb84] SCHEDULE: Ex-factory planned for tomorrow with 32-33k pcs (1 container, 53.48 CBM) as brown color is behind schedule while black is in excess. (Mail 1a1538b5bb3f6600) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 12:09 ev:16abe61f] SCHEDULE: Handover of goods at Karachi must be completed by 22.10.2026 to catch the CMA vessel. (Mail 1a153a24ac7870b5) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 17:15 ev:b9108646] SCHEDULE: Cut-off date for the first shipment batch of approx. 35,000 pcs (55 CBM) extended from 22nd to 23rd October on CMA vessel. (Mail 1a154bb35d1a0ed1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-19 17:15 ev:65a9a229] SCHEDULE: Remaining quantities are expected to be completed by 30th October. (Mail 1a154bb35d1a0ed1) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Gmail-Verlauf (2 Ereignisse nennen das Programm); Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:53bb666d] SCHEDULE: KUNDE_X Polyester: Ex-mill ~115 CBM planned for 30.10.2026, sailing from Karachi on 03.11.2026 and ETA Hamburg on 02.12.2026. (Mail 1a163038333c6ecb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:ba660989] SHIPMENT: KUNDE_X Polyester: 51 CBM dispatched yesterday (21.10.2026). (Mail 1a163038333c6ecb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-26 11:20 ev:dfa4dc48] SHIPMENT: Commercial invoice, packing list, bill of lading draft and CRO issued for container TXGU-410959-6. (Mail 1a177ba249af249a) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Kennung '561874'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
- [2026-10-26 13:00 ev:b8e8e94d] SCHEDULE: Revised plan for KUNDE_X Polyester: 1st 40ft HQ ex-mill 30.10, sailing Karachi 05.11. (Mail 1a17815b1851bebb) [Zuordnung: ueber Programm KUNDE_X Alpha zugeordnet (Wort 'kunde_x'; Notiz in allen 3 Orders des Programms: PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11), nicht per PO-Nr belegt]
## #30 PO-LIEFERANT_G-MC-26SM002
- [2026-10-12 18:49 ev:825e091b] OTHER: Request to push the webbing supplier to complete the revised binding webbing for GT0304 as soon as possible. (Mail 1a1310554e320fa0)
## #25 PO-LIEFERANT_D-ALI20260821
- [2026-10-12 18:51 ev:18930b64] ORDER_CHANGE: Discussion about changing two details for F-1 rise size (rise length 4cm shorter after stretching and width same as AN-43). Two versions will be shown tomorrow. (Mail 1a131067d7fcdc7d) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
## #37 PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER
- [2026-10-12 18:55 ev:65364282] SHIPMENT: Versandbenachrichtigung mit HBL vom Spediteur EC Lontor erhalten (CMA CGM RIO GRANDE, ETD 14.08., ETA 13.09.). (Mail 1a1310a6ed02f60a)
- [2026-10-12 18:55 ev:0966db75] OTHER: Baumaßnahme und Sperrung der Einfahrt ab 07.09.2026 für die Dauer von 2 Wochen angekündigt. (Mail 1a1310a6ed02f60a)
- [2026-10-12 22:02 ev:b26b8665] SHIPMENT: Sendung per Seefracht (4*40HQ) mit MBL XIA1965473 und HBL XIME26070257, ETD Xiamen 7. August, Spediteur fragt nach Palettierungs- und Sortieranweisungen. (Mail 1a131b5dbbcc7e59)
## #24 PO-WONDERS-XW042-20260709
- [2026-10-12 22:01 ev:62739b49] ORDER_CHANGE: Barcode change for Rain Jacket Crocodile (black, white, olive) cannot be applied to current bulk as it is already sticked; XW-042B will be applied to the second order instead. (Mail 1a131b463096a596) [Zuordnung: ueber Programm Wonders XW-042 zugeordnet (Kennung 'XW-042'; Notiz in allen 2 Orders des Programms: PO-WONDERS-XW042-20260709, PO-WONDERS-XW-SM260730), nicht per PO-Nr belegt]
- [2026-10-14 14:05 ev:6a55d0a7] ORDER_CHANGE: Smilodox bestätigt die Style-Nummern je Druck: XW-042 für Crocodile Print und XW-042_A für Cheetah Print. Der Lieferant soll für jeden Druck die richtige Style-Nummer verwenden. (Mail 1a13a4d78eb77f59) [Zuordnung: ueber Programm Wonders XW-042 zugeordnet (Kennung 'XW-042'; Notiz in allen 2 Orders des Programms: PO-WONDERS-XW042-20260709, PO-WONDERS-XW-SM260730), nicht per PO-Nr belegt]
## #33 PO-WONDERS-XW-SM260730
- [2026-10-12 22:01 ev:62739b49] ORDER_CHANGE: Barcode change for Rain Jacket Crocodile (black, white, olive) cannot be applied to current bulk as it is already sticked; XW-042B will be applied to the second order instead. (Mail 1a131b463096a596) [Zuordnung: ueber Programm Wonders XW-042 zugeordnet (Kennung 'XW-042'; Notiz in allen 2 Orders des Programms: PO-WONDERS-XW042-20260709, PO-WONDERS-XW-SM260730), nicht per PO-Nr belegt]
- [2026-10-14 14:05 ev:6a55d0a7] ORDER_CHANGE: Smilodox bestätigt die Style-Nummern je Druck: XW-042 für Crocodile Print und XW-042_A für Cheetah Print. Der Lieferant soll für jeden Druck die richtige Style-Nummer verwenden. (Mail 1a13a4d78eb77f59) [Zuordnung: ueber Programm Wonders XW-042 zugeordnet (Kennung 'XW-042'; Notiz in allen 2 Orders des Programms: PO-WONDERS-XW042-20260709, PO-WONDERS-XW-SM260730), nicht per PO-Nr belegt]
## #34 PO-WONDERS-XW-SM260811
- [2026-10-14 05:51 ev:55678539] OTHER: Der Lieferant meldet, dass XW26-008 (Long Sleeve) und XW26-009 (Tank Top) die Farbe light grey nicht haben, daher entfaellt die E-Serie fuer diese Styles. Er fragt, ob die anderen Farbgruppen die E-Serie ueberspringen oder ersetzen sollen. (Mail 1a138891a17b99d9)
## #96 PO-LIEFERANT_I-SPR2026000000409
- [2026-10-14 09:29 ev:c300c053] QUALITY: White printing defects noticed on the snake print; suggested switching to a black base fabric. (Mail 1a13951c52d8cf78) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-14 09:29 ev:91118219] ORDER_CHANGE: Request to add regular leggings with leo pattern (same as leggings 26803) to the production list. (Mail 1a13951c52d8cf78)
## #38 PO-ALPHA-SWEAT-PROGRAM-2026-06-03
- [2026-10-14 12:18 ev:91bfe96a] ORDER_CHANGE: Israr (Lieferant A) hat das Massblatt der Siera Pant nach Anweisung von Imran Saleem aktualisiert und einen WhatsApp-Screenshot als Referenz angehaengt. Auf Fadels Rueckfrage vom 12.10. antwortet er damit, dass die Aenderungen auf Imrans Angaben beruhen. (Mail 1a139eb8e8f30e55)
- [2026-10-22 11:48 ev:3a6c9e52] SHIPMENT: Sweat Styles (Air): 4th air shipment of 5,000-6,000 pcs shipping today (22.10.2026), total shipped after today approx. 15,000 pcs. (Mail 1a163038333c6ecb)
- [2026-10-22 11:48 ev:69e7e864] SCHEDULE: Sweat Styles (Air): Total air quantity of 60,000 pcs to be closed by 05.11.2026. (Mail 1a163038333c6ecb) [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]
- [2026-10-26 13:00 ev:8931e28d] SHIPMENT: Sweat Styles air shipments update: 15,000 pcs shipped so far, 4,500 pcs planned for today. Target of 45,000 pcs for 05.11 under review. (Mail 1a17815b1851bebb) [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]
## #1 PO-LIEFERANT_H-RAINJACKET
- [2026-10-16 11:02 ev:bad68a3f] SHIPMENT: Bill of Lading (Telex Release) issued for sea shipment of MEN'S WINDBREAKER JACKET (122 cartons, 1676.95 KGS, 8.784 CBM) from Xiamen to Hamburg. (Mail 1a143f2ed32e9264) [Zuordnung: Betreffnummer F260526SF = PO-Nr der Order; nicht per PO-Nr belegt]
## #53 PO-ALPHA-NOOS-STOCK-INCREASE-2025-12-16
- [2026-10-27 11:15 ev:fc4bd063] SAMPLE: Sample/Prototype Vergleich für Style SNM26-009 durchgeführt. (Mail 1a17cdb6398a2259)
- [2026-10-27 11:18 ev:b4fc4423] SAMPLE: Sample/Prototyp Vergleich für Style SNM26-009 mit Maße- und Materialabweichungen. (Mail 1a17cdebff5e1cbb)
- [2026-10-27 14:41 ev:55bbffd2] SAMPLE: Maßvergleich und Materialprüfung für Sample SNM26-009 durchgeführt (Status: Offen). (Mail 1a17d988636a057a)
- [2026-10-27 14:50 ev:d3672520] SAMPLE: Sample-Vergleich und Maßtabelle für Style SNM26-009 durchgeführt, Status offen. (Mail 1a17da0dcf0831f6)

## Nicht zugeordnet (Mensch schaut)
- [2026-10-12 18:34] SCHEDULE: Status inquiry regarding expected 10,000 T-Shirts with an ex-mill date of September 25. (Umar) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:34] SCHEDULE: Lieferant A confirmed ex-goods date by 30th September. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:37] DELAY: Container wurde in der Nacht zum 05.09. gelöscht, Transportkapazität ist aufgrund von Streiks jedoch eingeschränkt. (SI_2026_06_0047) -> keine Order gefunden
- [2026-10-12 18:38] OTHER: Nicole Chen from Lieferant C sent the carton marking layout for review. (XW-042) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:38] OTHER: Lieferant hat das Layout fuer Barcode-Sticker und Kartonmarkierungen fuer Artikel XW-042 uebermittelt. (XIANGMEN LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:38] OTHER: Smilodox requested missing sizes and corresponding barcodes in the barcode stickers layout and carton marking file. (XW-042) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:38] OTHER: Nicole Chen from Lieferant C confirmed that barcode stickers will be attached accordingly and do not need to be printed directly on the carton. (XW-042) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:38] OTHER: Smilodox requested the completed version of the barcode stickers layout and carton marking for reference and final check. (None) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:38] OTHER: Lieferant hat aktualisierte Kartonmarkierungen und Barcode-Aufkleber für Artikel XW-042 zur Prüfung zugesandt. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:38] OTHER: Carton markings and barcode stickers checked and confirmed as complete and correct. (XW-042) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:38] OTHER: Carton marking for style XW-042 has been approved. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:46] SHIPMENT: Container EGSU 155 511-8 wurde entladen. (LIEFERANT_B ENTERPRISES PVT LIMITED) -> mehrdeutig: PO-LIEFERANT_B-2026-06-13-3123, PO-LIEFERANT_B-2026-06-13-AA8B
- [2026-10-12 18:48] OTHER: Vendor sent barcode stickers layout and carton marking for style XW-042 for review and confirmation. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:53] SHIPMENT: Container HMMU6963097 arrived in Hamburg via vessel ONE RELIABILITY V#0020W, delivery order issued. (LIEFERANT_B ENTERPRISES) -> mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd
- [2026-10-12 18:54] SHIPMENT: Inbound vessel arrived with container HMMU6963097 containing knitted socks from Karachi, Pakistan. (LIEFERANT_B ENTERPRISES) -> mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd
- [2026-10-12 22:00] SCHEDULE: Inquiry regarding production and logistics status for orders XW-042 Croco/Cheetah Print, SNM26-006_A, and XW-042 Croco (1st Order), requesting confirmation of EXW, ETD, and ETA dates. (XW-042) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 22:00] DELAY: Forwarder holiday from Oct 01-07 due to National Day, waiting for SPEDITION_B contact. (China Lieferant X) -> mehrdeutig: 2 laufende Orders von LIEFERANT_X INDUSTRY CO.,LTD
- [2026-10-12 22:01] SCHEDULE: Lieferant bittet um Zusendung der Barcode-Informationen bis spätestens 15. Oktober. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: 4 laufende Orders von Lieferant C
- [2026-10-12 22:01] OTHER: Discussion regarding barcodes for style XW-042 which have already been applied to bulk production and cannot be changed. (None) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 05:51] OTHER: Der Lieferant teilt mit, dass die Barcodes fuer XW-042 (Rain Jacket Crocodile, black/white/olive) bereits auf die Bulk-Produktion aufgebracht sind und nicht mehr auf XW-042_A geaendert werden koennen. XW-042B wird nur fuer die zweite Bestellung verwendet. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 12:22] SCHEDULE: Shipment date for newly added styles will be delayed compared to committed date and confirmed later. (Lieferant A) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 14:14] ORDER_CHANGE: Clarification on style numbers to be used for the prints: XW-042 for Crocodile Print and XW-042_A for Cheetah Print. (None) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 14:29] SHIPMENT: Commercial invoice updated to delete sample charges. (26071) -> mehrdeutig: PO-LIEFERANT_W-26071-DE-EA-2EXTRA, PO-LIEFERANT_W-26071-DE-EA-2
- [2026-10-19 12:00] SAMPLE: Physical samples received and forwarded to factory to check exact costs. (Profit Cultural & Creative Group Corporation) -> mehrdeutig: PO-LIEFERANT_AK-2025-10-18-B1EF, PO-LIEFERANT_Y-WS26245, PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER, PO-KUNDE_Y-Q2-2027-LIEFERANT_Y, PO-KUNDE_Y-Q2-2027-LIEFERANT_B
- [2026-10-22 09:28] ORDER_CHANGE: Embroidery size adjustment in physical production due to fabric behavior and stitches. (Lieferant A) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-26 12:47] SHIPMENT: Shipment of 39 cartons containing 373 pcs of knitted dyed garments (Invoice TE-26-2003-A) via air freight from Lahore, Pakistan to Hamburg, Germany. (LIEFERANT_B ENTERPRISES (PVT) LTD.) -> keine Order gefunden
- [2026-10-26 14:32] SCHEDULE: Request for written confirmation of ex-factory dates and sample status for B2B orders (Sports Club, Easy Fitness, XtraFit, Peaks, Kunde Y). (None) -> keine Order gefunden
- [2026-10-27 15:39] SHIPMENT: Shipment documents for invoice SPR2026000000445 sent with 17007 pieces in 1056 boxes. (SPR2026000000445) -> mehrdeutig: PO-LIEFERANT_I-SPR2026000000438, PO-LIEFERANT_I-SPR2026000000422, PO-LIEFERANT_I-SPR2026000000409

## Info ohne PO-Bezug (Muster/Artwork/Allgemeines): bleibt im Blatt 'Ereignisse', kein Handlungsbedarf im PLM
- 392 Ereignisse

## Sendungen (Bereich Shipments)
- keine

## Ergebnis Notizen
```
[
 {
  "title": "PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 19,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 19
 },
 {
  "title": "PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 19,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 19
 },
 {
  "title": "PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 17,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 17
 },
 {
  "title": "PO-LIEFERANT_G-MC-26SM002",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_D-ALI20260821",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 1,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 1
 },
 {
  "title": "PO-WONDERS-XW042-20260709",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 2,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 2
 },
 {
  "title": "PO-WONDERS-XW-SM260730",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 2,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 2
 },
 {
  "title": "PO-WONDERS-XW-SM260811",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_I-SPR2026000000409",
  "unchanged": true
 },
 {
  "title": "PO-ALPHA-SWEAT-PROGRAM-2026-06-03",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_H-RAINJACKET",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 1,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 1
 },
 {
  "title": "PO-ALPHA-NOOS-STOCK-INCREASE-2025-12-16",
  "unchanged": true
 }
]
```

## PO-IDs
- nichts zu tun (Nachtrag heute schon gelaufen)

## Projekte
- Projekte im PLM: 33 | Lieferanten ohne Projekt: 0 | Orders ohne Projekt: 0 | geplant: 0 neue Projekte, 0 Verknuepfungen
- nichts zu tun

## Projekt-Produkte
- Projekt-Produkte: 1 Produkte in 1 Projekten zu verknuepfen (Limit 100)
- WARNUNG Lieferant A: 1 Produkt(e) ohne Variante nicht aufgenommen
- Backup: /home/runner/work/Dashboard-Produktion/Dashboard-Produktion/output/backup/vendor_project_products_vor_2026-10-28_092835.json
- Projekt-Produkte: neu 1, Fehler 0

## Status
- Vorschlaege: 1 (hoch 0, mittel 1, niedrig 0), davon automatisch zulaessig: 0 | STATUS_AUTO AN

## Zahlungen
- Orders geprueft: 80 | Aktionen: 0 (diesen Lauf 0, Rest 0) | Klaerfall-Kandidaten: 6
  - KLAERFALL [Lieferant A] Datenpflege: Plan unveraendert (echte Zahlungen). : Zahlung: Zahlungsplan pruefen: Summe der Raten 2407565.55 != Gesamtwert 2316341.30 (+91224.25)
  - KLAERFALL [Lieferant H garment company] Datenpflege: Plan unveraendert (echte Zahlungen). : Zahlung: Zahlungsplan pruefen: Summe der Raten 56248.40 != Gesamtwert 55950.00 (+298.40)
  - KLAERFALL [LIEFERANT_W CO., LTD] Datenpflege: Plan unveraendert (echte Zahlungen). : Zahlung: Zahlungsplan pruefen: Notiz der Order nennt widerspruechliche/nicht abgeglichene Bedingungen; alle 4 
  - KLAERFALL [Lieferant AJ fashion] Datenpflege: Plan unveraendert (echte Zahlungen). : Zahlung: Zahlungsplan pruefen: alle 4 Raten mit gleicher Faelligkeit (Vorlage, nicht abgeglichen)
  - KLAERFALL [Lieferant P Co.,Ltd.] Datenpflege: Plan unveraendert (echte Zahlungen). : Zahlung: Zahlungsplan pruefen: Summe der Raten 97386.80 != Gesamtwert 100386.80 (-3000.00); Notiz der Order ne
  - KLAERFALL [Lieferant AG] Datenpflege: Plan unveraendert (echte Zahlungen). : Zahlung: Zahlungsplan pruefen: alle 4 Raten mit gleicher Faelligkeit (Vorlage, nicht abgeglichen)
- Klaerfaelle neu eingetragen: 0 (Kandidaten 6, bekannte uebersprungen)

## Gelernte Aliase (gespeichert)
- keine neuen

## Gelernte Absender-Domains
- keine neuen

## Mail-Verlauf (Thread)
- neu gelernt: 0 Verlauf-Order-Paare (gesamt 84 Verlaeufe) | ueber Verlauf zugeordnet: 1 Ereignisse | THREAD_MATCH an

## Programme, Nummern, Info-Regel
- ueber Programm zugeordnet: 21 Ereignisse (59 Notizzeilen in den Orders der Gruppen) | ueber Betreffnummer/Positionswort: 1 | als Info (Muster/Streichung ohne Order): 3 | PROGRAMM_MATCH an, NUMMER_MATCH an, INFO_REGEL an

## Klärfälle (PLM-Tabelle)
- Kandidaten 15, neu eingetragen 0, geloescht 20 (Rest naechster Lauf: 0), offen gesamt 45

## Zuordnungen aus der Tabelle
- geschrieben: angewendet 0, abgelehnt 0, schon angewendet 0, nicht gelesen (Limit 30) 0

## Anhaenge
- Anhaenge: neu 0, uebersprungen 28, Fehler 0, ausgeschlossen 49
- uebersprungen (Name im PLM vorhanden): 0917 PACKING INFORMATION.pdf -> PO-LIEFERANT_G-MC-26SM002
- uebersprungen (Name im PLM vorhanden): PL--SMI2612.pdf -> PO-LIEFERANT_AA-WINTER-2026-04-29
- uebersprungen (Name im PLM vorhanden): LIEFERANT_AA26104 -invoice.pdf -> PO-LIEFERANT_AA-WINTER-2026-04-29
- uebersprungen (Name im PLM vorhanden): WS26175-1 CI AND PL 26-8-5.xls -> PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER
- uebersprungen (Name im PLM vorhanden): WS26175-2 CI AND PL 26-8-5.xls -> PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER
- uebersprungen (Name im PLM vorhanden): WS26175-3 CI AND PL 26-8-5.xls -> PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER
- uebersprungen (Name im PLM vorhanden): PL--SMI2612.pdf -> PO-LIEFERANT_AA-WINTER-2026-04-29
- uebersprungen (Name im PLM vorhanden): LIEFERANT_AA2692 -invoice.pdf -> PO-LIEFERANT_AA-WINTER-2026-04-29
- uebersprungen (Name im PLM vorhanden): CI PL FOR XW-SM260513.xls -> PO-WONDERS-XW-SM260513
- uebersprungen (Name im PLM vorhanden): XW-SM260513 Balance payment CI.xlsx -> PO-WONDERS-XW-SM260513
- uebersprungen (Name im PLM vorhanden): xw-sm260513 Balance payment CI.xlsx -> PO-WONDERS-XW-SM260513
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821 SEA INV.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821 SEA PL.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821-AIR INV.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821-AIR PL.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821-TRAIN INV.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821-TRAIN PL.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): Lieferant V Plan PACKING List 14-Oct.xls -> PO-LIEFERANT_V-KCCN0513
- uebersprungen (Name im PLM vorhanden): SPR2026000000409.pdf -> PO-LIEFERANT_I-SPR2026000000409
- uebersprungen (Name im PLM vorhanden): LIEFERANT_AA2674-invoice - 30%.pdf -> PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER
- uebersprungen (Name im PLM vorhanden): LIEFERANT_AA2688 -invoice 35%.pdf -> PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER
- uebersprungen (Name im PLM vorhanden): SPR2026000000422.pdf -> PO-LIEFERANT_I-SPR2026000000422
- uebersprungen (Name im PLM vorhanden): SPR2026000000438.pdf -> PO-LIEFERANT_I-SPR2026000000438
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821-TRAIN INV.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): LIEFERANT_D-ALI20260821-TRAIN PL.pdf -> PO-LIEFERANT_D-ALI20260821
- uebersprungen (Name im PLM vorhanden): CI PL FOR XW-SM260710.xls -> PO-WONDERS-XW042-20260709
- uebersprungen (Name im PLM vorhanden): XW-SM260710 balance payment PI.xlsx -> PO-WONDERS-XW042-20260709

## Techpacks
- neue Techpack/Spec-Dateien seit 2026-10-28T09:29: 0 | hochgeladen 0 | schon als Datei vorhanden 0 | ohne Produkt 0 | Limit-Rest 0

## Mensch entscheidet (37)
- 1a13103fd472a81b_1.json: ORPHAN_DOC 62092211
- 1a1538b5bb3f6600_1.json: AMBIGUOUS_DOC passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a1538b5bb3f6600_2.json: AMBIGUOUS_DOC passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a1682ab9dcc2d5a_1.json: ORPHAN_DOC 
- 1a168c1bddb1726c_1.json: BLOCKER Lieferant unbekannt: None (nicht gefunden)
- 1a176dd5eaeba732_1.json: BLOCKER Lieferant unbekannt: LIEFERANT_J TEKSTİL SAN.VE TİC.LTD.ŞTİ. (nicht gefunden)
- 1a177ba249af249a_1.json: AMBIGUOUS_DOC passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a17c5576c0d951e_1.json: REORDER_QUESTION #4 PO-LIEFERANT_X-JM260704
- 1a17dcd1b307e869_1.json: AMBIGUOUS_DOC passt zu mehreren Orders: PO-LIEFERANT_I-SPR2026000000438, PO-LIEFERANT_I-SPR2026000000422, PO-LIEFERANT_I-SPR2026000000409
- Ereignis nicht zuordenbar: Status inquiry regarding expected 10,000 T-Shirts with an ex-mill date of September 25. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Lieferant A confirmed ex-goods date by 30th September. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Container wurde in der Nacht zum 05.09. gelöscht, Transportkapazität ist aufgrund von Stre (keine Order gefunden)
- Ereignis nicht zuordenbar: Nicole Chen from Lieferant C sent the carton marking layout for review. (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Lieferant hat das Layout fuer Barcode-Sticker und Kartonmarkierungen fuer Artikel XW-042 u (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Smilodox requested missing sizes and corresponding barcodes in the barcode stickers layout (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Nicole Chen from Lieferant C confirmed that barcode stickers will be attached according (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Smilodox requested the completed version of the barcode stickers layout and carton marking (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Lieferant hat aktualisierte Kartonmarkierungen und Barcode-Aufkleber für Artikel XW-042 zu (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Carton markings and barcode stickers checked and confirmed as complete and correct. (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Carton marking for style XW-042 has been approved. (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Container EGSU 155 511-8 wurde entladen. (mehrdeutig: PO-LIEFERANT_B-2026-06-13-3123, PO-LIEFERANT_B-2026-06-13-AA8B)
- Ereignis nicht zuordenbar: Vendor sent barcode stickers layout and carton marking for style XW-042 for review and con (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Container HMMU6963097 arrived in Hamburg via vessel ONE RELIABILITY V#0020W, delivery orde (mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd)
- Ereignis nicht zuordenbar: Inbound vessel arrived with container HMMU6963097 containing knitted socks from Karachi, P (mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd)
- Ereignis nicht zuordenbar: Inquiry regarding production and logistics status for orders XW-042 Croco/Cheetah Print, S (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Forwarder holiday from Oct 01-07 due to National Day, waiting for SPEDITION_B contact. (mehrdeutig: 2 laufende Orders von LIEFERANT_X INDUSTRY CO.,LTD)
- Ereignis nicht zuordenbar: Lieferant bittet um Zusendung der Barcode-Informationen bis spätestens 15. Oktober. (mehrdeutig: 4 laufende Orders von Lieferant C)
- Ereignis nicht zuordenbar: Discussion regarding barcodes for style XW-042 which have already been applied to bulk pro (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Der Lieferant teilt mit, dass die Barcodes fuer XW-042 (Rain Jacket Crocodile, black/white (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Shipment date for newly added styles will be delayed compared to committed date and confir (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Clarification on style numbers to be used for the prints: XW-042 for Crocodile Print and X (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Commercial invoice updated to delete sample charges. (mehrdeutig: PO-LIEFERANT_W-26071-DE-EA-2EXTRA, PO-LIEFERANT_W-26071-DE-EA-2)
- Ereignis nicht zuordenbar: Physical samples received and forwarded to factory to check exact costs. (mehrdeutig: PO-LIEFERANT_AK-2025-10-18-B1EF, PO-LIEFERANT_Y-WS26245, PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER, PO-KUNDE_Y-Q2-2027-LIEFERANT_Y, PO-KUNDE_Y-Q2-2027-LIEFERANT_B)
- Ereignis nicht zuordenbar: Embroidery size adjustment in physical production due to fabric behavior and stitches. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Shipment of 39 cartons containing 373 pcs of knitted dyed garments (Invoice TE-26-2003-A)  (keine Order gefunden)
- Ereignis nicht zuordenbar: Request for written confirmation of ex-factory dates and sample status for B2B orders (Spo (keine Order gefunden)
- Ereignis nicht zuordenbar: Shipment documents for invoice SPR2026000000445 sent with 17007 pieces in 1056 boxes. (mehrdeutig: PO-LIEFERANT_I-SPR2026000000438, PO-LIEFERANT_I-SPR2026000000422, PO-LIEFERANT_I-SPR2026000000409)
