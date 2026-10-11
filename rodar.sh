#!/usr/bin/env bash
# Sequência operacional. Uso:
#   ./rodar.sh matriz      # (re)valida fontes — antes da 1ª coleta e quando algo começar a falhar
#   ./rodar.sh diario      # notícias
#   ./rodar.sh semanal     # bibliografia incremental (+ triagem pelo agente, prompts/triagem.md §A)
#   ./rodar.sh mensal      # séries de dados (ComexStat publica nos primeiros dias úteis)
#   ./rodar.sh backfill    # 1 vez: bibliografia desde 1970 + séries desde 1997
# Código de saída != 0 = coleta degradada ou falha: NÃO commitar em silêncio; reportar.
set -uo pipefail
cd "$(dirname "$0")"
modo="${1:-diario}"
st=0
case "$modo" in
  matriz)   python3 verificar_fontes.py || st=$? ;;
  diario)   python3 noticias.py || st=$? ;;
  semanal)  python3 biblio.py || st=$? ;;
  mensal)   python3 dados.py || st=$?
            python3 mapeamento.py || st=$? ;;
  backfill) python3 biblio.py --backfill || st=$?
            python3 dados.py --backfill || st=$? ;;
  backfill-biblio) python3 biblio.py --backfill || st=$? ;;
  backfill-dados)  python3 dados.py --backfill || st=$? ;;
  retro-sites) python3 retro_sites.py || st=$?
               python3 retro_pdfs.py || st=$? ;;
  retro-gn)    python3 retro_gn.py --minutos "${MINUTOS:-40}" || st=$? ;;
  anm)         python3 anm.py || st=$? ;;
  *) echo "modo desconhecido: $modo"; exit 64 ;;
esac
echo "rodar.sh $modo -> saída $st"
exit "$st"
