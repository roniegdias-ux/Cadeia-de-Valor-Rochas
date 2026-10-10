#!/usr/bin/env python3
"""
mapeamento.py — anexo estatístico do mapeamento da cadeia (só tabelas, sem
interpretação). Regenerado a cada execução mensal; o texto analítico fica em
estudo/mapeamento-v*.md e cita estas tabelas.

Saída: estudo/anexo-estatistico.md
Tudo em US$ correntes (FOB), salvo indicação. Fontes: ComexStat (exportação e
importação brasileira), UN Comtrade (concorrentes e mercado dos EUA), corpus
bibliográfico (biblio/corpus.jsonl).
"""

import collections as C
import csv
import json
import os
from datetime import datetime, timezone

S = "dados/series"
GRUPO = {"2514": "ardósia", "6803": "ardósia", "2515": "brutas carbonáticas (mármore)",
         "2516": "brutas silicáticas (granito etc.)", "25062000": "brutas silicáticas (granito etc.)",
         "6801": "beneficiadas", "6802": "beneficiadas"}
M49 = {"76": "Brasil", "156": "China", "380": "Itália", "699": "Índia", "792": "Turquia", "724": "Espanha",
       "620": "Portugal", "818": "Egito", "300": "Grécia", "842": "EUA", "484": "México", "124": "Canadá",
       "710": "África do Sul", "826": "Reino Unido", "251": "França", "276": "Alemanha", "246": "Finlândia"}


def ler(nome):
    p = f"{S}/{nome}.csv"
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


def mi(v):
    return f"{v / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(v, d=0):
    s = f"{v:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(a, b):
    return num(100 * a / b, 1) + "%" if b else "—"


def exportacoes():
    ex = ler("comex_export_sh4_pais")
    for r in ler("comex_export_quartzito_pais"):
        ex.append(dict(r, headingCode="25062000"))
    return ex


def secao_serie(ex):
    a = C.defaultdict(lambda: [0.0, 0.0])
    for r in ex:
        for k in ((r["year"], "total"), (r["year"], GRUPO[r["headingCode"]])):
            a[k][0] += float(r["metricFOB"])
            a[k][1] += float(r["metricKG"])
    anos = sorted({y for y, _ in a})
    ult = max(int(r["monthNumber"]) for r in ex if r["year"] == anos[-1])
    md = ["## A1. Exportação brasileira de rochas ornamentais, 1997–" + anos[-1], "",
          f"_{anos[-1]} parcial: jan–{ult:02d}. Quartzito (NCM 2506.20) só existe na série a partir de 2007; "
          "antes disso o grupo silicático bruto está subestimado._", "",
          "| Ano | US$ mi FOB | Mil t | US$/t médio | % beneficiadas no valor | US$/t beneficiadas | US$/t brutas silicáticas |",
          "|---|---|---|---|---|---|---|"]
    for y in anos:
        t, b, s = a[(y, "total")], a[(y, "beneficiadas")], a[(y, "brutas silicáticas (granito etc.)")]
        md.append(f"| {y} | {mi(t[0])} | {num(t[1] / 1e6)} | {num(t[0] / (t[1] / 1000)) if t[1] else '—'} | "
                  f"{pct(b[0], t[0])} | {num(b[0] / (b[1] / 1000)) if b[1] else '—'} | "
                  f"{num(s[0] / (s[1] / 1000)) if s[1] else '—'} |")
    return md


def secao_destinos(ex, ano):
    v, pg = C.defaultdict(float), C.defaultdict(lambda: C.defaultdict(float))
    for r in ex:
        if r["year"] == ano:
            v[r["country"]] += float(r["metricFOB"])
            pg[GRUPO[r["headingCode"]]][r["country"]] += float(r["metricKG"])
    t = sum(v.values())
    hhi = sum((x / t * 100) ** 2 for x in v.values())
    md = [f"## A2. Destinos — {ano}", "", f"Países de destino: {len(v)}. Concentração (HHI, 0–10.000): **{num(hhi)}** "
          "(acima de 2.500 = mercado altamente concentrado).", "",
          "| Destino | US$ mi | % do valor |", "|---|---|---|"]
    md += [f"| {k} | {mi(x)} | {pct(x, t)} |" for k, x in sorted(v.items(), key=lambda i: -i[1])[:12]]
    md += ["", "Destino por grupo (% do **peso**):", "", "| Grupo | 1º | 2º | 3º |", "|---|---|---|---|"]
    for gname, d in sorted(pg.items()):
        tt = sum(d.values())
        top = sorted(d.items(), key=lambda i: -i[1])[:3]
        md.append(f"| {gname} | " + " | ".join(f"{k} {pct(x, tt)}" for k, x in top) + " |")
    return md


