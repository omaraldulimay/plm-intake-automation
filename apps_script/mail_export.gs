/**
 * PLM-Mail-Export v2 (Google Apps Script) - laeuft im Konto von kontakt@firma.example
 *
 * Was es tut: holt relevante Geschaeftsmails (POs, PIs, Rechnungen, Excel/PDF-Anhaenge) und legt sie in Drive ab:
 *   PLM-Mails/mails_<Zeitstempel>_<Nr>.txt   Mails eines Laufs gesammelt (Kopf + Text), Trenner "===== MAIL ====="
 *   PLM-Mails/Anhaenge/<Datum>_<MessageId>_<Dateiname>   Anhaenge (Excel, PDF, CSV, Word)
 *   PLM-Mails/PLM-Mails Protokoll   Sheet: Blatt "Exportiert" (eine Zeile pro Mail), Blatt "Threads" (Fortschritt)
 * Es LIEST nur Gmail: es aendert, loescht, sendet oder markiert KEINE Mails.
 *
 * Schnell, weil: (1) Gmail filtert serverseitig (nur passende Threads kommen beim Skript an),
 * (2) pro Lauf werden wenige Textdateien geschrieben statt eine Datei pro Mail, (3) Sheet-Zeilen werden gesammelt geschrieben.
 * Relevanz = Thread hat Excel/PDF/CSV/Word-Anhang ODER eines der Stichworte. Alle Nachrichten eines passenden Threads
 * (ab START_DATE) werden exportiert, damit der Zusammenhang erhalten bleibt.
 *
 * Reihenfolge: erst NEUE Mails (seit letztem Lauf), danach ALTE Mails rueckwaerts (neu -> alt) ab START_DATE.
 * Einrichtung: siehe unten "SETUP".
 */

var CONFIG = {
  START_DATE: '2025/10/01',          // ab diesem Datum (Gmail-Format JJJJ/MM/TT)
  FOLDER_NAME: 'PLM-Mails',
  ATTACH_FOLDER_NAME: 'Anhaenge',
  LOG_NAME: 'PLM-Mails Protokoll',
  MAX_RUNTIME_MS: 4.5 * 60 * 1000,    // vor dem Apps-Script-Limit sauber stoppen, Fortschritt bleibt gespeichert
  THREADS_PER_PAGE: 50,
  FLUSH_EVERY: 20,                    // Mails, nach denen gesammelt in Sheet/Textdatei geschrieben wird
  ATTACHMENT_EXT: /\.(xlsx|xls|xlsm|csv|ods|pdf|docx?|odt)$/i,
  MAX_BODY_CHARS: 60000,
  MAX_ATTACHMENT_BYTES: 25 * 1024 * 1024,
  // Gmail-Suchbegriffe (ODER-verknuepft): Anhang-Typen und Stichworte
  FILE_TYPES: ['xlsx', 'xls', 'xlsm', 'csv', 'ods', 'pdf', 'doc', 'docx', 'odt'],
  KEYWORDS: ['"purchase order"', '"packing list"', '"P.O"', 'PO', 'PI', 'proforma', 'invoice', 'rechnung', 'order',
             'bestellung', 'shipment', 'sendung', 'container', 'booking', 'sample', 'muster', 'payment', 'zahlung',
             'deposit', 'ETD', 'ETA', 'delivery', 'lieferung', 'production', 'produktion', 'price', 'preis',
             // ergaenzt 15.10. nach gapCheck (relevante Mails ohne diese Woerter fielen durch: "Produktionsstand", "carton mark", "UPC sticker confirmation", "Lieferant Extra modifications")
             'samples', 'orders', 'invoices', 'confirmation', 'bestaetigung', 'barcode', 'UPC', 'EAN', 'sticker', 'etikett', 'carton', 'karton',
             'packaging', 'verpackung', 'inspection', 'freight', 'fracht', 'tracking', 'modifications', 'produktionsstand', 'fitting', 'approval', 'freigabe'],
  // Jede Mail dieser Lieferanten-/Spediteur-Domains zaehlt als relevant, auch ohne Anhang und Stichwort (Kontaktdomains der PLM-Lieferanten + haeufige Absender mit Anhaengen, Stand 15.10.2026).
  // Neue Lieferanten: Domain hier ergaenzen (Lieferanten mit Gmail-Adresse erfasst nur die Stichwortsuche).
  VENDOR_DOMAINS: ['lieferant-a.example', 'lieferant-g.example', 'lieferant_ad.cn', 'lieferant-c.example', 'lieferant-extra.example.cn', 'lieferant-b.example', 'lieferant_y.net', 'lieferant-extra.example', 'lieferant_v.cn',
                   'spedition_b.de', 'lieferant_u.cn', 'lieferant-d.example', 'lieferant-i.example', 'lieferant-extra.example', 'lieferant-j.example', 'lieferant_w.cn', 'lieferant-extra.example', 'lieferant_h.cn',
                   'lieferant_t.cn', 'lieferant-extra.example', 'lieferant-extra.example', 'lieferant_ag.net', 'lieferant_ag.com', 'lieferant-extra.example', 'lieferant-extra.example', 'lieferant-extra.example',
                   'lieferant_ab.com', 'lieferant-f.example', 'lieferant-extra.example.tr', 'lieferant-extra.example', 'lieferant-extra.example.cn', 'lieferant-extra.example', 'lieferant-extra.example', 'lieferant-extra.example',
                   'lieferant-extra.example', 'lieferant-extra.example', 'medico.eu', 'lieferant-extra.example', 'lieferant-extra.example', 'lieferant-extra.example', 'lieferant-e.example', 'lieferant-extra.example.tr',
                   'lieferant-extra.example', 'lieferant-extra.example', 'lieferant-extra.example', 'lieferant_ae.com', 'lieferant-extra.example.tr', 'lieferant-extra.example']
};

