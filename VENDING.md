# UPKEEP machines

The native campaign now offers one solid UPKEEP machine near each floor's
starting point, off the mandatory route. Walk close, face it, and press **F**
or **right click**. The game and adaptive music pause while the menu is open.
Press **1–3** or click an offer to buy. A successful purchase resumes play with
cleared controls; **Esc** leaves the menu and keeps the run paused. Enter/click
then resumes as usual. A physical player's menu retains physical control
ownership while paused.

Start with **6 scrap**. Each native counted kill adds **1**; each discovered
native secret/cache adds **3**. Repeated reads, revisits and counter resets do
not pay again. Scrap is capped at 999. Prices are `6 + floor - 1 + 3 × current
rank`. The machine dispenses **one upgrade per floor**. Skipping it preserves
your scrap. There are no rerolls, restocks or permanent unlocks in this pass.

Each seed determines an ordered stock permutation for each floor. The first
three upgrades below their two-rank cap are offered; fewer may remain late in
a run. Choices, wallet and spent machines persist across native floor changes.
Retry/new seed creates a fresh engine and resets all run upgrades.

| Upgrade | Effect per rank |
| --- | --- |
| Deep Lungs | +25 ordinary health-pickup capacity and an immediate heal of up to 25. Existing overheal is preserved. |
| Composite Lining | 10% less incoming damage before armour. Fractional hits round up; chip damage remains meaningful. |
| Hot Loads | +20% player weapon damage, rounded down after scaling. Boss binding/shield rules still apply. |
| Ammo Bins | +50% base ammo capacity; +30 bullets, 8 shells, 30 cells and 2 rockets on purchase. Stacks with a backpack. |
| Runner Coils | +10% forward/strafe thrust. Turning, collision and creature-imposed movement restrictions stay native. |

The effects are additive by rank. Native fatal/telefrag-class damage (1000 or
more) bypasses the perk damage calculation. Soul/mega health pickup rules are
unchanged. This is an initial balance pass, not a completed long-run economy.

## Scope and interface

`NativeGame` enables vending for identity campaigns. Browser `Game`, legacy
demo/operator clients, and isolated studies keep their defaults. Calling
`campaign(..., assets=..., identity=True, vending=True)` opts a generated map
into it. The sprite is original procedural cabinet art drawn with Pillow and
the existing Departure Mono typeface; Freedoom supplies its palette. It adds
`VENDA0`/`VENDB0` at 48×72 native units instead of replacing an existing prop family.

The C engine owns money, ranks, reward high-water marks, stock filtering, use
range/sight/height, costs and atomic purchase validation. Python pauses its
external game clock and presents the authoritative `STATE.vending` object.
The future 3D backend can implement the same state/choice contract; this change
does not port the upgrades into the separate UZDoom tower prototype.

- `RVEND`: header `<4sIHH>` (`RVN1`, seed, entry count 1–7, zero reserved),
  then 16-byte `<HHhh5B3x>` records (map, unique machine ID, signed x/y,
  permutation of perk IDs 0–4, three zero bytes). One record and exactly one
  matching machine per active map are required. Malformed metadata fails closed.
- `VEND <machine-id> <slot-0..2>` returns `VEND {ok, ...}`. It requires a live
  player who opened that unspent machine, within 96 map units, facing within
  45 degrees, within 24 vertical units and with native line of sight.
- `VCLOSE` closes the menu. The desktop's authenticated loopback `buy` action
  also requires the current `revision`, `vendor` and `slot`; physical shop
  ownership blocks automated takeover. `close_shop` leaves play paused.
- `STATE.vending` exposes `active`, `credits`, `earned`, `spent`, `menu_open`,
  effective capacities/scales, ranks and current machine/offer information.

Build both native sizes with `make -C doomgeneric -f Makefile.ipc -j8`.
With `FREEDOOM_WAD` set, run `python -m unittest -v test_vending
test_desktop_controls test_native_playability test_resolution`. The real-engine
fixtures walk, turn, collect supplies, use machines, shoot, take damage and
cross native exits; they do not mutate gameplay through test-only commands.
