# -*- coding: utf-8 -*-
"""scrape_rio.py — raspa a programação do Festival do Rio (festivaldorio.com.br).

O site é um app Inertia.js: cada página traz o JSON completo no atributo `data-page`.
  /br/filmes?page=N           -> lista (9 por página, props.elements + props.pagy)
  /br/filmes/<slug>           -> props.pelicula (ficha) + pelicula.programacoesAsJson (sessões)
  edições anteriores:         /br/edicoes-anteriores/<ano>/filmes...

Sessões (formato visto em 2025): lista de "programações", cada uma com 1+ salas:
  {"data": "Ter, 7 Out", "sessao": "21H45", "cinema_name": "Estação NET Gávea 5",
   "cinema_address": "...", "cinema_programacao_url": "/br/programacao?cinema[]=estacao-net-gavea",
   "ingresso_url_venda": ..., "program_tags": ["debate", "guest", "limited_gratuity"]}
Em 21/09/2026 a edição 2026 ainda NÃO publicou horários (programmingPublic=false,
programacoesAsJson=[]) — o raspador grava os filmes e 0 sessões; rodar de novo quando sair.

Saída (mesmo schema que o planejador.template.html usa, herdado do Planejador da Mostra):
  data/rio_<ano>_filmes.json · data/rio_<ano>_sessoes.json · data/rio_<ano>_meta.json

Uso:  py -3.10 scrape_rio.py            # edição corrente (2026)
      py -3.10 scrape_rio.py --ano 2025 # edição anterior (tem sessões — bom para testar)
"""
import sys, re, json, html, time, zlib, datetime, collections, urllib.request, urllib.error
from pathlib import Path

BASE = "https://www.festivaldorio.com.br"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
DATA = Path(__file__).parent / "data"
MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8,
         "set": 9, "out": 10, "nov": 11, "dez": 12}
TAGS = {"debate": "debate", "guest": "com convidados", "limited_gratuity": "gratuito (lugares limitados)",
        "gratuity": "gratuito", "free": "gratuito"}

ano = int(sys.argv[sys.argv.index("--ano") + 1]) if "--ano" in sys.argv else 2026
corrente = ano == 2026
LISTA = "/br/filmes" if corrente else f"/br/edicoes-anteriores/{ano}/filmes"


def pagina(path):
    for tent in range(4):
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
            txt = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
            m = re.search(r'data-page="([^"]*)"', txt)
            if not m:
                raise ValueError("sem data-page")
            time.sleep(0.25)                      # educado com o servidor
            return json.loads(html.unescape(m.group(1)))
        except Exception as e:
            if tent == 3 or getattr(e, "code", None) == 404:   # 404 não melhora tentando de novo
                raise
            print(f"   ! {path}: {e} — tentando de novo")
            time.sleep(2 + 3 * tent)


def id_estavel(texto):
    """id numérico estável (o link da agenda codifica ids em base 36)."""
    return str(zlib.crc32(texto.encode("utf-8")) % 9_000_000 + 1_000_000)


def data_iso(txt):                                 # "Ter, 7 Out" -> "2025-10-07"
    m = re.search(r"(\d{1,2})\s+([A-Za-zçÇ]{3})", txt)
    return f"{ano}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def hora(txt):                                     # "21H45" -> "21:45"
    m = re.search(r"(\d{1,2})\s*[Hh:]\s*(\d{2})", txt)
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def cinema_base(c):
    """'Estação NET Gávea 5' -> 'Estação NET Gávea' (sala numerada no fim)."""
    return re.sub(r"\s+\d+[A-Z]?$", "", c.strip())


# Siglas que o .title() estragava ("Rodrigo Monte, Abc"): associações de fotografia/montagem,
# TV, DJ/MC e algarismos romanos ficam em maiúsculas.
SIGLAS = {"ABC", "AMC", "AFC", "ASC", "BSC", "AIC", "CSC", "SBC", "EDT", "ACE", "TV", "DJ", "MC",
          "EPP", "ME", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}


def nome_proprio(x):
    """'RODRIGO MONTE, ABC' -> 'Rodrigo Monte, ABC' (só mexe em texto todo em maiúsculas)."""
    if not x.isupper():
        return x
    return re.sub(r"[^\W\d_]+",
                  lambda m: m.group(0) if m.group(0) in SIGLAS else m.group(0).capitalize(), x)


