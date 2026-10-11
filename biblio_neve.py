#!/usr/bin/env python3
"""
biblio_neve.py — etapa 4: bola de neve (snowballing) sobre o corpus.

Busca por palavra-chave perde obras que usam outro vocabulário. A técnica padrão
de revisão sistemática completa a busca pelas citações:
  - para trás: o que as obras centrais citam (referenced_works no OpenAlex)
  - para frente: quem cita as obras centrais (filtro cites: no OpenAlex)

Obras centrais (sementes): escopo "brasil", relevância "forte", com id OpenAlex,
as N mais citadas (--sementes). Candidatos passam pelo mesmo filtro de cadeia.py
e entram no corpus com achado_por "neve:tras" ou "neve:frente".
Uma rodada por execução; rodar de novo é a 2ª rodada (as novas obras viram
sementes). Parar quando a rodada trouxer poucas obras novas (saturação).

Saída: biblio/corpus.jsonl atualizado · biblio/neve.md
"""

import argparse
import collections
import json
import os
import sys
import time
from datetime import datetime, timezone

import biblio
import cadeia
import rede

API = "https://api.openalex.org/works"


def converter(w):
    loc = (w.get("primary_location") or {})
    return {"titulo": w.get("title") or "", "ano": w.get("publication_year"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", "").lower() or None,
            "autores": [a["author"]["display_name"] for a in w.get("authorships", [])[:20] if a.get("author")],
            "veiculo": ((loc.get("source") or {}).get("display_name")) or "", "tipo": w.get("type") or "",
            "idioma": w.get("language") or "", "resumo": biblio._resumo_openalex(w.get("abstract_inverted_index"))[:3000],
            "acesso_aberto": (w.get("open_access") or {}).get("oa_url"), "citacoes": w.get("cited_by_count"),
            "ids": {"openalex": w.get("id")}, "link": (w.get("doi") or loc.get("landing_page_url") or w.get("id")),
            "paises_autores": sorted({c for a in w.get("authorships", []) for c in a.get("countries", [])})}


def lote(ids):
    """Busca até 50 obras por id OpenAlex numa chamada."""
    curtos = "|".join(i.rsplit("/", 1)[-1] for i in ids)
    obj, cod, erro, _ = rede.buscar_json(API + "?" + rede.qs(filter=f"openalex:{curtos}", **{"per-page": 50},
                                                             mailto=rede.CONTATO or None))
    return (obj or {}).get("results", []), erro


def citantes(wid, maximo=200):
    out, cursor = [], "*"
    while cursor and len(out) < maximo:
        obj, cod, erro, _ = rede.buscar_json(API + "?" + rede.qs(filter=f"cites:{wid.rsplit('/', 1)[-1]}",
                                                                 **{"per-page": 200}, cursor=cursor,
                                                                 mailto=rede.CONTATO or None))
        if erro or not obj:
            break
        out += obj.get("results", [])
        cursor = (obj.get("meta") or {}).get("next_cursor") if obj.get("results") else None
    return out


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser()
    p.add_argument("--sementes", type=int, default=150)
    a = p.parse_args()
    corpus = collections.OrderedDict()
    with open(biblio.CORPUS, encoding="utf-8") as fh:
        for linha in fh:
            r = json.loads(linha)
            corpus[r["_k"]] = r
    feitas = set(rede.ler_json("biblio/neve-estado.json", []))
    sementes = sorted((r for r in corpus.values()
                       if r.get("escopo") == "brasil" and (r.get("relevancia") or "").startswith("forte")
                       and (r.get("ids") or {}).get("openalex") and r["ids"]["openalex"] not in feitas),
                      key=lambda r: -(r.get("citacoes") or 0))[: a.sementes]
    print(f"biblio_neve: {len(sementes)} sementes")

    # para trás: referências das sementes (precisa reabrir cada semente para ler referenced_works)
    refs = set()
    for i in range(0, len(sementes), 50):
        obras, erro = lote([s["ids"]["openalex"] for s in sementes[i:i + 50]])
        for w in obras:
            refs.update(w.get("referenced_works") or [])
        time.sleep(1)
    conhecidos = {(r.get("ids") or {}).get("openalex") for r in corpus.values()}
    refs -= conhecidos
    candidatos = []
    refs = sorted(refs)
    for i in range(0, len(refs), 50):
        obras, _ = lote(refs[i:i + 50])
        candidatos += [("neve:tras", w) for w in obras]
        time.sleep(1)
    # para frente: quem cita cada semente
    for s in sementes:
        candidatos += [("neve:frente", w) for w in citantes(s["ids"]["openalex"])
                       if w.get("id") not in conhecidos]
        time.sleep(1)

    relevantes, por_via = [], collections.Counter()
    for via, w in candidatos:
        r = converter(w)
        ok, motivo, elos = cadeia.avaliar(r["titulo"], r["resumo"], r["veiculo"])
        if not ok:
            continue
        r.update(relevancia=motivo, elos_pre=elos, coletado_em=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                 achado_por=[via])
        r["escopo"] = cadeia.escopo(r)
        relevantes.append(r)
        por_via[via] += 1
    novas = biblio.mesclar(corpus, relevantes)
    for k, r in corpus.items():
        r["_k"] = k
    ordenado = sorted(corpus.values(), key=lambda r: (-(r.get("ano") or 0), r["titulo"]))
    with open(biblio.CORPUS + ".tmp", "w", encoding="utf-8") as fh:
        for r in ordenado:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(biblio.CORPUS + ".tmp", biblio.CORPUS)
    with open("biblio/corpus.bib", "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(biblio.bibtex(r, r["_k"]) for r in ordenado) + "\n")
    with open("biblio/corpus.ris", "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(biblio.ris(r) for r in ordenado) + "\n")
    rede.gravar_json("biblio/neve-estado.json", sorted(feitas | {s["ids"]["openalex"] for s in sementes}))

    esc = collections.Counter(corpus[k].get("escopo") for k in novas)
    md = [f"# Bola de neve — {datetime.now(timezone.utc):%Y-%m-%d}", "",
          f"- Sementes nesta rodada: {len(sementes)} (núcleo Brasil, relevância forte, mais citadas)",
          f"- Candidatos: {len(candidatos)} (referências não vistas + citantes); relevantes pelo filtro: {len(relevantes)} "
          f"({dict(por_via)})",
          f"- **Obras novas no corpus: {len(novas)}** — por escopo: {dict(esc)}; corpus total: {len(corpus)}",
          "- Critério de parada: quando uma rodada trouxer menos de ~5% de obras novas em relação às sementes, saturou.", "",
          "| Ano | Obra | Via | Escopo |", "|---|---|---|---|"]
    for k in sorted(novas, key=lambda k: -(corpus[k].get("ano") or 0))[:150]:
        r = corpus[k]
        md.append(f"| {r.get('ano') or '—'} | [{r['titulo'][:150].replace('|', '/')}]({r.get('link') or ''}) | "
                  f"{', '.join(r['achado_por'])} | {r.get('escopo')} |")
    with open("biblio/neve.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print(f"biblio_neve: {len(novas)} obras novas de {len(candidatos)} candidatos")
    sys.exit(0)


if __name__ == "__main__":
    main()
