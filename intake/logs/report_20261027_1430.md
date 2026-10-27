# Alltagslauf 2026-10-27 14:26 (AUSGEFUEHRT)

Neu: 14 Dokument-Dateien, 342 Ereignis-Dateien

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

## Entscheidung noetig (Reorder oder Teil derselben Bestellung?)
Per overrides.json: NOTE = nur Notiz an vorhandene PO, CREATE = neue PO, SKIP = ignorieren:
- 1a17c5576c0d951e_1.json -> vorhanden: #4 PO-LIEFERANT_X-JM260704

## Notizen/Ereignisse
# Ereignisse -> PLM

## #30 PO-LIEFERANT_G-MC-26SM002
- [2026-10-12 18:49 ev:825e091b] OTHER: Request to push the webbing supplier to complete the revised binding webbing for GT0304 as soon as possible. (Mail 1a1310554e320fa0)
- [2026-10-27 11:20 ev:a6574b50] SCHEDULE: Railway cargo shipment is expected to arrive on Nov. 13, 2026. (Mail 1a17ce00db3a9a9d)
- [2026-10-27 11:20 ev:cc2aeab9] SHIPMENT: Railway shipment dispatched with FCR LCL26100205. (Mail 1a17ce00db3a9a9d)
- [2026-10-27 11:20 ev:45cfb5e3] SHIPMENT: Sea shipment dispatched under Bill of Lading SEF261023462. (Mail 1a17ce00db3a9a9d)
## #37 PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER
- [2026-10-12 18:55 ev:65364282] SHIPMENT: Versandbenachrichtigung mit HBL vom Spediteur EC Lontor erhalten (CMA CGM RIO GRANDE, ETD 14.08., ETA 13.09.). (Mail 1a1310a6ed02f60a)
- [2026-10-12 22:02 ev:b26b8665] SHIPMENT: Sendung per Seefracht (4*40HQ) mit MBL XIA1965473 und HBL XIME26070257, ETD Xiamen 7. August, Spediteur fragt nach Palettierungs- und Sortieranweisungen. (Mail 1a131b5dbbcc7e59)
## #34 PO-WONDERS-XW-SM260811
- [2026-10-14 05:51 ev:55678539] OTHER: Der Lieferant meldet, dass XW26-008 (Long Sleeve) und XW26-009 (Tank Top) die Farbe light grey nicht haben, daher entfaellt die E-Serie fuer diese Styles. Er fragt, ob die anderen Farbgruppen die E-Serie ueberspringen oder ersetzen sollen. (Mail 1a138891a17b99d9)
## #96 PO-LIEFERANT_I-SPR2026000000409
- [2026-10-14 09:29 ev:c300c053] QUALITY: White printing defects noticed on the snake print; suggested switching to a black base fabric. (Mail 1a13951c52d8cf78) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-14 09:29 ev:91118219] ORDER_CHANGE: Request to add regular leggings with leo pattern (same as leggings 26803) to the production list. (Mail 1a13951c52d8cf78)
## #38 PO-ALPHA-SWEAT-PROGRAM-2026-06-03
- [2026-10-14 12:18 ev:91bfe96a] ORDER_CHANGE: Israr (Lieferant A) hat das Massblatt der Siera Pant nach Anweisung von Imran Saleem aktualisiert und einen WhatsApp-Screenshot als Referenz angehaengt. Auf Fadels Rueckfrage vom 12.10. antwortet er damit, dass die Aenderungen auf Imrans Angaben beruhen. (Mail 1a139eb8e8f30e55)
- [2026-10-22 11:48 ev:53bb666d] SCHEDULE: KUNDE_X Polyester: Ex-mill ~115 CBM planned for 30.10.2026, sailing from Karachi on 03.11.2026 and ETA Hamburg on 02.12.2026. (Mail 1a163038333c6ecb) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:ba660989] SHIPMENT: KUNDE_X Polyester: 51 CBM dispatched yesterday (21.10.2026). (Mail 1a163038333c6ecb) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:3a6c9e52] SHIPMENT: Sweat Styles (Air): 4th air shipment of 5,000-6,000 pcs shipping today (22.10.2026), total shipped after today approx. 15,000 pcs. (Mail 1a163038333c6ecb)
- [2026-10-22 11:48 ev:69e7e864] SCHEDULE: Sweat Styles (Air): Total air quantity of 60,000 pcs to be closed by 05.11.2026. (Mail 1a163038333c6ecb) [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]
- [2026-10-26 13:00 ev:8931e28d] SHIPMENT: Sweat Styles air shipments update: 15,000 pcs shipped so far, 4,500 pcs planned for today. Target of 45,000 pcs for 05.11 under review. (Mail 1a17815b1851bebb) [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]
- [2026-10-27 09:40 ev:615c87af] OTHER: Replacement of EAN barcode labels for Siara pants due to system error and duplicate assignment. (Mail 1a17c848ed4b3022)
- [2026-10-27 09:40 ev:b2d14bc7] SHIPMENT: Bordeaux color is being delivered today, Blau Uni is currently in embroidery. (Mail 1a17c848ed4b3022)
- [2026-10-27 09:45 ev:282117a4] OTHER: Update of barcode labels for Siera pants (style 26385) due to duplicate EAN assignments. (Mail 1a17c88f29ee0d80)
- [2026-10-27 14:00 ev:7b844154] SAMPLE: Lieferant sendet aktualisierte Barcode-Etiketten für den Style Jogginghose Siara (26385) zur Freigabe. (Mail 1a17d726a919e247)
## #9 PO-LIEFERANT_V-KCCN0513
- [2026-10-26 16:06 ev:c8407420] PAYMENT: Smilodox insists on paying the balance upon receipt of a copy of the Bill of Lading and cannot arrange payment before shipment. (Mail 1a178bfd2bec982d) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-27 10:09 ev:e80009f9] SCHEDULE: Fadel Abdullah stated that they are working with the forwarder to find the best shipping route and details will be shared once confirmed. The QC team will contact them directly for the inspection date. (Mail 1a17c9ef1514f841) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
## #4 PO-LIEFERANT_X-JM260704
- [2026-10-27 08:48 ev:93af2f90] SHIPMENT: Goods shipped via sea on vessel CMA CGM RODOLPHE with ATD 2026-10-23 and ETA 2026-11-22. (Mail 1a17c5576c0d951e)
- STATUS: In Production -> In Transit (Meilenstein SHIPPED (1a17c5576c0d951e))
## #19 PO-LIEFERANT_AA-WINTER-2026-04-29
- [2026-10-27 09:18 ev:b1bf96aa] SHIPMENT: Ankunftsavis für Bahnsendung eingetroffen, voraussichtliche Abnahme am 28.10.2026. (Mail 1a17c7104a8a3ec3)
- [2026-10-27 14:04 ev:59551d21] SHIPMENT: Ankunft der Sendung und Bereitstellung des Auslieferungsscheins und der ATB-Nummer. (Mail 1a17d765b565dc78) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-27 14:04 ev:a7d34d73] SCHEDULE: Ankunft der Sendung am 26.10.2026 in Hamburg. (Mail 1a17d765b565dc78) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
## #53 PO-ALPHA-NOOS-STOCK-INCREASE-2025-12-16
- [2026-10-27 11:15 ev:fc4bd063] SAMPLE: Sample/Prototype Vergleich für Style SNM26-009 durchgeführt. (Mail 1a17cdb6398a2259)
- [2026-10-27 11:18 ev:b4fc4423] SAMPLE: Sample/Prototyp Vergleich für Style SNM26-009 mit Maße- und Materialabweichungen. (Mail 1a17cdebff5e1cbb)

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
- [2026-10-12 18:46] PAYMENT: Die lokalen FOB-Gebühren am Abgangshafen wurden noch nicht beglichen, weshalb die Freigabeerklärung noch nicht erteilt werden kann. (LIEFERANT_A (PVT) LTD.) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:46] SHIPMENT: Container EGSU 155 511-8 wurde entladen. (LIEFERANT_B ENTERPRISES PVT LIMITED) -> mehrdeutig: PO-LIEFERANT_B-2026-06-13-3123, PO-LIEFERANT_B-2026-06-13-AA8B
- [2026-10-12 18:46] SHIPMENT: Container GAOU 642 138-0 wurde entladen. (Lieferant A Pvt Ltd) -> mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-12 18:46] SHIPMENT: Container EGHU 914 348-0 wurde entladen. (Lieferant A Pvt Ltd) -> mehrdeutig: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-12 18:47] SHIPMENT: Container EGHU9143480 wurde durch das Hauptzollamt Hamburg überlassen (Zollanmeldung und Einfuhrabgabenbescheid erstellt). (LIEFERANT_A (PVT) LTD.) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:47] SHIPMENT: Container GAOU6421380 aus Ningbo (Versender Lieferant A, Pakistan) wurde am 12.10.2026 customs-cleared / überlassen in Hamburg. (LIEFERANT_A (PVT) LTD.) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:48] OTHER: Vendor sent barcode stickers layout and carton marking for style XW-042 for review and confirmation. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:51] ORDER_CHANGE: Lieferant bittet darum, für diesen Auftrag normales Papier für das Etikett (paper tag) statt des dicken Papiers zu verwenden, da die Produktionszeit knapp und die Kosten ein Problem sind. (Ningbo Lieferant D Co.,Ltd) -> keine Order gefunden
- [2026-10-12 18:51] ORDER_CHANGE: Lieferant lehnt nachträgliche Änderungen an Care Label und Papierqualität der Verpackung für laufende Bestellung ab, da dies die Kosten erhöht. (Irena) -> keine Order gefunden
- [2026-10-12 18:51] ORDER_CHANGE: Discussion about changing two details for F-1 rise size (rise length 4cm shorter after stretching and width same as AN-43). Two versions will be shown tomorrow. (Ningbo lieferant_d Co., Ltd) -> keine Order gefunden
- [2026-10-12 18:52] SCHEDULE: Supplier requested to start production based on the F-3 print label. (Ningbo lieferant_d Co., Ltd) -> keine Order gefunden
- [2026-10-12 18:53] SHIPMENT: Container HMMU6963097 arrived in Hamburg via vessel ONE RELIABILITY V#0020W, delivery order issued. (LIEFERANT_B ENTERPRISES) -> mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd
- [2026-10-12 18:54] SHIPMENT: Inbound vessel arrived with container HMMU6963097 containing knitted socks from Karachi, Pakistan. (LIEFERANT_B ENTERPRISES) -> mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd
- [2026-10-12 22:00] SCHEDULE: Inquiry regarding production and logistics status for orders XW-042 Croco/Cheetah Print, SNM26-006_A, and XW-042 Croco (1st Order), requesting confirmation of EXW, ETD, and ETA dates. (XW-042) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 22:01] ORDER_CHANGE: Barcode change for Rain Jacket Crocodile (black, white, olive) cannot be applied to current bulk as it is already sticked; XW-042B will be applied to the second order instead. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 22:01] OTHER: Discussion regarding barcodes for style XW-042 which have already been applied to bulk production and cannot be changed. (None) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-13 12:14] SCHEDULE: Alpha hat den Zeitplan für das KUNDE_X-Polyester-Programm mitgeteilt: 50-60% Ex Factory am 20. Oktober, Rest bis 30. Oktober 2026. (Alpha) -> mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-13 12:15] SCHEDULE: Confirmed EXW dates for KUNDE_X Polystyles Alpha: 50-60% on 20th Oct ex-fty and the rest until 30th Oct. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-13 12:46] SHIPMENT: Vessel planning updated with CMA CGM FIGARO 0019, ETD 2026-10-26, ETA 2023-11-23. (Alpha) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 05:51] OTHER: Der Lieferant teilt mit, dass die Barcodes fuer XW-042 (Rain Jacket Crocodile, black/white/olive) bereits auf die Bulk-Produktion aufgebracht sind und nicht mehr auf XW-042_A geaendert werden koennen. XW-042B wird nur fuer die zweite Bestellung verwendet. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 08:16] SCHEDULE: Lieferant A bittet um Schiffsplanung auf Basis eines Ex-Factory-Termins am 20.10.2026, da der Cut-off 22.10.2026 nicht eingehalten werden kann. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 08:16] SHIPMENT: Schiffsplanung laut Zia Hussain (Quellzitat aus Verlauf): Reederei CMA, Cut-off 22.10.2026, ETD 26.10.2026, ETA 23.11.2026, Schiff CMA CGM FIGARO 0019. Die Mail fragt zudem nach 40'/20'-Container fuer die CRO. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 14:05] ORDER_CHANGE: Smilodox bestätigt die Style-Nummern je Druck: XW-042 für Crocodile Print und XW-042_A für Cheetah Print. Der Lieferant soll für jeden Druck die richtige Style-Nummer verwenden. (lieferant-c.example) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 14:14] ORDER_CHANGE: Clarification on style numbers to be used for the prints: XW-042 for Crocodile Print and XW-042_A for Cheetah Print. (None) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 14:29] SHIPMENT: Commercial invoice updated to delete sample charges. (26071) -> mehrdeutig: PO-LIEFERANT_W-26071-DE-EA-2EXTRA, PO-LIEFERANT_W-26071-DE-EA-2
- [2026-10-16 08:45] SCHEDULE: Lieferant A shared the production and delivery planning up to November 5 for sweat styles, Siara trousers, and the KUNDE_X polystyle project. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-16 11:02] SHIPMENT: Bill of Lading (Telex Release) issued for sea shipment of MEN'S WINDBREAKER JACKET (122 cartons, 1676.95 KGS, 8.784 CBM) from Xiamen to Hamburg. (FUJIAN LIEFERANT_H GARMENTS CO.,LTD.) -> keine Order gefunden
- [2026-10-18 12:37] SCHEDULE: Request for production status update and ex-factory confirmation for the KUNDE_X polyester program as the 20.10. ex-factory date approaches. (None) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 11:43] SCHEDULE: Ex-factory planned for tomorrow with 32-33k pcs (1 container, 53.48 CBM) as brown color is behind schedule while black is in excess. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 12:00] SAMPLE: Physical samples received and forwarded to factory to check exact costs. (Profit Cultural & Creative Group Corporation) -> mehrdeutig: PO-LIEFERANT_AK-2025-10-18-B1EF, PO-LIEFERANT_Y-WS26245, PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER, PO-KUNDE_Y-Q2-2027-LIEFERANT_Y, PO-KUNDE_Y-Q2-2027-LIEFERANT_B
- [2026-10-19 12:09] SCHEDULE: Handover of goods at Karachi must be completed by 22.10.2026 to catch the CMA vessel. (Lieferant F) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 17:15] SCHEDULE: Cut-off date for the first shipment batch of approx. 35,000 pcs (55 CBM) extended from 22nd to 23rd October on CMA vessel. (None) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 17:15] SCHEDULE: Remaining quantities are expected to be completed by 30th October. (None) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-26 08:49] ORDER_CHANGE: Cancellation of multiple styles/items (ORA-T-526, 01955, Women Longsleeve Henley, Sweatshirt Oversize, Sweatpant Oversize, FAB-001, FAB-002). (Lieferant AD) -> keine Order gefunden
- [2026-10-26 08:51] ORDER_CHANGE: Cancellation of styles FAB-001 and FAB-002. (Lieferant B) -> keine Order gefunden
- [2026-10-26 08:58] ORDER_CHANGE: Smilodox cancelled items FAB-001 and FAB-002, and the supplier inquired about their product category. (Lieferant B) -> keine Order gefunden
- [2026-10-26 11:20] SHIPMENT: Commercial invoice, packing list, bill of lading draft and CRO issued for container TXGU-410959-6. (561874_2510) -> keine Order gefunden
- [2026-10-26 12:47] SHIPMENT: Shipment of 39 cartons containing 373 pcs of knitted dyed garments (Invoice TE-26-2003-A) via air freight from Lahore, Pakistan to Hamburg, Germany. (LIEFERANT_B ENTERPRISES (PVT) LTD.) -> keine Order gefunden
- [2026-10-26 13:00] SCHEDULE: Revised plan for KUNDE_X Polyester: 1st 40ft HQ ex-mill 30.10, sailing Karachi 05.11. (Alpha) -> mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-26 14:32] SCHEDULE: Request for written confirmation of ex-factory dates and sample status for B2B orders (Sports Club, Easy Fitness, XtraFit, Peaks, Kunde Y). (None) -> keine Order gefunden
- [2026-10-26 16:23] SCHEDULE: Revised planning for air freight quantities to meet deadlines, detailing shipped quantities, WIP, and upcoming shipments for sweat styles, siara, and the KUNDE_X Project. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-26 17:23] OTHER: Barcode layouts and carton mark template confirmed for styles XW26-006, XW26-008, and XW26-009. (None) -> mehrdeutig: PO-WONDERS-XW-SM260811, PO-WONDERS-XW-SM260513
- [2026-10-27 08:30] SCHEDULE: Lieferant A reports that 17,500 garments have been shipped so far, and plans to ship another 30,000-40,000 garments by November 5, bringing the total shipped to 55,000-60,000 garments. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-27 09:12] OTHER: Barcode layouts and carton mark template for XW26-006, XW26-008 and XW26-009 are approved. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260811, PO-WONDERS-XW-SM260513
- [2026-10-27 10:05] PAYMENT: Smilodox confirmed that the balance payment will be arranged by the end of this week. (None) -> mehrdeutig: 2 laufende Orders von LIEFERANT_X INDUSTRY CO.,LTD

