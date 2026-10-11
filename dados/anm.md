# ANM — geografia da lavra — 2026-10-11

- Arquivos encontrados no servidor de dados abertos: 85 (lista em `fontes/anm-arquivos.json`)
- Arquivos CFEM de arrecadação: 6; arquivos de produção (AMB/RAL): 7

- CFEM `CFEM_Arrecadacao_2002_2006.csv`: 31009 linhas de rochas usadas, 0 puladas por ano já coberto (anos 2003–2006)
- CFEM `CFEM_Arrecadacao_2007_2011.csv`: 50282 linhas de rochas usadas, 0 puladas por ano já coberto (anos 2007–2011)
- CFEM `CFEM_Arrecadacao_2012_2016.csv`: 71559 linhas de rochas usadas, 0 puladas por ano já coberto (anos 2012–2016)
- CFEM `CFEM_Arrecadacao_2017_2021.csv`: 76642 linhas de rochas usadas, 0 puladas por ano já coberto (anos 2017–2021)
- CFEM `CFEM_Arrecadacao_2022_2026.csv`: 82178 linhas de rochas usadas, 0 puladas por ano já coberto (anos 2022–2026)
- CFEM `CFEM_Arrecadacao.csv`: 0 linhas de rochas usadas, 311670 puladas por ano já coberto (anos —–—)
- **anm_cfem_rochas**: 18827 linhas (ano × UF × município × substância)
- `Agua_Mineral_Producao.csv`: nenhuma substância de rocha ornamental casou (coluna Substância Mineral). Classes existentes: Água
- **anm_producao_beneficiada**: 298 linhas de rochas ornamentais
- **anm_producao_bruta**: 679 linhas de rochas ornamentais
- **anm_investimentopesquisamineralbrasil**: 226 linhas de rochas ornamentais
- **anm_investimentopesquisamineralmunicipio**: 4507 linhas de rochas ornamentais
- **anm_investimentopesquisamineraluf**: 1110 linhas de rochas ornamentais
- `RequerimentoPesquisaMineral.csv`: sem coluna de substância, ignorado (colunas: ['IdentificadorRequerimento', 'NUP', 'DataProtocolizacao', 'Origem', 'CpfCnpj', 'TipoPessoa', 'Nome', 'TipoRequerimento'])
- 
- ### Recorte ornamental da CFEM (R$ milhões recolhidos)
- 
- | Ano | Inequívoco | Granito/gnaisse no polo | Soma ornamental | Brita | Ambíguo fora do polo |
- |---|---|---|---|---|---|
- | 2015 | 6.3 | 13.7 | **20.0** | 4.1 | 55.4 |
- | 2016 | 7.7 | 11.2 | **18.9** | 2.9 | 48.3 |
- | 2017 | 7.2 | 8.5 | **15.7** | 2.3 | 40.0 |
- | 2018 | 8.1 | 5.3 | **13.4** | 1.6 | 32.0 |
- | 2019 | 8.7 | 4.9 | **13.6** | 1.8 | 33.9 |
- | 2020 | 10.1 | 5.7 | **15.8** | 1.8 | 40.9 |
- | 2021 | 14.5 | 7.2 | **21.7** | 1.9 | 52.2 |
- | 2022 | 16.5 | 6.3 | **22.8** | 2.5 | 69.0 |
- | 2023 | 14.5 | 7.2 | **21.6** | 3.3 | 84.8 |
- | 2024 | 19.8 | 7.7 | **27.5** | 4.1 | 99.2 |
- | 2025 | 26.8 | 6.6 | **33.4** | 5.4 | 98.0 |
- | 2026 | 12.0 | 3.3 | **15.3** | 3.5 | 48.7 |
- _Regra e lista de municípios do polo em config.json (cfem.recorte), a validar com o setor._

## Falhas

- https://app.anm.gov.br/dadosabertos/: HTTP 0 URLError: <urlopen error [Errno 104] Connection reset by peer>

_"GRANITO" na ANM mistura brita e rocha ornamental: não somar sem recorte._
