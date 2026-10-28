# Alltagslauf 2026-10-28 07:42 (AUSGEFUEHRT)

Neu: 16 Dokument-Dateien, 475 Ereignis-Dateien

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
| 1a18029be127d27d_1.json | DELIVERY_DOC | XW-SM260710 | #24 PO-WONDERS-XW042-20260709 |

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

## #31 PO-LIEFERANT_AG-2026-06-24
- [2026-10-12 18:32 ev:1da0c263] SHIPMENT: Yükleme detayı, konşimento ve çeki listesi gönderildi. (Mail 1a130f54771ecddc)
- [2026-10-12 18:33 ev:4a0014b2] SHIPMENT: Export declaration and invoice for shipment issued. (Mail 1a130f64567930c6)
## #16 PO-LIEFERANT_AG-2026-03-17
- [2026-10-12 18:32 ev:94763980] SHIPMENT: Warenladung für den Transport am 11.09.2026 vorbereitet und Lkw-Daten mitgeteilt (Traktor: 34 NVV 280, Auflieger: 34 ZR 6698). (Mail 1a130f5cbf1f16cf) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
## #25 PO-LIEFERANT_D-ALI20260821
- [2026-10-12 18:37 ev:59287eba] SAMPLE: Revised samples for fleece kenna jacket (size XS) were sent via Fedex and are expected to arrive this Wednesday. Attached is a fitting video. (Mail 1a130f9b61384348)
- [2026-10-12 18:37 ev:98d26bac] SAMPLE: Revised samples sent by FedEx with tracking number 8767 4657 6407. (Mail 1a130f9bd78eb3c8)
- [2026-10-12 18:51 ev:c2edcfd4] ORDER_CHANGE: Lieferant bittet darum, für diesen Auftrag normales Papier für das Etikett (paper tag) statt des dicken Papiers zu verwenden, da die Produktionszeit knapp und die Kosten ein Problem sind. (Mail 1a1310662d7b006d) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-12 18:51 ev:db42ddbf] ORDER_CHANGE: Lieferant lehnt nachträgliche Änderungen an Care Label und Papierqualität der Verpackung für laufende Bestellung ab, da dies die Kosten erhöht. (Mail 1a13106686f7aea5) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-12 18:51 ev:93dd57ff] ORDER_CHANGE: Number of hangtags reduced from three to two; current packaging plan approved. (Mail 1a13106754de64be) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-12 18:51 ev:18930b64] ORDER_CHANGE: Discussion about changing two details for F-1 rise size (rise length 4cm shorter after stretching and width same as AN-43). Two versions will be shown tomorrow. (Mail 1a131067d7fcdc7d) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-12 18:52 ev:4ceaabe6] DELAY: Vendor states that adding a flag label on the waistband will increase the price and delay the ETD to October 25th, 2026. (Mail 1a1310742b8c819e) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-12 18:52 ev:cc0e420a] DELAY: Lieferant teilt mit, dass die Lieferung aufgrund der gewünschten Flaggen-Labels am Bund (zusätzlicher Maschinenaufwand) verzögert wird und empfiehlt, das Design nicht zu ändern. (Mail 1a1310752e71b091) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-12 18:52 ev:e42a2ec0] ORDER_CHANGE: Clarifications and changes regarding labels and hangtags: fabric compositions confirmed, size labels updated (remove website and wash care symbols), woven flag label cancelled for leggings but remains for the jacket, and only two hangtags required. (Mail 1a1310757def3bf5) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-12 18:52 ev:17f86094] SCHEDULE: Supplier requested to start production based on the F-3 print label. (Mail 1a131076496537e2) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-26 08:22 ev:b4ba9b95] SHIPMENT: Air freight has been divided into 5 documents (AWB K327852, K363390, K363397, K363480, K363698) and bill of lading has been released. (Mail 1a17716e75e62ae1)
- [2026-10-26 08:50 ev:1c928d76] SHIPMENT: The shipment has been dispatched by railway with FCR number DMRF261010369. (Mail 1a1773033126917d)
- [2026-10-26 08:50 ev:8ee27a02] PAYMENT: Supplier requests the third payment for the railway shipment. (Mail 1a1773033126917d)
- [2026-10-26 10:43 ev:5bf94612] SHIPMENT: Goods have been shipped by sea in 2x40'HQ containers under B/L NGBE26101866. (Mail 1a17797d16e6a650)
- [2026-10-26 10:43 ev:299f440b] PAYMENT: Supplier requested to arrange the third payment (30% balance 35 days after shipment). (Mail 1a17797d16e6a650)
- [2026-10-26 10:43 ev:c8c74128] ORDER_CHANGE: Short shipment due to quality issues: AN-44 is short by 17 pcs and F-3 is short by 170 pcs. Invoice and packing list have been revised. (Mail 1a17797d16e6a650)
- [2026-10-26 16:15 ev:d6ba1197] PAYMENT: Payment order of 53,230.73 USD (47,706.34 EUR) initiated for balance against B/L 30 of CI - LIEFERANT_D-AALI20360821 SEA, currently pending. (Mail 1a178c8718ba250a)
- [2026-10-26 16:21 ev:98cca90b] PAYMENT: Payment order status ACSP (pending) for balance against B/L of invoice LIEFERANT_D-AALI20360821 for 26764.88 USD. (Mail 1a178cdf098f5a17)
- [2026-10-27 02:56 ev:feb285ab] PAYMENT: The 2nd payment made on October 15th has been recorded. (Mail 1a17b12b21617ccc)
- [2026-10-27 02:56 ev:43aa2a0a] PAYMENT: Vendor requests the third payment for a total balance of $87654.69. (Mail 1a17b12b21617ccc)
- [2026-10-27 02:56 ev:5c2c0ec6] ORDER_CHANGE: Invoice total adjusted due to shortages (AN-44: 17 pcs short, F-3: 170 pcs short). (Mail 1a17b12b21617ccc)
- [2026-10-27 03:10 ev:88cc75e7] PAYMENT: The second payment made on October 15th has been recorded and reduced from the invoice. (Mail 1a17b1f488d2ba80)
- [2026-10-27 18:02 ev:fadab84b] PAYMENT: Smilodox confirmed that the third payment will be arranged according to the agreed term of 35 days after shipment. (Mail 1a17e504ac41efc5)
- [2026-10-27 18:20 ev:73e661b8] PAYMENT: Smilodox confirmed that payment will be arranged closer to the agreed due date. (Mail 1a17e605e5fd92ba) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- ZAHLUNG bezahlt: 53230.73
- ZAHLUNG bezahlt: 26764.88
## #38 PO-ALPHA-SWEAT-PROGRAM-2026-06-03
- [2026-10-12 18:39 ev:0dfb479c] QUALITY: Zia asked Mr. Umar for clear pictures and confirmation if the inspection of the 2nd container can be offered today. (Mail 1a130fbe5cd95274)
- [2026-10-12 18:39 ev:cd376fbd] QUALITY: Today inspection of 3000 pcs garment is presented, tomorrow 4000-4500 pcs audit will be presented to move container and catch cut-off. (Mail 1a130fbf0fb09f68)
- [2026-10-12 18:40 ev:b687c284] QUALITY: Smilodox requested the final inspection report (FRI report) table as a PDF for internal documentation. (Mail 1a130fc94c9fe623)
- [2026-10-12 18:40 ev:f0fdb225] SHIPMENT: Shipment details and packing list for the first sweat style container containing 7489 pieces (693 cartons, 49.896 CBM) shipped by sea. (Mail 1a130fc9beab03ac)
- [2026-10-14 11:11 ev:f847e19f] SHIPMENT: Lieferant meldet Luftfrachtsendung Multan nach Hannover (229 Kartons, 1.888 Stueck) mit Flug SV-801 am 16.10.2026. Rechnung und Packliste liegen vor, die Airway Bill steht noch aus. (Mail 1a139ae6379ca9e8)
- [2026-10-14 11:11 ev:a480d84d] OTHER: Der Excel-Anhang enthaelt eine 'Custom Invoice' mit hoeheren Stueckpreisen (Summe 20.006,10 USD) neben der Buyer Invoice (13.145,50 USD). Auch der Betrag in Worten und die Zahlungsdokumente nennen 20.006,10 USD. (Mail 1a139ae6379ca9e8)
- [2026-10-14 11:37 ev:8010d3d4] SHIPMENT: Lieferant A hat die Airway Bill 065-4958 9923 (Saudi Arabian Airline, Agent Sky Trax Cargo Services) für Invoice AK/623/26 übersandt. Luftfracht Multan (PKR) über JED nach Hannover, Flug SV-801 am 16.10.2026, 229 Kartons, 1888 Stück (1172 Hoodies, 716 Hosen), Bruttogewicht 1660 kg, Fracht prepaid. (Mail 1a139c642ee52d1e)
- [2026-10-14 12:18 ev:91bfe96a] ORDER_CHANGE: Israr (Lieferant A) hat das Massblatt der Siera Pant nach Anweisung von Imran Saleem aktualisiert und einen WhatsApp-Screenshot als Referenz angehaengt. Auf Fadels Rueckfrage vom 12.10. antwortet er damit, dass die Aenderungen auf Imrans Angaben beruhen. (Mail 1a139eb8e8f30e55)
- [2026-10-15 09:08 ev:0c257ff8] QUALITY: Final inspection report issued for AL29008 with overall result PASS under AQL 2.5. (Mail 1a13e648043ef214)
- [2026-10-15 09:08 ev:06dcd57f] QUALITY: Final inspection report issued for 26498 with overall result PASS under AQL 2.5. (Mail 1a13e648043ef214) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-16 08:45 ev:9b19f16d] SCHEDULE: Lieferant A shared the production and delivery planning up to November 5 for sweat styles, Siara trousers, and the KUNDE_X polystyle project. (Mail 1a14375cebc5ad72) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-19 13:26 ev:5fc02359] ORDER_CHANGE: Dark blue T-shirt quantity and Khaki color fleece were cancelled, but fabric is in-house. Vendor asks whether to proceed with production based on the first order quantities using the existing fabric. (Mail 1a153e9cfdad5fcf) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-20 08:31 ev:c93b68f5] SHIPMENT: Shipment dispatched by air (Flight SV-801, MAWB 065-5830 7653) from Multan Airport to Hannover Airport. (Mail 1a158022cc4f34ad)
- [2026-10-20 08:35 ev:dcf4aa41] SHIPMENT: Airway Bill issued for shipment via Saudi Arabian Airlines, ETD 21-10-2026 from Multan to Hannover. (Mail 1a15805610a04a76)
- [2026-10-20 08:35 ev:d16c3cf1] SCHEDULE: ETD for shipment AK/625/26 is scheduled for 21-10-2026. (Mail 1a15805610a04a76)
- [2026-10-20 15:37 ev:e9ab8c30] SAMPLE: Status check requested for missing photo samples across multiple styles and colors. (Mail 1a15988301969094)
- [2026-10-20 16:53 ev:798ee69e] SAMPLE: Smilodox is requesting the status and expected delivery date for missing photo samples across multiple styles and colors. (Mail 1a159ce2c726cec4)
- [2026-10-21 11:58 ev:0eb9d076] SCHEDULE: Plan for 2nd batch (116 CBM) of KUNDE_X Polyester: Ex-mill 30.10.2026, sailing 03.11.2026, ETA 02.12.2026. (Mail 1a15de5cd594ccf1) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-21 11:58 ev:74ee19f0] SHIPMENT: 4th air shipment of Sweat Styles (~4,000 pcs) scheduled to be dispatched by 22.10. (Mail 1a15de5cd594ccf1) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-21 11:58 ev:4780466a] SCHEDULE: Smilodox Sweat Styles production balance committed for 05.11 (~30,000 pcs). (Mail 1a15de5cd594ccf1) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-21 13:26 ev:d2a19a8e] SAMPLE: Vendor sent an updated dispatched samples detail excel sheet clarifying dispatched sample statuses and tracking information. (Mail 1a15e363d30f29ba)
- [2026-10-22 10:30 ev:988bfe29] SAMPLE: Request for missing photo samples and expected delivery date for 34 articles with 118 open color variants. (Mail 1a162bbc61057147)
- [2026-10-22 11:48 ev:53bb666d] SCHEDULE: KUNDE_X Polyester: Ex-mill ~115 CBM planned for 30.10.2026, sailing from Karachi on 03.11.2026 and ETA Hamburg on 02.12.2026. (Mail 1a163038333c6ecb) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:ba660989] SHIPMENT: KUNDE_X Polyester: 51 CBM dispatched yesterday (21.10.2026). (Mail 1a163038333c6ecb) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-22 11:48 ev:3a6c9e52] SHIPMENT: Sweat Styles (Air): 4th air shipment of 5,000-6,000 pcs shipping today (22.10.2026), total shipped after today approx. 15,000 pcs. (Mail 1a163038333c6ecb)
- [2026-10-22 11:48 ev:69e7e864] SCHEDULE: Sweat Styles (Air): Total air quantity of 60,000 pcs to be closed by 05.11.2026. (Mail 1a163038333c6ecb) [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]
- [2026-10-22 13:06 ev:e94c01ae] SHIPMENT: Sweat Air #1 shipped via flight AK/621/26, MAWB 065-49589945, quantity 4091 pcs, value USD 27,758.50, currently stuck with Saudia (not received). (Mail 1a1634a6d4270d28)
- [2026-10-22 13:06 ev:fa8b514d] SHIPMENT: Sweat Air #2 shipped via flight AK/623/26, MAWB 065-49589923, quantity 1888 pcs, value USD 13,145.50, not received. (Mail 1a1634a6d4270d28)
- [2026-10-22 13:06 ev:66b998ca] SHIPMENT: Sweat Air #3 shipped via flight AK/625/26, MAWB 065-58307653, quantity 3284 pcs, value USD 23,080.80, in transit with ETA approx. 26.10.2026. (Mail 1a1634a6d4270d28)
- [2026-10-22 13:06 ev:4affdd32] SHIPMENT: Sweat Air #4 shipping today with docs pending, approx. 5000-6000 pcs, ETA approx. 29.10.2026. (Mail 1a1634a6d4270d28)
- [2026-10-22 13:06 ev:c10e205a] SHIPMENT: KUNDE_X #12 dispatched on 21.10.2026 with 51 CBM, docs pending, ETA approx. 30.11.2026. (Mail 1a1634a6d4270d28) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-22 13:06 ev:520254de] SCHEDULE: KUNDE_X Polyester next batch ex-mill date set to 30.10.2026, sailing from Karachi on 03.11.2026, ETA Hamburg 02.12.2026. (Mail 1a1634a6d4270d28) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-22 13:15 ev:499d206c] SAMPLE: The supplier has already dispatched photo samples in size M for men and size S for women for several styles and will dispatch more styles tomorrow. (Mail 1a16352d6004ec7b)
- [2026-10-23 16:49 ev:a8cedebb] SHIPMENT: Some photo samples have already been dispatched, and specific styles are ready to dispatch. (Mail 1a1693d1f3184736)
- [2026-10-24 09:13 ev:717f8fe5] SHIPMENT: Commercial invoice and packing list for shipment AK/630/26 sent via air, MAWB 065-5830 7664, flight SV-801. (Mail 1a16cc1d7966233c)
- [2026-10-24 09:19 ev:ad319a33] SHIPMENT: Shipment has been dispatched by air with MAWB 065-5830 7664, containing hoodies and pants. (Mail 1a16cc73e1de040d)
- [2026-10-24 11:23 ev:7b2b06a3] SHIPMENT: Commercial invoice and packing list provided for air shipment under MAWB 065-5830 7664, flight SV-801. (Mail 1a16d3964b454ec4)
- [2026-10-26 13:00 ev:8931e28d] SHIPMENT: Sweat Styles air shipments update: 15,000 pcs shipped so far, 4,500 pcs planned for today. Target of 45,000 pcs for 05.11 under review. (Mail 1a17815b1851bebb) [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]
- [2026-10-26 15:08 ev:9bb27488] SAMPLE: Updated list of missing photo samples sent without the samples already dispatched. (Mail 1a1788b19a37efc0)
- [2026-10-26 16:23 ev:fcf7af10] SCHEDULE: Revised planning for air freight quantities to meet deadlines, detailing shipped quantities, WIP, and upcoming shipments for sweat styles, siara, and the KUNDE_X Project. (Mail 1a178cfa1755d585) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-26 17:05 ev:8c9a8021] SCHEDULE: Clarification on shipment schedule: 20,000 pcs of sweat styles will be shipped by November 5 instead of October 5, achieving 33% of the planned 60,000 pcs. (Mail 1a178f6171fff840) [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]
- [2026-10-27 08:30 ev:25c591d3] SCHEDULE: Lieferant A reports that 17,500 garments have been shipped so far, and plans to ship another 30,000-40,000 garments by November 5, bringing the total shipped to 55,000-60,000 garments. (Mail 1a17c4491e778d2c) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-27 09:40 ev:615c87af] OTHER: Replacement of EAN barcode labels for Siara pants due to system error and duplicate assignment. (Mail 1a17c848ed4b3022)
- [2026-10-27 09:40 ev:b2d14bc7] SHIPMENT: Bordeaux color is being delivered today, Blau Uni is currently in embroidery. (Mail 1a17c848ed4b3022)
- [2026-10-27 09:45 ev:282117a4] OTHER: Update of barcode labels for Siera pants (style 26385) due to duplicate EAN assignments. (Mail 1a17c88f29ee0d80)
- [2026-10-27 14:00 ev:7b844154] SAMPLE: Lieferant sendet aktualisierte Barcode-Etiketten für den Style Jogginghose Siara (26385) zur Freigabe. (Mail 1a17d726a919e247)
- DATUM: {'etdEstimatedDate': '2026-10-21T00:00:00.000Z'}
## #3 PO-LIEFERANT_X-JM260511
- [2026-10-12 18:40 ev:6d83b5a4] SHIPMENT: Forwarder asked to confirm booking for a 40GP container from Xiamen to Hamburg. (Mail 1a130fd1e25464a5)
- [2026-10-12 18:40 ev:16b9889b] SHIPMENT: Freistellung von Reederei erhalten fuer Sendung von Xiamen nach Hamburg. (Mail 1a130fd275ddaeaa)
- [2026-10-12 18:41 ev:49861ff3] SHIPMENT: Consol shipment of 1 x 40GP container from Xiamen to Hamburg with multiple POs (26M10_001 / 26M10_002 / 26M10_003). Forwarder notes potential delays due to strikes. (Mail 1a130fd6a4621085)
- [2026-10-12 18:41 ev:868313b7] SHIPMENT: Shipper schafft eine frühe Abfahrt für die Konsolidierung (PO: 26M10_001 / 26M10_002 / 26M10_003, 1 x 40GP von Xiamen nach Hamburg). (Mail 1a130fd709ff2449)
- [2026-10-12 22:00 ev:5303498d] SHIPMENT: First orders (26M10_001, 26M10_002, 26M10_003) have been shipped with ATD Sep 18 and ETA Oct 18. (Mail 1a131b3fe10a9d0b)
- [2026-10-12 22:00 ev:e4c43e91] PAYMENT: Supplier requested balance payment for shipped orders in order to arrange telex release. (Mail 1a131b3fe10a9d0b)
- [2026-10-14 10:52 ev:3c5da8da] PAYMENT: Balance payment was arranged last Monday. Bank slip will be forwarded once received. (Mail 1a1399d2d44495ac)
- [2026-10-16 10:17 ev:f2521c29] PAYMENT: Lieferant fragt nach dem Zahlungsbeleg (bank slip). (Mail 1a143ca375d4d40a)
- [2026-10-19 08:36 ev:0600d9cb] SHIPMENT: Bill of Lading issued, goods shipped on board and telex release arranged. (Mail 1a152e05703026ba)
## #30 PO-LIEFERANT_G-MC-26SM002
- [2026-10-12 18:41 ev:c5045ea9] QUALITY: Embroidery quality issue reported with bulging/uneven areas, requesting a revision and replacement of lettering artwork. (Mail 1a130fda9f50a77c) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:41 ev:4a8d450c] QUALITY: Explanation regarding embroidery issue on black-on-black vs. white-thread version. (Mail 1a130fdc6ea61188)
- [2026-10-12 18:41 ev:5244718b] SAMPLE: Wendy provided feedback on the embroidery logo and suggested using the regular version as before or switching to silkscreen due to wrinkling issues on the thick coated fabric. (Mail 1a130fde06007855)
- [2026-10-12 18:49 ev:0a004c43] SAMPLE: Pre-production samples for GT0303 and GT0304-volcanic ash are not yet 100% correct and shipping was postponed due to high freight costs (> USD 500). (Mail 1a13105453aef277)
- [2026-10-12 18:49 ev:825e091b] OTHER: Request to push the webbing supplier to complete the revised binding webbing for GT0304 as soon as possible. (Mail 1a1310554e320fa0)
- [2026-10-13 14:16 ev:6bbd48ca] SHIPMENT: Wendy (lieferant_g) schlaegt vor, etwa 30 % der Ware (ca. 11 CBM) per Bahn und die restlichen 28 CBM in einem 20-Fuss-Container per Seefracht zu versenden, bei einem Gesamtvolumen von 38,7 CBM. Sie fragt, ob das fuer Smilodox funktioniert. (Mail 1a1353161646a1a7)
- [2026-10-13 14:16 ev:5c3d68a7] OTHER: Wendy wartet weiterhin auf die Kontaktdaten des Seefrachtspediteurs, die fuer die Buchung benoetigt werden. Sie weist darauf hin, dass Cargo normalerweise 4-5 Tage vor ETD im Lager sein muss und eine Verspaetung den Schiffsabgang gefaehrden kann. (Mail 1a1353161646a1a7)
- [2026-10-13 17:42 ev:5e1dc75e] SHIPMENT: Wendy schlägt vor, ca. 30 % der Ware (ca. 11 CBM) per Bahn und die restlichen 28 CBM in einem 20'-Container per See zu versenden, statt der bisher vorgeschlagenen 50/50-Aufteilung. Sie bittet um Bestätigung der Bahnmenge für die Buchung beim Forwarder. (Mail 1a135ee35d89aafb)
- [2026-10-13 17:42 ev:1da44e1f] SHIPMENT: Die Kontaktdaten des Seespediteurs fehlen dem Lieferanten weiterhin; die Ware muss üblicherweise 4–5 Tage vor ETD im Lager sein, eine Verzögerung von einem Tag kann das Schiff kosten. (Mail 1a135ee35d89aafb)
- [2026-10-14 09:22 ev:abdf27d8] SHIPMENT: Der Lieferant muss dringend Bahnfracht beim Spediteur buchen und bittet um Bestätigung der Bahn-CBM. Vorschlag: ca. 12 CBM per Bahn (ca. 30%), der Rest in einen 20'-Container. Alternative ist die von Smilodox genannte 50%-Variante (19 CBM Bahn). (Mail 1a1394accb2fcd73)
- [2026-10-20 11:20 ev:cbe71c2b] SHIPMENT: Acknowledgement of invoice and packing list for railway shipment. (Mail 1a1589d09778b37a)
- [2026-10-20 11:49 ev:3fcd7bcf] SHIPMENT: Wendy has contacted the sea shipment forwarder (the same company used for the previous railway shipment) and provided vessel information. (Mail 1a158b7bcae61f56)
- [2026-10-27 11:20 ev:a6574b50] SCHEDULE: Railway cargo shipment is expected to arrive on Nov. 13, 2026. (Mail 1a17ce00db3a9a9d)
- [2026-10-27 11:20 ev:cc2aeab9] SHIPMENT: Railway shipment dispatched with FCR LCL26100205. (Mail 1a17ce00db3a9a9d)
- [2026-10-27 11:20 ev:45cfb5e3] SHIPMENT: Sea shipment dispatched under Bill of Lading SEF261023462. (Mail 1a17ce00db3a9a9d)
- [2026-10-27 14:52 ev:24b8f864] PAYMENT: Smilodox announced that they will review the shipping documents and arrange the balance payment by the end of the week. (Mail 1a17da26d892f493)
## #19 PO-LIEFERANT_AA-WINTER-2026-04-29
- [2026-10-12 18:48 ev:26f01536] SHIPMENT: Final shipping documents (packing list and invoice) received; waiting for B/L. Vessel: MSC IRIS GL635W, POL-POD: SHANGHAI-HAMBURG. (Mail 1a13103f670add8b) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:48 ev:c2e0decd] PAYMENT: Supplier requested 15% payment of the total amount. (Mail 1a13103fd472a81b)
- [2026-10-12 18:48 ev:f628ebf5] SHIPMENT: Bill of Lading Draft provided for shipment via MSC IRIS/GL635W from Shanghai to Hamburg. (Mail 1a13103fd472a81b) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:48 ev:522affb4] PAYMENT: Smilodox plans to arrange the 15% deposit payment this week. (Mail 1a1310407c233805) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:48 ev:9eda0178] SHIPMENT: Smilodox requested the packing list for the remaining 2,000 pcs to arrange the forwarder and plan shipment. (Mail 1a1310407c233805) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:48 ev:a688700a] SCHEDULE: Shipment is expected to be made by train on September 30th. (Mail 1a131040aa2307c7) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:48 ev:fcb6236c] SCHEDULE: Smilodox requests train departure on 30 September to be secured; otherwise, goods must be shipped by air freight at LIEFERANT_AA's cost. (Mail 1a1310410f6c749f)
- [2026-10-12 18:48 ev:94aaa261] SHIPMENT: The train freight has been booked for September 30, and additional sea freight costs apply. (Mail 1a13104186b4eaaf) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:48 ev:5de9d074] PAYMENT: Lieferant fragt nach dem Zahlungsstatus für die offenen Dokumente. (Mail 1a131042422142be) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-12 18:48 ev:c9d17673] SHIPMENT: Bill of Lading issued for shipment of MEN'S JACKET (Style SMI2612) in container MSNU6530944. (Mail 1a131042a7ab573e) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-20 09:31 ev:b62e8cb7] PAYMENT: 15% payment of USD 4,046.63 made upon shipment for order LIEFERANT_AA26104 (Note: bank reference states LIEFERANT_AA226104). (Mail 1a1583954f10adee)
- [2026-10-20 09:31 ev:0e9780fa] PAYMENT: Sea freight payment of USD 2,630.00 made for order LIEFERANT_AA26104 (Note: bank reference states LIEFERANT_AA226104). (Mail 1a1583954f10adee)
- [2026-10-27 09:18 ev:b1bf96aa] SHIPMENT: Ankunftsavis für Bahnsendung eingetroffen, voraussichtliche Abnahme am 28.10.2026. (Mail 1a17c7104a8a3ec3)
- [2026-10-27 14:04 ev:59551d21] SHIPMENT: Ankunft der Sendung und Bereitstellung des Auslieferungsscheins und der ATB-Nummer. (Mail 1a17d765b565dc78) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-27 14:04 ev:a7d34d73] SCHEDULE: Ankunft der Sendung am 26.10.2026 in Hamburg. (Mail 1a17d765b565dc78) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- DATUM: {'etdEstimatedDate': '2026-09-30T00:00:00.000Z'}
## #37 PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER
- [2026-10-12 18:55 ev:65364282] SHIPMENT: Versandbenachrichtigung mit HBL vom Spediteur EC Lontor erhalten (CMA CGM RIO GRANDE, ETD 14.08., ETA 13.09.). (Mail 1a1310a6ed02f60a)
- [2026-10-12 22:02 ev:b26b8665] SHIPMENT: Sendung per Seefracht (4*40HQ) mit MBL XIA1965473 und HBL XIME26070257, ETD Xiamen 7. August, Spediteur fragt nach Palettierungs- und Sortieranweisungen. (Mail 1a131b5dbbcc7e59)
- [2026-10-20 12:57 ev:698d8441] OTHER: Fadel Abdullah asked to wait until next Thursday for the signed and stamped authorization letter because Kemal is on holiday. (Mail 1a158f60bb3df5fa)
- [2026-10-21 11:32 ev:a45cb185] PAYMENT: Lydia from Lieferant Y confirmed they will wait until next Thursday regarding payment and discuss with their bank. (Mail 1a15dce3df2ca187)
## #4 PO-LIEFERANT_X-JM260704
- [2026-10-12 22:00 ev:e0e4b3aa] SCHEDULE: Delivery times for reorders 26M10_001 and 26M10_002 remain unchanged. (Mail 1a131b3fe10a9d0b)
- [2026-10-12 22:01 ev:99a9dc35] SCHEDULE: Doreen Liu asks when the shipping will be arranged for reorders 26M10_001 and 26M10_002 and is waiting for forwarder information. (Mail 1a131b454cfe1d5e)
- [2026-10-12 22:01 ev:e6b2bf67] SCHEDULE: Doreen Liu asks when the shipping will be arranged for reorders 26M10_001 and 26M10_002 and is waiting for forwarder information. (Mail 1a131b454cfe1d5e)
- [2026-10-27 08:48 ev:93af2f90] SHIPMENT: Goods shipped via sea on vessel CMA CGM RODOLPHE with ATD 2026-10-23 and ETA 2026-11-22. (Mail 1a17c5576c0d951e)
- [2026-10-27 10:05 ev:c5500e68] PAYMENT: Smilodox confirmed that the balance payment will be arranged by the end of this week. (Mail 1a17c9be3cf4bcb3) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
## #24 PO-WONDERS-XW042-20260709
- [2026-10-12 22:00 ev:609a98cf] SCHEDULE: Production status update for XW-042 Crocodile: Sewing cargo will be ready on Oct 15th, EXW is Oct 15, 2026. (Mail 1a131b40a276d682)
- [2026-10-28 02:39 ev:9b8d805d] SHIPMENT: Rain Jacket bulk cargo handed over to forwarder by supplier. (Mail 1a18029be127d27d)
- [2026-10-28 02:39 ev:31181f32] PAYMENT: Balance payment requested for invoice XW-SM260710. (Mail 1a18029be127d27d)
- [2026-10-28 02:39 ev:3bb8dcb9] BELEG INVOICE: INVOICE XW-SM260710 | 5075 Stk | 71050 USD | Zahlungen: Deposit 21000 Paid, Balance 50050 Unpaid: With 5% more or less both in quantity and total amount is allowed. (Mail 1a18029be127d27d)
- DATUM: {'exFactoryExpectedDate': '2026-10-15T00:00:00.000Z', 'etdEstimatedDate': '2026-10-25T00:00:00.000Z'}
## #33 PO-WONDERS-XW-SM260730
- [2026-10-12 22:00 ev:d1400af8] SCHEDULE: Production status update for XW-042 New (Crocodile/Cheetah Print): Dying fabric, EXW Dec 10, 2026. (Mail 1a131b40a276d682)
- [2026-10-14 12:54 ev:36c630ae] OTHER: Fuer den XW-042 Cheetah Print ist Barcode XW-042_A zu verwenden. XW-042_B wird intern im System von Smilodox geloescht und darf nicht verwendet werden. (Mail 1a13a0cd5be2dac5)
- [2026-10-14 13:01 ev:ce6267b1] ORDER_CHANGE: Für den XW-042 Cheetah Print ist Barcode XW-042_A zu verwenden, XW-042_B nicht. Der Lieferant soll die Stylebezeichnung auf XW-042_A aendern. Der Lieferant hat um Bestaetigung gebeten, ob so vorgegangen werden soll. (Mail 1a13a133dd81f60d)
- DATUM: {'exFactoryExpectedDate': '2026-12-10T00:00:00.000Z', 'etdEstimatedDate': '2026-12-20T00:00:00.000Z'}
## #34 PO-WONDERS-XW-SM260811
- [2026-10-12 22:00 ev:4fc86c2b] SCHEDULE: Production status update for XW26-006 re order: Woven yard, EXW Dec 30, 2026. (Mail 1a131b40a276d682)
- [2026-10-12 22:00 ev:f8f2a74a] SCHEDULE: Production status update for XW26-008: Woven yard, EXW Dec 30, 2026. (Mail 1a131b40a276d682)
- [2026-10-12 22:00 ev:8229b2c6] SCHEDULE: Production status update for XW26-009: Woven yard, EXW Dec 30, 2026. (Mail 1a131b40a276d682)
- [2026-10-12 22:01 ev:d173749a] OTHER: Fadel Abdullah asks for the latest deadline to provide complete barcode information for styles XW-042 Croco/Cheetah Print, XW26-006, XW26-008, and XW26-009 to avoid production impacts. (Mail 1a131b44a07811c6)
- [2026-10-14 05:51 ev:55678539] OTHER: Der Lieferant meldet, dass XW26-008 (Long Sleeve) und XW26-009 (Tank Top) die Farbe light grey nicht haben, daher entfaellt die E-Serie fuer diese Styles. Er fragt, ob die anderen Farbgruppen die E-Serie ueberspringen oder ersetzen sollen. (Mail 1a138891a17b99d9)
- [2026-10-14 12:54 ev:059ea0fd] OTHER: Smilodox bestaetigt, dass Light Grey nicht Teil dieser Bestellung ist. Die E-Serie der Barcodes fuer XW26-008 und XW26-009 soll fuer diese Bestellung entfallen. Die uebrigen Farbgruppen muessen nicht ersetzt oder neu nummeriert werden. (Mail 1a13a0cd5be2dac5)
- [2026-10-14 13:01 ev:133a4173] ORDER_CHANGE: Light Grey ist in dieser Bestellung nicht enthalten, daher entfällt die E-Serie. Die anderen Farbgruppen werden nicht umnummeriert oder ersetzt. (Mail 1a13a133dd81f60d)
- [2026-10-15 12:57 ev:8a540984] SAMPLE: For the pp sample, sizes can be mixed across colors. For style XW26-006 short sleeve t shirt, three colors are repeat colors, so only the new colorway pp samples will be sent. (Mail 1a13f3583a2f7e57)
- [2026-10-21 10:59 ev:dfff3245] SAMPLE: Revised size chart for XW26-009 tank top provided for review. (Mail 1a15db094f3829ce)
- [2026-10-21 12:21 ev:4d9502dc] OTHER: The supplier sent the barcode layout and carton marks for styles XW26-006, XW26-008, and XW26-009 for review. (Mail 1a15dfc30a9f3dae)
- [2026-10-22 09:37 ev:557f6ea6] SAMPLE: Lieferant bittet um Freigabe bzw. Bestätigung der Größentabelle für das Tank Top (Style XW26-009). (Mail 1a1628b5c4a07fd7)
- [2026-10-26 06:39 ev:d7fd809e] SAMPLE: Nicole Chen requests confirmation of the updated size chart for the tank top (style XW26-009) in order to arrange the PP sample urgently. (Mail 1a176b95fadafc1e)
- [2026-10-26 17:22 ev:4dd65ac8] SAMPLE: Size chart for style XW26-009 is confirmed, and a new sample in sizes M and L has been requested. (Mail 1a179058187cbc24)
- [2026-10-26 17:23 ev:b8dfa830] OTHER: Barcode layouts and carton mark template confirmed for styles XW26-006, XW26-008, and XW26-009. (Mail 1a179066adc3ffe3) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- [2026-10-27 09:12 ev:c6f93a49] OTHER: Barcode layouts and carton mark template for XW26-006, XW26-008 and XW26-009 are approved. (Mail 1a17c6aae634ba58) [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]
- DATUM: {'exFactoryExpectedDate': '2026-12-30T00:00:00.000Z', 'etdEstimatedDate': '2027-01-10T00:00:00.000Z'}
## #36 PO-LIEFERANT_AA-26WJD-108-REORDER
- [2026-10-12 22:00 ev:86a9fb5f] SCHEDULE: Style SMI2606 and SMI2612 will be delayed by around 10 days. (Mail 1a131b41523af8ff)
- [2026-10-12 22:00 ev:2167852c] SCHEDULE: Style SMI2606 and SMI2612 will be delayed by around 10 days. (Mail 1a131b41523af8ff)
- [2026-10-12 22:00 ev:44479dd0] DELAY: Smilodox rejects delayed delivery for two styles and requests them to be sent via air freight. (Mail 1a131b42bfd25f35)
- [2026-10-12 22:00 ev:af890551] SCHEDULE: Lieferant bittet um Mitteilung des Speditors für FOB Myanmar. (Mail 1a131b43a74532a0)
- [2026-10-20 09:31 ev:a38974f7] PAYMENT: 35% payment of USD 6,880.65 made for order LIEFERANT_AA2688 (40 days after shipment). (Mail 1a1583954f10adee)
- [2026-10-21 08:51 ev:5baf66d5] SCHEDULE: All seven styles are ready for shipping and vessel booking is urgently needed. The Myanmar factory will be on holiday from October 25 to 27. (Mail 1a15d3ab873f5a50)
## #96 PO-LIEFERANT_I-SPR2026000000409
- [2026-10-14 09:29 ev:c300c053] QUALITY: White printing defects noticed on the snake print; suggested switching to a black base fabric. (Mail 1a13951c52d8cf78) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-14 09:29 ev:91118219] ORDER_CHANGE: Request to add regular leggings with leo pattern (same as leggings 26803) to the production list. (Mail 1a13951c52d8cf78)
- [2026-10-14 20:08 ev:2a65a103] SHIPMENT: Shipping documents and packing list sent for order SPR2026000000409. (Mail 1a13b99baac29b3c)
## #28 PO-WONDERS-XW-SM260513
- [2026-10-16 13:51 ev:df7911e0] SHIPMENT: Three styles of women sherpa fleece jacket with the same fabric as XW-124 and the printing short original sample have been sent out via FedEx. (Mail 1a1448d82196ef74) [Zuordnung: Stylecode im Ereignistext, nicht per PO-Nr belegt]
- [2026-10-22 04:30 ev:5e9cc470] SHIPMENT: Telex released Bill of Lading (B/L) issued for shipment of 2x40'HQ containers (1406 cartons) on board vessel CMA CGM CALLISTO V.0R11EW1MA from Xiamen to Hamburg. (Mail 1a1617227098bfc5)
- [2026-10-22 08:46 ev:aad9c45a] SHIPMENT: Smilodox confirmed receipt of the complete set of shipping documents and the telex-released B/L. (Mail 1a1625c88f4fc219)
## #9 PO-LIEFERANT_V-KCCN0513
- [2026-10-20 10:31 ev:47a0488e] PAYMENT: Smilodox requested shipping documents to arrange the balance payment as previously agreed. (Mail 1a1586ff6a8b3210) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-20 14:19 ev:aa301025] PAYMENT: Lieferant fordert dringende Zahlung für Commercial Invoice der Styles KC-JK-00027 und KC-PT-00058 an, bevor der Versand arrangiert wird. (Mail 1a15941543d3ae95)
- [2026-10-21 17:30 ev:00219170] SAMPLE: Fitting comments for style KC-JK-00030 WDF: Make a Halfzip with two pockets and a pocket at the chest based on the provided reference. (Mail 1a15f23d930c1b30)
- [2026-10-21 17:30 ev:31cf0a95] SAMPLE: Fitting comments for style KC-JK-00030 WRF: Remove the center horizontal seam, add a zipper, and add drawcords. (Mail 1a15f23d930c1b30)
- [2026-10-21 17:30 ev:e1606919] SAMPLE: Fitting comments for style KC-PT-00058 WGL: Add an additional seam between second and third pleat, make white pleats decorative only, extend overall length by 4 cm, and change white stripes to black. (Mail 1a15f23d930c1b30)
- [2026-10-21 17:30 ev:6fc80529] SAMPLE: Fitting comments for style KC-JK-00027 WRF: Add arm waistband to bottom, reduce width by 2 cm each side, drop armhole by 3 cm, reduce neck width by 1 cm on each side, and declare size M as S. (Mail 1a15f23d930c1b30)
- [2026-10-21 17:30 ev:fe22ed2a] SAMPLE: Fitting comments for style KC-JK-00013 WRF: Change seam to have a more waisted cut. (Mail 1a15f23d930c1b30)
- [2026-10-21 17:30 ev:a5f584c9] ORDER_CHANGE: Style KC-JK-00027 WSF has been cancelled. (Mail 1a15f23d930c1b30)
- [2026-10-23 11:53 ev:e16635c9] PAYMENT: Vendor is requesting the balance payment for styles KC-JK-00027 and KC-PT-00058 before arranging shipment. (Mail 1a1682df93e02e92)
- [2026-10-26 11:33 ev:642255d5] QUALITY: Shipment samples have been approved by Smilodox, awaiting QC inspection date. (Mail 1a177c600824114a) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-26 11:33 ev:bc155287] PAYMENT: Discussion regarding payment terms before shipment versus payment against shipping documents. (Mail 1a177c600824114a) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-26 16:06 ev:c8407420] PAYMENT: Smilodox insists on paying the balance upon receipt of a copy of the Bill of Lading and cannot arrange payment before shipment. (Mail 1a178bfd2bec982d) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
- [2026-10-27 10:09 ev:e80009f9] SCHEDULE: Fadel Abdullah stated that they are working with the forwarder to find the best shipping route and details will be shared once confirmed. The QC team will contact them directly for the inspection date. (Mail 1a17c9ef1514f841) [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]
## #35 PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER
- [2026-10-20 10:33 ev:69dac721] PAYMENT: Supplier confirmed receipt of remittance of 6151.6 USD for LIEFERANT_AA2674. (Mail 1a158718945a7330)
- [2026-10-22 18:21 ev:a6272759] SHIPMENT: Smilodox is requesting the ATB for customs clearance urgently and announces that someone from SPEDITION_B will contact the forwarder for collection. (Mail 1a1646b0a8a9bea7)
- [2026-10-23 04:23 ev:68c7312e] SHIPMENT: Shipment status update: currently in Mala, distance to Hamburg 1031km, ETA 2026-10-26 to 2026-10-27. (Mail 1a166923925870f0)
- ZAHLUNG bezahlt: 6151.60
## #10 PO-ALPHA-TBC-EASYFITNESS-ALPHA-ALPHAWOMEN
- [2026-10-20 11:18 ev:e0304f4f] SAMPLE: Final Tech Packs for Easy Fitness are confirmed with one measurement change for style SEW26-004 (reduce W1/2 Relaxed for size XL by 0,5cm). (Mail 1a1589b9764c96f8)
- [2026-10-21 13:23 ev:3249c9d8] SAMPLE: Updated technical file for Women Short SEW26-004 sent for approval. (Mail 1a15e33d4fbb8ef8)
- [2026-10-21 17:30 ev:11c65710] SAMPLE: Tech pack review and feedback for development styles, including requested adjustments for embroidery sizes. (Mail 1a15f15f671b9d43)
## #98 PO-LIEFERANT_I-SPR2026000000422
- [2026-10-20 17:17 ev:af070f19] SHIPMENT: Shipment documents and commercial invoice for 19,275 pieces issued on 20.10.2026. (Mail 1a159e3b788a4764)
- [2026-10-23 15:35 ev:660989e6] SAMPLE: Photo samples listed for styles 26296, 26740, 26573, 26782, 26772, 26783, 26761, and 26784. (Mail 1a168f99f5b68f7a)
## #27 PO-LIEFERANT_T-PO26005SG-W
- [2026-10-21 11:09 ev:414bf8a5] SHIPMENT: Goods shipped on board on 2026-09-12 and forwarder released B/L. (Mail 1a15db8efc35f1e2)
## #57 PO-LIEFERANT_B-2026-07-02-FB54
- [2026-10-21 14:03 ev:0479fd28] SHIPMENT: Second container shipped via sea under B/L AGLLHE10240. (Mail 1a15e58e8bf56e63)
- [2026-10-21 14:03 ev:037005ab] PAYMENT: Supplier requested 35% payment of USD 16,227.04 against the scanned B/L for the 2nd container. (Mail 1a15e58e8bf56e63)
- [2026-10-22 09:28 ev:60d0f301] OTHER: Fadel Abdullah informed the supplier about the correct sock composition and requested a check and update of the HS code and shipping documents accordingly. (Mail 1a1628299a57a120)
- [2026-10-22 12:15 ev:801be710] SHIPMENT: Updated invoice and packing list with correct composition details provided. (Mail 1a1631c440498b5e)
- [2026-10-22 23:12 ev:471f0c4c] PAYMENT: Smilodox will arrange the payment tomorrow and requested a revised Commercial Invoice for the first container with updated material composition and payment breakdown. (Mail 1a16575c479df5ae)
- [2026-10-23 07:08 ev:0f75a6b0] PAYMENT: Vendor explains that for the 2nd container, there is no advance remaining, so the invoice terms are 50% on scan BL and 50% on 75 days from BL date. (Mail 1a16728aab2c91c6) [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]
- [2026-10-24 13:17 ev:a884f03b] PAYMENT: Smilodox confirmed that the payment will be arranged tomorrow. (Mail 1a16da17151841e4)
- [2026-10-24 13:17 ev:96f8d301] SHIPMENT: First container (2265-EXP-2026) shipped by sea via vessel ONE MARVEL / 0085. (Mail 1a16da17151841e4)
- [2026-10-24 13:38 ev:c487fb7b] SHIPMENT: Updated commercial invoice and packing list sent for the 2nd container. (Mail 1a16db47c8fb336a)
## #90 PO-LIEFERANT_A-ALP-58-25
- [2026-10-22 08:30 ev:f1853633] SAMPLE: Updated TP with correct NOOS base of SNW26-003 sent due to a previous mistake, and inquiry regarding EMB design sizes and variation. (Mail 1a1624e0c8897ddb)
## #26 PO-LIEFERANT_AH-SMI-SOHO-0526
- [2026-10-23 10:12 ev:a384e08b] SHIPMENT: Bill of Lading issued for shipment with 1x40'HQ container containing 432 cartons of knitted sweaters, shipped from Ningbo to Hamburg. (Mail 1a167d1a83c0f85d)
- [2026-10-23 11:05 ev:e752cf18] SHIPMENT: All goods were fully shipped via sea on MADRID MAERSK V.642W under B/L NGBE26101254. (Mail 1a168025869a4cbc)
- [2026-10-23 11:05 ev:f8939710] PAYMENT: Supplier requested balance payment for the shipment. (Mail 1a168025869a4cbc)
## #99 PO-LIEFERANT_I-SPR2026000000438
- [2026-10-23 15:27 ev:b2b9181c] SHIPMENT: Shipment documents sent for 7267 pieces across 623 cartons. (Mail 1a168f1c8a9d3d4c)
## #70 PO-LIEFERANT_AI-2026-03-18-751E
- [2026-10-26 07:19 ev:b43ae605] SHIPMENT: Export documents and packing list provided for shipment of 30711 pieces in 515 boxes. (Mail 1a176dd5eaeba732)
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
- [2026-10-12 18:46] PAYMENT: Die lokalen FOB-Gebühren am Abgangshafen wurden noch nicht beglichen, weshalb die Freigabeerklärung noch nicht erteilt werden kann. (LIEFERANT_A (PVT) LTD.) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:46] SHIPMENT: Container EGSU 155 511-8 wurde entladen. (LIEFERANT_B ENTERPRISES PVT LIMITED) -> mehrdeutig: PO-LIEFERANT_B-2026-06-13-3123, PO-LIEFERANT_B-2026-06-13-AA8B
- [2026-10-12 18:46] SHIPMENT: Container GAOU 642 138-0 wurde entladen. (Lieferant A Pvt Ltd) -> mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-12 18:46] SHIPMENT: Container EGHU 914 348-0 wurde entladen. (Lieferant A Pvt Ltd) -> mehrdeutig: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-12 18:47] SHIPMENT: Container EGHU9143480 wurde durch das Hauptzollamt Hamburg überlassen (Zollanmeldung und Einfuhrabgabenbescheid erstellt). (LIEFERANT_A (PVT) LTD.) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:47] SHIPMENT: Container GAOU6421380 aus Ningbo (Versender Lieferant A, Pakistan) wurde am 12.10.2026 customs-cleared / überlassen in Hamburg. (LIEFERANT_A (PVT) LTD.) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-12 18:48] OTHER: Vendor sent barcode stickers layout and carton marking for style XW-042 for review and confirmation. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 18:53] SHIPMENT: Container HMMU6963097 arrived in Hamburg via vessel ONE RELIABILITY V#0020W, delivery order issued. (LIEFERANT_B ENTERPRISES) -> mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd
- [2026-10-12 18:54] SHIPMENT: Inbound vessel arrived with container HMMU6963097 containing knitted socks from Karachi, Pakistan. (LIEFERANT_B ENTERPRISES) -> mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd
- [2026-10-12 22:00] SCHEDULE: Inquiry regarding production and logistics status for orders XW-042 Croco/Cheetah Print, SNM26-006_A, and XW-042 Croco (1st Order), requesting confirmation of EXW, ETD, and ETA dates. (XW-042) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 22:00] DELAY: Forwarder holiday from Oct 01-07 due to National Day, waiting for SPEDITION_B contact. (China Lieferant X) -> mehrdeutig: 2 laufende Orders von LIEFERANT_X INDUSTRY CO.,LTD
- [2026-10-12 22:01] SCHEDULE: Lieferant bittet um Zusendung der Barcode-Informationen bis spätestens 15. Oktober. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: 4 laufende Orders von Lieferant C
- [2026-10-12 22:01] ORDER_CHANGE: Barcode change for Rain Jacket Crocodile (black, white, olive) cannot be applied to current bulk as it is already sticked; XW-042B will be applied to the second order instead. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-12 22:01] OTHER: Discussion regarding barcodes for style XW-042 which have already been applied to bulk production and cannot be changed. (None) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-13 12:14] SCHEDULE: Alpha hat den Zeitplan für das KUNDE_X-Polyester-Programm mitgeteilt: 50-60% Ex Factory am 20. Oktober, Rest bis 30. Oktober 2026. (Alpha) -> mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-13 12:15] SCHEDULE: Confirmed EXW dates for KUNDE_X Polystyles Alpha: 50-60% on 20th Oct ex-fty and the rest until 30th Oct. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-13 12:46] SHIPMENT: Vessel planning updated with CMA CGM FIGARO 0019, ETD 2026-10-26, ETA 2023-11-23. (Alpha) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 05:51] OTHER: Der Lieferant teilt mit, dass die Barcodes fuer XW-042 (Rain Jacket Crocodile, black/white/olive) bereits auf die Bulk-Produktion aufgebracht sind und nicht mehr auf XW-042_A geaendert werden koennen. XW-042B wird nur fuer die zweite Bestellung verwendet. (LIEFERANT_C CO.,LTD.) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 08:16] SCHEDULE: Lieferant A bittet um Schiffsplanung auf Basis eines Ex-Factory-Termins am 20.10.2026, da der Cut-off 22.10.2026 nicht eingehalten werden kann. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 08:16] SHIPMENT: Schiffsplanung laut Zia Hussain (Quellzitat aus Verlauf): Reederei CMA, Cut-off 22.10.2026, ETD 26.10.2026, ETA 23.11.2026, Schiff CMA CGM FIGARO 0019. Die Mail fragt zudem nach 40'/20'-Container fuer die CRO. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 12:22] SCHEDULE: Shipment date for newly added styles will be delayed compared to committed date and confirmed later. (Lieferant A) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-14 14:05] ORDER_CHANGE: Smilodox bestätigt die Style-Nummern je Druck: XW-042 für Crocodile Print und XW-042_A für Cheetah Print. Der Lieferant soll für jeden Druck die richtige Style-Nummer verwenden. (lieferant-c.example) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 14:14] ORDER_CHANGE: Clarification on style numbers to be used for the prints: XW-042 for Crocodile Print and XW-042_A for Cheetah Print. (None) -> mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709
- [2026-10-14 14:29] SHIPMENT: Commercial invoice updated to delete sample charges. (26071) -> mehrdeutig: PO-LIEFERANT_W-26071-DE-EA-2EXTRA, PO-LIEFERANT_W-26071-DE-EA-2
- [2026-10-16 11:02] SHIPMENT: Bill of Lading (Telex Release) issued for sea shipment of MEN'S WINDBREAKER JACKET (122 cartons, 1676.95 KGS, 8.784 CBM) from Xiamen to Hamburg. (FUJIAN LIEFERANT_H GARMENTS CO.,LTD.) -> keine Order gefunden
- [2026-10-18 12:37] SCHEDULE: Request for production status update and ex-factory confirmation for the KUNDE_X polyester program as the 20.10. ex-factory date approaches. (None) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 11:43] SCHEDULE: Ex-factory planned for tomorrow with 32-33k pcs (1 container, 53.48 CBM) as brown color is behind schedule while black is in excess. (Lieferant A Pvt Ltd) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 12:00] SAMPLE: Physical samples received and forwarded to factory to check exact costs. (Profit Cultural & Creative Group Corporation) -> mehrdeutig: PO-LIEFERANT_AK-2025-10-18-B1EF, PO-LIEFERANT_Y-WS26245, PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER, PO-KUNDE_Y-Q2-2027-LIEFERANT_Y, PO-KUNDE_Y-Q2-2027-LIEFERANT_B
- [2026-10-19 12:09] SCHEDULE: Handover of goods at Karachi must be completed by 22.10.2026 to catch the CMA vessel. (Lieferant F) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 17:15] SCHEDULE: Cut-off date for the first shipment batch of approx. 35,000 pcs (55 CBM) extended from 22nd to 23rd October on CMA vessel. (None) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-19 17:15] SCHEDULE: Remaining quantities are expected to be completed by 30th October. (None) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-22 09:28] ORDER_CHANGE: Embroidery size adjustment in physical production due to fabric behavior and stitches. (Lieferant A) -> mehrdeutig: 26 laufende Orders von Lieferant A
- [2026-10-26 08:49] ORDER_CHANGE: Cancellation of multiple styles/items (ORA-T-526, 01955, Women Longsleeve Henley, Sweatshirt Oversize, Sweatpant Oversize, FAB-001, FAB-002). (Lieferant AD) -> keine Order gefunden
- [2026-10-26 08:51] ORDER_CHANGE: Cancellation of styles FAB-001 and FAB-002. (Lieferant B) -> keine Order gefunden
- [2026-10-26 08:58] ORDER_CHANGE: Smilodox cancelled items FAB-001 and FAB-002, and the supplier inquired about their product category. (Lieferant B) -> keine Order gefunden
- [2026-10-26 11:20] SHIPMENT: Commercial invoice, packing list, bill of lading draft and CRO issued for container TXGU-410959-6. (561874_2510) -> keine Order gefunden
- [2026-10-26 12:47] SHIPMENT: Shipment of 39 cartons containing 373 pcs of knitted dyed garments (Invoice TE-26-2003-A) via air freight from Lahore, Pakistan to Hamburg, Germany. (LIEFERANT_B ENTERPRISES (PVT) LTD.) -> keine Order gefunden
- [2026-10-26 13:00] SCHEDULE: Revised plan for KUNDE_X Polyester: 1st 40ft HQ ex-mill 30.10, sailing Karachi 05.11. (Alpha) -> mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08
- [2026-10-26 14:32] SCHEDULE: Request for written confirmation of ex-factory dates and sample status for B2B orders (Sports Club, Easy Fitness, XtraFit, Peaks, Kunde Y). (None) -> keine Order gefunden
- [2026-10-27 15:39] SHIPMENT: Shipment documents for invoice SPR2026000000445 sent with 17007 pieces in 1056 boxes. (SPR2026000000445) -> mehrdeutig: PO-LIEFERANT_I-SPR2026000000438, PO-LIEFERANT_I-SPR2026000000422, PO-LIEFERANT_I-SPR2026000000409

