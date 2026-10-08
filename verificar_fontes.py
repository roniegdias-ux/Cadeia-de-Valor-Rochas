#!/usr/bin/env python3
"""
verificar_fontes.py — matriz de acesso. Roda ANTES de qualquer coleta e
sempre que uma fonte começar a falhar.

Lê fontes/candidatas.json, testa cada fonte pela rede real e grava:
  fontes/confirmadas.json            — o que os coletores podem usar
  fontes/matriz-acesso-AAAA-MM-DD.md — toda célula com HTTP; falha é dita

Regras herdadas da matriz do inteligencia-midia:
  - nenhuma URL é inventada: só a do catálogo ou a anunciada pela própria home
    (<link rel="alternate" type="application/rss+xml">);
  - candidatas.json nunca é editado por este script;
  - 403/407 vindos do proxy de agente são política do ambiente, não da fonte:
    a matriz diz isso em vez de condenar a fonte.

Uso: python3 verificar_fontes.py [--trilha noticias|biblio|dados]
"""

import argparse
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import rede

CAND = "fontes/candidatas.json"
CONF = "fontes/confirmadas.json"
LINK_ALT = re.compile(
    r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', re.I)
HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def autodescobrir(home):
    cod, corpo, erro, _ = rede.buscar(home, tentativas=2)
    if erro:
        return None, f"home HTTP {cod} ({erro})"
    html = corpo[:300000].decode("utf-8", "replace")
    for tag in LINK_ALT.findall(html):
        h = HREF.search(tag)
        if h and "comments" not in h.group(1):
            return urllib.parse.urljoin(home, h.group(1)), f"home {cod}; feed anunciado"
    return None, f"home {cod}; nenhum feed anunciado"


def testar_rss(f):
    tentativas = [u for u in [f.get("url_teste")] if u]
    nota = []
    for url in tentativas:
        cod, corpo, erro, _ = rede.buscar(url)
        if not erro:
            try:
                itens = rede.extrair_itens(corpo)
                datados = sum(1 for i in itens if rede.parse_data(i["data_bruta"]))
                if not datados:   # XML válido mas sem item datado: não alimenta nada
                    nota.append(f"{url}: 200, {len(itens)} itens, {datados} com data (feed vazio)")
                    continue
                return {"veredito": "COLETAVEL", "url": url, "http": cod,
                        "detalhe": f"{len(itens)} itens, {datados} com data"}
            except ValueError as e:
                nota.append(f"{url}: 200 mas {e}")
        else:
            nota.append(f"{url}: HTTP {cod} ({erro})")
    if f.get("url_home"):
        achado, msg = autodescobrir(f["url_home"])
        nota.append(msg)
        if achado:
            cod, corpo, erro, _ = rede.buscar(achado)
            if not erro:
                try:
                    itens = rede.extrair_itens(corpo)
                    if not any(rede.parse_data(i["data_bruta"]) for i in itens):
                        raise ValueError("feed anunciado sem item datado")
                    return {"veredito": "COLETAVEL", "url": achado, "http": cod,
                            "detalhe": f"descoberto pela home; {len(itens)} itens"}
                except ValueError as e:
                    nota.append(f"{achado}: {e}")
            else:
                nota.append(f"{achado}: HTTP {cod} ({erro})")
    return {"veredito": "FALHOU", "url": None, "http": None, "detalhe": " | ".join(nota) or "sem URL"}


def testar_api(f):
    cod, corpo, erro, n = rede.buscar(f["url_teste"], ua=rede.UA_API)
    if erro:
        return {"veredito": "FALHOU", "url": f["url_teste"], "http": cod, "detalhe": f"{erro} ({n} tent.)"}
    try:
        json.loads(corpo)
        return {"veredito": "COLETAVEL", "url": f["url_teste"], "http": cod, "detalhe": f"JSON {len(corpo)} B"}
    except ValueError:
        return {"veredito": "FALHOU", "url": f["url_teste"], "http": cod,
                "detalhe": rede.rotular_nao_esperado(corpo, "200 mas não-JSON")}


def testar_csv(f):
    # Só os primeiros bytes: o arquivo da CFEM tem centenas de MB.
    cod, corpo, erro, _ = rede.buscar(f["url_teste"], cabecalhos={"Range": "bytes=0-4000"})
    if erro:
        return {"veredito": "FALHOU", "url": f["url_teste"], "http": cod, "detalhe": erro}
    cabeca = corpo.decode("latin-1", "replace").splitlines()[:1]
    return {"veredito": "COLETAVEL", "url": f["url_teste"], "http": cod,
            "detalhe": f"cabeçalho: {cabeca[0][:200] if cabeca else '(vazio)'}"}


def testar(f):
    if f["veredito"] in ("A_LOCALIZAR", "PAGO") or not (f.get("url_teste") or f.get("url_home")):
        return {"veredito": f["veredito"], "url": None, "http": None, "detalhe": "não testável automaticamente"}
    r = {"rss": testar_rss, "api": testar_api, "csv": testar_csv}[f["tipo"]](f)
    if r["veredito"] == "FALHOU" and re.search(r"Tunnel connection failed: 40[37]|CONNECT.*40[37]", r["detalhe"] or ""):
        r["veredito"] = "BLOQUEADO_AMBIENTE"
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trilha")
    a = p.parse_args()
    cand = [f for f in rede.ler_json(CAND) if not a.trilha or f["trilha"] == a.trilha]
    agora = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(testar, cand))

    conf = {c["id"]: c for c in rede.ler_json(CONF, [])}
    linhas = []
    for f, r in zip(cand, res):
        conf[f["id"]] = {"id": f["id"], "trilha": f["trilha"], "tipo": f["tipo"], "nome": f["nome"],
                         "veredito": r["veredito"], "url": r["url"], "testado_em": agora.isoformat()}
        linhas.append(f"| {f['nome']} | {f['trilha']} | {f['tipo']} | {r['http'] or '—'} | "
                      f"**{r['veredito']}** | {r['url'] or '—'} | {(r['detalhe'] or '').replace('|', '/')[:220]} |")
    rede.gravar_json(CONF, sorted(conf.values(), key=lambda x: (x["trilha"], x["id"])))

    bloq = sum(r["veredito"] == "BLOQUEADO_AMBIENTE" for r in res)
    md = [f"# Matriz de acesso — {agora:%Y-%m-%d}", "",
          f"Instante: `{agora.isoformat(timespec='seconds')}`. {len(cand)} fontes testadas.", ""]
    if bloq:
        md += [f"> **{bloq} fontes recusadas pelo proxy do ambiente (403/407 no CONNECT).** "
               "Isso é política de rede da sessão, não da fonte. Liberar a rede e rodar de novo.", ""]
    md += ["| Fonte | Trilha | Tipo | HTTP | Veredito | URL usada | Detalhe |",
           "|---|---|---|---|---|---|---|"] + linhas
    destino = f"fontes/matriz-acesso-{agora:%Y-%m-%d}.md"
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    ok = sum(r["veredito"] == "COLETAVEL" for r in res)
    print(f"{destino}: {ok}/{len(cand)} coletáveis, {bloq} bloqueadas pelo ambiente.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