/** Gmail-Suche: Basisfilter + Relevanz (Anhang-Typ ODER Stichwort), alles serverseitig. */
function buildQuery_() {
  var files = CONFIG.FILE_TYPES.map(function (e) { return 'filename:' + e; });
  return 'after:' + CONFIG.START_DATE +
    ' -category:promotions -category:social -category:forums' +
    ' -from:(noreply OR no-reply OR newsletter OR mailer-daemon)' +
    ' -in:spam -in:trash' +
    ' {' + files.concat(CONFIG.KEYWORDS).concat(['from:(' + CONFIG.VENDOR_DOMAINS.join(' OR ') + ')']).join(' ') + '}';
}

/**
 * Hauptfunktion (Trigger). Reihenfolge je Lauf:
 *  1. NEUE Mails: alles seit dem letzten erfolgreichen Lauf (mit 2 Tagen Ueberlappung) - kommt immer zuerst.
 *  2. ALTE Mails: Rueckwaerts-Nachfuellen ab START_DATE bis zum Zeitlimit; der Fortschritt (backfillBefore) wird
 *     nach jedem Thread gespeichert, der naechste Lauf macht dort weiter.
 */
function exportRelevantMails() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) { Logger.log('Anderer Lauf aktiv, uebersprungen'); return; }   // keine parallelen Laeufe (Dubletten)
  try {
    runExport_();
  } finally {
    lock.releaseLock();
  }
}

