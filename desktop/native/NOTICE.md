# Third-party native capture components

This local preview integrates unmodified NTE Drive Calculator native-plugins-v3 components, Core 0.4.4.
These are third-party binaries, not Keke Assistant's independently implemented game reader.

The bundle includes the upstream capture/core license, copyright, source provenance, compatibility metadata and third-party dependency notices.
Exact binary fingerprints are pinned in component-identity.json. Four plugin signature files are preserved unchanged.

Inventory synchronization uses read-only inventory/character/item/team/environment RPCs. The separate native equipment workflow uses user-confirmed equip_module, equip_core, unequip_module and unequip_core operations for single-piece changes, and equipment.equip_one_key for saved plans containing a core and drives. Each plan is checked against a fresh full snapshot after dispatch; cross-character transfers are listed in the preview and the final snapshot verifies all affected equipment. No arbitrary RPC, combat collection, signature bypass or live injection loader is exposed.
The assistant includes a minimal JSON export of 12 native shape footprints and 25 character boards from the public game_static catalog, with table provenance and source database hash in inventory/equipment-layouts.json. UI coordinates use the normalized footprint's top-left corner; native RPC and snapshot coordinates use the original shape pivot. The catalog preserves the offset for conversion in both directions. Runtime does not read an installed Calculator directory. Layout solving reuses Keke Assistant's existing DriveLayoutSolver; Python independently validates each chosen placement.
Deployment copies the matched D3D host and all signed plugins into the user-selected game executable directory, only after the game exits.

Capture SOURCE.md explicitly states that its base commit alone does not reproduce the modified build. This preview is for this user's local testing. Do not treat inclusion of license/source links as fulfillment of corresponding-source requirements for external redistribution; obtain the matching source or applicable distribution authorization before a public release.

Source references: https://github.com/hxwd94666/NTE-Drive-Calculator and the bundled licenses/native-capture/{capture,core}/SOURCE.md.
