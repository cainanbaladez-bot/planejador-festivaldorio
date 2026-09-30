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

## Atualização de 28/09/2026 e sessões remarcadas

Re-raspagem: **313 filmes, 928 sessões, 11 cinemas** (eram 298 / 926 / 10). Em 4 dias o festival
acrescentou 15 filmes (41 sessões — entre eles os capítulos de *The Story of Documentary Film*,
que ganharam páginas próprias), **remarcou 21 sessões** (dia, hora ou sala) e **tirou 39** (quase
todas de 13 e 14/10). Cinema novo: Armazém da Utopia (Av. Rodrigues Alves → região Centro).

**Agenda que o festival mudou.** A agenda guarda o id da sessão, e o id muda quando muda
dia/hora/sala — antes o app apagava a sessão da agenda calado. Agora:
- `data/rio_<ano>_historico.json` guarda **toda sessão já publicada** (versionado; semeado em
  28/09 com o que estava no ar desde 24/09). A cada build, a sessão que sumiu é pareada com uma
  sessão **nova do mesmo filme** na mesma rodada (ordem cronológica) → "remarcada"; sem par →
  "tirada". Vai para o app como `MUDOU` (id antigo → filme, texto da sessão antiga, id novo).
- O app troca a remarcada sozinho, tira a cancelada, e mostra na Minha Agenda um aviso com o
  antes → depois e o link para as outras sessões do filme; toast ao abrir; evento
  `rio/agenda-mudou`. O aviso fica guardado até a pessoa tocar em "Ok, entendi".
- **Nunca apagar o histórico** entre uma raspagem e outra — é ele que lembra as sessões antigas.

### 📤 Compartilhar e 🔄 versão nova sem atraso (29/09/2026)

- **📤 Compartilhar** (no lugar do 🔗 Link, logo depois do ⚡ Montar): com `navigator.share`
  (celular, Safari, Edge) abre o menu do próprio aparelho — WhatsApp, Instagram, e-mail — com
  título, texto e o link da agenda; sem ele, copia o link como antes. Motivo: em 29/09 no Rio,
  um link copiado às 9h09 trouxe 12 pessoas em uma hora (7 montaram a própria agenda), mais do
  que o X no dia inteiro. Eventos `compartilhou` / `compartilhar-cancelou` / `link-copiado`.
- **Versão nova sem atraso:** o `sw.js` serve do cache e baixa a nova em segundo plano, então a
  programação nova só aparecia na abertura seguinte. Agora, quando a versão nova assume
  (`controllerchange`): se a pessoa abriu há menos de 8 s e não tocou em nada, recarrega sozinho;
  senão, barra "🔄 Programação atualizada · Recarregar". Nunca na 1ª instalação nem quando chegou
  por link de agenda. Eventos `atualizou-sozinho` / `atualizou-barra`. Testado trocando o
  VERSAO do sw.js com a página aberta: as duas situações se comportam como descrito.

## Atualização diária automática (desde 30/09/2026)

Tarefa do Windows **PlanejadorRio-Atualiza**: todo dia às 7h (ou assim que o PC ligar, se
estava desligado), de 30/09 a 15/10 — termina sozinha em 16/10. Roda `atualiza_diario.py`:
raspa → confere → enriquece → sobe o `VERSAO` do sw.js → build → teste → commit.

- **Travas:** raspagem que falha, grade fechada, queda de mais de 10% dos filmes ou 20% das
  sessões, ou teste que não passa → desfaz tudo e não publica nada. Sem mudança no site do
  festival → não faz commit.
- **Publica sozinho** (`PUBLICAR = True` desde 29/09/2026 — o push pelo terminal funciona).
  Para voltar ao push manual pelo GitHub Desktop, trocar para `False` no topo do script.
- **Log:** `data/atualizacao.log` (fora do git). Ver a tarefa: Agendador de Tarefas do Windows.
- 1ª rodada (29/09, 23h09): **343 filmes (+30, a mostra nova "Cinema Circulação"), 985
  sessões**, 61 novas ou remarcadas. Cinema novo Areninha Renato Russo → Zona Norte.

## Pacote de navegação (29/09/2026)

- **★ Nota do Letterboxd + 🏆 festivais/prêmios** — `enrich_filmes.py`, copiado de SP (mesmo
  método: casa título + ano + diretor no autocomplete do Letterboxd, lê a nota do JSON-LD;
  festivais por regex na sinopse). Rodar depois de cada raspagem, antes do build:
  `py -3.10 enrich_filmes.py` (~10 min na 1ª vez; cache em `data/letterboxd_cache.json`, então
  as seguintes só buscam os filmes novos). Em 29/09: **158/313 com nota** (muita estreia de
  2026 ainda sem avaliação), 132 com festival, 30 premiados. Conferido: os casamentos batem
  (os 2 de slug estranho eram título em outra língua — *La bola negra*, *Czech Girl*).
  Volta o filtro Festivais, o selo e a ordenação por nota, e o objetivo "Melhores avaliações".
- **⏱ Modo festival** — o app sabe que horas são no Rio. Sessão que já começou fica apagada
  ("já passou"), sem "+ AGENDA", fora do montador (`liberada()`), dos filtros de dia/cinema e
  da ordem cronológica. O filtro de dia começa em **Hoje / Amanhã** durante o festival.
  Testar como se fosse outro momento: `?agora=2026-10-03T15:00` na URL (os testes em `tests/`
  usam `?agora=2025-10-01T00:00`, porque as datas de teste são de 2025).
- **🛡 Proteção da agenda** — `navigator.storage.persist()` na 1ª gravação com conteúdo (Chrome
  e app instalado protegem da limpeza automática; o Safari ignora). Dica "💾 mande o link para
  você mesmo" na Minha Agenda só para quem está no Safari do iPhone (apaga dado de site sem
  visita há 7 dias) ou dentro do X/Instagram (gaveta própria); fecha uma vez e não volta. O
  passo a passo do iPhone avisa que o app instalado começa vazio.

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
- **Enriquecimento (desde 29/09):** o filtro "Festivais" e o objetivo "Melhores avaliações" dependem do
  `enrich_filmes.py` de SP (festivais citados na sinopse + nota do Letterboxd), que não foi adaptado.
  Sem esses dados, o filtro de festival, a ordenação por nota e o objetivo "Melhores avaliações"
  somem da tela (dia/cinema também somem enquanto não houver sessões).

## Pendências

1. Re-raspar e republicar enquanto o festival completa a grade (subir `VERSAO` no `sw.js`).
2. Adaptar o `enrich_filmes.py` (Letterboxd) se quiser o filtro de festivais e as notas.
3. Ícones próprios do Rio (hoje são os de SP).
4. País vem truncado do site ("Sérvia + 4 países"); dá para montar a lista inteira pelo filtro de país da grade.
