#!/usr/bin/env python3
"""
biblio.py — trilha 2: levantamento bibliográfico.

Dois modos:
  --backfill      toda a literatura desde config.biblio_consultas.inicio_backfill
                  (uma vez; depois só incremental)
  (padrão)        incremental: só publicações dos últimos 2 anos civis,
                  rodar semanalmente — literatura não muda de um dia para o outro

Fontes: OpenAlex (espinha), Crossref (DOIs recentes que o OpenAlex ainda não
pegou), BDTD (teses e dissertações brasileiras). Só entram as confirmadas
na matriz (fontes/confirmadas.json).

Corpus acumulado: biblio/corpus.jsonl (1 registro por obra, dedup por DOI e
por título normalizado+ano). Exportações: biblio/corpus.bib e biblio/corpus.ris
para Zotero/Mendeley. Relatório: biblio/AAAA-MM-DD-biblio.md com as obras
NOVAS da execução, por elo da cadeia.

Tudo que o robô afirma vem de metadado (título, resumo, ano, veículo). Ele não
lê o PDF e não diz o que a obra "conclui".
"""

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import cadeia
import rede

CORPUS = "biblio/corpus.jsonl"
MAX_POR_TERMO = {"openalex": 2000, "crossref": 300, "bdtd": 500}


def _resumo_openalex(inv):
    if not inv:
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


def openalex(termo, ano_ini, log):
    chave = os.environ.get("OPENALEX_API_KEY")
    cursor, n, out = "*", 0, []
    while cursor and n < MAX_POR_TERMO["openalex"]:
        url = ("https://api.openalex.org/works?" + rede.qs(
            filter=f"title_and_abstract.search:{termo},from_publication_date:{ano_ini}-01-01",
            **{"per-page": 200}, cursor=cursor, mailto=rede.CONTATO or None, api_key=chave))
        obj, cod, erro, _ = rede.buscar_json(url)
        if erro:
            log.append({"fonte": "openalex", "termo": termo, "http": cod, "erro": erro})
            return out
        for w in obj.get("results", []):
            loc = (w.get("primary_location") or {})
            out.append({
                "titulo": w.get("title") or "", "ano": w.get("publication_year"),
                "doi": (w.get("doi") or "").replace("https://doi.org/", "").lower() or None,
                "autores": [a["author"]["display_name"] for a in w.get("authorships", [])[:20] if a.get("author")],
                "veiculo": ((loc.get("source") or {}).get("display_name")) or "",
                "tipo": w.get("type") or "", "idioma": w.get("language") or "",
                "resumo": _resumo_openalex(w.get("abstract_inverted_index"))[:3000],
                "acesso_aberto": (w.get("open_access") or {}).get("oa_url"),
                "citacoes": w.get("cited_by_count"), "ids": {"openalex": w.get("id")},
                "link": (w.get("doi") or loc.get("landing_page_url") or w.get("id")),
                "paises_autores": sorted({c for a in w.get("authorships", []) for c in a.get("countries", [])}),
            })
        n += len(obj.get("results", []))
        cursor = (obj.get("meta") or {}).get("next_cursor")
        if not obj.get("results"):
            break
    log.append({"fonte": "openalex", "termo": termo, "http": 200, "erro": None, "registros": len(out)})
    return out


def crossref(termo, ano_ini, log):
    out, cursor = [], "*"
    while cursor and len(out) < MAX_POR_TERMO["crossref"]:
        url = "https://api.crossref.org/works?" + rede.qs(
            **{"query.bibliographic": termo}, filter=f"from-pub-date:{ano_ini}",
            rows=100, cursor=cursor, mailto=rede.CONTATO or None,
            select="DOI,title,author,issued,container-title,type,abstract,URL,language,is-referenced-by-count")
        obj, cod, erro, _ = rede.buscar_json(url)
        if erro:
            log.append({"fonte": "crossref", "termo": termo, "http": cod, "erro": erro})
            return out
        msg = obj.get("message", {})
        for w in msg.get("items", []):
            ano = ((w.get("issued") or {}).get("date-parts") or [[None]])[0][0]
            out.append({
                "titulo": (w.get("title") or [""])[0], "ano": ano, "doi": (w.get("DOI") or "").lower() or None,
                "autores": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (w.get("author") or [])[:20]],
                "veiculo": (w.get("container-title") or [""])[0], "tipo": w.get("type") or "",
                "idioma": w.get("language") or "", "resumo": re.sub(r"<[^>]+>", " ", w.get("abstract") or "")[:3000],
                "acesso_aberto": None, "citacoes": w.get("is-referenced-by-count"),
                "ids": {"crossref": w.get("DOI")}, "link": w.get("URL"), "paises_autores": [],
            })
        cursor = msg.get("next-cursor") if msg.get("items") else None
    log.append({"fonte": "crossref", "termo": termo, "http": 200, "erro": None, "registros": len(out)})
    return out