## Info ohne PO-Bezug (Muster/Artwork/Allgemeines): bleibt im Blatt 'Ereignisse', kein Handlungsbedarf im PLM
- 349 Ereignisse

## Sendungen (Bereich Shipments)
- neu: Sendung PO-LIEFERANT_X-JM260704 (sea, in_transit, 2 Pos.)
- aktualisiert: Sendung PO-LIEFERANT_G-MC-26SM002 {'trackingNumber': 'LCL26100205', 'status': 'in_transit'}

## Ergebnis Sendungen
- Sendung neu: Sendung PO-LIEFERANT_X-JM260704 -> HTTP 201
- Sendung aktualisiert: Sendung PO-LIEFERANT_G-MC-26SM002 ['notes', 'trackingNumber', 'status'] -> HTTP 200
- per REST zurueckgelesen: alle vorhanden

## Ergebnis Notizen
```
[
 {
  "title": "PO-LIEFERANT_G-MC-26SM002",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 3,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 3
 },
 {
  "title": "PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER",
  "unchanged": true
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
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 4,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 4
 },
 {
  "title": "PO-LIEFERANT_V-KCCN0513",
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
  "title": "PO-LIEFERANT_X-JM260704",
  "statusSet": "In Transit",
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
  "title": "PO-LIEFERANT_AA-WINTER-2026-04-29",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 3,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 3
 },
 {
  "title": "PO-ALPHA-NOOS-STOCK-INCREASE-2025-12-16",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 2,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 2
 }
]
```

