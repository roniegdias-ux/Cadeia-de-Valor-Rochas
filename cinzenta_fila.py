#!/usr/bin/env python3
"""
cinzenta_fila.py — prepara a fila de fichamento da literatura cinzenta (prompts/triagem.md §D).

Determinístico. Lê biblio/cinzenta/indice.jsonl e decide, por documento:
  - duplicata de versão (mesmo nome sem sufixos -1, -v2, _compressed…): fica o de texto maior
  - tabela pura (Exporta_Importa da Abirochas, relatórios mensais do Sindirochas): NÃO vai ao
    fichamento — os números repetem o ComexStat, já validado; só há tabelas, sem comentário
  - fora de escopo óbvio (código de ética, manual de contrapartida, páginas Joomla etc.)
  - o resto entra na fila: informes e estudos com texto corrido

Saída: biblio/cinzenta/fila.jsonl (1 linha por documento, com a decisão e o motivo).
"""

import collections
import json
import os
import re
import unicodedata

INDICE = "biblio/cinzenta/indice.jsonl"
SAIDA = "biblio/cinzenta/fila.jsonl"
TABELA = re.compile(r"exporta_?importa|^exportac(o|õ)es[-_](de[-_])?rochas|^exportacoes[-_]sindirochas|"
                    r"relat[oó]rio[-_ ]?(de[-_ ])?exporta|relatorio[-_]exporta|^novembro2020|^dezembro-2020|"
                    r"pauta[-_]de[-_]valores|sumario-link", re.I)
FORA = re.compile(r"index\.php|codigo-etica|manual-de-contrapartida|protocolo-agenda|resolucao-antaq|"
                  r"book_moveis|stone-finder|livro_guia", re.I)


def chave_versao(nome):
    n = unicodedata.normalize("NFKD", nome.lower()).encode("ascii", "ignore").decode()
    n = re.sub(r"\.pdf$", "", n)
    n = re.sub(r"([-_ ](v\d+|\d|compressed|b))+$", "", n)
    return re.sub(r"[^a-z0-9]+", "", n)


def emissor(r):
    s = r.get("site") or ""
    for nome in ("abirochas", "sindirochas", "centrorochas", "litos"):
        if nome in s:
            return nome.capitalize()
    return s


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    docs = [r for r in map(json.loads, open(INDICE, encoding="utf-8")) if r.get("caracteres", 0) >= 200]
    grupos = collections.defaultdict(list)
    for r in docs:
        grupos[(emissor(r), chave_versao(r["arquivo"]))].append(r)
    fila = []
    for (em, _), rs in sorted(grupos.items()):
        rs.sort(key=lambda r: -r["caracteres"])
        for i, r in enumerate(rs):
            if i:
                dec, motivo = "duplicata", f"versão de {rs[0]['arquivo']}"
            elif TABELA.search(r["arquivo"]):
                dec, motivo = "tabela", "só tabelas de comércio exterior (repete o ComexStat)"
            elif FORA.search(r["arquivo"]):
                dec, motivo = "fora", "fora de escopo do estudo"
            else:
                dec, motivo = "fichar", ""
            fila.append({"id": r["id"], "arquivo": r["arquivo"], "url": r["url"], "emissor": em,
                         "caracteres": r["caracteres"], "texto": f"biblio/cinzenta/textos/{r['id']}.txt",
                         "decisao": dec, "motivo": motivo})
    with open(SAIDA, "w", encoding="utf-8") as f:
        for r in fila:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    c = collections.Counter(r["decisao"] for r in fila)
    print(f"cinzenta_fila: {len(fila)} documentos → " + ", ".join(f"{k} {v}" for k, v in c.most_common()))


if __name__ == "__main__":
    main()
