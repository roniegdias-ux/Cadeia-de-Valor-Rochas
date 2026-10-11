#!/usr/bin/env python3
"""
retro_gdelt.py — notícias retroativas via GDELT DOC 2.0 (cobertura desde 2017).

O Google News RSS ignora o filtro de datas (validação de 2026-10-11: ~95% dos
itens fora do mês pedido). O GDELT tem janela de busca real
(startdatetime/enddatetime), devolve até 250 artigos por consulta, com título,
veículo, idioma e data de captura. Uma consulta combinada por mês; se bater no
teto, o mês é repartido em quinzenas.

Também grava uma sonda do HTML das páginas de tema da A Gazeta (conteúdo montado
por JavaScript) em fontes/sondas/, para desenhar o extrator certo.

Saída: noticias/retro/gdelt/AAAA.jsonl · noticias/retro/gdelt.md
Retomável por noticias/retro/gdelt-estado.json.
"""

import argparse
import collections
import json
import os
import sys
import time
from datetime import datetime, timezone

import cadeia
import rede

API = "https://api.gdeltproject.org/api/v2/doc/doc"
DIR = "noticias/retro/gdelt"
ESTADO = "noticias/retro/gdelt-estado.json"
CONSULTA = ('("rochas ornamentais" OR "setor de rochas" OR "mármore e granito" OR Centrorochas OR Abirochas '
            'OR "Vitória Stone Fair" OR "Brazilian granite" OR "Brazilian quartzite" OR "dimension stone")')


def janelas(inicio, fim):
    a, m = inicio
    while (a, m) <= fim:
        prox = (a + (m == 12), m % 12 + 1)
        yield f"{a}{m:02d}01000000", f"{prox[0]}{prox[1]:02d}01000000", f"{a}-{m:02d}"
        a, m = prox


def buscar_janela(ini, fim):
    url = API + "?" + rede.qs(query=CONSULTA, mode="artlist", format="json", maxrecords=250,
                              startdatetime=ini, enddatetime=fim, sort="datedesc")
    cod, corpo, erro, _ = rede.buscar(url, ua=rede.UA_API, tentativas=3)
    if erro:
        return None, f"HTTP {cod} {erro[:120]}"
    try:
        return json.loads(corpo or b"{}").get("articles", []), None
    except ValueError:
        # GDELT responde texto puro quando a consulta é inválida ou o limite estoura
        return None, corpo[:160].decode("utf-8", "replace")


def sonda_agazeta():
    os.makedirs("fontes/sondas", exist_ok=True)
    cod, corpo, erro, _ = rede.buscar("https://www.agazeta.com.br/tema/rochas-ornamentais", tentativas=2)
    with open("fontes/sondas/agazeta-tema-rochas.html", "wb") as f:
        f.write((corpo or b"")[:400000] if not erro else f"erro: HTTP {cod} {erro}".encode())


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser()
    p.add_argument("--minutos", type=float, default=60)
    a = p.parse_args()
    sonda_agazeta()
    estado = rede.ler_json(ESTADO, {"feito": {}})
    agora = datetime.now(timezone.utc)
    limite = time.time() + a.minutos * 60
    fila = [j for j in janelas((2017, 1), (agora.year, agora.month)) if j[2] not in estado["feito"]][::-1]
    anos, erros, feitos = {}, collections.Counter(), 0
    for ini, fim, rotulo in fila:
        if time.time() > limite:
            break
        arts, erro = buscar_janela(ini, fim)
        time.sleep(6)   # limite público do GDELT: 1 requisição a cada 5 s
        if arts is None:
            erros[erro[:40]] += 1
            continue
        reg = {"n": len(arts), "rel": 0, "fora": 0}
        for art in arts:
            data = (art.get("seendate") or "")[:8]
            if not (ini[:8] <= data < fim[:8]):
                reg["fora"] += 1
            # A busca do GDELT casa o texto inteiro; o título sozinho muitas vezes não traz o termo.
            # Nada é descartado aqui: o filtro só marca, e a triagem decide.
            rel, motivo, elos = cadeia.avaliar(art.get("title", ""))
            reg["rel"] += rel
            motivo = motivo or "consulta-dirigida (termo no texto, não no título)"
            ano = data[:4]
            if ano not in anos:
                p_ano = f"{DIR}/{ano}.jsonl"
                anos[ano] = ({r["chave"]: r for r in map(json.loads, open(p_ano, encoding="utf-8"))}
                             if os.path.exists(p_ano) else {})
            k = rede.normalizar(art.get("title", ""))
            anos[ano].setdefault(k, {"publicado": f"{data[:4]}-{data[4:6]}-{data[6:8]}", "titulo": art.get("title"),
                                     "link": art.get("url"), "veiculo": art.get("domain"),
                                     "idioma": art.get("language"), "pais_fonte": art.get("sourcecountry"),
                                     "relevancia": motivo, "elos_pre": elos, "chave": k})
        estado["feito"][rotulo] = reg
        feitos += 1
    os.makedirs(DIR, exist_ok=True)
    for ano, itens in anos.items():
        with open(f"{DIR}/{ano}.jsonl", "w", encoding="utf-8") as f:
            for r in sorted(itens.values(), key=lambda r: r["publicado"]):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    rede.gravar_json(ESTADO, estado)

    por_ano, veic, total = collections.Counter(), collections.Counter(), 0
    for nome in sorted(os.listdir(DIR)):
        for r in map(json.loads, open(f"{DIR}/{nome}", encoding="utf-8")):
            por_ano[r["publicado"][:4]] += 1
            veic[r["veiculo"]] += 1
            total += 1
    f_ = estado["feito"]
    md = [f"# Notícias retroativas via GDELT — {agora:%Y-%m-%d}", "",
          f"- Meses consultados: {len(f_)}; pendentes: {len(fila) - feitos}; erros nesta execução: {dict(erros) or 'nenhum'}",
          f"- Itens únicos relevantes: **{total}**",
          f"- Meses no teto de 250 artigos (cobertura possivelmente incompleta): {sum(1 for v in f_.values() if v['n'] >= 250)}",
          f"- Itens fora da janela pedida: {sum(v['fora'] for v in f_.values())} de {sum(v['n'] for v in f_.values())} (controle do filtro de datas)",
          "- Só título, veículo e data de captura pelo GDELT. Texto não lido.", "",
          "| Ano | Itens |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(por_ano.items())]
    md += ["", "| Veículo | Itens |", "|---|---|"] + [f"| {k} | {v} |" for k, v in veic.most_common(25)]
    with open("noticias/retro/gdelt.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"retro_gdelt: {feitos} meses, {total} itens, erros {dict(erros)}")
    sys.exit(0 if feitos else 2)


if __name__ == "__main__":
    main()