def bdtd(termo, ano_ini, log):
    out, pagina = [], 1
    while len(out) < MAX_POR_TERMO["bdtd"]:
        url = "https://bdtd.ibict.br/vufind/api/v1/search?" + rede.qs(
            lookfor=f'"{termo}"', type="AllFields", limit=100, page=pagina) + \
            "".join(f"&field[]={f}" for f in ("id", "title", "authors", "publicationDates", "urls", "summary", "institutions", "formats"))
        obj, cod, erro, _ = rede.buscar_json(url, ua=rede.UA)
        if erro:
            log.append({"fonte": "bdtd", "termo": termo, "http": cod, "erro": erro})
            return out
        recs = obj.get("records") or []
        for r in recs:
            anos = [int(x[:4]) for x in (r.get("publicationDates") or []) if str(x)[:4].isdigit()]
            ano = anos[0] if anos else None
            if ano and ano < ano_ini:
                continue
            autores = r.get("authors") or {}
            nomes = list((autores.get("primary") or {}).keys()) if isinstance(autores, dict) else []
            out.append({
                "titulo": r.get("title") or "", "ano": ano, "doi": None, "autores": nomes,
                "veiculo": "; ".join(r.get("institutions") or []), "tipo": "tese/dissertação",
                "idioma": "pt", "resumo": " ".join(r.get("summary") or [])[:3000], "acesso_aberto": None,
                "citacoes": None, "ids": {"bdtd": r.get("id")},
                "link": ((r.get("urls") or [{}])[0].get("url")) if r.get("urls") else None, "paises_autores": ["BR"],
            })
        if len(recs) < 100:
            break
        pagina += 1
    log.append({"fonte": "bdtd", "termo": termo, "http": 200, "erro": None, "registros": len(out)})
    return out


COLETORES = {"openalex": openalex, "crossref": crossref, "bdtd": bdtd}


def chave_titulo(r):
    return f"{rede.normalizar(r['titulo'])[:120]}|{r.get('ano') or ''}"


def mesclar(corpus, novos):
    """Dedup por DOI e por título+ano. Devolve as chaves das obras novas."""
    por_doi = {r["doi"]: k for k, r in corpus.items() if r.get("doi")}
    adicionadas = []
    for r in novos:
        k = por_doi.get(r["doi"]) if r.get("doi") else None
        k = k or chave_titulo(r)
        if k in corpus:
            alvo = corpus[k]
            alvo["ids"].update(r["ids"])
            alvo["achado_por"] = sorted(set(alvo["achado_por"]) | set(r["achado_por"]))
            for campo in ("resumo", "doi", "acesso_aberto", "veiculo"):
                if not alvo.get(campo) and r.get(campo):
                    alvo[campo] = r[campo]
            continue
        corpus[k] = r
        if r.get("doi"):
            por_doi[r["doi"]] = k
        adicionadas.append(k)
    return adicionadas


def bibtex(r, k):
    chave = re.sub(r"\W", "", (r["autores"][0].split()[-1] if r["autores"] else "anon")) + str(r.get("ano") or "")
    tipo = "phdthesis" if "tese" in r["tipo"] else "article"
    campos = {"title": r["titulo"], "author": " and ".join(r["autores"]), "year": r.get("ano"),
              "journal" if tipo == "article" else "school": r.get("veiculo"), "doi": r.get("doi"), "url": r.get("link"),
              "keywords": ", ".join(r.get("elos_pre", []))}
    corpo = ",\n".join(f"  {c} = {{{str(v).replace('{', '').replace('}', '')}}}" for c, v in campos.items() if v)
    return f"@{tipo}{{{chave}_{hashlib.sha1(k.encode()).hexdigest()[:6]},\n{corpo}\n}}"


