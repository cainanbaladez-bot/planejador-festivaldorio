# -*- coding: utf-8 -*-
"""Enriquece os filmes do Festival do Rio com (1) festivais/prêmios extraídos da sinopse
e (2) nota do Letterboxd (média + nº de votos), casando por título original + ano.

Copiado do Planejador da Mostra (SP) em 29/09/2026 — mesmo método; muda só de onde lê/grava.

Uso:  py -3.10 enrich_filmes.py            # roda tudo (Letterboxd ~10 min, com cache)
      py -3.10 enrich_filmes.py --so-festivais   # só a parte offline

Saída: data/rio_<ano>_enriquecimento.json  {filme_id: {festivais, premiado, premio_txt, lb_*}}
Cache Letterboxd: data/letterboxd_cache.json (por id de filme; ids do Rio são estáveis) (reexecutar não re-baixa o que já tem).
"""
import json, re, sys, time, unicodedata, urllib.request, urllib.parse, gzip, io
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
ANO = int(sys.argv[sys.argv.index("--ano") + 1]) if "--ano" in sys.argv else 2026
SAIDA = DATA / f"rio_{ANO}_enriquecimento.json"
CACHE = DATA / "letterboxd_cache.json"

# ─── festivais: padrão → nome canônico ───
FESTIVAIS = [
    (r"Cannes", "Cannes"),
    (r"Berlim|Berlinale", "Berlim"),
    (r"Veneza|Venice", "Veneza"),
    (r"Locarno", "Locarno"),
    (r"Toronto", "Toronto"),
    (r"Sundance", "Sundance"),
    (r"Roterd[ãa]", "Roterdã"),
    (r"San Sebasti[áa]n", "San Sebastián"),
    (r"Tribeca", "Tribeca"),
    (r"SXSW", "SXSW"),
    (r"Annecy", "Annecy"),
    (r"Karlovy Vary", "Karlovy Vary"),
    (r"Telluride", "Telluride"),
    (r"IDFA|Amsterd[ãa]", "IDFA"),
    (r"Visions du R[ée]el", "Visions du Réel"),
    (r"Hot Docs", "Hot Docs"),
    (r"Xangai", "Xangai"),
    (r"Busan", "Busan"),
    (r"Mar del Plata", "Mar del Plata"),
    (r"Guadalajara", "Guadalajara"),
    (r"Festival de Havana", "Havana"),
    (r"Gramado", "Gramado"),
    (r"Bras[íi]lia", "Brasília"),
    (r"[ÉE] Tudo Verdade", "É Tudo Verdade"),
    (r"Mostra Internacional de Cinema de S[ãa]o Paulo|Mostra de S[ãa]o Paulo", "Mostra SP"),
    (r"Cinema do Real", "Cinéma du Réel"),
    (r"Nova York", "Nova York"),
]
RE_PREMIO = re.compile(
    r"[Vv]encedor|[Gg]anhou|[Gg]anhador|[Pp]remiad[oa]|Palma de Ouro|Urso de Ouro|"
    r"Urso de Prata|Le[ãa]o de Ouro|Le[ãa]o de Prata|Concha de Ouro|Grande Pr[êe]mio|"
    r"Pr[êe]mio do J[úu]ri|Pr[êe]mio Especial|Melhor [A-ZÀ-Üa-zà-ü]+")
RE_FRASE = re.compile(r"[^.\n]*\.")

def festivais_da_sinopse(sinopse):
    fests, premio_txt = [], []
    for frase in RE_FRASE.findall(sinopse or ""):
        eh_premio = bool(RE_PREMIO.search(frase))
        citou = False
        for pat, nome in FESTIVAIS:
            if re.search(pat, frase):
                citou = True
                if nome not in fests:
                    fests.append(nome)
        if eh_premio and (citou or re.search(r"[Ff]estival|[Mm]ostra|[Pp]r[êe]mio", frase)):
            t = frase.strip()
            if t not in premio_txt:
                premio_txt.append(t)
    return fests, bool(premio_txt), " ".join(premio_txt[:2])

# ─── letterboxd ───
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip",
    "Referer": "https://letterboxd.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}

