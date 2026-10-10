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
    (r"Jerusal[ée]m", "Jerusalém"),
    (r"Gotemburgo", "Gotemburgo"),
    (r"T[óo]quio", "Tóquio"),
    (r"Crac[óo]via", "Cracóvia"),
    (r"Clermont-Ferrand", "Clermont-Ferrand"),
]
# Regra apertada em 09/10/2026 (pedido do Cainan: usar SÓ o que o próprio festival diz).
# Antes, qualquer frase com "vencedor"/"Melhor X" + "festival/prêmio" contava: entrava enredo
# ("vencedor do Prêmio Nobel", "arquiteto vencedor do Pritzker", "ao Festival Melhor Dia").
# Agora: (1) frase = até . ? ou ! (pergunta de enredo não gruda no prêmio);
# (2) festival só conta em frase que fala de festival (palavra de contexto) — cidade citada no
#     enredo (Brasília, Veneza, Nova York...) não vira festival;
# (3) prêmio só conta se a frase tem marca de prêmio E cita um festival da lista ou a palavra
#     Festival/Mostra — "Prêmio Nobel" sozinho não passa; "Melhor X" só com categoria de cinema.
RE_PREMIO = re.compile(
    r"\b(vencedor|vencedora|venceu|ganhou|ganhador|ganhadora|premiad[oa]s?|recebeu|levou|"
    r"pr[êe]mios?|award|palma de ouro|urso de (ouro|prata|cristal)|le[ãa]o de (ouro|prata)|"
    r"concha de (ouro|prata)|leopardo de ouro|tigre|men[çc][ãa]o (especial|honrosa)|kikito|"
    r"melhor (filme|longa|curta|dire[çc][ãa]o|diretor|diretora|ator|atriz|roteiro|document[áa]rio|"
    r"fotografia|montagem|atua[çc][ãa]o|interpreta[çc][ãa]o|elenco|anima[çc][ãa]o|som|trilha))\b", re.I)
RE_CONTEXTO = re.compile(
    r"\b(festival|festivais|mostra|berlinale|competi[çc][ãa]o|sele[çc][ãa]o oficial|estreia|estreou|"
    r"exibido|exibida|premi|vencedor|vencedora|pr[êe]mio|urso|le[ãa]o|palma|concha|leopardo|"
    r"un certain regard|um certo olhar|quinzena|semana da cr[íi]tica|orizzonti|panorama|f[óo]rum|"
    r"generation|cineastas do presente|world cinema|sundance|tribeca|sxsw|idfa|hot docs)", re.I)
# não é prêmio DO FILME: prêmio de pessoa fora do cinema, ou homenagem da própria Mostra a
# um cineasta ("Paulo Branco recebe o Prêmio Leon Cakoff nesta 50ª Mostra")
RE_NAO_FILME = re.compile(r"\b(nobel|pritzker|jabuti|pulitzer|grammy|leon cakoff|pr[êe]mio humanidade|homenag\w*)\b|\bnesta \d+ª mostra", re.I)
RE_FRASE = re.compile(r"[^.?!\n]*[.?!]")

def festivais_da_sinopse(sinopse):
    fests, premio_txt = [], []
    for frase in RE_FRASE.findall(sinopse or ""):
        if not RE_CONTEXTO.search(frase):
            continue
        citou = False
        for pat, nome in FESTIVAIS:
            if re.search(pat, frase):
                citou = True
                if nome not in fests:
                    fests.append(nome)
        eh_premio = bool(RE_PREMIO.search(frase)) and not RE_NAO_FILME.search(frase)
        if eh_premio and (citou or re.search(r"\b(festival|mostra)\b", frase, re.I)):
            t = frase.strip()
            if t not in premio_txt:
                premio_txt.append(t)
    return fests, bool(premio_txt), " ".join(premio_txt[:2])

def festival_do_premio(premio_txt):
    """Festival que deu o prêmio: o 1º citado DEPOIS da 1ª marca de prêmio da frase
    ("Estreia em Berlim, prêmio de melhor filme em Jerusalém" = Jerusalém); se nenhum vem
    depois, o último citado antes ("estreia em Berlim, onde X recebeu o Urso" = Berlim)."""
    m = RE_PREMIO.search(premio_txt or "")
    if not m:
        return None
    pos = sorted((x.start(), nome) for pat, nome in FESTIVAIS for x in re.finditer(pat, premio_txt))
    depois = [n for p, n in pos if p >= m.start()]
    antes = [n for p, n in pos if p < m.start()]
    return depois[0] if depois else (antes[-1] if antes else None)

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

def histograma_lb(slug):
    """As 10 contagens do gráfico de notas do Letterboxd, de meia estrela a ★★★★★ (09/10/2026).
    Cada barra vem como title="12,645 ★★★★ ratings (35%)"; faixa sem nota não vem → 0."""
    html = http_get(f"https://letterboxd.com/csi/film/{slug}/rating-histogram/")
    faixas = ["half-★", "★", "★½", "★★", "★★½", "★★★", "★★★½", "★★★★", "★★★★½", "★★★★★"]
    achou = {lab: int(n.replace(",", "")) for n, lab in
             re.findall(r'title="([\d,]+)\s+(half-★|★+½?)\s+ratings?', html)}
    return [achou.get(f, 0) for f in faixas] if achou else None

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
        reg = {"festivais": fests, "premiado": premiado, "premio_txt": premio_txt,
               "premio_fest": festival_do_premio(premio_txt)}

        if not so_fest:
            if fid in cache:
                # histograma de notas (09/10/2026): busca só o que ainda não tem
                c = cache[fid]
                if c.get("lb_url") and "lb_hist" not in c:
                    try:
                        c["lb_hist"] = histograma_lb(c["lb_url"].rstrip("/").split("/film/")[1])
                    except Exception as e:
                        print(f"  ! histograma {f.get('titulo')}: {e}")
                    time.sleep(0.4)
                    if sum(1 for x in cache.values() if "lb_hist" in x) % 20 == 0:
                        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                reg.update(c)
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
