# Matriz de acesso — 2026-10-12

Instante: `2026-10-12T10:51:10+00:00`. 23 fontes testadas.

| Fonte | Trilha | Tipo | HTTP | Veredito | URL usada | Detalhe |
|---|---|---|---|---|---|---|
| OpenAlex | biblio | api | 200 | **COLETAVEL** | https://api.openalex.org/works?filter=title_and_abstract.search:dimension%20stone&per-page=1 | JSON 19319 B |
| Crossref | biblio | api | 200 | **COLETAVEL** | https://api.crossref.org/works?query.bibliographic=dimension+stone&rows=1 | JSON 4714 B |
| BDTD/IBICT (teses e dissertações) | biblio | api | 200 | **COLETAVEL** | https://bdtd.ibict.br/vufind/api/v1/search?lookfor=%22rochas+ornamentais%22&type=AllFields&limit=1 | JSON 673 B |
| Semantic Scholar | biblio | api | 429 | **FALHOU** | https://api.semanticscholar.org/graph/v1/paper/search?query=dimension+stone&limit=1 | HTTPError 429 / {"message": "Too Many Requests. Please wait and try again or apply for a key for higher rate limits. https://www.semanticscholar.org/product/api#api-key-form", "code": "429"} (4 tent.) |
| ComexStat (MDIC) — API | dados | api | 200 | **COLETAVEL** | https://api-comexstat.mdic.gov.br/general/filters | JSON 1174 B |
| UN Comtrade | dados | api | 200 | **COLETAVEL** | https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=76&period=2023&cmdCode=6802&flowCode=X&partnerCode=0 | JSON 965 B |
| Banco Central — SGS | dados | api | 200 | **COLETAVEL** | https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/1?formato=json | JSON 38 B |
| ANM — CFEM arrecadação | dados | csv | — | **FALHOU** | https://app.anm.gov.br/dadosabertos/ARRECADACAO/CFEM_Arrecadacao.csv | URLError: <urlopen error [Errno 104] Connection reset by peer> |
| ANM — Anuário Mineral Brasileiro (AMB) | dados | manual | — | **A_LOCALIZAR** | — | não testável automaticamente |
| IBGE — PIA-Empresa / PIA-Produto (CNAE 08.10 e 23.91) | dados | manual | — | **A_LOCALIZAR** | — | não testável automaticamente |
| RAIS/CAGED (emprego CNAE 0810-0/02, 0810-0/03, 2391-5) | dados | manual | — | **A_LOCALIZAR** | — | não testável automaticamente |
| USGS — Mineral Commodity Summaries: Stone (Dimension) | dados | manual | — | **A_LOCALIZAR** | — | não testável automaticamente |
| Montani — Rapporto Marmo e Pietre nel Mondo | dados | manual | — | **PAGO** | — | não testável automaticamente |
| Google News pt-BR (consultas do config.json) | noticias | rss | — | **FALHOU** | — | https://news.google.com/rss/search?q=%22rochas+ornamentais%22&hl=pt-BR&gl=BR&ceid=BR:pt-419: 200, 0 itens, 0 com data (feed vazio) |
| Centrorochas | noticias | rss | — | **FALHOU** | — | https://centrorochas.org.br/feed/: 200, 0 itens, 0 com data (feed vazio) / home 200; feed anunciado / https://centrorochas.org.br/feed/: feed anunciado sem item datado |
| Abirochas | noticias | rss | — | **FALHOU** | — | https://abirochas.com.br/feed/: HTTP 0 (URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired (_ssl.c:1010)>) / home HTTP 0 (URLError: <urlopen error [SSL: CERTIFICA |
| Revista Rochas de Qualidade | noticias | rss | — | **FALHOU** | — | https://www.rochas.com.br/feed/: HTTP 0 (URLError: <urlopen error [Errno -2] Name or service not known>) / home HTTP 0 (URLError: <urlopen error [Errno -2] Name or service not known>) |
| Litos Online | noticias | rss | — | **FALHOU** | — | https://www.litosonline.com/feed/: HTTP 404 (HTTPError 404: Not Found / <!DOCTYPE html> <html lang="en" dir="ltr" prefix="content: http://purl.org/rss/1.0/modules/content/ dc: http://purl.org/dc/terms/ foaf: http://xmlns |
| Stone World (EUA) | noticias | rss | — | **FALHOU** | — | https://www.stoneworld.com/rss: 200 mas HTTP 200 mas HTML (91543 bytes) / home 200; nenhum feed anunciado |
| A Gazeta (ES) — economia | noticias | rss | — | **FALHOU** | — | home 200; nenhum feed anunciado |
| Folha Vitória | noticias | rss | 200 | **COLETAVEL** | https://www.folhavitoria.com.br/feed/ | 10 itens, 10 com data |
| Brasil Mineral | noticias | rss | — | **FALHOU** | — | home 200; nenhum feed anunciado |
| Revista Minérios & Minerales | noticias | rss | — | **FALHOU** | — | https://revistaminerios.com.br/feed/: HTTP 0 (URLError: <urlopen error timed out>) / home HTTP 0 (URLError: <urlopen error timed out>) |
