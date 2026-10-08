#!/usr/bin/env python3
"""
noticias.py — trilha 1: varredura de notícias do setor (diária).

Diferença deliberada em relação ao inteligencia-midia: o noticiário de rochas
ornamentais é ralo (dezenas de itens/semana, não milhares/dia) e chega atrasado
ao Google News. Por isso a janela padrão é de 7 dias e a novidade é decidida
pelo histórico (noticias/vistos.json): cada item é reportado uma única vez, no
dia em que aparece pela primeira vez.

Saída:
  noticias/AAAA-MM-DD-bruto.json   — itens novos e relevantes + log por fonte
  noticias/AAAA-MM-DD-noticias.md  — registro de coleta + itens por elo da cadeia

Uso: python3 noticias.py [--dias 7] [--sem-historico] [--data AAAA-MM-DD]
Código de saída 2 = coleta degradada (mais da metade das fontes falhou).
"""

import argparse
import collections
import concurrent.futures as cf
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

import cadeia
import rede

GN = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
LOCALE = {"pt": ("pt-BR", "BR", "BR:pt-419"), "en": ("en-US", "US", "US:en"),
          "it": ("it", "IT", "IT:it"), "es": ("es-419", "AR", "AR:es-419")}
VISTOS = "noticias/vistos.json"


def alvos(config, confirmadas, forcar):
    """(nome, url, generalista). Google News só entra se a matriz o confirmou."""
    out = []
    gn_ok = forcar or any(c["id"] == "gn_pt" and c["veredito"] == "COLETAVEL" for c in confirmadas)
    if gn_ok:
        for lang, consultas in config["noticias_consultas"].items():
            if lang.startswith("_"):
                continue
            hl, gl, ceid = LOCALE[lang]
            for q in consultas:
                url = GN.format(q=urllib.parse.quote_plus(f"{q} when:30d"), hl=hl, gl=gl, ceid=ceid)
                out.append((f"GN[{lang}] {q}", url, False))
    for c in confirmadas:
        if c["trilha"] == "noticias" and c["tipo"] == "rss" and c["veredito"] == "COLETAVEL" \
                and c["id"] != "gn_pt" and c.get("url"):
            out.append((c["nome"], c["url"], True))
    return out