## PO-IDs
- nichts zu tun (Nachtrag heute schon gelaufen)

## Projekte
- Projekte im PLM: 33 | Lieferanten ohne Projekt: 0 | Orders ohne Projekt: 0 | geplant: 0 neue Projekte, 0 Verknuepfungen
- nichts zu tun

## Projekt-Produkte
- Projekt-Produkte: 0 Produkte in 0 Projekten zu verknuepfen (Limit 100)
- WARNUNG Lieferant A: 1 Produkt(e) ohne Variante nicht aufgenommen
- nichts zu tun

## Status
- Vorschlaege: 2 (hoch 1, mittel 1, niedrig 0), davon automatisch zulaessig: 1 | STATUS_AUTO AN
- PO-LIEFERANT_B-2026-07-02-FB54: Draft -> Approved
- Backup: /home/runner/work/Dashboard-Produktion/Dashboard-Produktion/output/backup/status_vor_2026-10-27_142937.json
- Status gesetzt 1, Fehler 0

## Zahlungen
- Orders geprueft: 80 | Aktionen: 0 (diesen Lauf 0, Rest 0) | Klaerfall-Kandidaten: 6
  - KLAERFALL [Lieferant A] PO-ALPHA-SWEAT-PROGRAM-2026-06-03: Zahlungsplan pruefen: Summe der Raten 2407565.55 != Gesamtwert 2316341.30 (+91224.25)
  - KLAERFALL [Lieferant H garment company] PO-LIEFERANT_H-RAINJACKET: Zahlungsplan pruefen: Summe der Raten 56248.40 != Gesamtwert 55950.00 (+298.40)
  - KLAERFALL [LIEFERANT_W CO., LTD] PO-LIEFERANT_W-2026-04-29: Zahlungsplan pruefen: Notiz der Order nennt widerspruechliche/nicht abgeglichene Bedingungen; alle 4 Raten mit
  - KLAERFALL [Lieferant AJ fashion] PO-LIEFERANT_AJ-2026-03-30: Zahlungsplan pruefen: alle 4 Raten mit gleicher Faelligkeit (Vorlage, nicht abgeglichen)
  - KLAERFALL [Lieferant P Co.,Ltd.] PO-LIEFERANT_T-PO26005SG-W: Zahlungsplan pruefen: Summe der Raten 97386.80 != Gesamtwert 100386.80 (-3000.00); Notiz der Order nennt wider
  - KLAERFALL [Lieferant AG] PO-LIEFERANT_AG-2026-03-17: Zahlungsplan pruefen: alle 4 Raten mit gleicher Faelligkeit (Vorlage, nicht abgeglichen)