def junta(v):
    if isinstance(v, list):
        return ", ".join(nome_proprio(x) for x in v)
    return v or ""


def minutos(p):
    return f"{p.get('duracao_coord_int')} min." if p.get("duracao_coord_int") else ""


# 1) lista de filmes
p1 = pagina(LISTA)["props"]
n_pag = p1["pagy"]["pages"]
urls = []
for n in range(1, n_pag + 1):
    props = p1 if n == 1 else pagina(f"{LISTA}?page={n}")["props"]
    urls += [e["url"] for e in props["elements"]]
    print(f"[lista] página {n}/{n_pag} — {len(urls)} filmes", end="\r")
urls = list(dict.fromkeys(urls))
print(f"\n[lista] {len(urls)} filmes únicos ({ano})")

# 1b) a grade (/br/programacao) tem programas que não estão na lista de filmes
# (ex.: "The Story of Documentary Film", 2026). A paginação é cumulativa: a última página
# traz tudo. Sessão sem filme ("/br/filmes/") não tem ficha e fica de fora.
grade = collections.defaultdict(list)             # url do filme -> sessões na grade
if corrente:
    pr = pagina("/br/programacao")["props"]
    ult = (pr.get("pagy") or {}).get("last") or 1
    if ult > 1:
        pr = pagina(f"/br/programacao?page={ult}")["props"]
    vistos, orfas = set(), []
    base = lambda t: re.sub(r"\s-\s*Programa\b.*$", "", t or "").strip().lower()
    for g in pr.get("elements") or []:
        for s in g.get("sessions") or []:
            if s.get("id") in vistos:
                continue
            vistos.add(s.get("id"))
            u = s.get("pelicula_url") or ""
            (orfas.append(s) if u.rstrip("/") in ("", "/br/filmes") else grade[u].append(s))
    # sessão sem link ("The Story of Documentary Film - Programa I"): liga ao filme de mesmo título-base
    por_titulo = {base(ss[0]["titulo"]): u for u, ss in grade.items()}
    for s in orfas:
        if base(s["titulo"]) in por_titulo:
            grade[por_titulo[base(s["titulo"])]].append(s)
        else:
            print(f"   ! sessão sem filme na grade, ignorada: {s['titulo']} {s['data']} {s['sessao']}")
    extras = [u for u in grade if u not in urls]
    urls += extras
    print(f"[grade] +{len(extras)} fora da lista de filmes: {', '.join(extras) or '—'}")


def ficha_da_grade(progs):
    """Ficha mínima montada da grade, para filme cuja página dá 404 no site.
    Programas em partes ("X - Programa I/II/III") viram um filme só; a parte vai na sessão."""
    t0 = progs[0]
    partes = sorted({m.group(1) for s in progs if (m := re.search(r"\s-\s*(Programa\b.*)$", s["titulo"]))})
    nota = (f"Exibido em {len(partes)} programas ({', '.join(partes)}) — o nome do programa aparece em cada "
            f"sessão. " if partes else "")
    return {
        "display_titulo": re.sub(r"\s-\s*Programa\b.*$", "", t0["titulo"]),
        "display_sinopse": nota + "A página deste filme está fora do ar no site do festival; "
                                  "os dados aqui vêm da grade de programação.",
        "genre": t0.get("genero", ""), "display_paises": t0.get("paises", ""),
        "duracao_coord_int": t0.get("duracao"), "mostra_name": t0.get("mostra", ""),
        "mostra_display_name": t0.get("mostra", ""), "poster_image": t0.get("card_image"),
        "programacoesAsJson": [[{
            "data": s["date_label"], "sessao": s["sessao"][0], "cinema_name": s["cinema"],
            "program_tags": ([m.group(1)] if (m := re.search(r"\s-\s*(Programa\b.*)$", s["titulo"])) else [])
                            + list(s.get("program_tags") or []),
        }] for s in progs],
    }


