"""
cadeia.py — taxonomia da cadeia produtiva e filtro de relevância.

Determinístico e auditável: a mesma entrada dá sempre o mesmo rótulo. É uma
PRÉ-classificação por palavras-chave; a classificação final por elo é feita
na etapa de triagem (prompts/triagem.md), que pode discordar e registra por quê.

Elos (cadeia produtiva -> cadeia de valor):
  E1 pesquisa geológica e lavra       E7 mercado consumidor, construção, design
  E2 beneficiamento primário          E8 resíduos, ambiente, sustentabilidade
  E3 beneficiamento final/marmoraria  E9 trabalho e saúde (silicose, acidentes)
  E4 insumos, máquinas, abrasivos     E10 governança: APL, política, regulação, tributo
  E5 logística e portos               E11 tecnologia e inovação
  E6 comercialização e exportação
"""

import re

from rede import sem_acento

ELOS = {
    "E1": ("lavra", r"\b(lavra|pedreira|quarr|jazida|bloco[s]? de|extra[cç][aã]o|extraction|prospec|geolog|sigmine|direito miner|outcrop|deposit)"),
    "E2": ("beneficiamento primario", r"\b(tear(es)?|serrag|gang ?saw|multifio|multi-?wire|fio diamantado|diamond wire|chapa[s]? bruta|slab|talha.?bloco|block cutter|sawing)"),
    "E3": ("beneficiamento final", r"\b(polim|polish|resina|resin|marmoraria|acabamento|finishing|levig|flamead|ladrilh|tile[s]?|bancada|countertop|worktop)"),
    "E4": ("insumos e maquinas", r"\b(abrasiv|rebolo|granalha|maquin|machinery|equipament|equipment|ferramenta diamant|diamond tool|8464|6804)"),
    "E5": ("logistica", r"\b(porto|port of|frete|freight|container|contêiner|log[ií]stic|navio|shipping|ferrovia|rodovi|cabotagem)"),
    "E6": ("comercializacao e exportacao", r"\b(export|import|balan[cç]a comercial|tarif|trade|com[eé]rcio exterior|fob|feira|fair|marmomac|coverings|pre[cç]o|price|mercados?|compradores|buyers|china|estados unidos|united states|eua|europa|[aá]sia)"),
    "E7": ("mercado e construcao", r"\b(constru[cç][aã]o civil|construction|revestimento|cladding|fachada|facade|arquitet|architect|design|interior|demanda|consumo|housing|imobili)"),
    "E8": ("residuos e sustentabilidade", r"\b(res[ií]duo|waste|lama|sludge|slurry|reciclag|recycl|reaproveit|ambient|environment|sustentab|sustainab|lca|ciclo de vida|life cycle|pegada|footprint|carbono|carbon|licenciamento ambiental)"),
    "E9": ("trabalho e saude", r"\b(silicos|s[ií]lica|silica|ocupacion|occupational|acidente|accident|trabalhador|worker|sa[uú]de|health|emprego|employment|rais|caged|sal[aá]rio|wage)"),
    "E10": ("governanca e politica", r"\b(apl\b|arranjo produtivo|cluster|pol[ií]tica|policy|regula|anm\b|dnpm|cfem|royalt|tribut|tax|icms|incentiv|sindica|associa[cç]|centrorochas|abirochas|sindirochas|governan|legisla|plano nacional)"),
    "E11": ("tecnologia e inovacao", r"\b(inova[cç]|innovation|tecnolog|technolog|caracteriza[cç][aã]o tecnol|ensaio|test(ing)? method|durabil|weathering|altera[cç][aã]o|patent|patente|automa[cç]|digital|machine learning)"),
}
_ELOS_RE = {k: re.compile(p, re.I) for k, (_, p) in ELOS.items()}

