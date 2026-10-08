#!/usr/bin/env python3
"""
dados.py — trilha 3: estatísticas e séries históricas.

Cadência mensal (ComexStat publica o mês anterior nos primeiros dias úteis);
Comtrade/CFEM têm defasagem anual, mas o custo de reconsultar é baixo.

  python3 dados.py              # atualiza ano corrente e anterior (pega revisões)
  python3 dados.py --backfill   # série inteira (ComexStat desde 1997, Comtrade desde 2000)
  python3 dados.py --so comexstat,bcb

Séries em dados/series/*.csv (formato longo, 1 linha por observação, colunas
exatamente como a fonte devolve + 'fonte' e 'coletado_em'). Uma série nunca é
editada à mão: é regravada pela fonte. Revisões (valor que mudou para um período
já gravado) são contadas e listadas no relatório, porque o ComexStat revisa.

Relatório: dados/AAAA-MM-DD-dados.md — cobertura de cada série, último período,
revisões, e um painel calculado SÓ a partir das séries (exportação por grupo,
preço médio US$/t, acumulado 12 meses vs 12 meses anteriores).
"""

import argparse
import collections
import csv
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import rede

SERIES = "dados/series"
COMEX = "https://api-comexstat.mdic.gov.br/general"
METRICAS = ("metricFOB", "metricKG", "primaryValue", "netWgt", "valor", "valor_recolhido", "quantidade")


# ------------------------------------------------------------ armazenamento

def chave_linha(r):
    return tuple((k, str(v)) for k, v in sorted(r.items()) if k not in METRICAS + ("coletado_em",))


