#!/usr/bin/env bash
set -e

FROM_DATE="${1:-2025-01-01}"
TO_DATE="${2:-2026-05-14}"

TICKERS=(
  SBER
  GAZP
  LKOH
  GMKN
  NVTK
  ROSN
  TATN
  MOEX
  VTBR
  AFLT
  ALRS
  MAGN
  NLMK
  CHMF
  PLZL
)

for ticker in "${TICKERS[@]}"; do
  echo "Updating $ticker from $FROM_DATE to $TO_DATE..."
  curl -s -X POST "http://127.0.0.1:8000/ingest/moex/$ticker?from_date=$FROM_DATE&to_date=$TO_DATE"
  echo ""
done

echo "Done."