# Relevância. Calibrado contra o 1º corpus real (2026-10-08): com "stone",
# "industry", "waste" genéricos, 2.117 de 2.613 obras entravam por acaso
# (cálculo renal, lixo nuclear em granito, agricultura orgânica).
#   FORTE    — basta sozinho
#   RESIDUO  — resíduo DE rocha ornamental (literatura grande e legítima do E8)
#   MATERIAL + CONTEXTO — rocha ornamental específica + termo do processo produtivo
FORTE = re.compile(
    r"rochas? ornament|rochas? de revestimento|pedras? ornament|pedras? naturais|pedra natural"
    r"|rochas? (brasileiras|capixabas|naturais)|setor de rochas|setor rochoso|marmorar|marmorista"
    r"|(?<!three-)(?<!two-)(?<!3-)(?<!2-)\bdimension(al)? stone|ornamental (stone|rock)|natural stone|stone fair"
    # pedra artificial/quartzo engenheirado: substituto direto e foco da silicose
    r"|engineered stone|artificial stone|agglomerated stone|quartz surfac|pedra artificial|quartzo (industrializado|engenheirado)"
    # "rochas" perto de termo setorial (manchete: "Exportações de rochas crescem")
    r"|\brochas?\b.{0,40}\b(export|setor|mercado|feira|beneficiament|marmor)|\b(export\w*|setor|feira)\b.{0,40}\brochas?\b"
    r"|centrorochas|abirochas|sindirochas|vit[oó]ria stone"
    r"|marmo e pietr|pietre ornamentali|lapidei|rocas ornamentales|piedra natural", re.I)
RESIDUO = re.compile(
    r"\b(marble|granite|quartzite|ornamental stone|dimension stone)\s+(waste|sludge|slurry|powder|dust|residue|cutting waste|processing waste)"
    r"|\bwaste\s+(marble|granite)\b"
    r"|res[ií]duos?\s+(de|do|da|das|dos)\s+(beneficiamento|serragem|corte|polimento|m[aá]rmore|granito|rochas?|quartzito)"
    r"|lama\s+(abrasiva|de (beneficiamento|serragem|m[aá]rmore|granito|rochas?))", re.I)
MATERIAL = re.compile(
    r"\b(m[aá]rmores?|marbles?|granitos?|granite|quartzitos?|quartzites?|ard[oó]sias?|slates?|travertin\w*"
    r"|gnaisses?|gneiss\w*|sienitos?|syenites?|charnoquitos?|charnockites?)\b", re.I)
CONTEXTO = re.compile(
    r"\b(quarr\w*|pedreiras?|lavra|blocos?|slabs?|chapas?|serrag\w*|sawing|gang ?saw|diamond wire|fio diamantado"
    r"|polim\w*|polish\w*|teares?|beneficiamento|revestimento|cladding|countertops?|bancadas?|ladrilh\w*|cantaria"
    r"|ornament\w*|exporta\w*|exports?|tarif\w*|mercado externo|marmorar\w*|silicos\w*"
    r"|cachoeiro|esp[ií]rito santo|nova ven[eé]cia|barra de s[aã]o francisco|santo ant[oô]nio de p[aá]dua)\b", re.I)


def avaliar(*textos):
    """Devolve (relevante: bool, motivo: str, elos: list[str])."""
    alvo = " ".join(t for t in textos if t)
    alvo_sa = sem_acento(alvo)
    forte = FORTE.search(alvo) or FORTE.search(alvo_sa)
    residuo = RESIDUO.search(alvo) or RESIDUO.search(alvo_sa)
    if forte:
        motivo = f"forte:{forte.group(0).lower()}"
    elif residuo:
        motivo = f"residuo:{residuo.group(0).lower()}"
    else:
        m, c = MATERIAL.search(alvo), CONTEXTO.search(alvo)
        if not (m and c):
            return False, "", []
        motivo = f"composto:{m.group(0).lower()}+{c.group(0).lower()}"
    elos = [k for k, rx in _ELOS_RE.items() if rx.search(alvo) or rx.search(alvo_sa)]
    return True, motivo, elos
