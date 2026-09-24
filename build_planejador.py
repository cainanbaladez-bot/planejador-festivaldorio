# -*- coding: utf-8 -*-
"""Gera o planejador do Festival do Rio: injeta os dados raspados no template.

Copiado do Planejador da Mostra (SP) — mesma lógica, mesmo template (com os textos de SP
trocados). O que é do Rio mora aqui: cores das mostras, regiões de cinema e os textos do topo.

Uso:  py -3.10 build_planejador.py              # 2026 -> planejador.html + docs/index.html
      py -3.10 build_planejador.py --ano 2025   # teste com a edição passada (tem sessões)
                                                  -> planejador_teste_2025.html (NÃO vai p/ docs/)
Antes: py -3.10 scrape_rio.py [--ano 2025]
"""
import sys, json, re, unicodedata, collections, datetime
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
TEMPLATE = BASE / "planejador.template.html"

ano = int(sys.argv[sys.argv.index("--ano") + 1]) if "--ano" in sys.argv else 2026
corrente = ano == 2026
SAIDA = BASE / ("planejador.html" if corrente else f"planejador_teste_{ano}.html")
SAIDA_SITE = BASE / "docs" / "index.html"

CAMPOS_FILME = [
    "id", "slug", "titulo", "titulo_original", "sinopse", "genero", "pais",
    "ano", "duracao", "secao", "classificacao", "diretores", "elenco",
    "roteiro", "fotografia", "montagem", "musica", "producao", "distribuicao",
    "imagem", "trailer", "link_compra", "url_pagina", "n_sessoes",
]
CAMPOS_SESSAO = [
    "sessao_id", "filme_id", "titulo", "data", "hora", "sala", "cinema",
    "endereco_cinema", "idioma", "legendas", "secao", "duracao", "link_compra",
]
PALETA = ["#6db3dd", "#f2a93b", "#8fbf6f", "#d1749c", "#b48ce0", "#ffd166",
          "#c9a15f", "#e2543a", "#5fc9bd", "#9aa8ff", "#e89f71", "#7fd1a0"]

# região -> [(palavra no NOME ou ENDEREÇO do cinema, bairro que aparece na tela)]. A ordem importa:
# Niterói vem antes do Centro porque o endereço da Reserva Cultural é "Av. Visconde do Rio Branco".
REGIOES_RIO = [
    ("niteroi", "Niterói", [("niteroi", "Niterói"), ("icarai", "Icaraí"), ("uff", "Niterói")]),
    ("botafogo", "Botafogo / Humaitá", [("voluntarios da patria", "Botafogo"), ("praia de botafogo", "Botafogo"),
                                        ("botafogo", "Botafogo"), ("humaita", "Humaitá"), ("urca", "Urca")]),
    ("gavea", "Gávea / Leblon / Ipanema / Lagoa", [("marques de sao vicente", "Gávea"), ("gavea", "Gávea"),
                                                   ("leblon", "Leblon"), ("ipanema", "Ipanema"), ("lagoa", "Lagoa"),
                                                   ("jardim botanico", "Jardim Botânico")]),
    ("copacabana", "Copacabana / Leme", [("copacabana", "Copacabana"), ("leme", "Leme")]),
    ("flamengo", "Flamengo / Laranjeiras / Catete / Santa Teresa", [("catete", "Catete"), ("flamengo", "Flamengo"),
                 ("laranjeiras", "Laranjeiras"), ("leite leal", "Laranjeiras"), ("jose wilker", "Laranjeiras"),
                 ("santa teresa", "Santa Teresa"), ("paschoal carlos magno", "Santa Teresa"), ("gloria", "Glória")]),
    ("centro", "Centro", [("praca maua", "Praça Mauá"), ("museu do amanha", "Praça Mauá"), ("floriano", "Cinelândia"),
                          ("odeon", "Cinelândia"), ("cinelandia", "Cinelândia"), ("rio branco", "Centro"),
                          ("primeiro de marco", "Centro"), ("ccbb", "Centro"), ("lapa", "Lapa"), ("centro", "Centro")]),
    ("norte", "Zona Norte", [("penha", "Penha"), ("bras de pina", "Penha"), ("nova brasilia", "Complexo do Alemão"),
                             ("alemao", "Complexo do Alemão"), ("tijuca", "Tijuca"), ("maracana", "Maracanã"),
                             ("vila isabel", "Vila Isabel"), ("meier", "Méier"), ("madureira", "Madureira"),
                             ("ilha do governador", "Ilha do Governador")]),
    ("oeste", "Barra / Zona Oeste", [("realengo", "Realengo"), ("barra", "Barra"), ("recreio", "Recreio"),
                                     ("jacarepagua", "Jacarepaguá"), ("campo grande", "Campo Grande"),
                                     ("bangu", "Bangu"), ("americas", "Barra")]),
]


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def regiao_de(cinema, endereco):
    alvo = sem_acento(f"{cinema} {endereco}")
    for rid, _, chaves in REGIOES_RIO:
        for k, bairro in chaves:
            if k in alvo:
                return rid, bairro
    return "outros", ""


def enxuga(lista, campos):
    return [{c: item.get(c, "") for c in campos} for item in lista]


filmes = json.loads((DATA / f"rio_{ano}_filmes.json").read_text(encoding="utf-8"))
sessoes = json.loads((DATA / f"rio_{ano}_sessoes.json").read_text(encoding="utf-8"))

