"""
rede.py — camada HTTP e de parsing comum aos três coletores.

Só biblioteca padrão. Portado de inteligencia-midia/coletor.py, onde cada
decisão abaixo foi tomada depois de uma falha real:
  - opener único com ProxyHandler + bundle de CA do proxy de agente;
  - descompressão de gzip mesmo sem Accept-Encoding (servidor manda assim);
  - até 4 tentativas com backoff só para 429/5xx/socket (403/404 são veredito);
  - em Atom, <published> vence <updated>;
  - 200 com HTML no lugar de XML é rotulado como bloqueio, não como XML ruim.
"""

import gzip
import http.client
import json
import os
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
# APIs acadêmicas (OpenAlex, Crossref) pedem UA identificável com contato:
# entra no "polite pool", com limite maior. O e-mail vem do ambiente para não
# ficar gravado no repositório.
CONTATO = os.environ.get("ROBO_CONTATO", "")
UA_API = ("cadeia-valor-rochas/0.1 "
          "(https://github.com/roniegdias-ux/Cadeia-de-Valor-Rochas"
          + (f"; mailto:{CONTATO}" if CONTATO else "") + ")")

TIMEOUT = 30
TENTATIVAS = 4
BACKOFF = 1.5
HTTP_REPETIVEL = {429, 500, 502, 503, 504, 0}


def contexto_ssl():
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        caminho = os.environ.get(var)
        if caminho and os.path.exists(caminho):
            return ssl.create_default_context(cafile=caminho)
    if os.path.exists("/root/.ccr/ca-bundle.crt"):
        return ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
    return ssl.create_default_context()


OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler(),
    urllib.request.HTTPSHandler(context=contexto_ssl()),
)


