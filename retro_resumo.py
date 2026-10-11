#!/usr/bin/env python3
"""
retro_resumo.py — consolida o acervo retroativo de notícias num só lugar.

Junta sites do setor (só páginas de notícia), Google News e GDELT, deduplica por
manchete normalizada e grava:
  noticias/retro/acervo.jsonl   — 1 notícia por linha, com fonte(s) e data
  noticias/retro/RESUMO.md      — cobertura por fonte e por ano, e o que ficou de fora

GDELT entra só com os itens cujo TÍTULO passa no filtro de cadeia.py: na
validação de 2026-10-11, 525 de 555 itens eram ruído (casas à venda, games).
"""

import collections
import glob
import json
import os
from datetime import datetime, timezone

import rede

NAO_NOTICIA = {"associado", "pessoa", "relatorio", "evento", "tema", "publicidade-legal", "obituario",
               "conteudo-de-marca", "patrocinado"}


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    acervo, fora = {}, collections.Counter()

    def add(fonte, data, titulo, link, veiculo, texto=False, elos=()):
        k = rede.normalizar(titulo)
        if not k:
            return
        r = acervo.setdefault(k, {"data": data, "titulo": titulo, "link": link, "veiculo": veiculo,
                                  "fontes": [], "texto_completo": False, "elos_pre": list(elos)})
        r["fontes"] = sorted(set(r["fontes"]) | {fonte})
        r["texto_completo"] = r["texto_completo"] or texto
        if data and (not r["data"] or data < r["data"]):
            r["data"] = data

    for f in glob.glob("noticias/retro/sites/*.jsonl"):
        for r in map(json.loads, open(f, encoding="utf-8")):
            if r["site"] == "centrorochas" and "/en/" in r["link"]:   # versão em inglês da mesma matéria
                fora["site:centrorochas:traducao-en"] += 1
                continue
            if r.get("tipo") in NAO_NOTICIA:
                fora[f"site:{r['site']}:{r.get('tipo')}"] += 1
                continue
            add(f"site:{r['site']}", r["data"], r["titulo"], r["link"], r["site"], r.get("caracteres", 0) >= 500,
                r.get("elos_pre", []))
    for f in glob.glob("noticias/retro/gn/*.jsonl"):
        for r in map(json.loads, open(f, encoding="utf-8")):
            add("google-news", r["publicado"][:10], r["titulo"], r["link"], r.get("veiculo"), False, r.get("elos_pre", []))
    for f in glob.glob("noticias/retro/gdelt/*.jsonl"):
        for r in map(json.loads, open(f, encoding="utf-8")):
            if r["relevancia"].startswith("consulta"):
                fora["gdelt:titulo-fora-do-recorte"] += 1
                continue
            add("gdelt", r["publicado"], r["titulo"], r["link"], r.get("veiculo"), False, r.get("elos_pre", []))
    for f in glob.glob("noticias/*-bruto.json"):   # varredura diária (desde 08/10/2026)
        for r in rede.ler_json(f, {}).get("itens", []):
            add("diario", r["publicado"][:10], r["titulo"], r["link"], r.get("veiculo"), False, r.get("elos_pre", []))

    itens = sorted(acervo.values(), key=lambda r: r["data"] or "", reverse=True)
    with open("noticias/retro/acervo.jsonl", "w", encoding="utf-8") as fh:
        for r in itens:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    por_fonte = collections.Counter(f.split(":")[0] if not f.startswith("site") else f for r in itens for f in r["fontes"])
    por_ano = collections.Counter((r["data"] or "????")[:4] for r in itens)
    anos = sorted(a for a in por_ano if a.isdigit())
    md = [f"# Acervo de notícias do setor — {datetime.now(timezone.utc):%Y-%m-%d}", "",
          f"**{len(itens)} notícias únicas**, das quais {sum(r['texto_completo'] for r in itens)} com texto completo "
          "(sites do setor); as demais só com manchete, veículo e data.", "",
          "## Por fonte", "", "| Fonte | Notícias |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in por_fonte.most_common()]
    md += ["", "## Por ano", "", "| Ano | Notícias |", "|---|---|"] + [f"| {a} | {por_ano[a]} |" for a in anos]
    md += ["", "## Fora do acervo (não é notícia ou não passou no filtro)", "", "| Motivo | Itens |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in fora.most_common()]
    md += ["", "## Limites conhecidos", "",
           "- Google News não aceita busca retroativa por data (validado em 2026-10-11): contribui só com 2025–2026.",
           "- GDELT cobre desde 2017 mas quase não indexa veículos brasileiros desse nicho; entra só o que passa no filtro pelo título.",
           "- Abirochas fecha a API e não publica sitemap; Folha Vitória e ES Hoje bloqueiam robôs (Cloudflare).",
           "- Antes de 2015 a cobertura depende da Revista Minérios e de arquivos antigos (Internet Archive, etapa 5)."]
    with open("noticias/retro/RESUMO.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print(f"retro_resumo: {len(itens)} notícias únicas")


if __name__ == "__main__":
    main()