function runExport_() {
  var start = Date.now();
  var props = PropertiesService.getScriptProperties();
  var root = getOrCreateFolder_(CONFIG.FOLDER_NAME, null);
  var ss = getOrCreateLog_(root);
  var ctx = {
    start: start,
    root: root,
    attachFolder: getOrCreateFolder_(CONFIG.ATTACH_FOLDER_NAME, root),
    sheet: ss.getSheetByName('Exportiert'),
    threadsSheet: ss.getSheetByName('Threads'),
    done: null, threadCounts: null,
    rowsBuf: [], threadsBuf: [], textBuf: [],
    added: 0, runStamp: Utilities.formatDate(new Date(start), 'UTC', 'yyyy-MM-dd_HHmmss'), fileNo: 0,
    minDate: parseDate_(CONFIG.START_DATE)
  };
  ctx.done = loadColumn_(ctx.sheet);
  ctx.threadCounts = loadThreadCounts_(ctx.threadsSheet);

  try {
    // --- Phase 1: neue Mails ---
    var lastSync = Number(props.getProperty('lastSync')) || 0;
    var newFrom = new Date((lastSync || start) - 2 * 24 * 3600 * 1000);
    var newComplete = processQuery_(buildQuery_() + ' after:' + fmt_(newFrom), ctx, null);
    if (newComplete) props.setProperty('lastSync', String(start));

    // --- Phase 2: alte Mails nachfuellen (rueckwaerts) ---
    if (props.getProperty('backfillDone') !== 'true' && Date.now() - start < CONFIG.MAX_RUNTIME_MS) {
      var before = props.getProperty('backfillBefore') || fmt_(new Date(start + 24 * 3600 * 1000));
      var complete = processQuery_(buildQuery_() + ' before:' + before, ctx, function (threadDate) {
        // Fortschritt nach jedem Thread merken (1 Tag Ueberlappung; Dubletten verhindert das Protokoll).
        var next = fmt_(new Date(threadDate.getTime() + 24 * 3600 * 1000));
        var cur = props.getProperty('backfillBefore');
        if (!cur || next < cur) props.setProperty('backfillBefore', next);
      });
      if (complete) props.setProperty('backfillDone', 'true');
    }
  } finally {
    flush_(ctx);   // auch bei Fehler/Zeitlimit: gesammelte Zeilen und Texte schreiben
  }
  Logger.log('Exportiert: ' + ctx.added + ' | Alt-Nachfuellung fertig: ' + (props.getProperty('backfillDone') === 'true'));
}

/** Verarbeitet alle Threads einer Suche, neu -> alt. true = Suche komplett durch, false = Zeitlimit. */
function processQuery_(query, ctx, onThread) {
  var offset = 0;
  while (true) {
    var threads = GmailApp.search(query, offset, CONFIG.THREADS_PER_PAGE);
    if (!threads.length) return true;
    for (var t = 0; t < threads.length; t++) {
      if (timeUp_(ctx)) return false;
      var th = threads[t];
      var tid = th.getId();
      var cnt = th.getMessageCount();
      if (ctx.threadCounts[tid] === cnt) {   // Thread unveraendert und schon fertig: ueberspringen
        if (onThread) onThread(th.getLastMessageDate());
        continue;
      }
      var msgs = th.getMessages();
      for (var m = 0; m < msgs.length; m++) {
        if (timeUp_(ctx)) return false;
        var msg = msgs[m];
        var id = msg.getId();
        if (ctx.done[id]) continue;
        if (msg.getDate() < ctx.minDate) continue;
        saveMessage_(msg, ctx);
        ctx.done[id] = true;
        ctx.added++;
        if (ctx.rowsBuf.length >= CONFIG.FLUSH_EVERY) flush_(ctx);
      }
      ctx.threadsBuf.push([tid, msgs.length]);   // Thread komplett durch
      ctx.threadCounts[tid] = msgs.length;
      if (onThread) onThread(th.getLastMessageDate());
    }
    offset += threads.length;
  }
}

function timeUp_(ctx) { return Date.now() - ctx.start >= CONFIG.MAX_RUNTIME_MS; }