## Info ohne PO-Bezug (Muster/Artwork/Allgemeines): bleibt im Blatt 'Ereignisse', kein Handlungsbedarf im PLM
- 388 Ereignisse

## Sendungen (Bereich Shipments)
- aktualisiert: Sendung PO-LIEFERANT_D-ALI20260821 LIEFERANT_D-ALI20260821-AIR {'status': 'in_transit', 'trackingNumber': 'K327852, K363390, K363397, K363480, K363698'}
- Mensch: PO-ALPHA-SWEAT-PROGRAM-2026-06-03: SHIPPED gemeldet, aber 2 offene Sendungen: Mensch ordnet zu

## Ergebnis Sendungen
- Sendung aktualisiert: Sendung PO-LIEFERANT_D-ALI20260821 LIEFERANT_D-ALI20260821-AIR ['notes', 'status', 'trackingNumber'] -> HTTP 200
- per REST zurueckgelesen: alle vorhanden

## Ergebnis Notizen
```
[
 {
  "title": "PO-LIEFERANT_AG-2026-06-24",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_AG-2026-03-17",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_D-ALI20260821",
  "statusSet": null,
  "statusOk": true,
  "notesAdded": 5,
  "dates": [],
  "paymentsMarkedPaid": 0,
  "dataUnchanged": true,
  "notesOk": true,
  "datesOk": true,
  "chat": 5
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
  "title": "PO-LIEFERANT_X-JM260511",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_G-MC-26SM002",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_AA-WINTER-2026-04-29",
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
  "title": "PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_X-JM260704",
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
  "unchanged": true
 },
 {
  "title": "PO-WONDERS-XW-SM260730",
  "unchanged": true
 },
 {
  "title": "PO-WONDERS-XW-SM260811",
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
  "title": "PO-LIEFERANT_AA-26WJD-108-REORDER",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_I-SPR2026000000409",
  "unchanged": true
 },
 {
  "title": "PO-WONDERS-XW-SM260513",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_V-KCCN0513",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER",
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
  "title": "PO-ALPHA-TBC-EASYFITNESS-ALPHA-ALPHAWOMEN",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_I-SPR2026000000422",
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
  "title": "PO-LIEFERANT_T-PO26005SG-W",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_B-2026-07-02-FB54",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_A-ALP-58-25",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_AH-SMI-SOHO-0526",
  "unchanged": true
 },
 {
  "title": "PO-LIEFERANT_I-SPR2026000000438",
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
  "title": "PO-LIEFERANT_AI-2026-03-18-751E",
  "unchanged": true
 },
 {
  "title": "PO-ALPHA-NOOS-STOCK-INCREASE-2025-12-16",
  "unchanged": true
 }
]
```

