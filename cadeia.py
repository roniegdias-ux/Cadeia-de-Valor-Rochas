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
    "E6": ("comercializacao e exportacao", r"\b(export|import|balan[cç]a comercial|tarif|trade|com[eé]rcio exterior|fob|feira|fair|marmomac|coverings|pre[cç]o|price|mercado externo|china|estados unidos|united states|eua)"),
    "E7": ("mercado e construcao", r"\b(constru[cç][aã]o civil|construction|revestimento|cladding|fachada|facade|arquitet|architect|design|interior|demanda|consumo|housing|imobili)"),
    "E8": ("residuos e sustentabilidade", r"\b(res[ií]duo|waste|lama|sludge|slurry|reciclag|recycl|reaproveit|ambient|environment|sustentab|sustainab|lca|ciclo de vida|life cycle|pegada|footprint|carbono|carbon|licenciamento ambiental)"),
    "E9": ("trabalho e saude", r"\b(silicos|s[ií]lica|silica|ocupacion|occupational|acidente|accident|trabalhador|worker|sa[uú]de|health|emprego|employment|rais|caged|sal[aá]rio|wage)"),
    "E10": ("governanca e politica", r"\b(apl\b|arranjo produtivo|cluster|pol[ií]tica|policy|regula|anm\b|dnpm|cfem|royalt|tribut|tax|icms|incentiv|sindica|associa[cç]|centrorochas|abirochas|sindirochas|governan|legisla|plano nacional)"),
    "E11": ("tecnologia e inovacao", r"\b(inova[cç]|innovation|tecnolog|technolog|caracteriza[cç][aã]o tecnol|ensaio|test(ing)? method|durabil|weathering|altera[cç][aã]o|patent|patente|automa[cç]|digital|machine learning)"),
}
_ELOS_RE = {k: re.compile(p, re.I) for k, (_, p) in ELOS.items()}

# Relevância: termo FORTE basta; termo de MATERIAL só conta se vier com termo
# de CONTEXTO setorial (senão "granite" traz toda a petrologia do mundo).
FORTE = re.compile(
    r"rochas? ornament|rochas? de revestimento|pedras? ornament|pedras? naturais|pedra natural"
    r"|dimension(al)? stone|ornamental (stone|rock)|natural stone|stone industr|stone sector"
    r"|marmoraria|marmorista|setor de rochas|centrorochas|abirochas|sindirochas|stone fair"
    r"|marmo e pietr|pietre ornamentali|rocas ornamentales|piedra natural", re.I)
MATERIAL = re.compile(
    r"\b(m[aá]rmore|marble|marmo|granit|quartzit|ard[oó]sia|slate|travertin|gnaiss|gneiss"
    r"|sienit|syenit|charnoquit|charnockit|limestone|calc[aá]rio|basalto|arenito|sandstone|pedra[s]?|stone[s]?|rocha[s]?)", re.I)
CONTEXTO = re.compile(
    r"\b(quarr|pedreira|lavra|bloco|block|slab|chapa|serrag|sawing|polim|polish|tear|"
    r"export|import|ind[uú]stri|industr|setor|sector|empresa|firm|mercado|market|com[eé]rcio|trade|"
    r"res[ií]duo|waste|sludge|lama|beneficiamento|processing|revestimento|cladding|tile|ladrilh|"
    r"cachoeiro|esp[ií]rito santo|minas gerais|nova ven[eé]cia|barra de s[aã]o francisco|"
    r"ornament|cantaria|countertop|bancada|construction|constru[cç][aã]o|silicos)", re.I)


def avaliar(*textos):
    """Devolve (relevante: bool, motivo: str, elos: list[str])."""
    alvo = " ".join(t for t in textos if t)
    alvo_sa = sem_acento(alvo)
    forte = FORTE.search(alvo) or FORTE.search(alvo_sa)
    if forte:
        motivo = f"forte:{forte.group(0).lower()}"
    else:
        m, c = MATERIAL.search(alvo), CONTEXTO.search(alvo)
        if not (m and c):
            return False, "", []
        motivo = f"composto:{m.group(0).lower()}+{c.group(0).lower()}"
    elos = [k for k, rx in _ELOS_RE.items() if rx.search(alvo) or rx.search(alvo_sa)]
    return True, motivo, elos