def secao_mensal_eua(ex):
    m = C.defaultdict(lambda: [0.0, 0.0])
    for r in ex:
        k = f"{r['year']}-{int(r['monthNumber']):02d}"
        m[k][0] += float(r["metricFOB"])
        if r["country"] == "Estados Unidos":
            m[k][1] += float(r["metricFOB"])
    meses = sorted(m)[-24:]
    md = ["## A3. Últimos 24 meses — total e participação dos EUA", "",
          "| Mês | US$ mi total | US$ mi EUA | % EUA |", "|---|---|---|---|"]
    md += [f"| {k} | {mi(m[k][0])} | {mi(m[k][1])} | {pct(m[k][1], m[k][0])} |" for k in meses]
    return md


def secao_uf():
    u = C.defaultdict(lambda: C.defaultdict(float))
    for r in ler("comex_export_sh4_uf"):
        u[r["year"]][r["state"]] += float(r["metricFOB"])
    anos = [y for y in ("2000", "2005", "2010", "2015", "2020", "2024", "2025") if y in u]
    ufs = sorted({k for y in anos for k in u[y]}, key=lambda k: -u[anos[-1]].get(k, 0))[:8]
    md = ["## A4. Polos exportadores — % do valor por UF", "", "| UF | " + " | ".join(anos) + " |",
          "|---|" + "---|" * len(anos)]
    for k in ufs:
        md.append(f"| {k} | " + " | ".join(pct(u[y].get(k, 0), sum(u[y].values())) for y in anos) + " |")
    return md


def secao_insumos():
    i = C.defaultdict(lambda: C.defaultdict(float))
    for r in ler("comex_import_insumos_pais"):
        i[(r["year"], r["headingCode"])][r["country"]] += float(r["metricFOB"])
    md = ["## A5. Importação de máquinas (SH 8464) e abrasivos (SH 6804)", "",
          "_Proxy, não medida exata: 8464 inclui máquinas para cerâmica, concreto e vidro; 6804 inclui abrasivos "
          "para metalurgia. Mostra origem e tendência, não o gasto exato do setor de rochas._", "",
          "| Ano | SH | US$ mi | 1ª origem | 2ª origem | 3ª origem |", "|---|---|---|---|---|---|"]
    for y in ("2000", "2005", "2010", "2015", "2020", "2024", "2025"):
        for h in ("8464", "6804"):
            d = i.get((y, h))
            if not d:
                continue
            t = sum(d.values())
            top = sorted(d.items(), key=lambda x: -x[1])[:3]
            md.append(f"| {y} | {h} | {mi(t)} | " + " | ".join(f"{k} {pct(x, t)}" for k, x in top) + " |")
    return md


def secao_concorrentes():
    w = ler("comtrade_export_mundo")
    tot, p68 = C.defaultdict(lambda: C.defaultdict(float)), C.defaultdict(lambda: [0.0, 0.0])
    anos = sorted({r["period"] for r in w})
    for r in w:
        pais = M49.get(r["reporterCode"], r["reporterCode"])
        tot[r["period"]][pais] += float(r["primaryValue"] or 0)
        if r["cmdCode"] == "6802" and r["period"] == anos[-2]:
            p68[pais][0] += float(r["primaryValue"] or 0)
            p68[pais][1] += float(r["netWgt"] or 0)
    sel = [y for y in ("2005", "2010", "2015", "2020", anos[-2], anos[-1]) if y in tot]
    paises = sorted(tot[sel[-1]], key=lambda k: -tot[sel[-1]][k])
    md = ["## A6. Concorrentes — exportação total de rochas (SH 2514–2516, 6801–6803), US$ mi", "",
          "_UN Comtrade, declarado pelo exportador. Sem quartzito 2506.20, por isso o Brasil aparece abaixo do "
          f"ComexStat. {anos[-1]} pode estar incompleto para alguns países._", "",
          "| País | " + " | ".join(sel) + " |", "|---|" + "---|" * len(sel)]
    md += [f"| {k} | " + " | ".join(mi(tot[y].get(k, 0)) for y in sel) + " |" for k in paises]
    md += ["", f"Preço médio de exportação de beneficiadas (SH 6802), {anos[-2]}:", "", "| País | US$/t |", "|---|---|"]
    md += [f"| {k} | {num(v[0] / (v[1] / 1000))} |" for k, v in sorted(p68.items(), key=lambda i: -(i[1][0] / i[1][1]) if i[1][1] else 0) if v[1]]
    return md


