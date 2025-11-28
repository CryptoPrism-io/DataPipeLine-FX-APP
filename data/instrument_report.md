# OANDA Instruments Snapshot

- Source: `data/oanda_instruments.csv` (pulled via OANDA instruments endpoint)
- Total instruments: 123
  - CURRENCY: 68
  - METAL: 21
  - CFD: 34

Sample records
- METAL: `XAU_CHF` (Gold/CHF) — marginRate: 0.05, pipLocation: -2
- CURRENCY: `NZD_SGD` — marginRate: 0.05, pipLocation: -4
- CFD: `USB05Y_USD` (US 5Y T-Note) — marginRate: 0.20, pipLocation: -2

Fields captured in CSV
- name, type, displayName, pipLocation, marginRate, minimumTradeSize, maximumOrderUnits, maximumPositionSize, maximumTrailingStopDistance, minimumTrailingStopDistance, maximumDistance, minimumDistance, minimumPriceVariation

Next steps
- Filter `data/oanda_instruments.csv` to select which instruments to add to `Config.TRACKED_PAIRS`.
- For new picks, run backfill via the “Manual Backfill” workflow (12/24/36 day options) or locally with `python backfill_1000_hours.py --days N`.
