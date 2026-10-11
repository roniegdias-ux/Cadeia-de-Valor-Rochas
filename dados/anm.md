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
- `Agua_Mineral_Producao.csv`: nenhuma substância de rocha ornamental casou (coluna Classe Substância Mineral)
- `Producao_Beneficiada.csv`: nenhuma substância de rocha ornamental casou (coluna Classe Substância)
- `Producao_Bruta.csv`: nenhuma substância de rocha ornamental casou (coluna Classe Substância)
- **anm_investimentopesquisamineralbrasil**: 226 linhas de rochas ornamentais
- **anm_investimentopesquisamineralmunicipio**: 4507 linhas de rochas ornamentais
- **anm_investimentopesquisamineraluf**: 1110 linhas de rochas ornamentais
- `RequerimentoPesquisaMineral.csv`: sem coluna de substância, ignorado (colunas: ['IdentificadorRequerimento', 'NUP', 'DataProtocolizacao', 'Origem', 'CpfCnpj', 'TipoPessoa', 'Nome', 'TipoRequerimento'])

## Falhas

- https://app.anm.gov.br/dadosabertos/: HTTP 0 URLError: <urlopen error [Errno 104] Connection reset by peer>

_"GRANITO" na ANM mistura brita e rocha ornamental: não somar sem recorte._