def gravar_serie(nome, novas):
    """Mescla linhas novas na série; devolve (total, adicionadas, revisoes[list])."""
    caminho = f"{SERIES}/{nome}.csv"
    antigas = collections.OrderedDict()
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                antigas[chave_linha(r)] = r
    adicionadas, revisoes = 0, []
    for r in novas:
        r = {k: ("" if v is None else str(v)) for k, v in r.items()}
        k = chave_linha(r)
        if k in antigas:
            mudou = [m for m in METRICAS if m in r and antigas[k].get(m, "") != r[m]]
            if mudou:
                revisoes.append((dict(k), {m: (antigas[k].get(m), r[m]) for m in mudou}))
        else:
            adicionadas += 1
        antigas[k] = r
    if not antigas:
        return 0, 0, []
    campos = []
    for r in antigas.values():
        campos += [c for c in r if c not in campos]
    os.makedirs(SERIES, exist_ok=True)
    with open(caminho + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(antigas.values())
    os.replace(caminho + ".tmp", caminho)
    return len(antigas), adicionadas, revisoes


def _lista_de_registros(obj):
    """A resposta do ComexStat aninha a lista; acha a primeira lista de dicts."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj
    if isinstance(obj, dict):
        for k in ("data", "list", "result", "results"):
            if k in obj:
                achado = _lista_de_registros(obj[k])
                if achado is not None:
                    return achado
    if isinstance(obj, list) and not obj:
        return []
    return None


# ----------------------------------------------------------------- ComexStat

def comexstat(cfg, anos, log, hoje):
    ncm = cfg["ncm_comexstat"]
    sh4 = list(ncm["sh4"])
    consultas = []
    for fluxo in ("export", "import"):
        consultas += [
            (f"comex_{fluxo}_sh4_pais", fluxo, "heading", sh4, ["heading", "country"]),
            (f"comex_{fluxo}_sh4_uf", fluxo, "heading", sh4, ["heading", "state"]),
            (f"comex_{fluxo}_ncm", fluxo, "ncm", None, ["ncm"]),            # NCM 8 díg., nacional
            (f"comex_{fluxo}_quartzito_pais", fluxo, "ncm", list(ncm["ncm8_extra"]), ["ncm", "country"]),
        ]
    consultas.append(("comex_import_insumos_pais", "import", "heading", list(ncm["sh4_cadeia_insumos"]), ["heading", "country"]))
    ultimo_mes = hoje.strftime("%Y-%m")
    resultado = {}
    for nome, fluxo, filtro, valores, detalhes in consultas:
        if valores is None:   # NCM nacional: filtra pelos SH4 e detalha por NCM
            filtro, valores = "heading", sh4
        linhas = []
        for ano in anos:
            ate = min(f"{ano}-12", ultimo_mes)
            corpo = {"flow": fluxo, "monthDetail": True, "period": {"from": f"{ano}-01", "to": ate},
                     "filters": [{"filter": filtro, "values": valores}],
                     "details": detalhes, "metrics": ["metricFOB", "metricKG"], "language": "pt"}
            obj, cod, erro, n = rede.buscar_json(COMEX, dados_json=corpo)
            regs = None if erro else _lista_de_registros(obj)
            if erro or regs is None:
                log.append({"serie": nome, "periodo": ano, "http": cod,
                            "erro": erro or f"estrutura inesperada: {str(obj)[:150]}"})
                continue
            for r in regs:
                r.update(fonte="comexstat", coletado_em=hoje.strftime("%Y-%m-%d"))
            linhas += regs
            log.append({"serie": nome, "periodo": ano, "http": cod, "erro": None, "linhas": len(regs)})
            time.sleep(2)   # a API devolve 429 se apertar
        resultado[nome] = linhas
    return resultado


# ------------------------------------------------------------------ Comtrade

def comtrade(cfg, anos, log, hoje):
    c = cfg["comtrade"]
    chave = os.environ.get("COMTRADE_KEY")
    base = ("https://comtradeapi.un.org/data/v1/get/C/A/HS" if chave
            else "https://comtradeapi.un.org/public/v1/preview/C/A/HS")
    cab = {"Ocp-Apim-Subscription-Key": chave} if chave else None
    out = {"comtrade_export_mundo": [], "comtrade_eua_import_parceiros": []}
    for ano in anos:
        if ano < c["inicio"]:
            continue
        pedidos = [("comtrade_export_mundo", dict(reporterCode=",".join(c["reporters"]), period=ano,
                                                   cmdCode=",".join(c["hs4"]), flowCode="X", partnerCode=0))]
        # Mercado dos EUA por origem (1 código por vez: preview corta em 500 linhas).
        pedidos += [("comtrade_eua_import_parceiros", dict(reporterCode=842, period=ano, cmdCode=h, flowCode="M"))
                    for h in c["hs4"]]
        for nome, params in pedidos:
            cod, corpo, erro, _ = rede.buscar(f"{base}?{rede.qs(**params)}", ua=rede.UA_API, cabecalhos=cab)
            ano = f"{params['period']} HS {params['cmdCode']}" if nome.startswith("comtrade_eua") else params["period"]
            if erro:
                log.append({"serie": nome, "periodo": ano, "http": cod, "erro": erro})
                continue
            regs = json.loads(corpo).get("data") or []
            if not chave and len(regs) >= 500:
                log.append({"serie": nome, "periodo": ano, "http": cod, "erro": "preview truncado em 500 linhas — usar COMTRADE_KEY"})
            keep = ("reporterCode", "reporterDesc", "partnerCode", "partnerDesc", "period", "cmdCode",
                    "flowCode", "primaryValue", "netWgt", "qty", "qtyUnitAbbr")
            out[nome] += [dict({k: r.get(k) for k in keep}, fonte="comtrade", coletado_em=hoje.strftime("%Y-%m-%d"))
                          for r in regs]
            log.append({"serie": nome, "periodo": ano, "http": cod, "erro": None, "linhas": len(regs)})
            time.sleep(1.2)
    return out


# ----------------------------------------------------------------------- BCB

def bcb(cfg, anos, log, hoje):
    out = {}
    for codigo, desc in cfg["bcb_sgs"].items():
        if codigo.startswith("_"):
            continue
        linhas = []
        a0, a1 = min(anos), max(anos)
        for ini in range(a0, a1 + 1, 10):     # API limita janelas longas
            fim = min(ini + 9, a1)
            url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?"
                   + rede.qs(formato="json", dataInicial=f"01/01/{ini}", dataFinal=f"31/12/{fim}"))
            obj, cod, erro, _ = rede.buscar_json(url)
            if erro:
                log.append({"serie": f"bcb_{codigo}", "periodo": f"{ini}-{fim}", "http": cod, "erro": erro})
                continue
            linhas += [{"serie": codigo, "descricao": desc, "data": r["data"], "valor": r["valor"],
                        "fonte": "bcb_sgs", "coletado_em": hoje.strftime("%Y-%m-%d")} for r in obj]
            log.append({"serie": f"bcb_{codigo}", "periodo": f"{ini}-{fim}", "http": cod, "erro": None, "linhas": len(obj)})
        out[f"bcb_sgs_{codigo}"] = linhas
    return out


# ---------------------------------------------------------------------- CFEM

def _col(cabecalho, *pistas):
    for p in pistas:
        for c in cabecalho:
            if p in rede.sem_acento(c).lower():
                return c
    return None


def _num(v):
    v = (v or "").strip()
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return 0.0


def cfem(cfg, anos, log, hoje):
    confirmadas = {c["id"]: c for c in rede.ler_json("fontes/confirmadas.json", [])}
    url = (confirmadas.get("anm_cfem") or {}).get("url")
    if not url:
        log.append({"serie": "cfem", "periodo": "-", "http": None, "erro": "anm_cfem não confirmada na matriz"})
        return {}
    cod, corpo, erro, _ = rede.buscar(url)
    if erro:
        log.append({"serie": "cfem", "periodo": "-", "http": cod, "erro": erro})
        return {}
    try:
        texto = corpo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = corpo.decode("latin-1")
    dialeto = csv.Sniffer().sniff(texto[:5000], delimiters=";,")
    leitor = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    cab = leitor.fieldnames or []
    c_ano, c_sub, c_uf = _col(cab, "ano"), _col(cab, "subst"), _col(cab, "uf", "estado")
    c_mun, c_val = _col(cab, "munic"), _col(cab, "valorrecolhido", "valor recolhido", "valor")
    c_qtd, c_un = _col(cab, "quantidade"), _col(cab, "unidade")
    if not (c_ano and c_sub and c_val):
        log.append({"serie": "cfem", "periodo": "-", "http": cod, "erro": f"colunas não reconhecidas: {cab[:15]}"})
        return {}
    rx = re.compile(cfg["cfem"]["substancias_regex"], re.I)
    agg = collections.defaultdict(lambda: [0.0, 0.0])
    for r in leitor:
        sub = (r.get(c_sub) or "").upper()
        if not rx.search(rede.sem_acento(sub)) and not rx.search(sub):
            continue
        k = (r.get(c_ano), r.get(c_uf) if c_uf else "", r.get(c_mun) if c_mun else "", sub,
             r.get(c_un) if c_un else "")
        agg[k][0] += _num(r.get(c_val))
        agg[k][1] += _num(r.get(c_qtd)) if c_qtd else 0
    linhas = [{"ano": k[0], "uf": k[1], "municipio": k[2], "substancia": k[3], "unidade": k[4],
               "valor_recolhido": round(v[0], 2), "quantidade": round(v[1], 3),
               "fonte": "anm_cfem", "coletado_em": hoje.strftime("%Y-%m-%d")} for k, v in sorted(agg.items())]
    log.append({"serie": "cfem", "periodo": "todos", "http": cod, "erro": None, "linhas": len(linhas)})
    return {"anm_cfem_rochas_municipio": linhas}


COLETORES = {"comexstat": comexstat, "comtrade": comtrade, "bcb": bcb, "cfem": cfem}
FONTE_MATRIZ = {"comexstat": "comexstat", "comtrade": "comtrade", "bcb": "bcb_sgs", "cfem": "anm_cfem"}


# -------------------------------------------------------------------- painel

def _ler(nome):
    p = f"{SERIES}/{nome}.csv"
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _campo(r, *nomes):
    for n in nomes:
        if n in r and r[n] != "":
            return r[n]
    return None


def painel_exportacao(cfg):
    """Exportação por grupo: FOB, toneladas, US$/t por ano + acumulado 12m. Só a partir da série gravada."""
    linhas = _ler("comex_export_sh4_pais") + _ler("comex_export_quartzito_pais")
    if not linhas:
        return ["_Sem série de exportação gravada._"]
    grupo_de = {cod: g for g, cods in cfg["ncm_comexstat"]["grupos"].items() for cod in cods}
    por_ano = collections.defaultdict(lambda: [0.0, 0.0])
    por_mes = collections.defaultdict(lambda: [0.0, 0.0])
    sem_campo = 0
    for r in linhas:
        ano = _campo(r, "year", "ano")
        mes = _campo(r, "monthNumber", "month", "mes")
        cod = _campo(r, "headingCode", "ncmCode", "coNcm", "heading", "ncm") or ""
        cod = re.sub(r"\D", "", cod)
        g = grupo_de.get(cod) or grupo_de.get(cod[:4])
        fob, kg = _campo(r, "metricFOB"), _campo(r, "metricKG")
        if not (ano and g and fob is not None):
            sem_campo += 1
            continue
        por_ano[(ano, g)][0] += float(fob)
        por_ano[(ano, g)][1] += float(kg or 0)
        if mes:
            por_mes[f"{ano}-{int(mes):02d}"][0] += float(fob)
            por_mes[f"{ano}-{int(mes):02d}"][1] += float(kg or 0)
    md = ["| Ano | Grupo | US$ FOB (mi) | Mil t | US$/t |", "|---|---|---|---|---|"]
    anos = sorted({a for a, _ in por_ano})[-6:]
    for a in anos:
        for g in sorted({g for aa, g in por_ano if aa == a}):
            fob, kg = por_ano[(a, g)]
            md.append(f"| {a} | {g} | {fob / 1e6:,.1f} | {kg / 1e6:,.1f} | {fob / (kg / 1000):,.0f} |" if kg else
                      f"| {a} | {g} | {fob / 1e6:,.1f} | — | — |")
    meses = sorted(por_mes)
    if len(meses) >= 24:
        u12, a12 = meses[-12:], meses[-24:-12]
        f1, f0 = sum(por_mes[m][0] for m in u12), sum(por_mes[m][0] for m in a12)
        k1, k0 = sum(por_mes[m][1] for m in u12), sum(por_mes[m][1] for m in a12)
        md += ["", f"**Acumulado 12 meses ({u12[0]} a {u12[-1]}) vs 12 anteriores, todos os grupos:** "
               f"FOB {f1 / 1e6:,.1f} mi ({(f1 / f0 - 1) * 100:+.1f}%), peso {k1 / 1e6:,.1f} mil t "
               f"({(k1 / k0 - 1) * 100:+.1f}%)." if f0 and k0 else ""]
    if sem_campo:
        md += ["", f"_{sem_campo} linhas sem ano/código/FOB reconhecível ficaram fora do painel — conferir nomes de coluna._"]
    md += ["", "_Grupos e NCMs: config.json. Insumos (8464/6804) são importação e não entram aqui._"]
    return md


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--so", default="comexstat,comtrade,bcb,cfem")
    p.add_argument("--forcar", action="store_true", help="ignora a matriz de acesso")
    p.add_argument("--data")
    a = p.parse_args()
    hoje = datetime.now(timezone.utc)
    data = a.data or hoje.strftime("%Y-%m-%d")
    cfg = rede.ler_json("config.json")
    ini = int(cfg["ncm_comexstat"]["inicio_serie"][:4]) if a.backfill else hoje.year - 1
    anos = list(range(ini, hoje.year + 1))
    ok = {c["id"] for c in rede.ler_json("fontes/confirmadas.json", []) if c["veredito"] == "COLETAVEL"}

    log, resumo = [], []
    for nome in a.so.split(","):
        if not a.forcar and FONTE_MATRIZ[nome] not in ok:
            log.append({"serie": nome, "periodo": "-", "http": None, "erro": "não confirmada na matriz (pulei)"})
            continue
        for serie, linhas in COLETORES[nome](cfg, anos, log, hoje).items():
            if not linhas:
                continue
            total, novas, rev = gravar_serie(serie, linhas)
            resumo.append((serie, total, novas, rev))

    erros = [l for l in log if l["erro"]]
    md = [f"# Dados e séries — {data}", "", "## Registro de coleta", "",
          f"- Modo: {'backfill desde ' + str(ini) if a.backfill else 'atualização ' + str(ini) + '–' + str(hoje.year)}",
          f"- Requisições: {len(log)}; com erro: {len(erros)}", ""]
    if erros:
        md += ["| Série | Período | HTTP | Erro |", "|---|---|---|---|"]
        md += [f"| {l['serie']} | {l['periodo']} | {l['http']} | {str(l['erro'])[:120].replace('|', '/')} |" for l in erros]
        md.append("")
    md += ["## Séries atualizadas", "", "| Série | Linhas totais | Novas | Revisadas |", "|---|---|---|---|"]
    md += [f"| `{s}` | {t} | {n} | {len(r)} |" for s, t, n, r in resumo]
    revs = [(s, k, d) for s, _, _, r in resumo for k, d in r][:30]
    if revs:
        md += ["", "### Revisões da fonte (até 30)", "", "| Série | Chave | Antes → depois |", "|---|---|---|"]
        md += [f"| {s} | {', '.join(f'{x}={y}' for x, y in k.items() if x not in ('fonte',))[:120]} | "
               f"{'; '.join(f'{m}: {v[0]} → {v[1]}' for m, v in d.items())} |" for s, k, d in revs]
    md += ["", "## Painel — exportação brasileira de rochas", ""] + painel_exportacao(cfg)
    with open(f"dados/{data}-dados.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"dados/{data}-dados.md: {len(resumo)} séries, {len(erros)} erros.")
    sys.exit(2 if log and len(erros) > len(log) / 2 else 0)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