/** Mail verarbeiten: Anhaenge sofort in Drive, Text und Protokollzeile in den Puffer. */
function saveMessage_(msg, ctx) {
  var d = msg.getDate();
  var tz = Session.getScriptTimeZone();
  var day = Utilities.formatDate(d, tz, 'yyyy-MM-dd');
  var names = [];
  try {
    var atts = msg.getAttachments({includeInlineImages: false, includeAttachments: true});
    for (var i = 0; i < atts.length; i++) {
      var name = atts[i].getName();
      if (!CONFIG.ATTACHMENT_EXT.test(name)) continue;
      var blob = atts[i].copyBlob();
      if (blob.getBytes().length > CONFIG.MAX_ATTACHMENT_BYTES) { names.push(name + ' [uebersprungen: zu gross]'); continue; }
      var fname = day + '_' + msg.getId() + '_' + safe_(name);
      ctx.attachFolder.createFile(blob.setName(fname));
      names.push(fname);
    }
    ctx.attFails = 0;
  } catch (e) {
    // z.B. "Limit Exceeded: Email Total Attachments Size": Mail trotzdem mit Text sichern, Fehler vermerken, nicht blockieren.
    // Bei mehreren Fehlern in Folge ist es eher ein Tageslimit: Lauf abbrechen, damit nichts ohne Anhaenge als erledigt gilt.
    ctx.attFails = (ctx.attFails || 0) + 1;
    if (ctx.attFails >= 3) throw e;
    names.push('[Anhaenge nicht lesbar: ' + String(e.message || e).slice(0, 80) + ']');
  }
  var body = (msg.getPlainBody() || '').slice(0, CONFIG.MAX_BODY_CHARS);
  ctx.textBuf.push(
    '===== MAIL =====\n' +
    'Message-ID: ' + msg.getId() + '\n' +
    'Thread-ID: ' + msg.getThread().getId() + '\n' +
    'Datum: ' + Utilities.formatDate(d, tz, 'yyyy-MM-dd HH:mm') + '\n' +
    'Von: ' + msg.getFrom() + '\n' +
    'An: ' + msg.getTo() + '\n' +
    'Cc: ' + msg.getCc() + '\n' +
    'Betreff: ' + msg.getSubject() + '\n' +
    'Anhaenge: ' + (names.length ? names.join(' | ') : '-') + '\n' +
    '----- TEXT -----\n' + body + '\n');
  ctx.rowsBuf.push([msg.getId(), Utilities.formatDate(d, tz, 'yyyy-MM-dd HH:mm'), msg.getFrom(), msg.getSubject(),
                    names.length, names.join(' | '), 'mails_' + ctx.runStamp + '_' + (ctx.fileNo + 1) + '.txt']);
}

/** Gesammelt schreiben: erst die Textdatei, dann Protokollzeilen und Thread-Fortschritt (im Protokoll steht nur, was gespeichert ist). */
function flush_(ctx) {
  if (ctx.textBuf.length) {
    ctx.fileNo++;
    ctx.root.createFile('mails_' + ctx.runStamp + '_' + ctx.fileNo + '.txt', ctx.textBuf.join('\n'), MimeType.PLAIN_TEXT);
    ctx.textBuf = [];
  }
  appendRows_(ctx.sheet, ctx.rowsBuf);
  ctx.rowsBuf = [];
  appendRows_(ctx.threadsSheet, ctx.threadsBuf);
  ctx.threadsBuf = [];
}

function appendRows_(sheet, rows) {
  if (!rows.length) return;
  var first = sheet.getLastRow() + 1;
  // Ein neues Blatt hat nur 1000 Zeilen; getRange ausserhalb davon wirft "coordinates outside the dimensions of the sheet".
  var missing = first + rows.length - 1 - sheet.getMaxRows();
  if (missing > 0) sheet.insertRowsAfter(sheet.getMaxRows(), Math.max(missing, 1000));
  sheet.getRange(first, 1, rows.length, rows[0].length).setValues(rows);
}

