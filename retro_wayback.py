#!/usr/bin/env python3
"""
retro_wayback.py — etapa 5: acervo antigo pelo Internet Archive (Wayback Machine).

Para cada prefixo de config.retro.wayback (sites do setor, inclusive de antes das
migrações, e pastas de PDF como a do Litos Online onde ficam os Informes
Abirochas), consulta o índice CDX do Internet Archive, que lista os endereços
REAIS arquivados — nenhum endereço é adivinhado. Depois:
  - páginas HTML com cara de notícia: baixa a cópia arquivada e extrai título,
    data e texto → noticias/retro/sites/wb-<id>.jsonl (entra no acervo consolidado)
  - PDFs que casam com config.retro.pdf_regex → noticias/retro/pdfs.json, com o
    endereço da cópia arquivada; retro_pdfs.py extrai o texto

Retomável (noticias/retro/wayback-estado.json) e com orçamento de tempo.
"""

import argparse
import collections
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import cadeia
import rede
import retro_sites

CDX = "https://web.archive.org/cdx/search/cdx"
NOTICIA = re.compile(r"noticia|news|informe|artigo|materia|blog|imprensa|/20\d\d/|\?p=\d+", re.I)
LIXO = re.compile(r"\.(css|js|jpg|jpeg|png|gif|svg|ico|woff2?|ttf|xml|json)(\?|$)|/(wp-json|wp-admin|feed|tag|category|author|page)/", re.I)


def cdx(prefixo):
    url = CDX + "?" + rede.qs(url=prefixo, output="json", fl="timestamp,original,mimetype,statuscode",
                              filter="statuscode:200", collapse="urlkey", limit=20000)
    for espera in (0, 60, 180):   # o índice CDX recusa conexões quando se pede rápido demais
        time.sleep(espera)
        obj, cod, erro, _ = rede.buscar_json(url, ua=rede.UA_API, tentativas=1)
        if not erro or not re.search(r"429|refused|111|timed out", erro):
            break
    if erro or not obj:
        return [], erro or "vazio"
    cab, *linhas = obj
    return [dict(zip(cab, l)) for l in linhas], None


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser()
    p.add_argument("--minutos", type=float, default=150)
    a = p.parse_args()
    cfg = rede.ler_json("config.json")["retro"]
    rx_pdf = re.compile(cfg["pdf_regex"], re.I)
    estado = rede.ler_json("noticias/retro/wayback-estado.json", {"lidas": []})
    lidas = set(estado["lidas"])
    pdfs = rede.ler_json("noticias/retro/pdfs.json", {})
    limite = time.time() + a.minutos * 60
    log = []
    for alvo in cfg["wayback"]:
        caminho = f"{retro_sites.DIR}/wb-{alvo['id']}.jsonl"
        existentes = retro_sites.ler_existentes(caminho)
        capturas, erro = cdx(alvo["prefixo"])
        time.sleep(20)
        n_pdf = n_pag = n_rel = 0
        paginas = []
        for c in capturas:
            orig, ts, mime = c["original"], c["timestamp"], c.get("mimetype", "")
            if mime == "application/pdf" or orig.lower().endswith(".pdf"):
                if rx_pdf.search(urllib.parse.unquote(orig)):
                    pdfs.setdefault(orig, {"site": f"wb-{alvo['id']}", "post": orig, "data": ts[:8],
                                           "arquivado": f"https://web.archive.org/web/{ts}id_/{orig}"})
                    n_pdf += 1
            elif "html" in mime and not LIXO.search(orig) and (alvo.get("todas") or NOTICIA.search(orig)):
                paginas.append(c)
        for c in paginas:
            if time.time() > limite:
                erro = (erro or "") + " orçamento de tempo esgotado (retomar)"
                break
            orig, ts = c["original"], c["timestamp"]
            if orig in lidas or orig in existentes:
                continue
            pg = retro_sites.pagina_html(f"https://web.archive.org/web/{ts}id_/{orig}")
            time.sleep(4)   # Internet Archive pede moderação (~15 requisições/minuto)
            lidas.add(orig)
            n_pag += 1
            if not pg:
                continue
            titulo, data, texto, links_pdf = pg
            for u in links_pdf:
                if rx_pdf.search(urllib.parse.unquote(u)):
                    pdfs.setdefault(u, {"site": f"wb-{alvo['id']}", "post": orig, "data": data or ts[:8]})
            if len(texto) < 300:
                continue
            rel, motivo, elos = cadeia.avaliar(titulo, texto[:3000])
            if not rel and alvo.get("generalista"):
                continue
            data = data or f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            existentes[orig] = {"site": f"wb-{alvo['id']}", "data": data, "titulo": titulo, "link": orig,
                                "arquivado": f"https://web.archive.org/web/{ts}/{orig}", "resumo": texto[:600],
                                "texto": texto[:6000], "caracteres": len(texto), "relevancia": motivo or "site-setorial",
                                "elos_pre": elos, "tipo": retro_sites.tipo_de(orig), "via": "wayback"}
            n_rel += 1
            if n_pag % 50 == 0:
                rede.gravar_json("noticias/retro/wayback-estado.json", {"lidas": sorted(lidas)})
        os.makedirs(retro_sites.DIR, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as fh:
            for r in sorted(existentes.values(), key=lambda r: r["data"], reverse=True):
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        anos = collections.Counter(r["data"][:4] for r in existentes.values())
        log.append({"alvo": alvo["prefixo"], "capturas": len(capturas), "paginas_candidatas": len(paginas),
                    "lidas_agora": n_pag, "noticias_novas": n_rel, "acervo": len(existentes), "pdfs": n_pdf,
                    "anos": dict(sorted(anos.items())), "erro": erro})
        print(f"  {alvo['prefixo']:<45} {len(capturas):>6} capturas, {n_rel} notícias novas, {n_pdf} PDFs  {erro or ''}")
    rede.gravar_json("noticias/retro/pdfs.json", pdfs)
    rede.gravar_json("noticias/retro/wayback-estado.json", {"lidas": sorted(lidas)})
    md = [f"# Acervo antigo pelo Internet Archive — {datetime.now(timezone.utc):%Y-%m-%d}", "",
          "Endereços vêm do índice CDX do Internet Archive (cópias reais arquivadas); nada é adivinhado.", "",
          "| Prefixo | Capturas | Páginas candidatas | Lidas agora | Notícias no acervo | PDFs achados | Anos | Erro |",
          "|---|---|---|---|---|---|---|---|"]
    for l in log:
        anos = ", ".join(f"{k}:{v}" for k, v in l["anos"].items() if k)
        md.append(f"| {l['alvo']} | {l['capturas']} | {l['paginas_candidatas']} | {l['lidas_agora']} | {l['acervo']} | "
                  f"{l['pdfs']} | {anos[:160]} | {(l['erro'] or '')[:80]} |")
    with open("noticias/retro/wayback.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