## PO-IDs
- geschrieben 0 (neu angelegt: 0), Fehler/Abweichungen nach Zuruecklesen: 0

## Projekte
- Projekte im PLM: 33 | Lieferanten ohne Projekt: 0 | Orders ohne Projekt: 0 | geplant: 0 neue Projekte, 0 Verknuepfungen
- nichts zu tun

## Projekt-Produkte
- Projekt-Produkte: 0 Produkte in 0 Projekten zu verknuepfen (Limit 100)
- WARNUNG Lieferant A: 1 Produkt(e) ohne Variante nicht aufgenommen
- nichts zu tun

## Status
- Vorschlaege: 1 (hoch 0, mittel 1, niedrig 0), davon automatisch zulaessig: 0 | STATUS_AUTO AN

## Zahlungen
- Orders geprueft: 80 | Aktionen: 1 (diesen Lauf 1, Rest 0) | Klaerfall-Kandidaten: 6
  - PO-LIEFERANT_AA-WINTER-2026-04-29 [Paid setzen] Paid gesetzt: LIEFERANT_AA26104 15% by shipment (Zahlungsmeldung, 4046.63)
  - KLAERFALL [Lieferant A] Plan unveraendert (echte Zahlungen). Lieferantenfe: Zahlung: Zahlungsplan pruefen: Summe der Raten 2407565.55 != Gesamtwert 2316341.30 (+91224.25)
  - KLAERFALL [Lieferant H garment company] Plan unveraendert (echte Zahlungen). Lieferantenfe: Zahlung: Zahlungsplan pruefen: Summe der Raten 56248.40 != Gesamtwert 55950.00 (+298.40)
  - KLAERFALL [LIEFERANT_W CO., LTD] Plan unveraendert (echte Zahlungen). Lieferantenfe: Zahlung: Zahlungsplan pruefen: Notiz der Order nennt widerspruechliche/nicht abgeglichene Bedingungen; alle 4 
  - KLAERFALL [Lieferant AJ fashion] Plan unveraendert (echte Zahlungen). Lieferantenfe: Zahlung: Zahlungsplan pruefen: alle 4 Raten mit gleicher Faelligkeit (Vorlage, nicht abgeglichen)
  - KLAERFALL [Lieferant P Co.,Ltd.] Plan unveraendert (echte Zahlungen). Lieferantenfe: Zahlung: Zahlungsplan pruefen: Summe der Raten 97386.80 != Gesamtwert 100386.80 (-3000.00); Notiz der Order ne
  - KLAERFALL [Lieferant AG] Plan unveraendert (echte Zahlungen). Lieferantenfe: Zahlung: Zahlungsplan pruefen: alle 4 Raten mit gleicher Faelligkeit (Vorlage, nicht abgeglichen)
