# Etapa não determinística — triagem e fichamento (agente LLM)

Única etapa que não é código. Roda depois dos coletores, sobre o que eles
gravaram. Isolada aqui para ser reprodutível: mesma entrada, mesmas regras.

## Regras inegociáveis (herdadas do inteligencia-midia)

1. Nenhuma afirmação sobre o que uma obra ou matéria diz sem ter lido o texto.
   Título e resumo permitem **triagem**, nunca **fichamento**.
2. Falha de acesso é registrada (HTTP, paywall, PDF escaneado), nunca preenchida por inferência.
3. Todo dado numérico citado em ficha leva trecho literal + página/seção. Número sem trecho não entra.
4. Divergência com a pré-classificação de `cadeia.py` é permitida e deve ser justificada em 1 linha.

## A. Triagem bibliográfica (semanal) — padrão PRISMA 2020

Entrada: registros de `biblio/corpus.jsonl` com `coletado_em` = data da execução e sem campo `triagem`.

Para cada registro, decidir com base em título + resumo:

| Campo | Valores |
|---|---|
| `triagem.decisao` | `incluir` / `excluir` / `incerto` (incerto vai para leitura humana) |
| `triagem.criterio` | um dos critérios abaixo |
| `triagem.elos` | E1..E11 (ver `cadeia.py`), pode corrigir `elos_pre` |
| `triagem.escala` | `Brasil` / `ES-MG-BA` (polo) / `internacional-comparável` / `internacional-genérico` |
| `triagem.tipo_evidencia` | `dado primário` / `estudo de caso` / `revisão` / `técnico-tecnológico` / `normativo` / `opinião` |

Critérios de inclusão (basta um): trata de rocha ornamental/de revestimento como **atividade econômica**
(lavra, beneficiamento, comércio, mercado, trabalho, resíduo, política, tecnologia de processo);
ou caracteriza tecnologicamente material comercializado como rocha ornamental.

Critérios de exclusão: geologia/petrologia sem vínculo com aproveitamento (`EX1`); brita/agregado
para construção (`EX2`); patrimônio/restauro sem dimensão produtiva (`EX3`, salvo se o estudo pedir);
duplicata não detectada (`EX4`); sem resumo e título ambíguo (→ `incerto`, não excluir).

Saída: `biblio/triagem/AAAA-MM-DD.jsonl` (1 linha por registro: `_k` + objeto `triagem`) e
tabela-resumo PRISMA no fim de `biblio/AAAA-MM-DD-biblio.md`:
identificados / duplicatas removidas / triados / excluídos (por critério) / incertos / incluídos.

## B. Fichamento (sob demanda, só incluídos com acesso aberto)

Baixar `acesso_aberto` (PDF/HTML). Medir texto extraído; < 2.000 caracteres = não lido.
Ficha em `biblio/fichas/<_k-hash>.md`:

```
# <título> (<ano>)
**Acesso:** <url> — texto completo (N caracteres) / falhou (motivo)
**Elo(s):** E.. — **Escala:** .. — **Método:** ..
**Pergunta da obra:** <1 linha>
**Achados com número** (trecho literal + página):
- "<trecho>" (p. X)
**Elos da cadeia que a obra descreve e como** (só o que está no texto):
**Lacunas declaradas pelos autores:**
```

## C. Notícias (diária, opcional)

Entrada: `noticias/AAAA-MM-DD-bruto.json`. Para itens dos elos E6 (comércio), E10 (governança)
e E8 (ambiente), abrir o link e, se o corpo tiver ≥ 500 caracteres, registrar em 1 linha **o fato**
(número, decisão, data) com o veículo. Manchete sem corpo lido fica marcada "só manchete".
Sem juízo de relevância: a seleção para o estudo é decisão humana.

## D. Fichamento da literatura cinzenta (Informes setoriais)

Entrada: `biblio/cinzenta/fila.jsonl`, linhas com `decisao` = `fichar` (gerada por `cinzenta_fila.py`;
tabelas puras de comércio exterior e duplicatas de versão já ficam de fora, com o motivo registrado).
Ler o arquivo `texto` INTEIRO antes de fichar. Saída: `biblio/cinzenta/fichas/<id>.json`, um por documento:

```json
{
  "id": "<id da fila>", "arquivo": "...", "emissor": "Abirochas|Centrorochas|...",
  "titulo": "<como aparece no documento>",
  "data_publicacao": "AAAA-MM ou null", "periodo_coberto": "ex.: 2024, jan-mai/2025, null",
  "tipo": "conjuntura|estudo-tematico|relatorio-mensal|pesquisa-com-empresas|apresentacao|posicionamento|outro",
  "tema": "<1 linha: do que trata>",
  "elos": ["E6", "E10"],
  "indicadores":  [{"nome": "...", "valor": "...", "unidade": "...", "periodo": "...", "trecho": "..."}],
  "explicacoes":  [{"fenomeno": "...", "causa_atribuida": "...", "trecho": "..."}],
  "mercados":     [{"pais": "...", "afirmacao": "...", "trecho": "..."}],
  "politicas":    [{"medida": "...", "afirmacao": "...", "trecho": "..."}],
  "precos":       [{"produto": "...", "afirmacao": "...", "trecho": "..."}],
  "desafios":     [{"afirmacao": "...", "trecho": "..."}],
  "pleitos":      [{"afirmacao": "...", "trecho": "..."}],
  "observacao": "<problema de leitura, documento fora de escopo, texto truncado etc., ou null>"
}
```

Regras específicas:
1. `trecho` é cópia LITERAL de uma passagem contínua do texto (20 a 300 caracteres), sem
   reescrever, sem juntar pedaços com "…". `cinzenta_tabela.py` confere cada trecho contra o texto e
   descarta o item cujo trecho não for encontrado.
2. `indicadores`: só os de destaque (no máximo 10), de preferência os que o documento usa para
   argumentar. Valores de comércio exterior repetem o ComexStat; o que interessa é o que NÃO está
   lá (produção, consumo interno, empregos, preços, capacidade instalada, participação de mercado).
3. `explicacoes` é o campo central: o que o emissor diz ter CAUSADO uma variação (câmbio, tarifa,
   frete, juros nos EUA, concorrência, pandemia…). Registrar a atribuição do emissor, não julgá-la.
4. Lista vazia quando o documento não trata do assunto. Nada inferido de fora do texto.
5. `elos`: E1 lavra · E2 beneficiamento primário · E3 beneficiamento final · E4 insumos e máquinas ·
   E5 logística · E6 comercialização e exportação · E7 mercado e construção · E8 resíduos e
   sustentabilidade · E9 trabalho e saúde · E10 governança e política · E11 tecnologia e inovação.
