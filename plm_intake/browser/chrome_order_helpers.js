/**
 * ===================================================================================================================
 * START HIER - ANLEITUNG FUER JEDEN CHAT, DER DIESE DATEI BEKOMMT (Projekt: Dashboard Produktion, Lifecycle-PLM)
 * ===================================================================================================================
 * AUFGABE: Bestellungen (POs) der Lieferanten aus den Mails von kontakt@firma.example ins Lifecycle-PLM migrieren.
 * Der Nutzer (Omar) sagt dir keinen Lieferanten: du findest den naechsten SELBST (siehe Schritt 2) und arbeitest dann selbststaendig.
 * Er kontrolliert nur nachtraeglich. Kurze, einfache Berichte (Deutsch): was angelegt, was uebersprungen, was er entscheiden muss.
 *
 * SCHRITT 0 - PARALLELE CHATS (WICHTIG): Mehrere Chats migrieren gleichzeitig ins selbe PLM. Daten NIE doppelt anlegen.
 *   - Lies output/MIGRATION_STATE.md GANZ (was angelegt ist, was "IN ARBEIT" ist, bekannte Fallen). Lies sie direkt VOR jedem Anlegen NEU.
 *   - Bevor du einen Lieferanten anfaengst: Zeile "IN ARBEIT: <Lieferant> (<Datum>, <Chat>)" in MIGRATION_STATE.md eintragen.
 *     Steht bei einem Lieferanten schon "IN ARBEIT", nimm einen anderen (oder frag Omar).
 *   - Direkt vor jedem __createOrder per REST pruefen (plm_client.call("GET","orders") in /path/to/project Produktion, Python),
 *     ob Titel/Lieferant/PO-Nr. schon existieren. Existiert sie: nicht neu anlegen.
 *   - SOFORT nach jedem Schreiben Titel, ID und Werte in MIGRATION_STATE.md eintragen (nicht erst am Ende). Am Ende die IN-ARBEIT-Zeile durch das Ergebnis ersetzen.
 *   - POs anderer Chats nur aendern, wenn du es begruenden kannst; vorher mit __fetchOrder sichern.
 *
 * SCHRITT 1 - TECHNIK (so wird geschrieben; andere Wege funktionieren NICHT):
 *   - REST kann Bestellungen mit Positionen nicht speichern (500). Der Lifecycle-MCP lehnt Schreibzugriffe ab. Funktioniert: App-GraphQL im Chrome-Tab.
 *   - Chrome-Tab (Claude in Chrome) auf https://app.lifecycleplm.com oeffnen (Omar ist eingeloggt). Den Code UNTEN in dieser Datei (ab "(function () {")
 *     einmal per javascript_tool ausfuehren; nach jedem Neuladen des Tabs erneut. Er definiert window.__createOrder, __fetchOrder, __updOrder.
 *   - Lesen: Google-Drive-Connector (Ordner "PLM-Mails", id REPLACE_WITH_GOOGLE_ID: mails_*.txt, Mail-Ordner mit mail.txt, Ordner "Anhaenge",
 *     Sheet "PLM-Mails Protokoll"; search_files mit fullText, read_file_content; grosse Dateien per Python/jq auswerten). PLM-Daten lesen: REST per
 *     plm_client.call (GET orders/vendors/products) oder query_database. Auftragsregister: output/review/Auftragsregister.xlsx (24 Bestellungen, 2,72 Mio USD).
 *
 * .xls-ANHAENGE (alte Excel-Dateien): read_file_content kann sie nicht lesen. Loesung: download_file_content (speichert grosse Dateien als JSON-Datei
 *   mit base64 in "content"), in einem eigenen leeren Ordner dekodieren und mit output/review/xls_dump.py auswerten:
 *   python3 -I output/review/xls_dump.py <datei.xls> [max_zeilen]   (kein xlrd/LibreOffice noetig; gibt alle Blaetter/Zellen aus).
 *
 * SCHRITT 2 - NAECHSTEN LIEFERANTEN FINDEN: Auftragsregister.xlsx (Spalte "PO im PLM") + MIGRATION_STATE.md abgleichen. Nimm einen Lieferanten, dessen
 *   Bestellung weder fertig noch "IN ARBEIT" ist; zuerst Status "In Produktion"/"Unterwegs", dann "Neue Order", zuletzt "Abgeschlossen".
 *   Suche seine PI/PO/Packliste/Rechnung in den Mails (fullText: Name, PO-/PI-Nr., Stylenummern). Findest du keine verwertbaren Daten: im State vermerken
 *   und den naechsten nehmen. Lies PI/PO-Excel und Packlisten, nicht nur den Mailtext.
 *
 * SCHRITT 3 - VOR DEM ANLEGEN VOLLSTAENDIGKEIT PRUEFEN: Lieferant, PO-/PI-Nr., Datum, Styles, Farben, Groessen, Mengen, Stueckpreise, Zahlungsbedingungen,
 *   Termine (ETD/EXW/ETA). Alle Zeilen- und Gesamtsummen nachrechnen und mit dem Register vergleichen. Bei Widerspruechen (PO vs. Rechnung vs. Register)
 *   nichts raten: Teillieferungen von der Gesamtbestellung trennen und Omar fragen. Die neueste Fassung (PI/Rechnung) schlaegt Entwuerfe. Fehlende Angaben
 *   nicht erfinden: 0 bzw. "ONE SIZE" als Platzhalter und im Notes-Feld unter "Offen" vermerken. Vendor-ID aus GET vendors; Produkt per query_database
 *   (products, SKU/Name) suchen: existiert es, item.product = Produkt-ID setzen, sonst ohne Link.
 *
 * SCHRITT 4 - ANLEGEN, DANACH PRUEFEN: __createOrder (Format unten). PO-Nummer, exFactoryExpectedDate, etdEstimatedDate in die dafuer vorgesehenen Felder;
 *   Quelle, PI-Nr., Incoterm, offene Punkte ins Notes-Feld. Danach per REST zurücklesen und gegen die Quelle pruefen (Positionen, Varianten, Menge je
 *   Groesse/Farbe, Preise, Gesamtwert, Zahlungen, Lieferant, keine Dubletten) und das Ergebnis nennen. REST-Liste /orders zeigt KEIN notes-Feld: Notes nur per __fetchOrder.
 *
 * REGELN: Bankdaten NIE ins PLM. Nichts loeschen (Testobjekte ZZ-TEST-* loescht Omar). Keine Mails senden/veraendern. Produktlinks bei bestehenden POs
 *   (Lieferant U, LIEFERANT_X, Bridge, Lieferant H) vor jedem Update gegen output/backup/orders_before_2026-10-07.json pruefen (product/variantId muessen erhalten bleiben).
 *   Teillieferungen (Rechnung kleiner als PO) in die Notes der Gesamt-PO schreiben, PO-Mengen nicht verkleinern, ausser Omar entscheidet es.
 *
 * ===================================================================================================================
 * FUNKTIONEN (Code unten)
 * ===================================================================================================================
 *   window.__createOrder({...})  -> legt eine neue PO an
 *   window.__fetchOrder(id)      -> liest eine PO (Notes, Termine, Positionen inkl. Produktlink, Zahlungen)
 *   window.__updOrder(id, patch) -> aendert nur die Felder in patch; Positionen/Zahlungen/Produktlinks bleiben erhalten
 *
 * Beispiel createOrder:
 *   await window.__createOrder({
 *     title:'PO-XW042-20260709', manufacturer:'<vendorId>', currency:'USD',
 *     poNumber:'XW042-20260709', useCustomPoNumber:true,
 *     exFactoryExpectedDate:'2026-10-20T00:00:00.000Z', etdEstimatedDate:'2026-10-15T00:00:00.000Z',   // Datum als ISO-STRING
 *     notes:'Quelle: ...',
 *     items:[{name:'XW-042 Rain Jacket', product:'<produktId optional>', variants:[{name:'Black', amounts:[{key:'S',quantity:400,price:14,cost:5600}]}]}],
 *     payments:[{name:'30% Deposit',status:'Unpaid',amount:21000,dueDate:Date.UTC(2026,6,10),terms:'30% deposit'}],  // dueDate = ms (Zahl)
 *     totalCost:70000, totalNumberOfPieces:5000, assignees:[]
 *   });
 * Pflicht in OrderInput: title, items, payments, assignees. totalCost/totalNumberOfPieces MUESSEN selbst mitgegeben werden.
 * cost je Menge = quantity*price (auf 2 Stellen gerundet). Groessen-Key als String ('S','M','2XL'; 'ONE SIZE' als Platzhalter). Payment-Status 'Unpaid'|'Paid'.
 */
