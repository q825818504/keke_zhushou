# Third-party native capture components

This local preview integrates unmodified NTE Drive Calculator native-plugins-v3 components, Core 0.4.4.
These are third-party binaries, not Keke Assistant's independently implemented game reader.

The bundle includes the upstream capture/core license, copyright, source provenance, compatibility metadata and third-party dependency notices.
Exact binary fingerprints are pinned in component-identity.json. Four plugin signature files are preserved unchanged.

Only read-only inventory/character/item/team/environment RPCs are exposed. No combat collection, equipment mutation, signature bypass or live injection loader is invoked.
Deployment copies the matched D3D host and all signed plugins into the user-selected game executable directory, only after the game exits.

Capture SOURCE.md explicitly states that its base commit alone does not reproduce the modified build. This preview is for this user's local testing. Do not treat inclusion of license/source links as fulfillment of corresponding-source requirements for external redistribution; obtain the matching source or applicable distribution authorization before a public release.

Source references: https://github.com/hxwd94666/NTE-Drive-Calculator and the bundled licenses/native-capture/{capture,core}/SOURCE.md.
