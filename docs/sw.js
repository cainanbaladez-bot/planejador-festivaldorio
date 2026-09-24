/* Service worker do Planejador do Festival do Rio (copiado do Planejador da Mostra).
   Objetivo: abrir instantâneo e funcionar sem internet no meio do festival.

   Estratégia do app (index.html, manifesto, ícones): stale-while-revalidate —
   serve do cache na hora e busca a versão nova em segundo plano, que entra no
   próximo acesso. Como o HTML tem ~1,3 MB com os dados dentro, buscar antes de
   mostrar deixaria a abertura lenta à toa.

   Pôsteres (vêm de fora): cache-first, guardados conforme aparecem. Assim o que
   a pessoa já viu continua aparecendo offline, sem baixar ~300 imagens de véspera.

   Ao publicar uma versão nova do app, suba o VERSAO — isso descarta o cache velho. */
const VERSAO = "rio-v3";
const SHELL  = "planejador-rio-shell-" + VERSAO;
const MIDIA  = "planejador-rio-posteres-" + VERSAO;

const ESSENCIAIS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icone-192.png",
  "./icone-512.png",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(SHELL)
      .then(c => c.addAll(ESSENCIAIS))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())   /* offline na 1ª instalação: segue a vida */
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(
        ks.filter(k => k.startsWith("planejador-rio-") && k !== SHELL && k !== MIDIA)
          .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  const mesmaOrigem = url.origin === self.location.origin;

  /* imagem de fora (pôster): cache-first */
  if (!mesmaOrigem) {
    if (req.destination !== "image") return;   /* fontes, links externos: deixa passar */
    e.respondWith(
      caches.open(MIDIA).then(async cache => {
        const guardado = await cache.match(req);
        if (guardado) return guardado;
        try {
          const resp = await fetch(req);
          if (resp && (resp.ok || resp.type === "opaque")) cache.put(req, resp.clone());
          return resp;
        } catch (err) {
          return guardado || Response.error();
        }
      })
    );
    return;
  }

  /* app: stale-while-revalidate */
  e.respondWith(
    caches.open(SHELL).then(async cache => {
      const guardado = await cache.match(req, { ignoreSearch: true });
      const rede = fetch(req).then(resp => {
        if (resp && resp.ok) cache.put(req, resp.clone());
        return resp;
      }).catch(() => null);
      if (guardado) { e.waitUntil(rede); return guardado; }
      const resp = await rede;
      if (resp) return resp;
      /* navegação offline sem nada em cache: entrega o app se ele existir */
      if (req.mode === "navigate") {
        const app = await cache.match("./index.html");
        if (app) return app;
      }
      return Response.error();
    })
  );
});