- Backup: /home/runner/work/Dashboard-Produktion/Dashboard-Produktion/output/backup/payments_vor_2026-10-28_074557.json
- Zahlungen: Platzhalter entfernt 0, Plaene aufgebaut 0, Paid gesetzt 1, Orders ok 1, Fehler 0
- Klaerfaelle neu eingetragen: 0 (Kandidaten 6, bekannte uebersprungen)

## Gelernte Aliase (gespeichert)
- MSNU6530944 -> 6acd059e658a87e64182ca6a (Ereignis)
- SMII12 -> 6acd059e658a87e64182ca6a (Ereignis)
- AK/623/26 -> 6ace076f5f317983615c62b8 (Ereignis)
- 065-4958 -> 6ace076f5f317983615c62b8 (Ereignis)
- LIEFERANT_AA2688 -> 6ace00135f317983615abfe8 (Ereignis)
- PO26005SG-W-2 -> 6acdf6a25f31798361589ea8 (Ereignis)
- HLBU2501958 -> 6acdf6a25f31798361589ea8 (Ereignis)
- HYZ260821045 -> 6acdf6a25f31798361589ea8 (Ereignis)
- K327852 -> 6acdea04658a87e6419413c6 (Ereignis)
- K363390 -> 6acdea04658a87e6419413c6 (Ereignis)
- K363397 -> 6acdea04658a87e6419413c6 (Ereignis)
- K363480 -> 6acdea04658a87e6419413c6 (Ereignis)
- K363698 -> 6acdea04658a87e6419413c6 (Ereignis)
- LIEFERANT_D-AALI20360821 -> 6acdea04658a87e6419413c6 (Ereignis)
- DMRF261010369 -> 6acdea04658a87e6419413c6 (Ereignis)
- XMHAM26100573 -> 6acde80e658a87e64193f7ae (Ereignis)

