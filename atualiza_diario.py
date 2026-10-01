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

PUBLICAR = True (desde 29/09/2026, a pedido do Cainan): publica sozinho — o push funciona
pelo terminal (credential helper "store"). Com False, só commita e o push fica no GitHub
Desktop (Push origin).

Log: data/atualizacao.log (fora do git). Rodar à mão: py -3.10 atualiza_diario.py
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PUBLICAR = True

BASE = Path(__file__).parent
DATA = BASE / "data"
LOG = DATA / "atualizacao.log"
ANO = 2026
ARQS = [DATA / f"rio_{ANO}_{n}.json" for n in ("filmes", "sessoes", "meta", "enriquecimento", "historico")]
ARQS += [DATA / "letterboxd_cache.json", BASE / "docs" / "index.html",
         BASE / "docs" / "sw.js", BASE / "planejador.html"]
VERSIONADOS = [str(p.relative_to(BASE)) for p in ARQS if p.name != "planejador.html"]
PENDENTE = DATA / "_push_pendente.json"
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


def validar(filmes, sessoes):
    import re as _re
    if not isinstance(filmes, list) or not isinstance(sessoes, list) or not filmes or not sessoes:
        raise ValueError("catálogo ou sessões vazios")
    ids = {f["id"] for f in filmes}
    if len(ids) != len(filmes) or len({s["sessao_id"] for s in sessoes}) != len(sessoes):
        raise ValueError("IDs duplicados")
    for s in sessoes:
        if s["filme_id"] not in ids:
            raise ValueError("sessão sem filme")
        dia = dt.date.fromisoformat(s["data"])
        if dia.year != ANO:
            raise ValueError("sessão fora da edição")
        if not _re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", s["hora"]):
            raise ValueError("hora inválida")
        dur = _re.fullmatch(r"(\d+)\s*min\.?", s.get("duracao", ""))
        if not dur or not 1 <= int(dur.group(1)) <= 600:
            raise ValueError("duração inválida")
    return True


def main():
    cod, branch = roda(["git", "branch", "--show-current"])
    if cod or (branch.strip() != "main" and "--dry-run" not in sys.argv):
        log("PAROU: atualização automática exige a branch main")
        return 1
    cod, estado = roda(["git", "status", "--porcelain", "--untracked-files=normal"])
    if cod or estado.strip():
        log("PAROU: checkout contém alterações; trabalho manual preservado")
        return 1
    if PENDENTE.exists():
        marca = json.loads(PENDENTE.read_text(encoding="utf-8"))
        cod, head = roda(["git", "rev-parse", "HEAD"])
        if cod or head.strip() != marca.get("sha"):
            log("PAROU: push pendente pertence a outro commit; revisão manual necessária")
            return 1
        cod, saida = roda(["git", "push", "origin", "main"], timeout=300)
        if cod:
            log("push pendente ainda falhou: " + saida.strip()[-200:])
            return 1
        PENDENTE.unlink()
        log("push pendente concluído")
    backup = DATA / "_antes_da_atualizacao"
    backup.mkdir(exist_ok=True)
    for a in ARQS:
        b = backup / a.name
        if a.exists():
            shutil.copy2(a, b)
        elif b.exists():
            b.unlink()

    def desfaz(motivo, status=1):
        for a in ARQS:
            b = backup / a.name
            if b.exists():
                shutil.copy2(b, a)
            elif a.exists():
                a.unlink()
        log(f"{'PAROU' if status else 'VERIFICADO'}: {motivo} — dados de antes restaurados, nada publicado")
        return status

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
    try:
        validar(filmes, sessoes)
    except (ValueError, KeyError, TypeError) as exc:
        return desfaz("dados inconsistentes: " + str(exc))

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
    sw.write_text(t.replace(m.group(0), f'const VERSAO = "{nova}";'), encoding="utf-8")

    cod, saida = roda(PY + ["build_planejador.py"])
    if cod != 0:
        return desfaz("o build falhou: " + saida.strip()[-200:])
    if any(m in (BASE / "docs" / "index.html").read_text(encoding="utf-8")
           for m in ("/*__FILMES__*/[]", "/*__SESSOES__*/[]", "__ANO__")):
        return desfaz("o build deixou marcas não substituídas")
    cod, saida = roda(["node", "tests/planner-smoke.js"])
    if cod != 0:
        return desfaz("o teste falhou: " + saida.strip()[-300:])
    if "--dry-run" in sys.argv:
        return desfaz(f"dry-run: {len(filmes)} filmes, {len(sessoes)} sessões; testes passaram", 0)

    novas = len({s["sessao_id"] for s in sessoes} - {s["sessao_id"] for s in sessoes0})
    sumiram = len({s["sessao_id"] for s in sessoes0} - {s["sessao_id"] for s in sessoes})
    resumo = (f"{len(filmes)} filmes ({len(filmes) - len(filmes0):+d}), {len(sessoes)} sessões; "
              f"{novas} sessões novas ou remarcadas, {sumiram} sumiram ou mudaram")
    hoje = dt.date.today().strftime("%d/%m")
    msg = (f"Programação de {hoje} (atualização automática)\n\n{resumo}.\n"
           f"Service worker {nova}.\n")
    cod, estado = roda(["git", "status", "--porcelain", "--untracked-files=normal"])
    alterados = {linha[3:].replace("\\", "/") for linha in estado.splitlines() if len(linha) >= 4}
    if cod or not alterados.issubset(set(VERSIONADOS)):
        # diz quais — em 01/10/2026 parou sem dizer e não deu para saber o porquê
        fora = sorted(alterados - set(VERSIONADOS))
        return desfaz("arquivos inesperados mudaram durante a atualização: " + ", ".join(fora)[:300])
    cod, saida = roda(["git", "add", "--", *VERSIONADOS])
    if cod:
        return desfaz("git add falhou: " + saida.strip()[-200:])
    cod, saida = roda(["git", "-c", "core.safecrlf=false", "commit", "-q", "-m", msg])
    if cod != 0:
        roda(["git", "restore", "--staged", "--", *VERSIONADOS])
        return desfaz("commit falhou: " + saida.strip()[-200:])
    log(f"commit feito — {resumo} — {nova}")

    if PUBLICAR:
        cod, saida = roda(["git", "push", "origin", "main"], timeout=300)
        log("publicado (push ok)" if cod == 0 else "push FALHOU: " + saida.strip()[-200:])
        if cod:
            _, head = roda(["git", "rev-parse", "HEAD"])
            PENDENTE.write_text(json.dumps({"sha": head.strip()}), encoding="utf-8")
            return 1
    else:
        log("pronto para publicar: falta o Push origin no GitHub Desktop")
    return 0


if __name__ == "__main__":
    import msvcrt
    trava = Path(tempfile.gettempdir()) / "planejador-rio-atualiza.lock"
    arquivo = trava.open("a+b")
    arquivo.seek(0)
    if not arquivo.read(1):
        arquivo.write(b"1")
        arquivo.flush()
    arquivo.seek(0)
    try:
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        log("PAROU: outra atualização está em andamento")
        sys.exit(1)
    try:
        sys.exit(main())
    except Exception as e:  # a tarefa roda sem console: tudo que der errado vai para o log
        log(f"ERRO inesperado: {e!r}")
        sys.exit(1)
    finally:
        arquivo.seek(0)
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
        arquivo.close()