# 2) ficha + sessões de cada filme
filmes, sessoes, publico = [], [], False
for i, url in enumerate(urls, 1):
    try:
        props = pagina(url)["props"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        if not grade.get(url):
            print(f"\n   ! {url}: 404 e fora da grade — filme ignorado")
            continue
        print(f"\n   ! {url}: 404 — ficha montada a partir da grade ({len(grade[url])} sessões)")
        props = {"programmingPublic": True, "pelicula": ficha_da_grade(grade[url])}
    publico = publico or bool(props.get("programmingPublic"))
    p = props["pelicula"]
    slug = url.rstrip("/").split("/")[-1]
    fid = id_estavel(f"{ano}/{slug}")
    teams = p.get("teams") or {}
    trailer = p.get("youtube_link_trailer") or p.get("vimeo_link_trailer") or ""
    n_ses = 0
    for prog in p.get("programacoesAsJson") or []:
        for s in (prog if isinstance(prog, list) else [prog]):
            d, h, sala = data_iso(s["data"]), hora(s["sessao"]), s.get("cinema_name", "")
            tags = ", ".join(TAGS.get(t, t) for t in (s.get("program_tags") or []))
            sessoes.append({
                "sessao_id": id_estavel(f"{ano}/{slug}/{d}/{h}/{sala}"), "filme_id": fid,
                "filme_slug": slug, "titulo": p.get("display_titulo", ""),
                "data": d, "hora": h, "sala": sala, "cinema": cinema_base(sala),
                "endereco_cinema": s.get("cinema_address", ""), "idioma": "",
                "legendas": tags, "secao": p.get("mostra_name", ""), "duracao": minutos(p),
                "link_compra": s.get("ingresso_url_venda") or "",
            })
            n_ses += 1
    filmes.append({
        "id": fid, "slug": slug, "url_pagina": BASE + url,
        "titulo": p.get("display_titulo", ""),
        "titulo_original": p.get("titulo_ingles_coord_int", "") or "",
        "sinopse": p.get("display_sinopse", "") or "",
        "genero": p.get("genre", "") or "", "pais": p.get("display_paises", "") or "",
        "ano": str(p.get("ano_coord_int") or ""), "duracao": minutos(p),
        "secao": p.get("mostra_name", "") or "", "mostra": p.get("mostra_display_name", "") or "",
        "classificacao": "",
        "diretores": p.get("diretor_coord_int", "") or junta(teams.get("Direção")),
        "elenco": p.get("elenco_coord_int", "") or "",
        "roteiro": junta(teams.get("Roteiro")), "fotografia": junta(teams.get("Fotografia")),
        "montagem": junta(teams.get("Montagem")), "musica": junta(teams.get("Música")),
        "producao": junta(teams.get("Empresa Produtora")), "distribuicao": "",
        "imagem": (p.get("poster_image") or {}).get("src") or (p.get("banner_image") or {}).get("src", ""),
        "trailer": trailer, "link_compra": "", "n_sessoes": str(n_ses),
    })
    print(f"[filmes] {i}/{len(urls)} — {len(sessoes)} sessões", end="\r")

# fichas montadas da grade não trazem endereço: usa o de outra sessão no mesmo cinema
endereco = {s["cinema"]: s["endereco_cinema"] for s in sessoes if s["endereco_cinema"]}
for s in sessoes:
    s["endereco_cinema"] = s["endereco_cinema"] or endereco.get(s["cinema"], "")

DATA.mkdir(exist_ok=True)
(DATA / f"rio_{ano}_filmes.json").write_text(json.dumps(filmes, ensure_ascii=False, indent=1), encoding="utf-8")
(DATA / f"rio_{ano}_sessoes.json").write_text(json.dumps(sessoes, ensure_ascii=False, indent=1), encoding="utf-8")
datas = sorted({s["data"] for s in sessoes})
meta = {"ano": ano, "raspado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "filmes": len(filmes), "sessoes": len(sessoes), "programacao_publica": publico,
        "primeiro_dia": datas[0] if datas else None, "ultimo_dia": datas[-1] if datas else None,
        "cinemas": sorted({s["cinema"] for s in sessoes})}
(DATA / f"rio_{ano}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
assert len({f["id"] for f in filmes}) == len(filmes), "colisão de id de filme"
assert len({s["sessao_id"] for s in sessoes}) == len(sessoes), "colisão de id de sessão"
print(f"\nOK {ano}: {len(filmes)} filmes, {len(sessoes)} sessões, horários públicos={publico}, "
      f"{meta['primeiro_dia']}..{meta['ultimo_dia']}, {len(meta['cinemas'])} cinemas")
