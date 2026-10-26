// Datei echt in den Lifecycle-Speicher laden und an eine ORDER haengen (/upload/presigned-url -> S3 -> addOrderAttachment). Nur additiv.
// Gegenstueck zu upload_helpers.js (Produkte). Mutation laut graphql_operationen.json: addOrderAttachmentFn(orderId, input: AddOrderAttachmentInput{name,fileType,fileUrl}).
window.__uploadOrderFile = async (orderId, name, mime, b64) => {
  const tok = localStorage.getItem('meta-auth-key'), brand = localStorage.getItem('lc_current_brand');
  const H = { 'Content-Type': 'application/json', Authorization: 'Bearer ' + tok, ...(brand ? { 'x-brand': brand } : {}) };
  const ext = (name.split('.').pop() || 'pdf').toLowerCase().replace(/[^a-z0-9]/g, '');
  const base = name.replace(/\.[^.]+$/, '').replace(/[^\w]/g, '').slice(0, 80);
  const fileName = 'r-' + Date.now() + '-attachment-' + Math.random().toString(36).slice(2, 8) + '-' + base + '.' + ext;
  const pr = await fetch('https://app-be.lifecycleplm.com/upload/presigned-url', { method: 'POST', headers: H, body: JSON.stringify({ fileName, type: mime, path: 'attachment' }) });
  if (!pr.ok) return { ok: false, step: 'presign', status: pr.status, body: (await pr.text()).slice(0, 200) };
  const ps = await pr.json();
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const fd = new FormData(); Object.entries(ps.fields || {}).forEach(([k, v]) => fd.append(k, v)); fd.append('file', new File([bin], fileName, { type: mime }));
  const up = await fetch(ps.url, { method: 'POST', body: fd });
  if (!up.ok) return { ok: false, step: 's3', status: up.status };
  const key = (ps.fields && ps.fields.Key) || fileName;
  const N = v => ({ kind: 'Name', value: v }), V = n => ({ kind: 'Variable', name: N(n) });
  const F = (n, sel, args) => ({ kind: 'Field', name: N(n), arguments: args || [], selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const NN = t => ({ kind: 'NonNullType', type: { kind: 'NamedType', name: N(t) } });
  const m = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: [{ kind: 'VariableDefinition', variable: V('o'), type: NN('String') }, { kind: 'VariableDefinition', variable: V('i'), type: NN('AddOrderAttachmentInput') }],
    selectionSet: { kind: 'SelectionSet', selections: [F('addOrderAttachment', [F('id'), F('name'), F('fileUrl'), F('fileType')], [{ kind: 'Argument', name: N('orderId'), value: V('o') }, { kind: 'Argument', name: N('input'), value: V('i') }])] } }] };
  const r = await window.__APOLLO_CLIENT__.mutate({ mutation: m, variables: { o: orderId, i: { name: name.replace(/\.[^.]+$/, ''), fileType: mime, fileUrl: key } }, errorPolicy: 'all' });
  const a = r.data && r.data.addOrderAttachment;
  return a ? { ok: true, id: a.id, name: a.name, fileUrl: a.fileUrl, fileType: a.fileType } : { ok: false, step: 'attach', err: (r.errors || []).map(e => e.message.slice(0, 200)) };
};
