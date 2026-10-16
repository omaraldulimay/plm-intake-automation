(async()=>{
// Liest alle Kategorien (id, Name, collectionId) per GraphQL (nur lesen).
const N=v=>({kind:'Name',value:v}); const V=n=>({kind:'Variable',name:N(n)});
const F=(name,args,sel)=>({kind:'Field',name:N(name),arguments:args||[],selectionSet:sel?{kind:'SelectionSet',selections:sel}:undefined});
const T=n=>({kind:'NamedType',name:N(n)});
const doc={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'query',variableDefinitions:[{kind:'VariableDefinition',variable:V('after'),type:T('Int')},{kind:'VariableDefinition',variable:V('limit'),type:T('Int')}],
 selectionSet:{kind:'SelectionSet',selections:[F('categories',[{kind:'Argument',name:N('after'),value:V('after')},{kind:'Argument',name:N('limit'),value:V('limit')}],[F('id'),F('name'),F('collectionId')])]}}]};
const c=window.__APOLLO_CLIENT__; const out=[];
for(let after=0;after<2000;after+=100){const r=await c.query({query:doc,variables:{after,limit:100},fetchPolicy:'no-cache',errorPolicy:'all'});const l=(r.data&&r.data.categories)||[];out.push(...l);if(l.length<100)break;}
return out;})()
