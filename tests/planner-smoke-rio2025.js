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

function boot(storageRaw = {}) {
  const html = fs.readFileSync("planejador_teste_2025.html", "utf8");
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
    location: { origin: "http://local", pathname: "/", protocol: "file:", hash: "", search: "" },
    history: { replaceState() {} }, navigator: {},
    localStorage: {
      getItem(key) { return local.has(key) ? local.get(key) : null; },
      setItem(key, value) { local.set(key, String(value)); },
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
`, app);

assert.equal(app.__linkOk, true, "o link deve preservar os três níveis");
assert.equal(app.__duracaoOk, true, "a disponibilidade deve considerar a duração completa");
assert.equal(app.__limiteOk, true, "terminar exatamente no limite deve ser permitido");
assert.equal(app.__trocaOk, true, "a regra de troca deve ser compartilhada");
assert.equal(app.__maxOk, true, "máximo de filmes deve favorecer dois filmes");
assert.equal(app.__prioOk, true, "prioridades deve preservar o favorito");
assert.equal(app.__deslocamentoOk, true, "menor deslocamento deve favorecer menos trocas de cinema");
assert.equal(app.__objetivosOk, true, "os seis objetivos devem estar disponíveis");

assert.doesNotThrow(() => boot({ rio2025_agenda: "json inválido", rio2025_watch3: "[" }),
  "armazenamento corrompido não deve impedir o app de abrir");

console.log("planner smoke: 10 casos passaram");
