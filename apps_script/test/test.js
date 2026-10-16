const H=require('./harness.js');const D=s=>new Date(s).getTime();
const KW=['purchase order','packing list','p.o','po','pi','proforma','invoice','rechnung','order','bestellung','shipment','sendung','container','booking','sample','muster','payment','zahlung','deposit','etd','eta','delivery','lieferung','production','produktion','price','preis'];
const EXT=/\.(xlsx|xls|xlsm|csv|ods|pdf|docx?|odt)$/i;
// Orakel: so verhaelt sich die Gmail-Suche des Skripts (Anhang-Typ ODER Stichwort als ganzes Wort)
H.setRelevant(m=>m.atts.some(a=>EXT.test(a))||KW.some(k=>new RegExp('(^|[^a-z0-9])'+k.replace('.','\\.')+'([^a-z0-9]|$)').test((m.subject+' '+m.body).toLowerCase())));
let seed=7;const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};
const start=D('2025-09-01T08:00:00Z'),end=D('2026-10-12T20:00:00Z');
const all=[];
for(let i=0;i<1000;i++){
  const date=start+Math.floor(rnd()*(end-start));const k=Math.floor(rnd()*8);
  let o={date,from:'x@lieferant.com',subject:'Hallo',body:'Guten Tag',atts:[]};
  if(k===0)o.subject='PO 1234 Alpha';else if(k===1)o.atts=['PO.xlsx'];else if(k===2)o.body='please find the proforma invoice';
  else if(k===3){o.atts=['logo.png'];o.subject='Gruesse';}else if(k===4){o.subject='Newsletter Angebote';o.body='Position und Pizza und Positiv';}
  else if(k===5)o.subject='Mittagessen?';else if(k===6)o.atts=['report.pdf'];else o.subject='Terminabstimmung';
  const id=H.addMail(o);all.push(id);
}
const t1=H.addMail({thread:'T-A',date:D('2026-03-01T10:00:00Z'),subject:'Re: Besuch',body:'Hi'});
const t2=H.addMail({thread:'T-A',date:D('2026-03-02T10:00:00Z'),subject:'Re: Besuch',body:'Hi',atts:['Order.xlsx']});
const MIN=D('2025-10-01T00:00:00Z');
const expected=()=>{const thr={};H.mails.forEach(m=>{(thr[m.thread]=thr[m.thread]||[]).push(m);});const e=[];Object.values(thr).forEach(ms=>{if(ms.some(m=>m.date>=MIN&&H.relevantOf(m)))ms.filter(m=>m.date>=MIN).forEach(m=>e.push(m.id));});return e;};
H.CONFIG.MAX_RUNTIME_MS=60000; // 60 s virtuell pro Lauf (echt 4,5 Min)
const ss=()=>H.drive.folders['PLM-Mails'].files.find(f=>f.ss).ss;
const rows=()=>ss().getSheetByName('Exportiert').rows.slice(1);
let runs=0,log=[],newId=null;
while(runs<300){runs++;H.run();H.tick(10*60*1000);
  log.push([runs,rows().length,H.props.backfillDone||'-',H.props.backfillBefore||'-']);
  if(runs===1)newId=H.addMail({date:H.now()-1000,subject:'NEU PO 9999',body:'neu'});
  if(H.props.backfillDone==='true'&&runs>3)break;}
H.run(); // noch ein Lauf nach Abschluss, holt ggf. Rest der neuen Mail
const res=[];const ck=(n,ok,i='')=>res.push((ok?'OK   ':'FEHL ')+n+(i?' | '+i:''));
const ex=rows().map(r=>r[0]);
const exp=expected();
ck('Nachfuellung fertig',H.props.backfillDone==='true',runs+' Laeufe (virtuelles Limit 60 s)');
ck('alle erwarteten Mails exportiert, nichts fehlt',exp.every(id=>ex.includes(id)),`erwartet ${exp.length}, exportiert ${ex.length}`);
ck('nichts Ueberfluessiges exportiert',ex.every(id=>exp.includes(id)));
ck('keine Dubletten',new Set(ex).size===ex.length);
ck('Mails vor 01.10.2025 nicht exportiert',ex.every(id=>H.mails.find(m=>m.id===id).date>=MIN));
const dateOf=id=>H.mails.find(m=>m.id===id).date;
ck('Lauf 1 holte die neuesten zuerst',dateOf(ex[0])>D('2026-09-15T00:00:00Z'),'erste: '+new Date(dateOf(ex[0])).toISOString().slice(0,10));
const firstRunCount=log[0][1];
ck('neue Mail nach Lauf 1 steht direkt hinter den Lauf-1-Mails (vor den alten)',ex.indexOf(newId)===firstRunCount,`Pos ${ex.indexOf(newId)+1}, Lauf-1-Mails ${firstRunCount}`);
const att=H.drive.folders['PLM-Mails'].subs.find(s=>s.name==='Anhaenge');
ck('Anhaenge nur xlsx/pdf, kein png',att.files.length>0&&att.files.every(f=>/\.(xlsx|pdf)$/i.test(f.name)),att.files.length+' Dateien');
const txt=H.drive.folders['PLM-Mails'].files.filter(f=>/^mails_.*\.txt$/.test(f.name));
const nMail=txt.reduce((a,f)=>a+(f.content.match(/===== MAIL =====/g)||[]).length,0);
ck('Textdateien enthalten genau die exportierten Mails',nMail===ex.length,`${txt.length} Dateien, ${nMail} Mails`);
ck('Textdatei-Name im Protokoll existiert',rows().every(r=>H.drive.folders['PLM-Mails'].files.some(f=>f.name===r[6])));
console.log(res.join('\n'));console.log('\nVerlauf:');log.slice(0,4).concat([['...']]).concat(log.slice(-2)).forEach(l=>console.log(l.join(' | ')));
console.log('Suchen:',H.stats.searches,'getMessages:',H.stats.getMessagesCalls);
