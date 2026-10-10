#!/usr/bin/env python3
"""
anm.py — etapa 3: dados da Agência Nacional de Mineração (geografia da lavra).

A ANM mudou os endereços de dados abertos em 2026 (o antigo app.anm.gov.br/
dadosabertos saiu do ar em 30/06/2026). Para não depender de URL decorada, o
script primeiro LISTA o servidor (índice de diretórios) e grava o que achou;
depois baixa:

  - CFEM (arrecadação por substância × município): filtrada pelas substâncias de
    config.cfem.substancias_regex e agregada → dados/series/anm_cfem_rochas.csv
  - Anuário Mineral Brasileiro e Relatório Anual de Lavra (produção por
    substância × UF/município): linhas das substâncias de rocha ornamental
    → dados/series/anm_<arquivo>.csv

Saída de diagnóstico: fontes/anm-arquivos.json e dados/anm.md
ATENÇÃO metodológica: "GRANITO" na ANM mistura brita e rocha ornamental; a série
grava a substância exatamente como a ANM nomeia, sem somar por conta própria.
"""

import collections
import csv
import io
import json
import os
import re
import sys
import urllib.parse
import zipfile
from datetime import datetime, timezone

import dados
import rede

BASES = ["https://dadosabertos.anm.gov.br/", "https://app.anm.gov.br/dadosabertos/"]
HREF = re.compile(r'href=["\']([^"\'?#]+)["\']', re.I)
ARQ = re.compile(r"\.(csv|zip|xlsx?)$", re.I)


def listar(base, log, prof=0, vistos=None):
    vistos = vistos if vistos is not None else set()
    if base in vistos or prof > 3 or len(vistos) > 400:
        return {}
    vistos.add(base)
    cod, corpo, erro, _ = rede.buscar(base, tentativas=2)
    if erro:
        log.append(f"{base}: HTTP {cod} {erro[:100]}")
        return {}
    achados = {}
    for h in HREF.findall(corpo.decode("utf-8", "replace")):
        u = urllib.parse.urljoin(base, h)
        if not u.startswith(base) or u == base:
            continue
        if ARQ.search(u):
            achados[u] = prof
        elif u.endswith("/"):
            achados.update(listar(u, log, prof + 1, vistos))
    return achados


def ler_tabela(url, corpo):
    """Devolve lista de (nome, DictReader-like rows) para CSV ou ZIP com CSVs."""
    if url.lower().endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(corpo))
        return [(n, z.read(n)) for n in z.namelist() if n.lower().endswith(".csv")]
    return [(url.rsplit("/", 1)[-1], corpo)]