- Klaerfaelle neu eingetragen: 0 (Kandidaten 6, bekannte uebersprungen)

## Gelernte Aliase (gespeichert)
- JM1020-JM260704 -> 6aa2c6ff9a579d813f7ee1f3 (Ereignis)
- TLLU1614709 -> 6aa2c6ff9a579d813f7ee1f3 (Ereignis)
- XIME26100206 -> 6aa2c6ff9a579d813f7ee1f3 (Ereignis)
- TEST1234567-8 -> 6acd059e658a87e64182ca6a (Ereignis)
- EPUU5000999 -> 6acdfdf15f317983615a3ffc (Ereignis)
- MSOU2664682 -> 6acdfdf15f317983615a3ffc (Ereignis)
- SEF261023462 -> 6acdfdf15f317983615a3ffc (Ereignis)

## Gelernte Absender-Domains
- lieferant-c.example -> 6a687a9a9d02f84f90b1aacd (neu)
- lieferant-a.example -> 6ac5ecfd28e7219816c2b710 (neu)
- lieferant-extra.example -> 6a6716ede3361bcadbbc948a (neu)
- lieferant-extra.example -> 6a68634a9d02f84f90af9c88 (neu)
- lieferant-g.example -> 6ac5fad228e7219816cb0a16 (neu)
- lieferant-a.example -> 6ac5ecfd28e7219816c2b710 (aktiv)

