#!/usr/bin/env python3
"""
retro_gn.py — etapa 2 da coleta retroativa: Google News mês a mês.

O RSS de busca do Google News devolve no máximo ~100 itens por consulta; por
isso cada consulta de config.retro.gn_consultas é repetida por mês, com
`after:AAAA-MM-01 before:AAAA-MM+1-01`, de config.retro.gn_inicio até o mês
corrente. Entrega manchete, veículo e data, nunca o texto.

Retomável e com orçamento de tempo: noticias/retro/gn-estado.json guarda cada
(consulta, mês) já feito; a execução para sozinha ao fim de --minutos e a
próxima continua de onde parou. Itens passam pelo filtro de cadeia.py e são
deduplicados por manchete normalizada.

Saída: noticias/retro/gn/AAAA.jsonl · noticias/retro/gn.md
"""

import argparse
import collections
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import cadeia
import rede

DIR = "noticias/retro/gn"
ESTADO = "noticias/retro/gn-estado.json"
GN = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
LOCALE = {"pt": ("pt-BR", "BR", "BR:pt-419"), "en": ("en-US", "US", "US:en")}


def meses(inicio, fim):
    a, m = map(int, inicio.split("-"))
    while (a, m) <= fim:
        prox = (a + (m == 12), m % 12 + 1)
        yield f"{a}-{m:02d}", f"{a}-{m:02d}-01", f"{prox[0]}-{prox[1]:02d}-01"
        a, m = prox


def carregar_ano(ano):
    p = f"{DIR}/{ano}.jsonl"
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return {r["chave"]: r for r in map(json.loads, f)}


def gravar_ano(ano, itens):
    os.makedirs(DIR, exist_ok=True)
    p = f"{DIR}/{ano}.jsonl"
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        for r in sorted(itens.values(), key=lambda r: r["publicado"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(p + ".tmp", p)


def combo(consultas):
    """Uma busca com OR por idioma: ~5x menos requisições que uma por termo."""
    return " OR ".join(f"({q})" if " " in q and not q.startswith('"') else q for q in consultas)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--minutos", type=float, default=180)
    p.add_argument("--pausa", type=float, default=5.0)
    a = p.parse_args()
    cfg = rede.ler_json("config.json")["retro"]
    estado = rede.ler_json(ESTADO, {"feito": {}})
    agora = datetime.now(timezone.utc)
    limite = time.time() + a.minutos * 60
    # Do mais recente para o mais antigo: confirma cedo que o filtro de datas
    # funciona e prioriza os anos com mais cobertura no Google News.
    todos = list(meses(cfg["gn_inicio"], (agora.year, agora.month)))[::-1]
    fila = collections.deque()
    for mes, ini, fim in todos:
        for lang, consultas in cfg["gn_consultas"].items():
            q = combo(consultas)
            if f"{lang}|COMBO|{mes}" not in estado["feito"]:
                fila.append((lang, q, "COMBO", mes, ini, fim))
            elif estado["feito"][f"{lang}|COMBO|{mes}"]["n"] >= 95:   # mês cheio: abre por termo
                fila.extend((lang, t, t, mes, ini, fim) for t in consultas
                            if f"{lang}|{t}|{mes}" not in estado["feito"])
    print(f"retro_gn: {len(fila)} buscas pendentes na fila inicial")

    anos, sujos = {}, set()
    recusas, feitos_agora, erros = 0, 0, collections.Counter()
    while fila and time.time() < limite:
        lang, q, rotulo, mes, ini, fim = fila.popleft()
        hl, gl, ceid = LOCALE[lang]
        url = GN.format(q=urllib.parse.quote_plus(f"{q} after:{ini} before:{fim}"), hl=hl, gl=gl, ceid=ceid)
        cod, corpo, erro, _ = rede.buscar(url, tentativas=1)
        if erro:
            erros[str(cod)] += 1
            if cod in (429, 503):   # Google limitando: espera longa e repete a mesma busca
                recusas += 1
                if recusas > 6:
                    print(f"  7 recusas seguidas (HTTP {cod}); parando para retomar na próxima execução")
                    break
                fila.appendleft((lang, q, rotulo, mes, ini, fim))
                time.sleep(120 * recusas)
            continue
        recusas = 0
        try:
            crus = rede.extrair_itens(corpo)
        except ValueError:
            erros["xml"] += 1
            continue
        reg = {"n": len(crus), "rel": 0, "fora_mes": 0}
        for c in crus:
            d = rede.parse_data(c["data_bruta"])
            if not d:
                continue
            if not (ini <= d.strftime("%Y-%m-%d") < fim):
                reg["fora_mes"] += 1
            rel, motivo, elos = cadeia.avaliar(c["titulo"], c["resumo"])
            if not rel:
                continue
            reg["rel"] += 1
            ano = d.year
            if ano not in anos:
                anos[ano] = carregar_ano(ano)
            k = rede.normalizar(c["titulo"])
            fonte = f"{lang}:{rotulo}"
            if k in anos[ano]:
                anos[ano][k]["consultas"] = sorted(set(anos[ano][k]["consultas"]) | {fonte})
                continue
            anos[ano][k] = {"publicado": d.isoformat(), "titulo": c["titulo"], "link": c["link"],
                            "veiculo": c["fonte_declarada"], "relevancia": motivo, "elos_pre": elos,
                            "consultas": [fonte], "chave": k}
            sujos.add(ano)
        estado["feito"][f"{lang}|{rotulo}|{mes}"] = reg
        if rotulo == "COMBO" and reg["n"] >= 95:
            for t in cfg["gn_consultas"][lang]:
                fila.appendleft((lang, t, t, mes, ini, fim))
        feitos_agora += 1
        if feitos_agora % 25 == 0:   # grava aos poucos: um timeout não perde o que já veio
            for ano in sujos:
                gravar_ano(ano, anos[ano])
            sujos.clear()
            rede.gravar_json(ESTADO, estado)
        time.sleep(a.pausa)

    for ano in sujos:
        gravar_ano(ano, anos[ano])
    rede.gravar_json(ESTADO, estado)
    relatorio(estado, len(fila), erros)
    print(f"retro_gn: {feitos_agora} buscas feitas agora, {len(fila)} pendentes, erros {dict(erros)}")
    sys.exit(0 if feitos_agora else 2)


def relatorio(estado, pendentes, erros):
    por_ano = collections.Counter()
    veic = collections.Counter()
    total = 0
    for nome in sorted(os.listdir(DIR)) if os.path.isdir(DIR) else []:
        with open(f"{DIR}/{nome}", encoding="utf-8") as f:
            for r in map(json.loads, f):
                por_ano[r["publicado"][:4]] += 1
                veic[r["veiculo"] or "?"] += 1
                total += 1
    feitos = estado["feito"]
    cheias = sum(1 for v in feitos.values() if v["n"] >= 95)
    md = [f"# Notícias retroativas (Google News, mês a mês) — {datetime.now(timezone.utc):%Y-%m-%d}", "",
          f"- (consulta, mês) concluídos: {len(feitos)}; pendentes: {pendentes}; erros nesta execução: {dict(erros) or 'nenhum'}",
          f"- Itens únicos relevantes no acervo: **{total}**",
          f"- Consultas que bateram no teto de ~100 itens (cobertura possivelmente incompleta naquele mês): {cheias}",
          "- Só manchete, veículo e data. Texto não lido.", "",
          "| Ano | Itens |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(por_ano.items())]
    md += ["", "## Veículos com mais itens", "", "| Veículo | Itens |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in veic.most_common(25)]
    with open("noticias/retro/gn.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