function fmt_(d) { return Utilities.formatDate(d, 'UTC', 'yyyy/MM/dd'); }
function safe_(s) { return String(s || '').replace(/[\\\/:*?"<>|\r\n\t]+/g, ' ').replace(/\s+/g, ' ').trim(); }
function parseDate_(s) { var p = s.split('/'); return new Date(+p[0], +p[1] - 1, +p[2]); }

function getOrCreateFolder_(name, parent) {
  var it = parent ? parent.getFoldersByName(name) : DriveApp.getFoldersByName(name);
  if (it.hasNext()) return it.next();
  return parent ? parent.createFolder(name) : DriveApp.createFolder(name);
}

function getOrCreateLog_(folder) {
  var files = folder.getFilesByName(CONFIG.LOG_NAME);
  if (files.hasNext()) {
    var existing = SpreadsheetApp.open(files.next());
    if (!existing.getSheetByName('Threads')) existing.insertSheet('Threads').appendRow(['Thread-ID', 'Nachrichten verarbeitet']);
    return existing;
  }
  var ss = SpreadsheetApp.create(CONFIG.LOG_NAME);
  DriveApp.getFileById(ss.getId()).moveTo(folder);
  var sh = ss.getSheets()[0];
  sh.setName('Exportiert');
  sh.appendRow(['Message-ID', 'Datum', 'Von', 'Betreff', 'Anzahl Anhaenge', 'Anhaenge', 'Textdatei']);
  ss.insertSheet('Threads').appendRow(['Thread-ID', 'Nachrichten verarbeitet']);
  return ss;
}

function loadColumn_(sh) {
  var map = {};
  var last = sh.getLastRow();
  if (last < 2) return map;
  var ids = sh.getRange(2, 1, last - 1, 1).getValues();
  for (var i = 0; i < ids.length; i++) map[ids[i][0]] = true;
  return map;
}

function loadThreadCounts_(sh) {
  var map = {};
  var last = sh.getLastRow();
  if (last < 2) return map;
  var rows = sh.getRange(2, 1, last - 1, 2).getValues();
  for (var i = 0; i < rows.length; i++) map[rows[i][0]] = rows[i][1];   // spaetere Zeilen ueberschreiben fruehere
  return map;
}

/** Zustand pruefen (nur lesen, aendert nichts): Fortschritt, Protokoll-Umfang und wie viele passende Threads Gmail insgesamt hat. Ergebnis: Ausfuehrungsprotokoll. */
function status() {
  var props = PropertiesService.getScriptProperties();
  var ss = getOrCreateLog_(getOrCreateFolder_(CONFIG.FOLDER_NAME, null));
  var ex = ss.getSheetByName('Exportiert'), th = ss.getSheetByName('Threads');
  var rows = Math.max(ex.getLastRow() - 1, 0);
  var minD = '-', maxD = '-';
  if (rows) {
    var ds = ex.getRange(2, 2, rows, 1).getValues().map(function (r) { return r[0] instanceof Date ? Utilities.formatDate(r[0], Session.getScriptTimeZone(), 'yyyy-MM-dd') : String(r[0]).slice(0, 10); }).sort();   // Sheets wandelt manche Datumstexte in Datumswerte um
    minD = ds[0]; maxD = ds[ds.length - 1];
  }
  var doneThreads = Object.keys(loadThreadCounts_(th)).length;
  var start = Date.now(), total = 0, offset = 0, complete = true;
  while (true) {
    if (Date.now() - start > 4 * 60 * 1000) { complete = false; break; }
    var n = GmailApp.search(buildQuery_(), offset, 500).length;
    total += n; offset += n;
    if (n < 500) break;
  }
  Logger.log('Protokoll: ' + rows + ' Mails, Datum ' + minD + ' bis ' + maxD);
  Logger.log('Threads im Protokoll: ' + doneThreads + ' | Threads in Gmail (passende Suche seit ' + CONFIG.START_DATE + '): ' + total + (complete ? '' : '+ (Zeitlimit, Zahl unvollstaendig)'));
  Logger.log('Fehlende Threads (ca.): ' + (complete ? Math.max(total - doneThreads, 0) : '?'));
  Logger.log('Nachfuellung: backfillDone=' + props.getProperty('backfillDone') + ', backfillBefore=' + props.getProperty('backfillBefore') + ', lastSync=' + (props.getProperty('lastSync') ? new Date(Number(props.getProperty('lastSync'))) : '-'));
}

/** Nachfuellung noch einmal anstossen (einmal ausfuehren, nachdem Stichwoerter/Domains in CONFIG ergaenzt wurden): die Suche laeuft rueckwaerts neu ab heute bis START_DATE.
 *  Bekannte Threads/Mails werden uebersprungen (Protokoll), nur bisher nicht erfasste kommen dazu. Ausloeser: normaler Trigger exportRelevantMails. Aendert sonst nichts. */
function resetBackfill() {
  var props = PropertiesService.getScriptProperties();
  props.setProperty('backfillDone', 'false');
  props.deleteProperty('backfillBefore');
  Logger.log('Nachfuellung zurueckgesetzt: der naechste Lauf von exportRelevantMails sucht rueckwaerts neu bis ' + CONFIG.START_DATE + ' (mehrere Laeufe, bis backfillDone wieder true ist; pruefen mit status()).');
}

/** Luecken-Check (nur lesen, aendert nichts): welche Threads der letzten DAYS Tage hat die Relevanz-Suche NICHT erfasst? Listet bis zu 40 davon mit Absender und Betreff im Ausfuehrungsprotokoll.
 *  So sieht man, ob dem Export relevante Mails ohne Anhang und ohne Stichwort entgehen. Aufruf: gapCheck() (Standard 30 Tage) oder gapCheck(60). */
function gapCheck(days) {
  var d = Number(days) || 30, t0 = Date.now();
  var from = fmt_(new Date(Date.now() - d * 24 * 3600 * 1000));
  var base = 'after:' + from + ' -category:promotions -category:social -category:forums -from:(noreply OR no-reply OR newsletter OR mailer-daemon) -in:spam -in:trash';
  var relevant = {}, offset = 0, n;
  do { var th = GmailApp.search(buildQuery_() + ' after:' + from, offset, 200); th.forEach(function (t) { relevant[t.getId()] = true; }); n = th.length; offset += n; } while (n === 200 && Date.now() - t0 < 5 * 60 * 1000);
  var all = 0, miss = [], total = 0;
  offset = 0;
  do {
    var ts = GmailApp.search(base, offset, 200);
    ts.forEach(function (t) { total++; if (!relevant[t.getId()]) { all++; if (miss.length < 40) { var m = t.getMessages()[0]; miss.push(String(m.getDate()).slice(4, 21) + ' | ' + String(m.getFrom()).slice(0, 40) + ' | ' + String(m.getSubject()).slice(0, 70)); } } });
    n = ts.length; offset += n;
  } while (n === 200 && Date.now() - t0 < 5 * 60 * 1000);
  Logger.log('Letzte ' + d + ' Tage: Threads gesamt ' + total + ', von der Relevanz-Suche erfasst ' + Object.keys(relevant).length + ', NICHT erfasst ' + all);
  Logger.log('Beispiele nicht erfasster Threads (max. 40):\n' + miss.join('\n'));
}

/* ===================== SETUP (einmalig, durch Kollege) =====================
 * 1. script.google.com -> bestehendes Projekt oeffnen -> den ganzen alten Code durch diesen ersetzen -> Speichern.
 * 2. Funktion "exportRelevantMails" waehlen und auf "Ausfuehren" klicken (Zugriff wurde schon erlaubt).
 * 3. Funktion "installTrigger" einmal ausfuehren (stuendlich; ersetzt einen vorhandenen 5-Minuten-Trigger). Ausschalten: links "Trigger" -> Eintrag loeschen.
 * 4. Nach Aenderung der Stichwoerter/Domains: resetBackfill() einmal ausfuehren, dann ein paar Laeufe abwarten, mit status() und gapCheck() pruefen.
 * Hinweis: Das Weiterleitungs-Skript ist ein anderes Projekt und bleibt unberuehrt (derzeit ohne Trigger).
 */
/* Stuendlich (Omar 15.10.): Das Nachfuellen bis 01.10.2025 ist fertig, es muessen nur noch NEUE Mails ins Blatt, und die Auslese (extract_po.gs) laeuft ohnehin stuendlich.
   EIN Trigger (everyHours) statt je Stunde einer: Apps Script erlaubt hoechstens 20 Trigger je Skript, die Auslese braucht schon 13. Ersetzt vorhandene Trigger (z. B. alle 5 Minuten). Einmal ausfuehren. */
function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'exportRelevantMails') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('exportRelevantMails').timeBased().everyHours(1).create();
}
