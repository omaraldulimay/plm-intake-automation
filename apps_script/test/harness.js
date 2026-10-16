const fs=require('fs'),vm=require('vm');
// ---- virtuelle Uhr ----
let virt=new Date('2026-10-13T10:00:00Z').getTime();
const RealDate=Date;
Date.now=()=>virt;
const tick=ms=>{virt+=ms;};
// ---- Mock-Postfach ----
const mails=[]; // {id,thread,date,from,to,subject,body,atts:[names]}
let idc=0;
function addMail(o){const id='m'+(++idc);mails.push({id,thread:o.thread||('t'+id),to:'kontakt@firma.example',cc:'',atts:[],body:'',...o,id});return id;}
function pad(n){return String(n).padStart(2,'0');}
global.Utilities={formatDate:(d,tz,f)=>{const y=d.getUTCFullYear(),M=pad(d.getUTCMonth()+1),D=pad(d.getUTCDate()),h=pad(d.getUTCHours()),mi=pad(d.getUTCMinutes());return f.replace('yyyy',y).replace('MM',M).replace('dd',D).replace('HH',h).replace('mm',mi);}};
global.Session={getScriptTimeZone:()=> 'UTC'};
global.LockService={getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})};
global.Logger={log:()=>{}};
global.MimeType={PLAIN_TEXT:'text/plain'};
function mkMsg(r){return {getId:()=>r.id,getDate:()=>new RealDate(r.date),getFrom:()=>r.from,getTo:()=>r.to,getCc:()=>r.cc,getSubject:()=>r.subject,getPlainBody:()=>r.body,
 getAttachments:()=>{tick(300);return r.atts.map(n=>({getName:()=>n,copyBlob:()=>{const b={name:n,blob:true,getBytes:()=>new Array(100),setName:x=>{b.name=x;return b;}};return b;}}));},
 getThread:()=>({getId:()=>r.thread})};}
let H_relevant=()=>true;
const stats={searches:0,getMessagesCalls:0};
global.GmailApp={search:(q,off,max)=>{stats.searches++;
 const after=(q.match(/after:(\d{4})\/(\d\d)\/(\d\d)/g)||[]).map(x=>{const p=x.slice(6).split('/');return Date.UTC(+p[0],+p[1]-1,+p[2]);});
 const before=(q.match(/before:(\d{4})\/(\d\d)\/(\d\d)/g)||[]).map(x=>{const p=x.slice(7).split('/');return Date.UTC(+p[0],+p[1]-1,+p[2]);});
 const lo=after.length?Math.max(...after):-Infinity, hi=before.length?Math.min(...before):Infinity;
 const th={};mails.forEach(m=>{(th[m.thread]=th[m.thread]||[]).push(m);});
 let list=Object.values(th).filter(ms=>ms.some(m=>m.date>=lo&&m.date<hi&&H_relevant(m))).map(ms=>({last:Math.max(...ms.map(m=>m.date)),ms}));
 list.sort((a,b)=>b.last-a.last);
 return list.slice(off,off+max).map(t=>({getId:()=>t.ms[0].thread,getMessageCount:()=>{tick(20);return t.ms.length;},getLastMessageDate:()=>new RealDate(t.last),getMessages:()=>{stats.getMessagesCalls++;tick(200);return t.ms.slice().sort((a,b)=>a.date-b.date).map(mkMsg);}}));}};
// Drive/Sheets
const drive={folders:{},files:[]};
function mkFolder(name,parent){const f={name,files:[],subs:[],id:'f'+Math.random()};
 f.createFile=(n,c)=>{tick(500);const x={name:typeof n==='string'?n:n.name,content:c};f.files.push(x);return x;};f.getFoldersByName=n=>{const m=f.subs.filter(x=>x.name===n);let i=0;return{hasNext:()=>i<m.length,next:()=>m[i++]};};
 f.createFolder=n=>{tick(500);const s=mkFolder(n,f);f.subs.push(s);return s;};
 f.getUrl=()=>'https://drive/'+name;f.getFilesByName=n=>{const m=f.files.filter(x=>x.name===n);let i=0;return{hasNext:()=>i<m.length,next:()=>m[i++]};};return f;}
global.DriveApp={getFoldersByName:n=>{const m=drive.folders[n]?[drive.folders[n]]:[];let i=0;return{hasNext:()=>i<m.length,next:()=>m[i++]};},createFolder:n=>drive.folders[n]=mkFolder(n),getFileById:id=>({moveTo:fo=>{const ss=sheets[id];fo.files.push({name:ss.name,ss});}})};
const sheets={};
function mkSheet(name){const rows=[];let max=1000;const s={name,rows,appendRow:r=>{tick(500);rows.push(r);if(rows.length>max)max=rows.length;},getLastRow:()=>rows.length,getMaxRows:()=>max,insertRowsAfter:(pos,n)=>{max+=n;},setName:n=>{s.name=n;},getRange:(r,c,nr,nc)=>{if(r-1+nr>max)throw new Error('The coordinates of the range are outside the dimensions of the sheet.');return {getValues:()=>rows.slice(r-1,r-1+nr).map(x=>x.slice(c-1,c-1+nc)),setValues:v=>{tick(500);v.forEach((row,i)=>{rows[r-1+i]=row;});}};}};return s;}
function mkSS(name){const ss={name,id:'ss'+Math.random(),sheets:[mkSheet('Tabelle1')]};ss.getSheets=()=>ss.sheets;ss.getId=()=>ss.id;ss.getSheetByName=n=>ss.sheets.find(x=>x.name===n)||null;ss.insertSheet=n=>{const s=mkSheet(n);ss.sheets.push(s);return s;};sheets[ss.id]=ss;return ss;}
global.SpreadsheetApp={create:n=>mkSS(n),open:f=>f.ss};
const props={};
global.PropertiesService={getScriptProperties:()=>({getProperty:k=>(k in props?props[k]:null),setProperty:(k,v)=>{props[k]=String(v);}})};
global.ScriptApp={getProjectTriggers:()=>[],newTrigger:()=>({timeBased:()=>({everyMinutes:()=>({create:()=>{}})})})};
vm.runInThisContext(fs.readFileSync(process.argv[2]||require('path').join(__dirname,'..','mail_export.gs'),'utf8'));
module.exports={setRelevant:f=>{H_relevant=f;},relevantOf:m=>H_relevant(m),addMail,mails,drive,props,stats,tick,setNow:t=>{virt=t;},now:()=>virt,run:()=>exportRelevantMails(),CONFIG,RealDate};
