# Planejador do Festival do Rio

Planejador pessoal da programação do **Festival do Rio**. É uma **cópia da lógica do
[Planejador da Mostra](../Planejador%20da%20Mostra/README.md)** (SP): mesmo template, mesmas
funções (★ em três níveis, agenda com conflito de horário, disponibilidade, ⚡ Montar minha agenda,
.ics, 🔗 Link, backup, PWA). Muda só a fonte dos dados e o que é do Rio (textos, cores das mostras,
regiões de cinema).

> **Projeto independente.** Não é um site oficial do Festival do Rio. Horários e ingressos devem
> ser confirmados em [festivaldorio.com.br](https://www.festivaldorio.com.br).

## Estado (24/09/2026)

- **Grade publicada em 24/09: 298 filmes, 926 sessões, 1–14 out, 10 cinemas.** O festival está
  soltando a grade **aos poucos** (o total no site foi de 731 a 928 sessões na mesma tarde) — por
  isso a faixa **ATUALIZADO** no topo diz de quando é o retrato. Rodar de novo o raspador + build
  nos próximos dias e republicar.
- **Conferido contra o site em 24/09:** as 735 sessões que a página `/br/programacao` entrega
  (ela para em 10/10) estão todas no local; o total do site (928) e o local (926) batem.
  Em 21/09 as 291 fichas de filme bateram campo a campo (só 3 diferenças triviais).
- **Publicado:** repositório `planejador-festivaldorio`, GitHub Pages na pasta `/docs`.
- Os ids dos filmes são estáveis (CRC32 de `ano/slug`): as ★ marcadas antes da grade continuam valendo.
- Testado de ponta a ponta também com a edição 2025 (`planejador_teste_2025.html`, 1.166 sessões).
  Os dois testes automáticos passam (`tests/`).

## Como rodar

```bash
py -3.10 scrape_rio.py              # raspa 2026 -> data/rio_2026_*.json   (~5 min)
py -3.10 build_planejador.py        # -> planejador.html + docs/index.html
py -3.10 scrape_rio.py --ano 2025   # edição passada, tem sessões (para testar)
py -3.10 build_planejador.py --ano 2025   # -> planejador_teste_2025.html (fora de docs/)
node tests/planner-smoke.js         # teste sobre docs/index.html
node tests/planner-smoke-rio2025.js # mesmo teste sobre o build de 2025 (com sessões)
```

Servidor local: configuração `planejador-rio` (porta 8791) no `launch.json` do Claude.

## Arquivos

| Arquivo | O que é |
|---|---|
| `scrape_rio.py` | Raspador. O site é um app **Inertia.js**: toda página traz o JSON completo no atributo `data-page`. Lista em `/br/filmes?page=N` (9 por página); ficha e sessões em `/br/filmes/<slug>` (`props.pelicula` + `pelicula.programacoesAsJson`). Edições passadas em `/br/edicoes-anteriores/<ano>/filmes`. |
| `build_planejador.py` | Injeta dados, cores das mostras e regiões no template. As **regiões** saem de palavras do nome/endereço de cada cinema (`REGIOES_RIO`, a ordem importa: Niterói antes do Centro por causa da "Av. Visconde do Rio Branco"). |
| `planejador.template.html` | Template copiado de SP, com os textos trocados por marcas `__ANO__`, `__SUB__`, `__BETA__`, `__MES__`, `/*__CORES__*/`, `/*__REGIOES__*/` e o estado `SEM_HORARIOS`. |
| `docs/` | O que o GitHub Pages publica (PWA: manifesto, `sw.js`, ícones — ainda os mesmos de SP). **Ao republicar, suba o `VERSAO` em `docs/sw.js`** (hoje `rio-v2`), senão quem instalou fica com o cache velho. |
| `data/` | Dados raspados e logs. |

## Diferenças em relação a SP

- **Mostras:** o site tem 28 submostras (20 são "Première Brasil: …"). Filtro e cor usam o **nome
  curto** (10 grupos em 2026); o nome completo vai entre colchetes no início da sinopse.
- **Sessões:** o site dá dia como "Ter, 7 Out" (sem ano) e hora como "21H45"; o raspador põe o ano
  da edição. A sala vem como "Estação NET Gávea 5" e o cinema é a sala sem o número.
  As etiquetas da sessão (debate, com convidados, gratuito) vão no campo `legendas`.
- **Grade x lista de filmes:** a grade (`/br/programacao`) tem programas fora da lista de filmes
  (2026: *The Story of Documentary Film*, em 3 programas). O raspador os acrescenta; se a ficha
  der 404 no site, monta uma ficha mínima com os dados da grade (a parte — "Programa II" — vai na
  sessão). A paginação da grade é cumulativa (a última página traz tudo) e para em 10/10; as
  fichas dos filmes trazem a grade inteira.
- **Créditos:** o site manda equipe em MAIÚSCULAS; `nome_proprio()` passa para Nome Próprio
  mantendo siglas (ABC, AMC, TV, DJ, algarismos romanos — lista `SIGLAS`).
- **Cache do service worker:** os caches se chamam `planejador-rio-*` e o `sw.js` só apaga os
  seus. Todo repositório do Pages da conta divide o domínio `cainanbaladez-bot.github.io`; antes
  o filtro `planejador-*` apagava o cache do Planejador da Mostra (SP) e vice-versa.
- **Chaves do navegador:** `rio<ano>_*` — cada edição guarda a agenda separada. Eventos de medição
  saem como `rio/<ação>` no mesmo GoatCounter dos outros sites.
- **📲 Instalar no celular (24/09/2026):** barra discreta embaixo (12 s, só no celular, `×` guarda
  a recusa) + link no rodapé. Android chama a janela do Chrome; iPhone mostra os passos do
  Compartilhar; navegador de dentro do X/Instagram/WhatsApp manda abrir no navegador antes.
  Mesmo código do de SP — detalhes no README de lá. Eventos `rio/instalar-*`.
- **Sem enriquecimento ainda:** o filtro "Festivais" e o objetivo "Melhores avaliações" dependem do
  `enrich_filmes.py` de SP (festivais citados na sinopse + nota do Letterboxd), que não foi adaptado.
  Sem esses dados, o filtro de festival, a ordenação por nota e o objetivo "Melhores avaliações"
  somem da tela (dia/cinema também somem enquanto não houver sessões).

## Pendências

1. Re-raspar e republicar enquanto o festival completa a grade (subir `VERSAO` no `sw.js`).
2. Adaptar o `enrich_filmes.py` (Letterboxd) se quiser o filtro de festivais e as notas.
3. Ícones próprios do Rio (hoje são os de SP).
4. País vem truncado do site ("Sérvia + 4 países"); dá para montar a lista inteira pelo filtro de país da grade.
