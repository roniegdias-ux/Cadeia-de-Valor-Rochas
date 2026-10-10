#!/usr/bin/env python3
"""
retro_sites.py — etapa 1 da coleta retroativa: acervo completo dos sites do setor.

Sites em WordPress expõem todo o histórico em /wp-json/wp/v2/posts. Para cada
site do config (retro.sites_wp) baixa título, data, link e texto de TODOS os
posts (ou só os que casam com `busca`, em veículo generalista), aplica o filtro
de relevância de cadeia.py e grava:

  noticias/retro/sites/<id>.jsonl   — 1 post por linha (texto limpo, até 6.000 c)
  noticias/retro/pdfs.json          — links de PDF citados nos posts (Informes etc.)
  noticias/retro/sites.md           — registro de coleta por site e por ano

Retomável: posts já gravados (por link) não são baixados de novo.
Uso: python3 retro_sites.py [--so centrorochas,abirochas] [--max-paginas 200]
"""

import argparse
import collections
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import cadeia
import rede

DIR = "noticias/retro/sites"
PDF_RX = re.compile(r'href=["\']([^"\']+\.pdf)["\']', re.I)


def limpar(h):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def ler_existentes(caminho):
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        return {r["link"]: r for r in map(json.loads, f)}


def coletar_site(s, max_paginas, log, pdfs):
    base = s["url"].rstrip("/") + "/wp-json/wp/v2/posts"
    caminho = f"{DIR}/{s['id']}.jsonl"
    existentes = ler_existentes(caminho)
    novos, vistos, descartados, pagina, erro, total = 0, 0, 0, 1, None, None
    while pagina <= max_paginas:
        url = base + "?" + rede.qs(per_page=100, page=pagina, search=s.get("busca"),
                                   _fields="date,link,title,excerpt,content")
        cod, corpo, erro_http, _ = rede.buscar(url, ua=rede.UA)
        if erro_http:
            # WordPress responde 400 rest_post_invalid_page_number ao passar da última página
            if cod == 400 and pagina > 1:
                break
            erro = f"HTTP {cod}: {erro_http[:160]}"
            break
        try:
            posts = json.loads(corpo)
        except ValueError:
            erro = rede.rotular_nao_esperado(corpo, "resposta não-JSON (site não é WordPress ou API fechada)")
            break
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            vistos += 1
            link = p.get("link")
            conteudo = (p.get("content") or {}).get("rendered", "")
            for pdf in PDF_RX.findall(conteudo):
                pdfs[pdf] = {"site": s["id"], "post": link, "data": (p.get("date") or "")[:10]}
            if not link or link in existentes:
                continue
            titulo = limpar((p.get("title") or {}).get("rendered"))
            texto = limpar(conteudo)
            rel, motivo, elos = cadeia.avaliar(titulo, texto[:3000])
            # Site do próprio setor: tudo é do setor, o filtro só classifica.
            if not rel and s.get("generalista"):
                descartados += 1
                continue
            existentes[link] = {"site": s["id"], "data": (p.get("date") or "")[:10], "titulo": titulo, "link": link,
                                "resumo": limpar((p.get("excerpt") or {}).get("rendered"))[:600],
                                "texto": texto[:6000], "caracteres": len(texto),
                                "relevancia": motivo or "site-setorial", "elos_pre": elos}
            novos += 1
        if len(posts) < 100:
            break
        pagina += 1
        time.sleep(1)
    os.makedirs(DIR, exist_ok=True)
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        for r in sorted(existentes.values(), key=lambda r: r["data"], reverse=True):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(caminho + ".tmp", caminho)
    anos = collections.Counter(r["data"][:4] for r in existentes.values())
    log.append({"site": s["id"], "nome": s["nome"], "erro": erro, "paginas": pagina, "posts_lidos": vistos,
                "novos": novos, "descartados": descartados, "total": len(existentes),
                "de": min(anos) if anos else None, "ate": max(anos) if anos else None, "por_ano": dict(sorted(anos.items()))})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--so")
    p.add_argument("--max-paginas", type=int, default=300)
    a = p.parse_args()
    sites = rede.ler_json("config.json")["retro"]["sites_wp"]
    if a.so:
        sites = [s for s in sites if s["id"] in a.so.split(",")]
    log, pdfs = [], rede.ler_json("noticias/retro/pdfs.json", {})
    for s in sites:
        coletar_site(s, a.max_paginas, log, pdfs)
        print(f"  {s['id']:<18} {log[-1]['total']:>6} posts ({log[-1]['de']}–{log[-1]['ate']})  {log[-1]['erro'] or ''}")
    rede.gravar_json("noticias/retro/pdfs.json", pdfs)

    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md = [f"# Acervo retroativo dos sites do setor — {hoje}", "",
          "Coleta pela API pública do WordPress (`/wp-json/wp/v2/posts`). Texto do post gravado até 6.000 caracteres.",
          "Sites generalistas usam busca por palavra e passam pelo filtro de relevância; sites do setor entram inteiros.", "",
          "| Site | Posts no acervo | Novos nesta execução | Período | Descartados (filtro) | Erro |", "|---|---|---|---|---|---|"]
    for l in log:
        md.append(f"| {l['nome']} | {l['total']} | {l['novos']} | {l['de'] or '—'}–{l['ate'] or '—'} | {l['descartados']} | {(l['erro'] or '').replace('|', '/')[:120]} |")
    md += ["", f"PDFs citados nos posts (Informes, estudos): **{len(pdfs)}** — lista em `pdfs.json`.", "",
           "## Posts por ano", "", "| Site | " + " | ".join(str(y) for y in range(2008, datetime.now().year + 1)) + " |",
           "|---|" + "---|" * (datetime.now().year + 1 - 2008)]
    for l in log:
        md.append(f"| {l['site']} | " + " | ".join(str(l["por_ano"].get(str(y), "")) for y in range(2008, datetime.now().year + 1)) + " |")
    os.makedirs("noticias/retro", exist_ok=True)
    with open("noticias/retro/sites.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    falhas = sum(1 for l in log if l["erro"])
    print(f"retro_sites: {sum(l['total'] for l in log)} posts, {len(pdfs)} PDFs, {falhas}/{len(log)} sites com erro")
    sys.exit(2 if falhas > len(log) / 2 else 0)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