(function () {
  const N = v => ({ kind: 'Name', value: v });
  const F = (n, sub, args) => ({ kind: 'Field', name: N(n), ...(args ? { arguments: args } : {}), ...(sub ? { selectionSet: { kind: 'SelectionSet', selections: sub } } : {}) });
  const Var = n => ({ kind: 'Variable', name: N(n) });
  const NN = t => ({ kind: 'NonNullType', type: { kind: 'NamedType', name: N(t) } });
  const sel = [F('id'), F('title'), F('orderNumber'), F('totalCost'), F('totalNumberOfPieces')];

  const createDoc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', name: N('createOrderFn'),
    variableDefinitions: [{ kind: 'VariableDefinition', variable: Var('data'), type: NN('OrderInput') }],
    selectionSet: { kind: 'SelectionSet', selections: [{ kind: 'Field', name: N('createOrder'),
      arguments: [{ kind: 'Argument', name: N('orderInput'), value: Var('data') }],
      selectionSet: { kind: 'SelectionSet', selections: sel } }] } }] };

  const updDoc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', name: N('UpdateOrder'),
    variableDefinitions: [{ kind: 'VariableDefinition', variable: Var('id'), type: NN('String') }, { kind: 'VariableDefinition', variable: Var('data'), type: NN('OrderInput') }],
    selectionSet: { kind: 'SelectionSet', selections: [{ kind: 'Field', name: N('updateOrder'),
      arguments: [{ kind: 'Argument', name: N('id'), value: Var('id') }, { kind: 'Argument', name: N('orderInput'), value: Var('data') }],
      selectionSet: { kind: 'SelectionSet', selections: [F('id'), F('title'), F('poNumber'), F('exFactoryExpectedDate'), F('etdEstimatedDate'), F('totalCost'), F('totalNumberOfPieces')] } }] } }] };

  const full = [F('id'), F('title'), F('notes'), F('poNumber'), F('useCustomPoNumber'), F('exFactoryExpectedDate'), F('etdEstimatedDate'), F('currency'),
    F('totalCost'), F('totalNumberOfPieces'), F('manufacturer', [F('id')]), F('status', [F('id'), F('status'), F('color'), F('order')]),
    F('items', [F('name'), F('product', [F('id')]), F('variants', [F('name'), F('variantId'), F('amounts', [F('key'), F('quantity'), F('price'), F('cost')])])]),
    F('payments', [F('name'), F('status'), F('amount'), F('dueDate'), F('terms')])];
  const getDoc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', name: N('q'),
    variableDefinitions: [{ kind: 'VariableDefinition', variable: Var('id'), type: NN('String') }],
    selectionSet: { kind: 'SelectionSet', selections: [F('getOrderById', full, [{ kind: 'Argument', name: N('id'), value: Var('id') }])] } }] };

  const client = () => window.__APOLLO_CLIENT__;
  const clean = a => JSON.parse(JSON.stringify(a, (k, v) => (k === '__typename' ? undefined : v)));

  window.__createOrder = async data => {
    const r = await client().mutate({ mutation: createDoc, variables: { data }, errorPolicy: 'all' });
    return { errors: (r.errors || []).map(e => e.message.slice(0, 300)), data: r.data };
  };
  // Kommentar in "Chats & Updates" der Bestellung (so sendet ihn auch die Oberflaeche: createNotificationComment, notificationType ORDER). Nur additiv.
  window.__postOrderComment = async (orderId, text) => {
    const V = Var;
    const doc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: [{ kind: 'VariableDefinition', variable: V('i'), type: NN('NotificationInput') }],
      selectionSet: { kind: 'SelectionSet', selections: [F('createNotificationComment', [F('_id'), F('action')], [{ kind: 'Argument', name: N('notificationInput'), value: V('i') }])] } }] };
    const r = await client().mutate({ mutation: doc, variables: { i: { notificationType: 'ORDER', referenceId: orderId, content: String(text).slice(0, 4000), taggedUsers: [] } }, errorPolicy: 'all' });
    const ok = !!(r.data && r.data.createNotificationComment && r.data.createNotificationComment._id);
    return { ok, err: (r.errors || []).map(e => e.message.slice(0, 200)).join('; ') };
  };
  window.__fetchOrder = async id => {
    const r = await client().query({ query: getDoc, variables: { id }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
    return { d: r.data && r.data.getOrderById, e: (r.errors || []).map(e => e.message.slice(0, 200)) };
  };
  window.__updOrder = async (id, patch) => {
    const { d, e } = await window.__fetchOrder(id);
    if (!d) return { err: e };
    const data = { title: d.title, manufacturer: d.manufacturer.id, currency: d.currency, totalCost: d.totalCost, totalNumberOfPieces: d.totalNumberOfPieces,
      notes: d.notes, poNumber: d.poNumber, useCustomPoNumber: d.useCustomPoNumber, exFactoryExpectedDate: d.exFactoryExpectedDate, etdEstimatedDate: d.etdEstimatedDate,
      items: clean(d.items).map(it => ({ ...it, product: it.product ? it.product.id : undefined })), payments: clean(d.payments), assignees: [], ...(d.status ? { status: clean(d.status) } : {}), ...patch };
    Object.keys(data).forEach(k => { if (data[k] === null || data[k] === undefined) delete data[k]; });
    const r = await client().mutate({ mutation: updDoc, variables: { id, data }, errorPolicy: 'all' });
    return { err: (r.errors || []).map(e => e.message.slice(0, 300)), data: r.data };
  };
  return 'Helfer geladen: __createOrder, __fetchOrder, __updOrder';
})();