def descomprimir(corpo, encoding):
    if not corpo:
        return corpo
    enc = (encoding or "").lower()
    if enc == "gzip" or corpo[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(corpo)
        except Exception:
            return corpo
    if enc == "deflate":
        for wbits in (-zlib.MAX_WBITS, zlib.MAX_WBITS):
            try:
                return zlib.decompress(corpo, wbits)
            except Exception:
                continue
    return corpo


def _uma_tentativa(url, ua, dados, cabecalhos):
    h = {"User-Agent": ua, "Accept": "*/*",
         "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
    h.update(cabecalhos or {})
    req = urllib.request.Request(url, data=dados, headers=h)
    try:
        with OPENER.open(req, timeout=TIMEOUT) as r:
            return r.status, descomprimir(r.read(), r.headers.get("Content-Encoding")), None, 0
    except urllib.error.HTTPError as e:
        try:
            espera = min(float(e.headers.get("Retry-After") or 0), 30)
        except (TypeError, ValueError):
            espera = 0
        motivo = str(getattr(e, "reason", "") or e.msg or "").strip()
        return e.code, b"", f"HTTPError {e.code}" + (f": {motivo[:90]}" if motivo else ""), espera
    except http.client.IncompleteRead as e:
        return 0, b"", f"IncompleteRead ({len(e.partial)} bytes)", 0
    except Exception as e:
        # 403/407 no CONNECT é política de egress do ambiente: repetir não muda nada.
        cod = 403 if "Tunnel connection failed: 40" in str(e) else 0
        return cod, b"", f"{type(e).__name__}: {e}", 0


def buscar(url, ua=UA, dados=None, cabecalhos=None, tentativas=TENTATIVAS):
    """Devolve (codigo_http, corpo_bytes, erro_str_ou_None, n_tentativas)."""
    espera = BACKOFF
    for n in range(1, tentativas + 1):
        codigo, corpo, erro, sugerida = _uma_tentativa(url, ua, dados, cabecalhos)
        if erro is None and 200 <= codigo < 300 and corpo:   # 206 = Range
            return codigo, corpo, None, n
        if n == tentativas or codigo not in HTTP_REPETIVEL:
            return codigo, corpo, erro or f"HTTP {codigo} / corpo vazio", n
        time.sleep(max(sugerida, espera))
        espera *= 2
    return 0, b"", "sem tentativas", 0


def buscar_json(url, dados_json=None, ua=UA_API, tentativas=TENTATIVAS):
    """GET (ou POST se dados_json) que devolve (obj, codigo, erro, tentativas)."""
    dados = cab = None
    if dados_json is not None:
        dados = json.dumps(dados_json).encode()
        cab = {"Content-Type": "application/json", "Accept": "application/json"}
    codigo, corpo, erro, n = buscar(url, ua=ua, dados=dados, cabecalhos=cab,
                                    tentativas=tentativas)
    if erro:
        return None, codigo, erro, n
    try:
        return json.loads(corpo), codigo, None, n
    except ValueError as e:
        return None, codigo, rotular_nao_esperado(corpo, f"JSON inválido: {e}"), n


def rotular_nao_esperado(corpo, padrao):
    cabeca = (corpo or b"")[:400].lstrip().lower()
    if cabeca.startswith(b"<!doctype html") or cabeca.startswith(b"<html"):
        return f"HTTP 200 mas HTML ({len(corpo)} bytes)"
    return padrao


# --------------------------------------------------------------- RSS / Atom

def tag_local(elem):
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def texto(elem):
    return "" if elem is None else "".join(elem.itertext()).strip()


def parse_data(bruto):
    """RFC822 ou ISO8601 (ou AAAA-MM-DD) -> datetime UTC. None se não der."""
    if not bruto:
        return None
    bruto = bruto.strip()
    try:
        d = parsedate_to_datetime(bruto)
    except Exception:
        try:
            d = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def extrair_itens(corpo):
    """RSS 2.0, RSS 1.0/RDF e Atom -> lista de dicts crus. ValueError se não for XML."""
    try:
        raiz = ET.fromstring(corpo)
    except ET.ParseError as e:
        raise ValueError(rotular_nao_esperado(corpo, f"XML inválido: {e}"))
    if tag_local(raiz).lower() == "html":   # XHTML bem-formado: bloqueio, não feed vazio
        raise ValueError(f"HTTP 200 mas HTML ({len(corpo)} bytes)")
    itens = []
    for elem in raiz.iter():
        if tag_local(elem) not in ("item", "entry"):
            continue
        c = {"titulo": "", "link": "", "data_bruta": "", "resumo": "",
             "fonte_declarada": "", "_updated": False}
        for filho in elem:
            nome = tag_local(filho)
            if nome == "title" and not c["titulo"]:
                c["titulo"] = texto(filho)
            elif nome == "link":
                href = filho.get("href")
                if href:
                    if filho.get("rel") in (None, "alternate") and not c["link"]:
                        c["link"] = href
                elif not c["link"]:
                    c["link"] = texto(filho)
            elif nome in ("pubDate", "published", "date"):
                if not c["data_bruta"] or c["_updated"]:
                    c["data_bruta"], c["_updated"] = texto(filho), False
            elif nome == "updated" and not c["data_bruta"]:
                c["data_bruta"], c["_updated"] = texto(filho), True
            elif nome in ("description", "summary", "content") and not c["resumo"]:
                c["resumo"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto(filho))).strip()[:800]
            elif nome == "source" and not c["fonte_declarada"]:
                c["fonte_declarada"] = texto(filho)
        del c["_updated"]
        if c["titulo"]:
            itens.append(c)
    return itens


# ------------------------------------------------------------ normalização

def sem_acento(t):
    t = unicodedata.normalize("NFKD", t or "")
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def normalizar(titulo):
    """Chave de deduplicação: sem acento, sem pontuação, minúsculo, sem ' - Veículo'."""
    t = sem_acento(titulo)
    t = re.sub(r"\s+-\s+[^-]{1,40}$", "", t)
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def ler_json(caminho, padrao=None):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho, obj):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def qs(**kw):
    return urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})
