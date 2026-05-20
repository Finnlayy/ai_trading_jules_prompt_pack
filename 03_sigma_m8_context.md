# Sigma/M8 Context

## Bestehendes PineScript

Datei:

`G:\Downloads_Sortiert_2026-05-20\pine\sigma_system_REV10.pine`

Backup vor Patch:

`G:\Downloads_Sortiert_2026-05-20\pine\sigma_system_REV10.pre_codex_20260520_185353.pine`

## Sigma Module

Das Script enthaelt:
- M1: EMH-LAC Regime Engine
- M2: Kelly Sizer
- M3: Walk-Forward Optimization
- M4: Crisis Scanner
- M5: Dashboard
- M6: Alert Engine
- M7: Monte Carlo Engine
- M8: Execution Quality Gate

## M8 Execution Quality Gate

M8 operationalisiert die Prompt-/Trading-Regeln:
- setup/trigger/invalidation/no-trade nicht vage behandeln
- confluence score statt Bauchgefuehl
- harte Reject-Gates
- simulation-first Alert Payloads

### M8 Inputs

- `Enable Quality Gate`
- `Minimum Confluence Score`
- `Max Simulated Trades per Day`
- `Entry Cooldown Bars`
- `Require Relative Volume`
- `Minimum Relative Volume`
- `Maximum Crisis Score for Entries`
- `Reject Wide MC Dispersion`
- `Maximum MC Path Dispersion`
- `Require MC Direction Alignment`
- `Minimum MC Direction Confirmation`
- `Show Quality Gate Plots`

### M8 Outputs

- `m8_long_score`
- `m8_short_score`
- `m8_long_gate`
- `m8_short_gate`
- `m8_long_rejected`
- `m8_short_rejected`
- `m8_reject_reason`
- structured simulation alert payloads

## Jules-Aufgabe mit Sigma/M8

Jules soll nicht das PineScript neu erfinden.

Jules soll planen:
- wie Sigma/M8-Signale in ein Python-Backend gelangen
- wie M8 Payloads validiert werden
- wie AI-Agenten M8-Kontext reviewen
- wie die deterministische Risk Engine final entscheidet
- wie jeder Trade simuliert und geloggt wird

## Strenge Grenze

M8 ist ein Gate, kein Gewinnversprechen.

AI darf M8 nicht ueberschreiben.

Wenn AI und M8 widersprechen:
- Default = reject
- Log = `AI_M8_CONFLICT`
- Human Review optional

