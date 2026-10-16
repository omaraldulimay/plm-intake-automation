const H=require('./harness.js');const D=s=>new Date(s).getTime();
H.setRelevant(m=>m.atts.some(a=>/\.(xlsx|pdf)$/i.test(a))||/\bpo\b/i.test(m.subject));
H.CONFIG.MAX_RUNTIME_MS=60000;
for(let i=0;i<60;i++)H.addMail({date:D('2025-10-05T00:00:00Z')+i*5*24*3600*1000,subject:i%2?'PO '+i:'Hallo',atts:i%3?[]:['x.xlsx']});
H.addMail({thread:'T-OLD',date:D('2025-11-01T10:00:00Z'),subject:'PO Alt',body:'x'});
let n=0;while(H.props.backfillDone!=='true'&&n<30){H.run();H.tick(600000);n++;}
const ss=()=>H.drive.folders['PLM-Mails'].files.find(f=>f.ss).ss;
const ids=()=>ss().getSheetByName('Exportiert').rows.slice(1).map(r=>r[0]);
const out=[];const ck=(a,ok,i='')=>out.push((ok?'OK   ':'FEHL ')+a+(i?' | '+i:''));
ck('Nachfuellung fertig',H.props.backfillDone==='true',n+' Laeufe');
const e0=ids().length;
for(let i=0;i<10;i++){H.run();H.tick(600000);}
ck('10 Folgelaeufe ohne neue Mails aendern nichts',ids().length===e0,e0+' -> '+ids().length);
const a=H.addMail({date:H.now()-60000,subject:'PO 777 neu',body:'neu'});
const b=H.addMail({thread:'T-OLD',date:H.now()-30000,subject:'Re: PO Alt',body:'PI anbei',atts:['PI.pdf']});
H.run();
ck('neue Mail sofort exportiert',ids().includes(a));
ck('Antwort in altem Thread exportiert',ids().includes(b));
for(let i=0;i<5;i++){H.run();H.tick(600000);}
ck('keine Dubletten nach weiteren Laeufen',new Set(ids()).size===ids().length&&ids().length===e0+2,'gesamt '+ids().length);
H.CONFIG.MAX_RUNTIME_MS=2500; // extrem knapp: ~1 Mail pro Lauf
const c=H.addMail({date:H.now()-1000,subject:'PO A',atts:['1.xlsx']}),d=H.addMail({date:H.now()-900,subject:'PO B',atts:['2.xlsx']}),e=H.addMail({date:H.now()-800,subject:'PO C',atts:['3.xlsx']});
for(let i=0;i<15;i++){H.run();H.tick(600000);}
ck('bei extrem knappem Zeitlimit kommen trotzdem alle neuen Mails nach mehreren Laeufen',[c,d,e].every(x=>ids().includes(x))&&new Set(ids()).size===ids().length);
console.log(out.join('\n'));