def http_get(url, extra=None):
    h = dict(HEADERS)
    if extra:
        h.update(extra)
    req = urllib.request.Request(url, headers=h)
    r = urllib.request.urlopen(req, timeout=25)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    return raw.decode("utf-8", "replace")

def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()

def sobrenomes(txt):
    outs = set()
    for nome in re.split(r",| e ", txt or ""):
        parts = norm(nome).split()
        if parts:
            outs.add(parts[-1])
    return outs

def busca_lb(titulo, ano, diretores):
    q = urllib.parse.quote(titulo)
    body = http_get(f"https://letterboxd.com/s/autocompletefilm?q={q}&limit=10",
                    {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
    cands = json.loads(body).get("data", [])
    try:
        ano_i = int(ano)
    except (TypeError, ValueError):
        ano_i = None
    dirs_mostra = sobrenomes(diretores)
    melhores = []
    for c in cands:
        ry = c.get("releaseYear")
        if ano_i and ry and abs(ry - ano_i) > 1:
            continue
        dirs_lb = set()
        for d in c.get("directors") or []:
            dirs_lb |= sobrenomes(d.get("name", ""))
        score = 0
        if ano_i and ry == ano_i:
            score += 2
        if dirs_mostra & dirs_lb:
            score += 3
        if norm(c.get("name")) == norm(titulo) or norm(c.get("originalName") or "") == norm(titulo):
            score += 2
        melhores.append((score, c))
    melhores.sort(key=lambda x: -x[0])
    if not melhores or melhores[0][0] < 2:   # exige pelo menos ano exato OU diretor
        return None
    return melhores[0][1]

def nota_lb(slug):
    html = http_get(f"https://letterboxd.com/film/{slug}/")
    m = re.search(r'<script type="application/ld\+json">\s*(?:/\*\s*<!\[CDATA\[\s*\*/)?\s*(\{.*?\})\s*(?:/\*\s*\]\]>\s*\*/)?\s*</script>', html, re.S)
    if not m:
        return None, None
    agg = json.loads(m.group(1)).get("aggregateRating") or {}
    return agg.get("ratingValue"), agg.get("ratingCount")

def main():
    so_fest = "--so-festivais" in sys.argv
    filmes = json.loads((DATA / f"rio_{ANO}_filmes.json").read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    out = {}
    pend = [f for f in filmes if f["id"] not in cache]
    print(f"{len(filmes)} filmes · {len(pend)} sem cache Letterboxd")

    for i, f in enumerate(filmes):
        fid = f["id"]
        fests, premiado, premio_txt = festivais_da_sinopse(f.get("sinopse"))
        reg = {"festivais": fests, "premiado": premiado, "premio_txt": premio_txt}

        if not so_fest:
            if fid in cache:
                reg.update(cache[fid])
            else:
                lb = {"lb_nota": None, "lb_votos": None, "lb_url": None}
                try:
                    titulo = f.get("titulo_original") or f.get("titulo")
                    c = busca_lb(titulo, f.get("ano"), f.get("diretores"))
                    if not c and f.get("titulo") and f.get("titulo") != titulo:
                        c = busca_lb(f["titulo"], f.get("ano"), f.get("diretores"))
                    if c:
                        nota, votos = nota_lb(c["slug"])
                        lb = {"lb_nota": nota, "lb_votos": votos,
                              "lb_url": "https://letterboxd.com" + c["url"]}
                    time.sleep(0.35)
                except Exception as e:
                    print(f"  ! {f.get('titulo')}: {e}")
                    time.sleep(2)
                cache[fid] = lb
                reg.update(lb)
                if len(cache) % 20 == 0:
                    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                    print(f"  … {i+1}/{len(filmes)} (cache salvo)")
        out[fid] = reg

    if not so_fest:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    com_nota = sum(1 for r in out.values() if r.get("lb_nota"))
    com_fest = sum(1 for r in out.values() if r["festivais"])
    print(f"OK: {SAIDA.name} — {com_fest} c/ festivais, {sum(1 for r in out.values() if r['premiado'])} premiados, {com_nota} c/ nota LB")

if __name__ == "__main__":
    main()