## Klärfälle (PLM-Tabelle)
- Kandidaten 41, neu eingetragen 2, geloescht 0 (Rest naechster Lauf: 0), offen gesamt 68

## Zuordnungen aus der Tabelle
- geschrieben: angewendet 0, abgelehnt 0, schon angewendet 0, nicht gelesen (Limit 30) 0

## Anhaenge
- Anhaenge: neu 0, uebersprungen 26, Fehler 0, ausgeschlossen 48
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

## Techpacks
- neue Techpack/Spec-Dateien seit 2026-10-27T14:30: 0 | hochgeladen 0 | schon als Datei vorhanden 0 | ohne Produkt 0 | Limit-Rest 0

## Mensch entscheidet (64)
- 1a13103fd472a81b_1.json: ORPHAN_DOC 62092211
- 1a1538b5bb3f6600_1.json: AMBIGUOUS_DOC passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a1538b5bb3f6600_2.json: AMBIGUOUS_DOC passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a1682ab9dcc2d5a_1.json: ORPHAN_DOC 
- 1a168c1bddb1726c_1.json: BLOCKER Lieferant unbekannt: None (nicht gefunden)
- 1a176dd5eaeba732_1.json: BLOCKER Lieferant unbekannt: LIEFERANT_J TEKSTİL SAN.VE TİC.LTD.ŞTİ. (nicht gefunden)
- 1a177ba249af249a_1.json: AMBIGUOUS_DOC passt zu mehreren Orders: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- 1a17c5576c0d951e_1.json: REORDER_QUESTION #4 PO-LIEFERANT_X-JM260704
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
- Ereignis nicht zuordenbar: Die lokalen FOB-Gebühren am Abgangshafen wurden noch nicht beglichen, weshalb die Freigabe (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Container EGSU 155 511-8 wurde entladen. (mehrdeutig: PO-LIEFERANT_B-2026-06-13-3123, PO-LIEFERANT_B-2026-06-13-AA8B)
- Ereignis nicht zuordenbar: Container GAOU 642 138-0 wurde entladen. (mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Container EGHU 914 348-0 wurde entladen. (mehrdeutig: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Container EGHU9143480 wurde durch das Hauptzollamt Hamburg überlassen (Zollanmeldung und E (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Container GAOU6421380 aus Ningbo (Versender Lieferant A, Pakistan) wurde am 12.10.2026  (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Vendor sent barcode stickers layout and carton marking for style XW-042 for review and con (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Lieferant bittet darum, für diesen Auftrag normales Papier für das Etikett (paper tag) sta (keine Order gefunden)
- Ereignis nicht zuordenbar: Lieferant lehnt nachträgliche Änderungen an Care Label und Papierqualität der Verpackung f (keine Order gefunden)
- Ereignis nicht zuordenbar: Discussion about changing two details for F-1 rise size (rise length 4cm shorter after str (keine Order gefunden)
- Ereignis nicht zuordenbar: Supplier requested to start production based on the F-3 print label. (keine Order gefunden)
- Ereignis nicht zuordenbar: Container HMMU6963097 arrived in Hamburg via vessel ONE RELIABILITY V#0020W, delivery orde (mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd)
- Ereignis nicht zuordenbar: Inbound vessel arrived with container HMMU6963097 containing knitted socks from Karachi, P (mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd)
- Ereignis nicht zuordenbar: Inquiry regarding production and logistics status for orders XW-042 Croco/Cheetah Print, S (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Barcode change for Rain Jacket Crocodile (black, white, olive) cannot be applied to curren (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Discussion regarding barcodes for style XW-042 which have already been applied to bulk pro (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Alpha hat den Zeitplan für das KUNDE_X-Polyester-Programm mitgeteilt: 50-60% Ex Factory am 20 (mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Confirmed EXW dates for KUNDE_X Polystyles Alpha: 50-60% on 20th Oct ex-fty and the rest unti (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Vessel planning updated with CMA CGM FIGARO 0019, ETD 2026-10-26, ETA 2023-11-23. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Der Lieferant teilt mit, dass die Barcodes fuer XW-042 (Rain Jacket Crocodile, black/white (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Lieferant A bittet um Schiffsplanung auf Basis eines Ex-Factory-Termins am 20.10.2026,  (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Schiffsplanung laut Zia Hussain (Quellzitat aus Verlauf): Reederei CMA, Cut-off 22.10.2026 (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Smilodox bestätigt die Style-Nummern je Druck: XW-042 für Crocodile Print und XW-042_A für (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Clarification on style numbers to be used for the prints: XW-042 for Crocodile Print and X (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Commercial invoice updated to delete sample charges. (mehrdeutig: PO-LIEFERANT_W-26071-DE-EA-2EXTRA, PO-LIEFERANT_W-26071-DE-EA-2)
- Ereignis nicht zuordenbar: Lieferant A shared the production and delivery planning up to November 5 for sweat styl (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Bill of Lading (Telex Release) issued for sea shipment of MEN'S WINDBREAKER JACKET (122 ca (keine Order gefunden)
- Ereignis nicht zuordenbar: Request for production status update and ex-factory confirmation for the KUNDE_X polyester pr (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Ex-factory planned for tomorrow with 32-33k pcs (1 container, 53.48 CBM) as brown color is (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Physical samples received and forwarded to factory to check exact costs. (mehrdeutig: PO-LIEFERANT_AK-2025-10-18-B1EF, PO-LIEFERANT_Y-WS26245, PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER, PO-KUNDE_Y-Q2-2027-LIEFERANT_Y, PO-KUNDE_Y-Q2-2027-LIEFERANT_B)
- Ereignis nicht zuordenbar: Handover of goods at Karachi must be completed by 22.10.2026 to catch the CMA vessel. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Cut-off date for the first shipment batch of approx. 35,000 pcs (55 CBM) extended from 22n (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Remaining quantities are expected to be completed by 30th October. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Cancellation of multiple styles/items (ORA-T-526, 01955, Women Longsleeve Henley, Sweatshi (keine Order gefunden)
- Ereignis nicht zuordenbar: Cancellation of styles FAB-001 and FAB-002. (keine Order gefunden)
- Ereignis nicht zuordenbar: Smilodox cancelled items FAB-001 and FAB-002, and the supplier inquired about their produc (keine Order gefunden)
- Ereignis nicht zuordenbar: Commercial invoice, packing list, bill of lading draft and CRO issued for container TXGU-4 (keine Order gefunden)
- Ereignis nicht zuordenbar: Shipment of 39 cartons containing 373 pcs of knitted dyed garments (Invoice TE-26-2003-A)  (keine Order gefunden)
- Ereignis nicht zuordenbar: Revised plan for KUNDE_X Polyester: 1st 40ft HQ ex-mill 30.10, sailing Karachi 05.11. (mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Request for written confirmation of ex-factory dates and sample status for B2B orders (Spo (keine Order gefunden)
- Ereignis nicht zuordenbar: Revised planning for air freight quantities to meet deadlines, detailing shipped quantitie (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Barcode layouts and carton mark template confirmed for styles XW26-006, XW26-008, and XW26 (mehrdeutig: PO-WONDERS-XW-SM260811, PO-WONDERS-XW-SM260513)
- Ereignis nicht zuordenbar: Lieferant A reports that 17,500 garments have been shipped so far, and plans to ship an (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Barcode layouts and carton mark template for XW26-006, XW26-008 and XW26-009 are approved. (mehrdeutig: PO-WONDERS-XW-SM260811, PO-WONDERS-XW-SM260513)
- Ereignis nicht zuordenbar: Smilodox confirmed that the balance payment will be arranged by the end of this week. (mehrdeutig: 2 laufende Orders von LIEFERANT_X INDUSTRY CO.,LTD)