def secao_eua():
    e = ler("comtrade_eua_import_parceiros")
    md = ["## A7. Mercado dos EUA — participação por origem nas importações de beneficiadas (SH 6802)", ""]
    anos = [y for y in ("2005", "2010", "2015", "2020", "2024", "2025") if any(r["period"] == y for r in e)]
    d = {y: C.defaultdict(float) for y in anos}
    for r in e:
        if r["period"] in d and r["cmdCode"] == "6802" and r["partnerCode"] != "0":
            d[r["period"]][M49.get(r["partnerCode"], r["partnerCode"])] += float(r["primaryValue"] or 0)
    paises = sorted(d[anos[-1]], key=lambda k: -d[anos[-1]][k])[:7]
    md += ["| Origem | " + " | ".join(anos) + " |", "|---|" + "---|" * len(anos)]
    md += [f"| {k} | " + " | ".join(pct(d[y].get(k, 0), sum(d[y].values())) for y in anos) + " |" for k in paises]
    md.append("| **Total EUA, US$ mi** | " + " | ".join(mi(sum(d[y].values())) for y in anos) + " |")
    return md


def secao_literatura():
    p = "biblio/corpus.jsonl"
    if not os.path.exists(p):
        return []
    c = [json.loads(x) for x in open(p, encoding="utf-8")]
    n = [r for r in c if r.get("escopo") == "brasil"]
    nomes = {"E1": "lavra", "E2": "benef. primário", "E3": "benef. final", "E4": "insumos/máquinas", "E5": "logística",
             "E6": "comércio/exportação", "E7": "mercado/construção", "E8": "resíduos/ambiente", "E9": "trabalho/saúde",
             "E10": "governança/política", "E11": "tecnologia"}
    el = C.Counter(e for r in n for e in r.get("elos_pre", []))
    dec = C.Counter((r["ano"] // 10 * 10) for r in n if r.get("ano"))
    md = ["## A8. Literatura — núcleo Brasil (NÃO TRIADA)", "",
          f"Corpus total: {len(c)} obras; escopo Brasil: **{len(n)}**. Classificação por palavra-chave sobre título e "
          "resumo; uma obra pode estar em vários elos. Ainda sem triagem PRISMA.", "",
          "| Elo | Obras |", "|---|---|"]
    md += [f"| {k} {nomes[k]} | {v} |" for k, v in sorted(el.items(), key=lambda i: -i[1])]
    md += ["", "| Década | Obras |", "|---|---|"] + [f"| {k}s | {v} |" for k, v in sorted(dec.items())]
    return md


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    ex = exportacoes()
    ano_cheio = str(max(int(r["year"]) for r in ex) - 1)
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    partes = [[f"# Anexo estatístico — mapeamento da cadeia de rochas ornamentais", "",
               f"Gerado em {hoje} por `mapeamento.py` a partir de `dados/series/` e `biblio/corpus.jsonl`. "
               "Valores em US$ correntes (FOB). Recorte NCM validado contra os Informes Abirochas (diferença de 0,1–0,2%)."],
              secao_serie(ex), secao_destinos(ex, ano_cheio), secao_mensal_eua(ex), secao_uf(), secao_insumos(),
              secao_concorrentes(), secao_eua(), secao_literatura()]
    os.makedirs("estudo", exist_ok=True)
    with open("estudo/anexo-estatistico.md", "w", encoding="utf-8") as f:
        f.write("\n\n".join("\n".join(p) for p in partes if p) + "\n")
    print("estudo/anexo-estatistico.md")


if __name__ == "__main__":
    main()