def coletar(nome, url, generalista, inicio, fim):
    linha = {"fonte": nome, "url": url, "http": None, "tentativas": 0, "itens_totais": 0,
             "na_janela": 0, "relevantes": 0, "sem_data": 0, "erro": None}
    cod, corpo, erro, n = rede.buscar(url)
    linha.update(http=cod, tentativas=n)
    if erro:
        linha["erro"] = erro
        return linha, []
    try:
        crus = rede.extrair_itens(corpo)
    except ValueError as e:
        linha["erro"] = str(e)
        return linha, []
    linha["itens_totais"] = len(crus)
    saida = []
    for c in crus:
        d = rede.parse_data(c["data_bruta"])
        if d is None:
            linha["sem_data"] += 1
            continue
        if not (inicio <= d <= fim + timedelta(hours=1)):
            continue
        linha["na_janela"] += 1
        rel, motivo, elos = cadeia.avaliar(c["titulo"], c["resumo"])
        # Consulta do Google News já é filtro; feed generalista precisa passar.
        if generalista and not rel:
            continue
        linha["relevantes"] += 1
        saida.append({"fonte": nome, "titulo": c["titulo"], "link": c["link"],
                      "publicado": d.isoformat(), "resumo": c["resumo"][:500],
                      "veiculo": c["fonte_declarada"] or nome,
                      "relevancia": motivo or "consulta-dirigida", "elos_pre": elos,
                      "chave": rede.normalizar(c["titulo"])})
    return linha, saida


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dias", type=int, default=7)
    p.add_argument("--data")
    p.add_argument("--sem-historico", action="store_true")
    p.add_argument("--forcar-google", action="store_true", help="usa Google News mesmo sem matriz")
    a = p.parse_args()

    agora = datetime.now(timezone.utc)
    data = a.data or agora.strftime("%Y-%m-%d")
    inicio = agora - timedelta(days=a.dias)
    config = rede.ler_json("config.json")
    confirmadas = rede.ler_json("fontes/confirmadas.json", [])
    lista = alvos(config, confirmadas, a.forcar_google)
    if not lista:
        sys.exit("Nenhuma fonte de notícias confirmada. Rode verificar_fontes.py primeiro.")

    log, itens = [], []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for linha, novos in ex.map(lambda t: coletar(*t, inicio, agora), lista):
            log.append(linha)
            itens.extend(novos)

    # Deduplicação: mesma manchete normalizada em fontes/consultas diferentes.
    por_chave = collections.OrderedDict()
    for it in sorted(itens, key=lambda x: x["publicado"]):
        k = it["chave"]
        if k in por_chave:
            por_chave[k]["fontes"] = sorted(set(por_chave[k]["fontes"]) | {it["fonte"]})
        else:
            it["fontes"] = [it.pop("fonte")]
            por_chave[k] = it
    vistos = {} if a.sem_historico else rede.ler_json(VISTOS, {})
    novos = [it for k, it in por_chave.items() if k not in vistos]
    for it in novos:
        vistos[it["chave"]] = data

    falhas = [l for l in log if l["erro"]]
    degradada = len(falhas) > len(log) / 2
    bruto = {"meta": {"gerado_em": agora.isoformat(), "janela_inicio": inicio.isoformat(),
                      "fontes_tentadas": len(log), "fontes_com_erro": len(falhas),
                      "itens_na_janela_dedup": len(por_chave), "itens_novos": len(novos),
                      "degradada": degradada},
             "log": sorted(log, key=lambda l: (l["erro"] is None, -l["relevantes"])),
             "itens": sorted(novos, key=lambda x: x["publicado"], reverse=True)}
    rede.gravar_json(f"noticias/{data}-bruto.json", bruto)
    if not a.sem_historico:
        rede.gravar_json(VISTOS, vistos)
    escrever_md(data, bruto)
    print(f"noticias/{data}: {len(novos)} itens novos; {len(falhas)}/{len(log)} fontes com erro.")
    for l in falhas:
        print(f"  FALHOU  {l['fonte'][:40]:<40} HTTP {l['http']}  {l['erro']}")
    sys.exit(2 if degradada else 0)


def escrever_md(data, b):
    m = b["meta"]
    falhas = [l for l in b["log"] if l["erro"]]
    md = [f"# Notícias — cadeia de rochas ornamentais — {data}", ""]
    if m["degradada"]:
        md += ["> **COLETA DEGRADADA:** mais da metade das fontes falhou. Não ler ausência de notícia como ausência de fato.", ""]
    md += ["## Registro de coleta", "",
           f"- Fontes tentadas: {m['fontes_tentadas']}; com erro: {m['fontes_com_erro']}"
           + (" — " + "; ".join(f"**{l['fonte']}** HTTP {l['http']} ({l['erro'][:80]})" for l in falhas) if falhas else ""),
           f"- Janela: desde {m['janela_inicio'][:16]} UTC; itens únicos na janela: {m['itens_na_janela_dedup']}; **novos hoje: {m['itens_novos']}**",
           "- Elos são pré-classificação por palavra-chave (cadeia.py), feita só sobre manchete e resumo do feed. Corpo não lido.", ""]
    por_elo = collections.defaultdict(list)
    for it in b["itens"]:
        por_elo[(it["elos_pre"] or ["sem elo"])[0]].append(it)   # 1 linha por item
    ordem = sorted(por_elo, key=lambda e: (e == "sem elo", int(e[1:]) if e != "sem elo" else 0))
    for e in ordem:
        nome = cadeia.ELOS[e][0] if e in cadeia.ELOS else "sem elo identificado"
        md += [f"## {e} — {nome} ({len(por_elo[e])}, por elo principal)", "", "| Data | Manchete | Veículo | Outros elos | Achado via |", "|---|---|---|---|---|"]
        for it in por_elo[e]:
            t = it["titulo"].replace("|", "/")
            md.append(f"| {it['publicado'][:10]} | [{t}]({it['link']}) | {it['veiculo']} | {' '.join(it['elos_pre'][1:])} | {', '.join(it['fontes'])[:60]} |")
        md.append("")
    if not b["itens"]:
        md += ["Nenhum item novo.", ""]
    with open(f"noticias/{data}-noticias.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
