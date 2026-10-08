# Robô — Cadeia Produtiva e Cadeia de Valor das Rochas Ornamentais Brasileiras

Levantamento contínuo de **bibliografia**, **notícias** e **dados/séries históricas** para o estudo de
mapeamento da cadeia produtiva e da cadeia de valor de rochas ornamentais. Segue o molde do
`inteligencia-midia`: catálogo de fontes validado por matriz de acesso → coletores determinísticos só com
biblioteca padrão → bruto versionado → uma única etapa LLM isolada → relatório `.md` com registro de coleta.

## Diferença de desenho em relação à varredura de mídia

A varredura de mídia é um problema de **um** ritmo (24 h). Este estudo tem **três**, e forçar tudo no ritmo
diário desperdiça execução e produz relatórios vazios:

| Trilha | Natureza | Cadência | Script | Saída |
|---|---|---|---|---|
| Notícias | fluxo ralo, chega atrasado ao agregador | diária, janela 7 d + histórico de vistos | `noticias.py` | `noticias/AAAA-MM-DD-{bruto.json,noticias.md}` |
| Bibliografia | estoque grande + fluxo lento | **backfill 1×**, depois semanal | `biblio.py` | `biblio/corpus.{jsonl,bib,ris}` + `biblio/AAAA-MM-DD-biblio.md` |
| Dados | séries com publicação mensal/anual e **revisão** | mensal (dia 8) | `dados.py` | `dados/series/*.csv` + `dados/AAAA-MM-DD-dados.md` |

## Eixo analítico comum: os elos da cadeia

`cadeia.py` define 11 elos e pré-classifica tudo (notícia, obra, série) por palavra-chave, de forma
determinística. A triagem LLM pode corrigir, justificando.

| Elo | Bibliografia/notícias | Dado quantitativo coletado | Lacuna atual |
|---|---|---|---|
| E1 lavra | sim | CFEM por substância × município (ANM) | AMB, SIGMINE (a localizar) |
| E2 beneficiamento primário | sim | NCM 2514–2516 (brutas/serradas) | PIA-Produto (a localizar) |
| E3 beneficiamento final | sim | NCM 6801–6803 (trabalhadas) | — |
| E4 insumos e máquinas | sim | importação SH4 8464 e 6804 por origem | — |
| E5 logística | sim | — | ANTAQ (porto de Vitória) — próxima fonte |
| E6 comercialização | sim | ComexStat mensal país × UF × NCM desde 1997; Comtrade concorrentes | — |
| E7 mercado/construção | sim | Comtrade: importação dos EUA por origem | — |
| E8 resíduos/ambiente | sim | — | só literatura |
| E9 trabalho/saúde | sim | — | RAIS/CAGED (Base dos Dados/BigQuery) |
| E10 governança | sim | CFEM | — |
| E11 tecnologia | sim | — | patentes (fase 2) |

## Estado da validação — leia antes de confiar em qualquer número

**Nenhuma fonte foi validada pela rede ainda.** O ambiente onde o robô foi escrito tem egress restrito: o
proxy recusou (403 no CONNECT) OpenAlex, Crossref, BDTD, IBGE, BCB, ComexStat, Comtrade, Google News e
os sites setoriais. Por isso:

- `fontes/candidatas.json` tem toda fonte como `A_VALIDAR`/`A_LOCALIZAR`; os coletores **só usam o que
  `verificar_fontes.py` confirmar** em `fontes/confirmadas.json` (ou `--forcar`).
- Formatos de API foram escritos a partir de documentação e memória. O formato do ComexStat
  (`POST /general`, filtro `heading` para SH4, `metricFOB`/`metricKG`) foi conferido em documentação
  secundária (pacote R `comexr`); os nomes de coluna da resposta **não** — o painel acusa linhas que não
  reconhece em vez de somá-las errado.
- URLs de feed dos sites setoriais e da CFEM são presunção; a matriz tenta autodescoberta pela home e
  nunca grava URL inventada.
- Os 17 testes (`python3 -m unittest discover -s tests`) usam fixtures sintéticas: provam parsing,
  filtro, deduplicação, detecção de revisão e painel — não provam acesso.

## Como rodar

```bash
./rodar.sh matriz      # 1º passo, obrigatório
./rodar.sh backfill    # 1 vez: bibliografia desde 1970 e séries desde 1997 (demora; ComexStat limita taxa)
./rodar.sh diario | semanal | mensal
```

Variáveis opcionais: `ROBO_CONTATO` (e-mail para o polite pool de OpenAlex/Crossref), `OPENALEX_API_KEY`,
`COMTRADE_KEY` (sem ela o Comtrade usa o preview, cortado em 500 linhas — o log avisa).

Execução agendada: `.github/workflows/coleta.yml` roda a parte determinística nos runners do GitHub
(rede aberta, sem custo de LLM) e commita. A triagem (`prompts/triagem.md`) fica com um agente Claude
agendado que lê o que foi commitado — a mesma divisão sugerida no `ALGORITMO-VARREDURA.md` do projeto de mídia.

## Ressalvas metodológicas já embutidas

- **Recorte NCM:** capítulos 25.14–25.16 e 68.01–68.03, mais 2506.20 (quartzito) por NCM, porque o SH4
  2506 inclui areia de quartzo. Conferir contra o recorte do Informe Abirochas antes de publicar.
- **CFEM "GRANITO"** mistura brita e rocha ornamental. A série é gravada por substância exatamente como a
  ANM a nomeia; não somar sem recorte.
- **ComexStat revisa** meses passados: a atualização mensal reconsulta ano corrente e anterior e o relatório
  lista cada revisão (antes → depois).
- **Pré-classificação ≠ leitura.** Elo e relevância vêm de título/resumo. Fichamento exige texto lido e
  trecho literal com página (regra herdada).
- **Literatura cinzenta** (Informes Abirochas, perfis MME/J. Mendo, CETEM, SEBRAE, USGS *Dimension Stone*,
  relatório Montani) não tem API: entra em `fontes/candidatas.json` como `A_LOCALIZAR`/`PAGO` e deve ser
  incorporada manualmente ao corpus.
