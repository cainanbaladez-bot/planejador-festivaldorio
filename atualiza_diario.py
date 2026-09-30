# -*- coding: utf-8 -*-
"""atualiza_diario.py — atualização diária da programação (Tarefa do Windows).

Criado em 29/09/2026: o festival segue remarcando e acrescentando sessões até o fim,
e a raspagem era manual. A tarefa "PlanejadorRio-Atualiza" roda isto todo dia.

Passos:  raspa → confere se veio inteiro → enriquece (festivais + Letterboxd) →
         se algo mudou: sobe o VERSAO do sw.js → build → teste → commit [→ push]

Travas (qualquer uma para tudo e devolve os dados de antes):
  · a raspagem falhou, ou veio com a grade fechada (programacao_publica = false);
  · caiu mais de 10% dos filmes ou 20% das sessões de um dia para o outro — site do
    festival fora do ar pela metade não pode virar programação publicada;
  · o teste automático (tests/planner-smoke.js) não passa.
Se nada mudou no site do festival, não faz build nem commit.

PUBLICAR = False: commita, mas o push fica com o Cainan (GitHub Desktop → Push origin).
Com True, publica sozinho (o push funciona pelo terminal desde 29/09/2026: credential
helper "store").

Log: data/atualizacao.log (fora do git). Rodar à mão: py -3.10 atualiza_diario.py
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PUBLICAR = False

BASE = Path(__file__).parent
DATA = BASE / "data"
LOG = DATA / "atualizacao.log"
ANO = 2026
ARQS = [DATA / f"rio_{ANO}_{n}.json" for n in ("filmes", "sessoes", "meta", "enriquecimento", "historico")]
PY = ["py", "-3.10"]          # a tarefa chama com pyw (sem janela); os passos, com py
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(msg):
    linha = f"[{dt.datetime.now():%d/%m/%Y %H:%M:%S}] {msg}"
    try:
        print(linha)
    except Exception:
        pass
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(linha + "\n")


def roda(cmd, timeout=1800):
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout,
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
                       creationflags=SEM_JANELA)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def carrega(nome):
    p = DATA / f"rio_{ANO}_{nome}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    backup = DATA / "_antes_da_atualizacao"
    backup.mkdir(exist_ok=True)
    for a in ARQS:
        if a.exists():
            shutil.copy2(a, backup / a.name)

    def desfaz(motivo):
        for a in ARQS:
            b = backup / a.name
            if b.exists():
                shutil.copy2(b, a)
        log(f"PAROU: {motivo} — dados de antes restaurados, nada publicado")
        return 1

    filmes0, sessoes0 = carrega("filmes") or [], carrega("sessoes") or []

    cod, saida = roda(PY + ["scrape_rio.py"])
    if cod != 0:
        return desfaz("a raspagem falhou: " + saida.strip().splitlines()[-1][:200] if saida.strip() else "a raspagem falhou")
    filmes, sessoes, meta = carrega("filmes"), carrega("sessoes"), carrega("meta")
    if not meta or not meta.get("programacao_publica"):
        return desfaz("o site voltou com a grade fechada")
    if len(filmes) < 0.9 * len(filmes0) or len(sessoes) < 0.8 * len(sessoes0):
        return desfaz(f"raspagem incompleta: {len(filmes0)}→{len(filmes)} filmes, "
                      f"{len(sessoes0)}→{len(sessoes)} sessões")

    chave = lambda s: (s["sessao_id"], s["data"], s["hora"], s["sala"])
    mudou_grade = sorted(map(chave, sessoes)) != sorted(map(chave, sessoes0))
    sem_data = lambda fs: sorted(json.dumps(f, sort_keys=True, ensure_ascii=False) for f in fs)
    mudou_filmes = sem_data(filmes) != sem_data(filmes0)
    if not (mudou_grade or mudou_filmes):
        # o meta tem a hora da raspagem; sem mudança, volta o de antes (a faixa ATUALIZADO
        # do site continua dizendo a hora da última versão publicada, que é a verdade)
        shutil.copy2(backup / f"rio_{ANO}_meta.json", DATA / f"rio_{ANO}_meta.json")
        log(f"sem mudança no site do festival ({len(filmes)} filmes, {len(sessoes)} sessões)")
        return 0

    cod, saida = roda(PY + ["enrich_filmes.py"], timeout=3600)
    if cod != 0:
        log("aviso: enriquecimento falhou, segue com o anterior — " + saida.strip()[-200:])

    sw = BASE / "docs" / "sw.js"
    t = sw.read_text(encoding="utf-8")
    m = re.search(r'const VERSAO = "rio-v(\d+)";', t)
    if not m:
        return desfaz("não achei o VERSAO no docs/sw.js")
    nova = f"rio-v{int(m.group(1)) + 1}"
    sw_antes = t
    sw.write_text(t.replace(m.group(0), f'const VERSAO = "{nova}";'), encoding="utf-8")

    cod, saida = roda(PY + ["build_planejador.py"])
    if cod != 0:
        sw.write_text(sw_antes, encoding="utf-8")
        return desfaz("o build falhou: " + saida.strip()[-200:])
    cod, saida = roda(["node", "tests/planner-smoke.js"])
    if cod != 0:
        sw.write_text(sw_antes, encoding="utf-8")
        roda(["git", "checkout", "--", "docs/index.html"])
        return desfaz("o teste falhou: " + saida.strip()[-300:])

    novas = len({s["sessao_id"] for s in sessoes} - {s["sessao_id"] for s in sessoes0})
    sumiram = len({s["sessao_id"] for s in sessoes0} - {s["sessao_id"] for s in sessoes})
    resumo = (f"{len(filmes)} filmes ({len(filmes) - len(filmes0):+d}), {len(sessoes)} sessões; "
              f"{novas} sessões novas ou remarcadas, {sumiram} sumiram ou mudaram")
    hoje = dt.date.today().strftime("%d/%m")
    msg = (f"Programação de {hoje} (atualização automática)\n\n{resumo}.\n"
           f"Service worker {nova}.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
    roda(["git", "add", "-A"])
    cod, saida = roda(["git", "-c", "core.safecrlf=false", "commit", "-q", "-m", msg])
    if cod != 0:
        log("commit falhou: " + saida.strip()[-200:])
        return 1
    log(f"commit feito — {resumo} — {nova}")

    if PUBLICAR:
        cod, saida = roda(["git", "push", "origin", "main"], timeout=300)
        log("publicado (push ok)" if cod == 0 else "push FALHOU: " + saida.strip()[-200:])
    else:
        log("pronto para publicar: falta o Push origin no GitHub Desktop")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # a tarefa roda sem console: tudo que der errado vai para o log
        log(f"ERRO inesperado: {e!r}")
        sys.exit(1)
