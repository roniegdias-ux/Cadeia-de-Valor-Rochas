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


LOC_LASTMOD = re.compile(r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]+))?", re.I)
SITEMAP_LOC = re.compile(r"<sitemap>\s*<loc>\s*([^<\s]+)\s*</loc>", re.I)
META = lambda prop: re.compile(r'<meta[^>]+(?:property|name)=["\']' + prop + r'["\'][^>]+content=["\']([^"\']+)', re.I)
OG_TITLE, PUB = META("og:title"), META("article:published_time")
LD_DATE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
NAO_POST = re.compile(r"/(tag|category|categoria|author|autor|page|wp-content|feed)/|\.(jpg|png|pdf|xml)$", re.I)
TIPOS_IGNORADOS = {"page", "attachment", "nav_menu_item", "wp_block", "wp_template", "wp_template_part",
                   "wp_navigation", "wp_font_family", "wp_font_face", "wp_global_styles"}


def tipos_de_conteudo(s):
    """rest_base de cada tipo publicável (posts + tipos personalizados, ex.: 'noticias')."""
    cod, corpo, erro, _ = rede.buscar(s["url"].rstrip("/") + "/wp-json/wp/v2/types", ua=rede.UA, tentativas=2)
    if erro:
        return ["posts"]
    try:
        tipos = json.loads(corpo)
    except ValueError:
        return ["posts"]
    bases = [t.get("rest_base") for k, t in tipos.items() if k not in TIPOS_IGNORADOS and t.get("rest_base")]
    return sorted(set(bases) | {"posts"})


def pagina_html(url):
    """(titulo, data, texto, pdfs) extraídos do HTML de uma página."""
    cod, corpo, erro, _ = rede.buscar(url, tentativas=2)
    if erro:
        return None
    h = corpo.decode("utf-8", "replace")
    titulo = (OG_TITLE.search(h) or re.search(r"<title>([^<]+)</title>", h, re.I))
    data = (PUB.search(h) or LD_DATE.search(h) or re.search(r'<time[^>]+datetime=["\']([^"\']+)', h, re.I))
    corpo_art = re.search(r"<article.*?</article>", h, re.S | re.I)
    paras = re.findall(r"<p[^>]*>(.*?)</p>", corpo_art.group(0) if corpo_art else h, re.S | re.I)
    return (limpar(titulo.group(1)) if titulo else "", (data.group(1) if data else "")[:10],
            limpar(" ".join(paras)), PDF_RX.findall(h))


def urls_do_sitemap(s, log_erros):
    raiz = s["url"].rstrip("/")
    filas = [raiz + p for p in ("/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml")]
    urls, vistos = {}, set()
    while filas and len(vistos) < 300:
        u = filas.pop(0)
        if u in vistos:
            continue
        vistos.add(u)
        cod, corpo, erro, _ = rede.buscar(u, tentativas=2)
        if erro:
            continue
        x = corpo.decode("utf-8", "replace")
        filhos = SITEMAP_LOC.findall(x)
        # só sitemaps de conteúdo: post, notícia, artigo (pula páginas, tags, autores, imagens)
        filas += [f for f in filhos if not re.search(r"(page|tag|categor|author|user|taxonom|attachment|image)", f, re.I)]
        for loc, lastmod in LOC_LASTMOD.findall(x):
            if not NAO_POST.search(loc) and loc.rstrip("/") != raiz:
                urls[loc] = (lastmod or "")[:10]
    if not urls:
        log_erros.append("sitemap vazio ou inacessível")
    return urls


def coletar_sitemap(s, existentes, pdfs, max_paginas):
    """Plano B quando a API está fechada ou vazia: sitemap + leitura de cada página."""
    erros = []
    urls = urls_do_sitemap(s, erros)
    if s.get("generalista"):
        # veículo generalista: só abre página cujo endereço já indica o tema (evita ler milhares de notícias)
        tema = re.compile(r"rocha|marmor|granit|quartzit|ardosia|centrorochas|abirochas|stone-fair|pedra", re.I)
        urls = {u: d for u, d in urls.items() if tema.search(u)}
    novos = descartados = 0
    for loc, lastmod in list(urls.items())[: max_paginas * 20]:
        if loc in existentes:
            continue
        r = pagina_html(loc)
        time.sleep(0.8)
        if not r:
            continue
        titulo, data, texto, links_pdf = r
        for pdf in links_pdf:
            pdfs[pdf] = {"site": s["id"], "post": loc, "data": data or lastmod}
        rel, motivo, elos = cadeia.avaliar(titulo, texto[:3000])
        if not rel and s.get("generalista"):
            descartados += 1
            continue
        existentes[loc] = {"site": s["id"], "data": data or lastmod, "titulo": titulo, "link": loc,
                           "resumo": texto[:600], "texto": texto[:6000], "caracteres": len(texto),
                           "relevancia": motivo or "site-setorial", "elos_pre": elos, "via": "sitemap"}
        novos += 1
    return novos, descartados, len(urls), (erros[0] if erros else None)


def coletar_site(s, max_paginas, log, pdfs):
    caminho = f"{DIR}/{s['id']}.jsonl"
    existentes = ler_existentes(caminho)
    novos = vistos = descartados = 0
    erro = None
    for tipo in tipos_de_conteudo(s):
        n, v, d, erro_tipo = coletar_api(s, tipo, max_paginas, existentes, pdfs)
        novos, vistos, descartados = novos + n, vistos + v, descartados + d
        if tipo == "posts":
            erro = erro_tipo
    via = "api"
    if vistos == 0:   # API fechada (401), inexistente (404) ou vazia: tenta o sitemap
        n, d, n_urls, erro_sm = coletar_sitemap(s, existentes, pdfs, max_paginas)
        novos, descartados, via = novos + n, descartados + d, f"sitemap ({n_urls} URLs)"
        erro = None if n_urls else f"{erro or 'API sem posts'}; {erro_sm}"
    gravar_site(s, caminho, existentes, log, novos, vistos, descartados, erro, via)


def coletar_api(s, tipo, max_paginas, existentes, pdfs):
    base = s["url"].rstrip("/") + "/wp-json/wp/v2/" + tipo
    novos, vistos, descartados, pagina, erro = 0, 0, 0, 1, None
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
    return novos, vistos, descartados, erro


def gravar_site(s, caminho, existentes, log, novos, vistos, descartados, erro, via):
    os.makedirs(DIR, exist_ok=True)
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        for r in sorted(existentes.values(), key=lambda r: r["data"], reverse=True):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(caminho + ".tmp", caminho)
    anos = collections.Counter(r["data"][:4] for r in existentes.values())
    log.append({"site": s["id"], "nome": s["nome"], "erro": erro, "via": via, "posts_lidos": vistos,
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
          "| Site | Via | Posts no acervo | Novos nesta execução | Período | Descartados (filtro) | Erro |", "|---|---|---|---|---|---|---|"]
    for l in log:
        md.append(f"| {l['nome']} | {l['via']} | {l['total']} | {l['novos']} | {l['de'] or '—'}–{l['ate'] or '—'} | {l['descartados']} | {(l['erro'] or '').replace('|', '/')[:120]} |")
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
