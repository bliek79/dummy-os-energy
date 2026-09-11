# Dummy OS Energy 0.2.0-alpha.23 - Safety Reserve SOC Wiring Fix

**Tag:** `0.2.0-alpha.23`

## Dummy OS Energy 0.2.0-alpha.23

This prerelease is a targeted follow-up to the alpha.22 live validation.

## Fixed
- Safety now reads the current Dummy OS Energy Reserve SOC entity `sensor.dummy_os_energy_do_plan_reserve_soc` instead of the stale hardcoded `sensor.do_plan_reserve_soc` entity id.
- This removes the false `reserve_not_ready` / `reserve_status: unavailable` condition observed while Reserve SOC itself was `ready` and `valid`.
- The matching Safety contract test is updated to guard the corrected lookup.

## Deliberately unchanged
- No broader entity naming cleanup is included; that work remains deferred.
- No Reserve SOC calculation changes.
- No Energy Need changes.
- No Scheduler or Plan Store changes.
- No Prestart logic changes.
- No physical execution changes.

## Safety and architecture
- `shadow_only` remains true.
- `active_use_permitted` remains false.
- `physical_execution_authority` remains false.
- Native architecture remains 15 minutes / 72 hours / 288 slots.

## Validation
- Pull request #213 validation completed successfully before merge.
- Release candidate must pass the full repository validation before publication.

## Live validation after installation
- Confirm DO Plan Reserve SOC remains `ready` / `valid`.
- Confirm DO Plan Safety reports `reserve_status: ready` and `reserve_valid: true`.
- Confirm `reserve_not_ready` is absent when Reserve SOC is healthy.
- Confirm Safety and Prestart remain fail-closed when no executable plan is selected.