## Alias-Konflikte (Kennung auf 2 Bestellungen, auf mehrdeutig gesetzt)
- ZIHWB260930LH137: PO-LIEFERANT_AA-WINTER-2026-04-29 <-> PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER

## Gelernte Absender-Domains
- lieferant-g.example -> 6ac5fad228e7219816cb0a16 (aktiv)
- lieferant-c.example -> 6a687a9a9d02f84f90b1aacd (aktiv)
- lieferant-i.example -> 6ac6389328e7219816f49114 (neu)
- lieferant-f.example -> 6ac5ecfd28e7219816c2b710 (neu)
- lieferant-extra.example -> 6a6716ede3361bcadbbc948a (aktiv)
- lieferant-extra.example.cn -> 6a68634a9d02f84f90af9c88 (neu)
- lieferant_v.cn -> 6a673902ebdb03340d0808d1 (neu)
- lieferant-i.example -> 6ac6389328e7219816f49114 (aktiv)
- lieferant-extra.example.cn -> 6a68634a9d02f84f90af9c88 (aktiv)
- lieferant_t.cn -> 6a685c399d02f84f90af467a (neu)
- lieferant_y.net -> 6ac5f7fc28e7219816c84d8b (neu)
- lieferant-b.example -> 6ac5f80228e7219816c84de2 (neu)
- lieferant-b.example -> 6ac5f80228e7219816c84de2 (aktiv)
- lieferant-extra.example -> 6a68634a9d02f84f90af9c88 (neu)
- lieferant_ad.cn -> 6a68571f9d02f84f90aefbed (neu)
- lieferant-extra.example -> 6a68571f9d02f84f90aefbed (neu)
- lieferant_v.cn -> 6a673902ebdb03340d0808d1 (aktiv)
- lieferant-j.example -> 6ac5fad628e7219816cb0a91 (neu)
- lieferant-d.example -> 6ac612c728e7219816e4b86b (neu)
- lieferant-d.example -> 6ac612c728e7219816e4b86b (aktiv)

