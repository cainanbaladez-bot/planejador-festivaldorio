const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function testTemplateRedirect() {
  const html = fs.readFileSync("planejador.template.html", "utf8");
  const firstScript = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
    .map(match => match[1]).find(script => script.includes("window.FILMES="));
  let destination = "";
  const context = {
    URL, decodeURIComponent,
    location: {
      pathname: "/planejador.template.html",
      href: "file:///projeto/planejador.template.html",
      replace(value) { destination = value; },
    },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(firstScript, context);
  assert.equal(destination, "file:///projeto/planejador.html",
    "abrir o template deve encaminhar para o aplicativo gerado");
}

function boot(storageRaw = {}, storageBroken = false) {
  const html = fs.readFileSync("docs/index.html", "utf8");
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
    .map(match => match[1]).filter(Boolean);
  const elements = new Map();
  const element = id => ({
    id, hidden: false, innerHTML: "", textContent: "", value: "", checked: false,
    style: {}, dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {}, setAttribute() {}, removeAttribute() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    appendChild() {}, remove() {}, focus() {}, scrollIntoView() {},
  });
  const local = new Map(Object.entries(storageRaw));
  const context = {
    console, performance, URL, URLSearchParams, Blob, TextEncoder, Date,
    setTimeout() {}, clearTimeout() {}, confirm() { return true; }, prompt() {},
    location: { origin: "http://local", pathname: "/", protocol: "file:", hash: "", search: "?agora=2025-10-01T00:00" }, /* modo festival: roda antes das datas de teste */
    history: { replaceState() {} }, navigator: {},
    localStorage: {
      getItem(key) { if(storageBroken) throw Error("storage blocked"); return local.has(key) ? local.get(key) : null; },
      setItem(key, value) { if(storageBroken) throw Error("storage blocked"); local.set(key, String(value)); },
    },
    addEventListener() {},
    document: {
      body: element("body"), activeElement: null,
      getElementById(id) { if (!elements.has(id)) elements.set(id, element(id)); return elements.get(id); },
      querySelectorAll() { return []; }, addEventListener() {},
      createElement(id) { return element(id); }, elementFromPoint() { return null; },
    },
  };
  context.window = context;
  vm.createContext(context);
  scripts.forEach((script, index) => vm.runInContext(script, context, { filename: `inline-${index}.js` }));
  return context;
}

const app = boot();
testTemplateRedirect();
const oldId=vm.runInContext("Object.keys(MUDOU)[0]",app);
assert(oldId,"a fixture de 2026 precisa incluir uma sessão removida");
const pendApp=boot({rio2026_agenda:JSON.stringify([oldId])});
assert.equal(vm.runInContext("agenda.size",pendApp),0,"sessão antiga não deve ser trocada automaticamente");
assert.equal(vm.runInContext(`pendencias.has(${JSON.stringify(oldId)})`,pendApp),true,
  "sessão antiga deve permanecer como pendência");
assert.equal(vm.runInContext("pendencias.size",boot({
  rio2026_pendencias:JSON.stringify([{id:oldId}]),rio2026_agenda:JSON.stringify([oldId])
})),1,"recarregar não deve duplicar pendências");
(async()=>{
app.setTimeout=fn=>fn();
await vm.runInContext(`
  const s={sessao_id:"teste",filme_id:FILMES[0].id,titulo:"Virada",data:"2026-10-31",
    hora:"23:30",duracao:"120 min.",cinema:"Cinema",sala:"1"};
  globalThis.__ics=icsEvento(s,1).join("\\r\\n");
`,app);
assert(app.__ics.includes("DTEND;TZID=America/Sao_Paulo:20261101T013000"),
  "ICS deve avançar o dia após a meia-noite");
vm.runInContext(`
  const virada={sessao_id:"fim",filme_id:FILMES[0].id,titulo:"Fim de ano",data:"2026-12-31",
    hora:"23:30",duracao:"120 min.",cinema:"Cinema",sala:"1"};
  globalThis.__icsAno=icsEvento(virada,1).join("\\r\\n");
  globalThis.__googleAno=new URL(linkGoogle(virada)).searchParams.get("dates");
`,app);
assert(app.__icsAno.includes("DTEND;TZID=America/Sao_Paulo:20270101T013000"),
  "ICS deve avançar o ano após a meia-noite");
assert.equal(app.__googleAno,"20261231T233000/20270101T013000",
  "Google Agenda deve avançar o dia e o ano");
vm.runInContext(`
  watch=new Map([[FILMES[0].id,1],[FILMES[1].id,2],[FILMES[2].id,3]]);
  const compartilhado=montarLink();
  location.hash=new URL(compartilhado).hash;
  const importado=lerLink();
  globalThis.__linkOk=JSON.stringify(importado.marc)===JSON.stringify([...watch]);

  dispOff=new Set([chaveCel("2025-10-18",3)]);
  globalThis.__duracaoOk=!liberada({data:"2025-10-18",hora:"18:30",duracao:"120 min.",cinema:"A"});
  globalThis.__limiteOk=liberada({data:"2025-10-18",hora:"18:00",duracao:"60 min.",cinema:"A"});

  planPrefs.margemCinema=40;
  const a={sessao_id:"a",filme_id:"a",data:"2025-10-18",hora:"18:00",duracao:"100 min.",cinema:"A"};
  const b={sessao_id:"b",filme_id:"b",data:"2025-10-18",hora:"20:00",duracao:"90 min.",cinema:"B"};
  globalThis.__trocaOk=problemaEntre(a,b).includes("40 min");

  const favorito=[{s:a,prio:1}], dois=[{s:a,prio:2},{s:{...b,hora:"22:00"},prio:2}];
  globalThis.__maxOk=cmpScore(scoreAgenda(dois,[],"max"),scoreAgenda(favorito,[],"max"))>0;
  globalThis.__prioOk=cmpScore(scoreAgenda(favorito,[],"prio"),scoreAgenda(dois,[],"prio"))>0;
  const mesmaSala=[{s:a,prio:1},{s:{...b,sessao_id:"c",cinema:"A"},prio:2}];
  const trocaSala=[{s:a,prio:1},{s:b,prio:2}];
  globalThis.__deslocamentoOk=cmpScore(scoreAgenda(mesmaSala,[],"trocas"),scoreAgenda(trocaSala,[],"trocas"))>0;
  globalThis.__objetivosOk=["max","prio","trocas","dias","espera","nota"].every(id=>OBJETIVOS.some(x=>x.id===id));
  globalThis.__comparacaoOk=typeof compararAlternativas==="function" && typeof escolherAlternativa==="function";
`, app);

assert.equal(app.__linkOk, true, "o link deve preservar os três níveis");
assert.equal(app.__duracaoOk, true, "a disponibilidade deve considerar a duração completa");
assert.equal(app.__limiteOk, true, "terminar exatamente no limite deve ser permitido");
assert.equal(app.__trocaOk, true, "a regra de troca deve ser compartilhada");
assert.equal(app.__maxOk, true, "máximo de filmes deve favorecer dois filmes");
assert.equal(app.__prioOk, true, "prioridades deve preservar o favorito");
assert.equal(app.__deslocamentoOk, true, "menor deslocamento deve favorecer menos trocas de cinema");
assert.equal(app.__objetivosOk, true, "os seis objetivos devem estar disponíveis");
assert.equal(app.__comparacaoOk, true, "comparação de alternativas deve estar disponível");
vm.runInContext(`
  watch=new Map(FILMES.slice(0,5).map((f,i)=>[f.id,(i%3)+1]));
  const fixa=SESSOES.find(s=>s.filme_id===FILMES[0].id);
  agenda=new Set([fixa.sessao_id]); fixadas=new Set([fixa.sessao_id]);
  manterAgenda=false; planPrefs.manter=false;
  proposta=encaixar("max",500);
`,app);
await vm.runInContext("compararAlternativas()",app);
vm.runInContext(`
  globalThis.__fixaOk=alternativas.length>=1&&alternativas.every(p=>p.base.some(s=>s.sessao_id===fixa.sessao_id));
  globalThis.__unicasOk=new Set(alternativas.map(p=>[...p.base.map(s=>s.sessao_id),...p.sel.map(x=>x.s.sessao_id)].sort().join("|"))).size===alternativas.length;
`,app);
assert.equal(app.__fixaOk,true,"todas as alternativas devem preservar a sessão fixada");
assert.equal(app.__unicasOk,true,"alternativas idênticas devem ser deduplicadas");

assert.doesNotThrow(() => boot({ rio2026_agenda: "json inválido", rio2026_watch3: "[" }),
  "armazenamento corrompido não deve impedir o app de abrir");
assert.doesNotThrow(() => boot({rio2026_watch:JSON.stringify({erro:true}),
  rio2026_agenda:JSON.stringify({erro:true}),rio2026_pendencias:JSON.stringify({erro:true})}),
  "tipos de armazenamento incorretos não devem impedir a abertura");
assert.doesNotThrow(() => boot({},true),"storage bloqueado não deve impedir a abertura");

console.log("planner smoke: 21 casos passaram");
})().catch(e=>{ console.error(e); process.exitCode=1; });
