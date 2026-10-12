#!/usr/bin/env python3
"""
cinzenta_tabela.py — confere e consolida as fichas da literatura cinzenta (prompts/triagem.md §D).

Determinístico. Para cada biblio/cinzenta/fichas/<id>.json, procura cada `trecho` no texto do
documento (normalização: NFKC, minúsculas, espaços colapsados, hifenização de fim de linha
desfeita). Item cujo trecho não é encontrado é DESCARTADO e contado — nenhuma afirmação entra
no estudo sem lastro literal.

Saída: biblio/cinzenta/fichas.jsonl (só itens conferidos) · estudo/informes-setoriais.md
"""

import collections
import glob
import json
import os
import re
import unicodedata
from datetime import datetime, timezone

LISTAS = ("indicadores", "explicacoes", "mercados", "politicas", "precos", "desafios", "pleitos")


def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"-\s*\n\s*", "", s)
    s = re.sub(r"[“”\"'‘’`]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def conferir(ficha, texto_norm):
    ok, ruins = {}, 0
    for campo in LISTAS:
        ok[campo] = []
        for item in ficha.get(campo) or []:
            t = norm(item.get("trecho") or "")
            if len(t) >= 12 and t in texto_norm:
                ok[campo].append(item)
            else:
                ruins += 1
    return ok, ruins


def celula(s, n=220):
    return re.sub(r"\s+", " ", str(s or "")).replace("|", "/")[:n]


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    fila = {r["id"]: r for r in map(json.loads, open("biblio/cinzenta/fila.jsonl", encoding="utf-8"))}
    fichas, total_ruins, total_itens = [], 0, 0
    for caminho in sorted(glob.glob("biblio/cinzenta/fichas/*.json")):
        f = json.load(open(caminho, encoding="utf-8"))
        meta = fila.get(f.get("id"))
        if not meta:
            print(f"  ficha sem documento na fila: {caminho}")
            continue
        texto = norm(open(meta["texto"], encoding="utf-8").read())
        conferidos, ruins = conferir(f, texto)
        total_itens += sum(len(f.get(c) or []) for c in LISTAS)
        total_ruins += ruins
        f.update(conferidos)
        f["url"] = meta["url"]
        f["itens_descartados"] = ruins
        fichas.append(f)
    fichas.sort(key=lambda f: (f.get("data_publicacao") or "0000", f["arquivo"]))
    with open("biblio/cinzenta/fichas.jsonl", "w", encoding="utf-8") as fh:
        for f in fichas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    pendentes = [r for r in fila.values() if r["decisao"] == "fichar" and r["id"] not in {f["id"] for f in fichas}]
    dec = collections.Counter(r["decisao"] for r in fila.values())
    md = [f"# Informes e estudos setoriais — fichamento conferido ({datetime.now(timezone.utc):%Y-%m-%d})", "",
          "Fonte: literatura cinzenta recuperada dos sites e do Internet Archive (`biblio/cinzenta/`). "
          "Fichamento por LLM segundo `prompts/triagem.md` §D; **cada item abaixo tem trecho literal "
          "conferido automaticamente contra o texto do PDF** (`cinzenta_tabela.py`).", "",
          f"- Documentos com texto: {len(fila)} → fichar {dec['fichar']}, tabelas de comércio exterior "
          f"{dec['tabela']} (repetem o ComexStat), duplicatas de versão {dec['duplicata']}, fora de escopo {dec['fora']}",
          f"- Fichados: {len(fichas)}; pendentes: {len(pendentes)}",
          f"- Itens propostos: {total_itens}; descartados por trecho não encontrado: {total_ruins} "
          f"({100 * total_ruins / max(total_itens, 1):.1f}%)", ""]

    md += ["## 1. O que o setor disse ter causado cada movimento", "",
           "| Data | Emissor | Fenômeno | Causa atribuída pelo emissor | Trecho literal |", "|---|---|---|---|---|"]
    for f in fichas:
        for e in f["explicacoes"]:
            md.append(f"| {f.get('data_publicacao') or '?'} | {f['emissor']} | {celula(e.get('fenomeno'), 90)} | "
                      f"{celula(e.get('causa_atribuida'), 120)} | “{celula(e.get('trecho'), 260)}” |")
    for titulo, campo, chave in (("2. Mercados de destino", "mercados", "pais"),
                                 ("3. Políticas, tarifas e regulação", "politicas", "medida"),
                                 ("4. Preços", "precos", "produto")):
        md += ["", f"## {titulo}", "", "| Data | Emissor | Assunto | Afirmação | Trecho literal |", "|---|---|---|---|---|"]
        for f in fichas:
            for e in f[campo]:
                md.append(f"| {f.get('data_publicacao') or '?'} | {f['emissor']} | {celula(e.get(chave), 60)} | "
                          f"{celula(e.get('afirmacao'), 140)} | “{celula(e.get('trecho'), 260)}” |")
    md += ["", "## 5. Indicadores que não vêm do ComexStat", "",
           "| Data | Emissor | Indicador | Valor | Período | Trecho literal |", "|---|---|---|---|---|---|"]
    for f in fichas:
        for e in f["indicadores"]:
            md.append(f"| {f.get('data_publicacao') or '?'} | {f['emissor']} | {celula(e.get('nome'), 70)} | "
                      f"{celula(e.get('valor'), 30)} {celula(e.get('unidade'), 20)} | {celula(e.get('periodo'), 25)} | "
                      f"“{celula(e.get('trecho'), 220)}” |")
    md += ["", "## 6. Desafios e pleitos declarados", "", "| Data | Emissor | Tipo | Afirmação | Trecho literal |",
           "|---|---|---|---|---|"]
    for f in fichas:
        for campo, rot in (("desafios", "desafio"), ("pleitos", "pleito")):
            for e in f[campo]:
                md.append(f"| {f.get('data_publicacao') or '?'} | {f['emissor']} | {rot} | "
                          f"{celula(e.get('afirmacao'), 160)} | “{celula(e.get('trecho'), 240)}” |")
    md += ["", "## 7. Documentos fichados", "", "| Data | Emissor | Tipo | Título | Tema | Elos | Descartados | Obs. |",
           "|---|---|---|---|---|---|---|---|"]
    for f in fichas:
        md.append(f"| {f.get('data_publicacao') or '?'} | {f['emissor']} | {f.get('tipo')} | [{celula(f.get('titulo'), 80)}]({f['url']}) | "
                  f"{celula(f.get('tema'), 120)} | {', '.join(f.get('elos') or [])} | {f['itens_descartados']} | "
                  f"{celula(f.get('observacao'), 80)} |")
    os.makedirs("estudo", exist_ok=True)
    with open("estudo/informes-setoriais.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print(f"cinzenta_tabela: {len(fichas)} fichas, {total_itens} itens, {total_ruins} descartados, {len(pendentes)} pendentes")


if __name__ == "__main__":
    main()