## Mail-Verlauf (Thread)
- neu gelernt: 7 Verlauf-Order-Paare (gesamt 84 Verlaeufe) | ueber Verlauf zugeordnet: 10 Ereignisse | THREAD_MATCH an

## Klärfälle (PLM-Tabelle)
- Kandidaten 38, neu eingetragen 4, geloescht 8 (Rest naechster Lauf: 0), offen gesamt 65

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
- neue Techpack/Spec-Dateien seit 2026-10-28T07:46: 0 | hochgeladen 0 | schon als Datei vorhanden 0 | ohne Produkt 0 | Limit-Rest 0

## Mensch entscheidet (61)
- Sendung: PO-ALPHA-SWEAT-PROGRAM-2026-06-03: SHIPPED gemeldet, aber 2 offene Sendungen: Mensch ordnet zu
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
- Ereignis nicht zuordenbar: Die lokalen FOB-Gebühren am Abgangshafen wurden noch nicht beglichen, weshalb die Freigabe (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Container EGSU 155 511-8 wurde entladen. (mehrdeutig: PO-LIEFERANT_B-2026-06-13-3123, PO-LIEFERANT_B-2026-06-13-AA8B)
- Ereignis nicht zuordenbar: Container GAOU 642 138-0 wurde entladen. (mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Container EGHU 914 348-0 wurde entladen. (mehrdeutig: PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Container EGHU9143480 wurde durch das Hauptzollamt Hamburg überlassen (Zollanmeldung und E (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Container GAOU6421380 aus Ningbo (Versender Lieferant A, Pakistan) wurde am 12.10.2026  (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Vendor sent barcode stickers layout and carton marking for style XW-042 for review and con (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Container HMMU6963097 arrived in Hamburg via vessel ONE RELIABILITY V#0020W, delivery orde (mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd)
- Ereignis nicht zuordenbar: Inbound vessel arrived with container HMMU6963097 containing knitted socks from Karachi, P (mehrdeutig: 7 laufende Orders von Lieferant B Enterprises (Pvt) Ltd)
- Ereignis nicht zuordenbar: Inquiry regarding production and logistics status for orders XW-042 Croco/Cheetah Print, S (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Forwarder holiday from Oct 01-07 due to National Day, waiting for SPEDITION_B contact. (mehrdeutig: 2 laufende Orders von LIEFERANT_X INDUSTRY CO.,LTD)
- Ereignis nicht zuordenbar: Lieferant bittet um Zusendung der Barcode-Informationen bis spätestens 15. Oktober. (mehrdeutig: 4 laufende Orders von Lieferant C)
- Ereignis nicht zuordenbar: Barcode change for Rain Jacket Crocodile (black, white, olive) cannot be applied to curren (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Discussion regarding barcodes for style XW-042 which have already been applied to bulk pro (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Alpha hat den Zeitplan für das KUNDE_X-Polyester-Programm mitgeteilt: 50-60% Ex Factory am 20 (mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Confirmed EXW dates for KUNDE_X Polystyles Alpha: 50-60% on 20th Oct ex-fty and the rest unti (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Vessel planning updated with CMA CGM FIGARO 0019, ETD 2026-10-26, ETA 2023-11-23. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Der Lieferant teilt mit, dass die Barcodes fuer XW-042 (Rain Jacket Crocodile, black/white (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Lieferant A bittet um Schiffsplanung auf Basis eines Ex-Factory-Termins am 20.10.2026,  (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Schiffsplanung laut Zia Hussain (Quellzitat aus Verlauf): Reederei CMA, Cut-off 22.10.2026 (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Shipment date for newly added styles will be delayed compared to committed date and confir (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Smilodox bestätigt die Style-Nummern je Druck: XW-042 für Crocodile Print und XW-042_A für (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Clarification on style numbers to be used for the prints: XW-042 for Crocodile Print and X (mehrdeutig: PO-WONDERS-XW-SM260730, PO-WONDERS-XW042-20260709)
- Ereignis nicht zuordenbar: Commercial invoice updated to delete sample charges. (mehrdeutig: PO-LIEFERANT_W-26071-DE-EA-2EXTRA, PO-LIEFERANT_W-26071-DE-EA-2)
- Ereignis nicht zuordenbar: Bill of Lading (Telex Release) issued for sea shipment of MEN'S WINDBREAKER JACKET (122 ca (keine Order gefunden)
- Ereignis nicht zuordenbar: Request for production status update and ex-factory confirmation for the KUNDE_X polyester pr (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Ex-factory planned for tomorrow with 32-33k pcs (1 container, 53.48 CBM) as brown color is (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Physical samples received and forwarded to factory to check exact costs. (mehrdeutig: PO-LIEFERANT_AK-2025-10-18-B1EF, PO-LIEFERANT_Y-WS26245, PO-LIEFERANT_Y-WS26175-KUNDE_X-SNEAKER, PO-KUNDE_Y-Q2-2027-LIEFERANT_Y, PO-KUNDE_Y-Q2-2027-LIEFERANT_B)
- Ereignis nicht zuordenbar: Handover of goods at Karachi must be completed by 22.10.2026 to catch the CMA vessel. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Cut-off date for the first shipment batch of approx. 35,000 pcs (55 CBM) extended from 22n (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Remaining quantities are expected to be completed by 30th October. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Embroidery size adjustment in physical production due to fabric behavior and stitches. (mehrdeutig: 26 laufende Orders von Lieferant A)
- Ereignis nicht zuordenbar: Cancellation of multiple styles/items (ORA-T-526, 01955, Women Longsleeve Henley, Sweatshi (keine Order gefunden)
- Ereignis nicht zuordenbar: Cancellation of styles FAB-001 and FAB-002. (keine Order gefunden)
- Ereignis nicht zuordenbar: Smilodox cancelled items FAB-001 and FAB-002, and the supplier inquired about their produc (keine Order gefunden)
- Ereignis nicht zuordenbar: Commercial invoice, packing list, bill of lading draft and CRO issued for container TXGU-4 (keine Order gefunden)
- Ereignis nicht zuordenbar: Shipment of 39 cartons containing 373 pcs of knitted dyed garments (Invoice TE-26-2003-A)  (keine Order gefunden)
- Ereignis nicht zuordenbar: Revised plan for KUNDE_X Polyester: 1st 40ft HQ ex-mill 30.10, sailing Karachi 05.11. (mehrdeutig: PO-LIEFERANT_B-2026-06-03-D601, PO-ALPHA-PAK-KUNDE_X-LAGER-2026-05-11, PO-ALPHA-PAK-KUNDE_X-CH-2026-05-11, PO-ALPHA-PAK-KUNDE_X-DE-2026-05-08)
- Ereignis nicht zuordenbar: Request for written confirmation of ex-factory dates and sample status for B2B orders (Spo (keine Order gefunden)
- Ereignis nicht zuordenbar: Shipment documents for invoice SPR2026000000445 sent with 17007 pieces in 1056 boxes. (mehrdeutig: PO-LIEFERANT_I-SPR2026000000438, PO-LIEFERANT_I-SPR2026000000422, PO-LIEFERANT_I-SPR2026000000409)