def ris(r):
    linhas = ["TY  - " + ("THES" if "tese" in r["tipo"] else "JOUR"), f"TI  - {r['titulo']}"]
    linhas += [f"AU  - {a}" for a in r["autores"]]
    for tag, campo in (("PY", "ano"), ("JO", "veiculo"), ("DO", "doi"), ("UR", "link"), ("AB", "resumo")):
        if r.get(campo):
            linhas.append(f"{tag}  - {r[campo]}")
    linhas += [f"KW  - {e}" for e in r.get("elos_pre", [])]
    return "\n".join(linhas + ["ER  - "])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--data")
    p.add_argument("--fontes", default="openalex,crossref,bdtd")
    p.add_argument("--forcar", action="store_true", help="ignora a matriz de acesso")
    a = p.parse_args()

    agora = datetime.now(timezone.utc)
    data = a.data or agora.strftime("%Y-%m-%d")
    cfg = rede.ler_json("config.json")["biblio_consultas"]
    ano_ini = cfg["inicio_backfill"] if a.backfill else agora.year - 1
    confirmadas = {c["id"] for c in rede.ler_json("fontes/confirmadas.json", []) if c["veredito"] == "COLETAVEL"}
    fontes = [f for f in a.fontes.split(",") if a.forcar or f in confirmadas]
    if not fontes:
        sys.exit("Nenhuma fonte bibliográfica confirmada. Rode verificar_fontes.py --trilha biblio.")

    log, brutos = [], []
    for f in fontes:
        for termo in cfg["termos"]:
            for r in COLETORES[f](termo, ano_ini, log):
                r["achado_por"] = [f"{f}:{termo}"]
                brutos.append(r)

    relevantes, descartados = [], 0
    for r in brutos:
        ok, motivo, elos = cadeia.avaliar(r["titulo"], r["resumo"], r["veiculo"])
        if not ok:
            descartados += 1
            continue
        r.update(relevancia=motivo, elos_pre=elos, coletado_em=data)
        relevantes.append(r)

    corpus = collections.OrderedDict()
    if os.path.exists(CORPUS):
        with open(CORPUS, encoding="utf-8") as fh:
            for linha in fh:
                r = json.loads(linha)
                corpus[r["_k"]] = r
    novas = mesclar(corpus, relevantes)
    for k, r in corpus.items():
        r["_k"] = k

    os.makedirs("biblio", exist_ok=True)
    ordenado = sorted(corpus.values(), key=lambda r: (-(r.get("ano") or 0), r["titulo"]))
    with open(CORPUS + ".tmp", "w", encoding="utf-8") as fh:
        for r in ordenado:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(CORPUS + ".tmp", CORPUS)
    with open("biblio/corpus.bib", "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(bibtex(r, r["_k"]) for r in ordenado) + "\n")
    with open("biblio/corpus.ris", "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(ris(r) for r in ordenado) + "\n")

    erros = [l for l in log if l["erro"]]
    escrever_md(data, a.backfill, ano_ini, fontes, log, len(brutos), descartados,
                [corpus[k] for k in novas], len(corpus))
    print(f"biblio/{data}: {len(brutos)} brutos, {descartados} fora do recorte, "
          f"{len(novas)} obras novas; corpus = {len(corpus)}. {len(erros)} consultas com erro.")
    sys.exit(2 if erros and len(erros) > len(log) / 2 else 0)


def escrever_md(data, backfill, ano_ini, fontes, log, n_brutos, descartados, novas, total):
    erros = [l for l in log if l["erro"]]
    md = [f"# Levantamento bibliográfico — {data}" + (" (backfill)" if backfill else ""), "",
          "## Registro de coleta", "",
          f"- Fontes: {', '.join(fontes)}; publicações desde {ano_ini}",
          f"- Consultas: {len(log)}; com erro: {len(erros)}"
          + ("" if not erros else " — " + "; ".join(f"{l['fonte']}/{l['termo']}: HTTP {l['http']}" for l in erros[:15])),
          f"- Registros brutos: {n_brutos}; fora do recorte (filtro cadeia.py): {descartados}",
          f"- **Obras novas: {len(novas)}**; corpus acumulado: {total}",
          "- Elo = pré-classificação por palavra-chave sobre título/resumo. Não é leitura da obra.", ""]
    por_elo = collections.defaultdict(list)
    for r in novas:
        por_elo[(r["elos_pre"] or ["sem elo"])[0]].append(r)
    for e in sorted(por_elo, key=lambda e: (e == "sem elo", int(e[1:]) if e != "sem elo" else 0)):
        nome = cadeia.ELOS[e][0] if e in cadeia.ELOS else "sem elo identificado"
        md += [f"## {e} — {nome} ({len(por_elo[e])})", "",
               "| Ano | Obra | Autores | Veículo | Tipo | Outros elos |", "|---|---|---|---|---|---|"]
        for r in sorted(por_elo[e], key=lambda r: -(r.get("ano") or 0)):
            aut = "; ".join(r["autores"][:3]) + (" et al." if len(r["autores"]) > 3 else "")
            t = r["titulo"].replace("|", "/")[:180]
            md.append(f"| {r.get('ano') or '—'} | [{t}]({r.get('link') or ''}) | {aut} | {(r['veiculo'] or '')[:50]} | "
                      f"{r['tipo']} | {' '.join(r['elos_pre'][1:])} |")
        md.append("")
    with open(f"biblio/{data}-biblio.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
