# Dummy OS Energy 0.2.0-alpha.22 - SOC Contract Runtime Wiring

**Tag:** `0.2.0-alpha.22`

## Dummy OS Energy 0.2.0-alpha.22

This prerelease fixes the live alpha.21 SOC wiring issue.

## Changed
- Energy Need and Safety now consume the shared central SOC Contract v1 runtime.
- Downstream SOC consumption no longer depends on the generated Home Assistant entity id of the SOC Contract sensor.
- The central SOC contract remains the single validation path for the raw Anker SOC source.

## Safety and architecture
- Fail-closed behaviour is retained for invalid or unavailable SOC input.
- Last-known-good SOC remains diagnostic only and is never used as current SOC fallback.
- `shadow_only` remains true.
- `active_use_permitted` remains false.
- `physical_execution_authority` remains false.
- Native architecture remains 15 minutes / 72 hours / 288 slots.

## Validation
- Focused SOC runtime wiring tests passed.
- Full pre-merge suite: 377 tests passed.
- Pull-request CI completed successfully.

## Live validation after installation
Validate the SOC Contract, Energy Need, Reserve SOC, Safety and Prestart chain in Home Assistant. In particular, Energy Need must no longer block on `soc_unavailable` when the central SOC contract is valid.
