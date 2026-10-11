# Acervo retroativo dos sites do setor — 2026-10-11

Coleta pela API pública do WordPress (`/wp-json/wp/v2/posts`). Texto do post gravado até 6.000 caracteres.
Sites generalistas usam busca por palavra e passam pelo filtro de relevância; sites do setor entram inteiros.

| Site | Via | Posts no acervo | Novos nesta execução | Período | Descartados (filtro) | Erro |
|---|---|---|---|---|---|---|
| Centrorochas | api | 1605 | 0 | 2019–2026 | 0 |  |
| Abirochas | sitemap (0 URLs) | 0 | 0 | —–— | 0 | HTTP 401: HTTPError 401: Unauthorized / {"code":"rest_cannot_access","message":"DRA: Only authenticated users can access |
| Sindirochas | sitemap (0 URLs) | 0 | 0 | —–— | 0 | HTTP 404: HTTPError 404: Not Found / <!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN"> <html><head> <title>404 Not Foun |
| Revista Minérios & Minerales | api | 49 | 0 | 2008–2026 | 192 |  |
| Folha Vitória | sitemap (0 URLs) | 0 | 0 | —–— | 0 | HTTP 403: HTTPError 403: Forbidden / <!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-e |
| ES Hoje | sitemap (0 URLs) | 0 | 0 | —–— | 0 | HTTP 403: HTTPError 403: Forbidden / <!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-e |
| A Gazeta (ES) | sitemap (1429 URLs) | 256 | 249 | 2015–2026 | 1175 |  |
| Brasil Mineral | sitemap (58 URLs) | 30 | 30 | 2020–2026 | 28 |  |

Tipos de página por site (só `noticia` e `pagina` são noticiário; `relatorio` vira PDF na literatura cinzenta):

- Centrorochas: noticia 1157, relatorio 195, associado 135, pessoa 98, evento 20
- Revista Minérios & Minerales: pagina 49
- A Gazeta (ES): colunas 68, economia 29, sul 19, policia 14, transito 14, agora 13, gv 11, cotidiano 10, especiais 9, hub-imobi 9, artigos 8, pagina 7, comentaristas 6, entretenimento 6, tema 5, esportes 4, conteudo-de-marca 3, patrocinado 3, publicidade-legal 2, anuario 2, norte 2, revista-ag 2, hz 2, editorial 2, brasil 1, imoveis 1, obituario 1, meio-ambiente 1, mundo 1, futebol-capixaba 1
- Brasil Mineral: noticias 25, bem-mineral 4, pagina 1

PDFs citados nos posts (Informes, estudos): **32** — lista em `pdfs.json`.

## Posts por ano

| Site | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| centrorochas |  |  |  |  |  |  |  |  |  |  |  | 73 | 208 | 148 | 134 | 156 | 176 | 166 | 544 |
| abirochas |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| sindirochas |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| minerios | 2 | 4 |  | 2 | 1 | 1 | 3 | 11 | 7 | 1 |  | 1 | 5 | 2 | 2 | 1 | 1 | 4 | 1 |
| folhavitoria |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| eshoje |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| agazeta |  |  |  |  |  |  |  | 1 |  | 5 | 17 | 45 | 24 | 31 | 13 | 18 | 39 | 27 | 36 |
| brasilmineral |  |  |  |  |  |  |  |  |  |  |  |  | 1 | 2 | 5 | 5 | 5 | 6 | 6 |