# O site tem 28 submostras; 20 delas são "Première Brasil: ...". Para filtrar e colorir, o
# planejador usa o NOME CURTO da mostra (~12 grupos). O nome completo segue na sinopse do modal.
for f in filmes:
    completo, curto = f.get("secao", ""), f.get("mostra") or f.get("secao", "")
    f["secao"] = curto
    if completo and completo != curto:
        f["sinopse"] = f"[{completo}] {f.get('sinopse', '')}"
sec_por_filme = {f["id"]: f["secao"] for f in filmes}
for s in sessoes:
    s["secao"] = sec_por_filme.get(s["filme_id"], s.get("secao", ""))

# cores: as mostras com mais filmes pegam as primeiras cores da paleta
cont = collections.Counter(f["secao"] for f in filmes if f["secao"])
cores = {sec: PALETA[i % len(PALETA)] for i, (sec, _) in enumerate(cont.most_common())}

# regiões: montadas a partir dos cinemas que aparecem nas sessões
por_cinema = collections.OrderedDict()
for s in sessoes:
    c = por_cinema.setdefault(s["cinema"], {"end": s.get("endereco_cinema", ""), "n": 0})
    c["n"] += 1
regioes = []
rotulo = {rid: rot for rid, rot, _ in REGIOES_RIO}
rotulo["outros"] = "Outros"
grupos = collections.OrderedDict((rid, []) for rid in list(rotulo))
for cin, info in por_cinema.items():
    rid, bairro = regiao_de(cin, info["end"])
    grupos[rid].append({"n": cin, "b": bairro, "ses": info["n"]})
for rid, cins in grupos.items():
    if cins:
        regioes.append({"id": rid, "rot": rotulo[rid], "ses": sum(c["ses"] for c in cins),
                        "cinemas": [{"n": c["n"], "b": c["b"]} for c in sorted(cins, key=lambda c: -c["ses"])]})
regioes.sort(key=lambda r: -r["ses"])

# textos do topo
MES_PT = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
datas = sorted({s["data"] for s in sessoes})
if datas:
    d0, d1 = (datetime.date.fromisoformat(d) for d in (datas[0], datas[-1]))
    periodo = f"{d0.day} {MES_PT[d0.month]} — {d1.day} {MES_PT[d1.month]} {d1.year}"
    mes = f"{MES_PT[d0.month].title()} {d0.year}" if d0.month == d1.month else f"{MES_PT[d0.month].title()} — {MES_PT[d1.month].title()} {d1.year}"
    sub = f"Festival do Rio · {periodo} · {len(filmes)} filmes · {len(sessoes)} sessões"
else:
    mes = str(ano)
    sub = f"Festival do Rio {ano} · {len(filmes)} filmes · horários ainda não publicados"
if not corrente:
    beta = (f'<div class="beta" role="note"><p><b>TESTE</b>Programação do Festival do Rio {ano}, '
            f'só para testar o planejador com sessões de verdade.</p></div>')
elif not sessoes:
    beta = (f'<div class="beta" role="note"><p><b>PRÉVIA</b>Os filmes do Festival do Rio {ano} já estão aqui. '
            f'Marque os seus com ★ — os horários entram assim que o festival publicar a grade.</p></div>')
else:
    # a grade entra no site aos poucos: diz de quando é o retrato que está no ar
    quando = datetime.datetime.fromisoformat(
        json.loads((DATA / f"rio_{ano}_meta.json").read_text(encoding="utf-8"))["raspado_em"])
    beta = (f'<div class="beta" role="note"><p><b>ATUALIZADO</b>Grade conferida no site do festival em '
            f'{quando:%d/%m} às {quando.hour}h{quando:%M}. O festival ainda pode acrescentar ou mudar sessões — '
            f'confirme horários e ingressos em <a href="https://www.festivaldorio.com.br/br/programacao" '
            f'target="_blank" rel="noopener">festivaldorio.com.br</a>.</p></div>')

def js(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

html = TEMPLATE.read_text(encoding="utf-8")
for marca, valor in (("/*__FILMES__*/[]", js(enxuga(filmes, CAMPOS_FILME))),
                     ("/*__SESSOES__*/[]", js(enxuga(sessoes, CAMPOS_SESSAO))),
                     ("/*__CORES__*/{}", js(cores)), ("/*__REGIOES__*/[]", js(regioes)),
                     ("__BETA__", beta), ("__SUB__", sub), ("__MES__", mes), ("__ANO__", str(ano))):
    assert marca in html, f"marca {marca} sumiu do template"
    html = html.replace(marca, valor)
SAIDA.write_text(html, encoding="utf-8")
if corrente:
    SAIDA_SITE.parent.mkdir(parents=True, exist_ok=True)
    SAIDA_SITE.write_text(html, encoding="utf-8")

print(f"OK: {SAIDA.name}{' + docs/index.html' if corrente else ''} — {len(filmes)} filmes, "
      f"{len(sessoes)} sessões, {len(cores)} mostras, {len(por_cinema)} cinemas em {len(regioes)} regiões, "
      f"{SAIDA.stat().st_size/1024:.0f} KB")
for r in regioes:
    print(f"   {r['rot']:<34} {r['ses']:>4} sessões · " + ", ".join(c['n'] for c in r['cinemas']))