def linhas_csv(b):
    try:
        t = b.decode("utf-8-sig")
    except UnicodeDecodeError:
        t = b.decode("latin-1")
    dial = csv.Sniffer().sniff(t[:5000], delimiters=";,|\t")
    return csv.DictReader(io.StringIO(t), dialect=dial)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    cfg = rede.ler_json("config.json")
    rx = re.compile(cfg["cfem"]["substancias_regex"], re.I)
    log, arquivos = [], {}
    for b in BASES:
        arquivos.update(listar(b, log))
    rede.gravar_json("fontes/anm-arquivos.json", sorted(arquivos))
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resumo = []

    # CFEM: arrecadação por substância e município
    agg = collections.defaultdict(lambda: [0.0, 0.0])
    cfem_urls = [u for u in arquivos if re.search(r"cfem", u, re.I) and re.search(r"arrecad", u, re.I)]
    for u in cfem_urls:
        cod, corpo, erro, _ = rede.buscar(u, tentativas=3)
        if erro:
            log.append(f"{u}: HTTP {cod} {erro[:100]}")
            continue
        for nome, b in ler_tabela(u, corpo):
            leitor = linhas_csv(b)
            cab = leitor.fieldnames or []
            c_ano, c_sub = dados._col(cab, "ano"), dados._col(cab, "subst")
            c_uf, c_mun = dados._col(cab, "uf", "estado"), dados._col(cab, "munic")
            c_val = dados._col(cab, "valorrecolhido", "valor recolhido", "valor")
            c_qtd, c_un = dados._col(cab, "quantidade"), dados._col(cab, "unidade")
            if not (c_ano and c_sub and c_val):
                log.append(f"{nome}: colunas não reconhecidas {cab[:12]}")
                continue
            n = 0
            for r in leitor:
                sub = (r.get(c_sub) or "").upper()
                if not rx.search(rede.sem_acento(sub)):
                    continue
                k = (r.get(c_ano), r.get(c_uf) if c_uf else "", r.get(c_mun) if c_mun else "", sub,
                     r.get(c_un) if c_un else "")
                agg[k][0] += dados._num(r.get(c_val))
                agg[k][1] += dados._num(r.get(c_qtd)) if c_qtd else 0
                n += 1
            resumo.append(f"CFEM `{nome}`: {n} linhas de rochas (colunas: ano={c_ano}, substância={c_sub}, valor={c_val})")
    if agg:
        linhas = [{"ano": k[0], "uf": k[1], "municipio": k[2], "substancia": k[3], "unidade": k[4],
                   "valor_recolhido": round(v[0], 2), "quantidade": round(v[1], 3), "fonte": "anm_cfem",
                   "coletado_em": hoje} for k, v in sorted(agg.items())]
        total, novas, _ = dados.gravar_serie("anm_cfem_rochas", linhas)
        resumo.append(f"**anm_cfem_rochas**: {total} linhas (ano × UF × município × substância)")

    # AMB / RAL: produção por substância
    prod_urls = [u for u in arquivos if re.search(r"amb|anuario|anu%c3%a1rio|ral|producao|produ%c3%a7%c3%a3o", u, re.I)
                 and not re.search(r"cfem", u, re.I)]
    for u in prod_urls[:40]:
        cod, corpo, erro, _ = rede.buscar(u, tentativas=3)
        if erro:
            log.append(f"{u}: HTTP {cod} {erro[:100]}")
            continue
        for nome, b in ler_tabela(u, corpo):
            try:
                leitor = linhas_csv(b)
            except csv.Error as e:
                log.append(f"{nome}: CSV ilegível ({e})")
                continue
            cab = leitor.fieldnames or []
            c_sub = dados._col(cab, "subst")
            if not c_sub:
                resumo.append(f"`{nome}`: sem coluna de substância, ignorado (colunas: {cab[:8]})")
                continue
            sel = [dict(r, fonte="anm", arquivo=nome, coletado_em=hoje) for r in leitor
                   if rx.search(rede.sem_acento((r.get(c_sub) or "").upper()))]
            if sel:
                serie = "anm_" + re.sub(r"\W+", "_", nome.rsplit(".", 1)[0]).lower()[:50]
                total, _, _ = dados.gravar_serie(serie, sel)
                resumo.append(f"**{serie}**: {total} linhas de rochas ornamentais")

    md = [f"# ANM — geografia da lavra — {hoje}", "",
          f"- Arquivos encontrados no servidor de dados abertos: {len(arquivos)} (lista em `fontes/anm-arquivos.json`)",
          f"- Arquivos CFEM de arrecadação: {len(cfem_urls)}; arquivos de produção (AMB/RAL): {len(prod_urls)}", ""]
    md += [f"- {x}" for x in resumo]
    if log:
        md += ["", "## Falhas", ""] + [f"- {x}" for x in log[:40]]
    md += ["", "_\"GRANITO\" na ANM mistura brita e rocha ornamental: não somar sem recorte._"]
    with open("dados/anm.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"anm: {len(arquivos)} arquivos listados; {len(resumo)} séries/registros; {len(log)} falhas")
    sys.exit(0 if arquivos else 2)


if __name__ == "__main__":
    main()
