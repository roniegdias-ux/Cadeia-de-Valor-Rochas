#!/usr/bin/env python3
"""
retro_pdfs.py — etapa 1b: literatura cinzenta em PDF (Informes Abirochas, estudos).

Fontes de links: noticias/retro/pdfs.json (PDFs citados nos posts dos sites,
gerado por retro_sites.py) + sitemaps de config.retro.sitemaps_pdf, filtrando por
config.retro.pdf_regex. Baixa cada PDF, extrai o texto com `pdftotext` (poppler)
e grava só o texto no repositório — o binário não é versionado.

Saída: biblio/cinzenta/textos/<id>.txt · biblio/cinzenta/indice.jsonl · biblio/cinzenta.md
Retomável: PDF já extraído não é baixado de novo.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timezone

import rede

DIR = "biblio/cinzenta"
INDICE = f"{DIR}/indice.jsonl"
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)


def de_sitemaps(urls, rx, log, profundidade=0):
    achados = {}
    for u in urls:
        cod, corpo, erro, _ = rede.buscar(u, tentativas=2)
        if erro:
            log.append(f"sitemap {u}: HTTP {cod} {erro[:80]}")
            continue
        locs = LOC.findall(corpo.decode("utf-8", "replace"))
        filhos = [l for l in locs if l.endswith(".xml") or "sitemap" in l.lower()]
        for l in locs:
            if l.lower().endswith(".pdf") and rx.search(urllib.parse.unquote(l)):
                achados[l] = {"site": urllib.parse.urlparse(u).netloc, "post": u, "data": ""}
        if filhos and profundidade < 2:
            achados.update(de_sitemaps(filhos[:200], rx, log, profundidade + 1))
    return achados


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    cfg = rede.ler_json("config.json")["retro"]
    rx = re.compile(cfg["pdf_regex"], re.I)
    log = []
    candidatos = {u: m for u, m in rede.ler_json("noticias/retro/pdfs.json", {}).items()
                  if rx.search(urllib.parse.unquote(u))}
    candidatos.update(de_sitemaps(cfg.get("sitemaps_pdf", []), rx, log))
    indice = {}
    if os.path.exists(INDICE):
        with open(INDICE, encoding="utf-8") as f:
            indice = {r["url"]: r for r in map(json.loads, f)}
    tem_pdftotext = shutil.which("pdftotext") is not None
    os.makedirs(f"{DIR}/textos", exist_ok=True)
    novos = falhas = 0
    for url, meta in sorted(candidatos.items()):
        if url in indice and indice[url].get("caracteres"):
            continue
        nome = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        ident = re.sub(r"[^\w-]+", "_", nome[:-4])[:80] + "_" + hashlib.sha1(url.encode()).hexdigest()[:6]
        reg = {"url": url, "arquivo": nome, "id": ident, "site": meta.get("site"), "post": meta.get("post"),
               "data_post": meta.get("data"), "caracteres": 0, "erro": None}
        cod, corpo, erro, _ = rede.buscar(url, tentativas=3)
        if erro or not corpo.startswith(b"%PDF"):
            reg["erro"] = erro or f"HTTP {cod} mas não é PDF"
            falhas += 1
        elif not tem_pdftotext:
            reg["erro"] = "pdftotext indisponível no ambiente"
        else:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(corpo)
                tmp.flush()
                r = subprocess.run(["pdftotext", "-layout", tmp.name, "-"], capture_output=True, timeout=120)
            texto = r.stdout.decode("utf-8", "replace").strip()
            reg["caracteres"] = len(texto)
            if len(texto) < 200:
                reg["erro"] = "PDF sem texto extraível (provavelmente imagem escaneada)"
            with open(f"{DIR}/textos/{ident}.txt", "w", encoding="utf-8") as f:
                f.write(f"Fonte: {url}\nPost de origem: {meta.get('post')}\n\n{texto}\n")
            novos += 1
        indice[url] = reg
        time.sleep(1)
    with open(INDICE, "w", encoding="utf-8") as f:
        for r in sorted(indice.values(), key=lambda r: r["arquivo"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = [r for r in indice.values() if r["caracteres"] >= 200]
    md = [f"# Literatura cinzenta em PDF — {datetime.now(timezone.utc):%Y-%m-%d}", "",
          f"- PDFs candidatos (filtro `{cfg['pdf_regex']}`): {len(candidatos)}",
          f"- Com texto extraído: **{len(ok)}**; falhas acumuladas: {sum(1 for r in indice.values() if r['erro'])}",
          f"- Novos nesta execução: {novos}; falhas nesta execução: {falhas}", ""]
    md += [f"- {l}" for l in log]
    md += ["", "| Arquivo | Site | Caracteres | Situação |", "|---|---|---|---|"]
    for r in sorted(indice.values(), key=lambda r: r["arquivo"]):
        md.append(f"| [{r['arquivo'][:80]}]({r['url']}) | {r['site']} | {r['caracteres']} | {(r['erro'] or 'ok')[:60]} |")
    with open("biblio/cinzenta.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"retro_pdfs: {len(candidatos)} candidatos, {len(ok)} com texto, {novos} novos, {falhas} falhas")
    sys.exit(0)


if __name__ == "__main__":
    main()
