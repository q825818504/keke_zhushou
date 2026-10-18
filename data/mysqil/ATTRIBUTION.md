# Mysqil · 环世全鉴 source attribution

- Source: [Mysqil · 环世全鉴](https://wiki.mysqil.com/)
- Stated source license: CC BY-NC-SA 4.0.
- License terms: [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-nc-sa/4.0/).
- Character, linked equipment, and complete arc-drive, sky-curtain, and driver-block catalog snapshots are stored under `data/mysqil/`.
- The arc-drive index, item pages, and downloaded item icons retain source links and author/license metadata in `data/mysqil/weapons/roster.json` and `data/knowledge/encyclopedia/arc_drives.json`.
- The sky-curtain index, all 12 item pages, and all 36 quality images retain source links and author/license metadata in `data/mysqil/cassettes/roster.json` and `data/knowledge/encyclopedia/sky_curtains.json`.
- The driver-block index, all 36 shape-quality pages, the linked mechanism guide, and 46 unique image assets retain source links and author/license metadata in `data/mysqil/driver-blocks/roster.json` and `data/knowledge/encyclopedia/driver_blocks.json`.
- Character records retain their source URL and human-review state. Arc-drive records retain the source URL, local snapshot path, icon checksum, and author/license metadata. Sky-curtain records retain the source URL, local snapshot path, three image checksums, and author/license metadata.
- Normalized encyclopedia records are structured extractions from preserved source pages; the public catalogs identify this change and link the license. Keep the author, source URL, license URL, and modification note when sharing adapted catalog data. The driver-block mechanism guide also preserves its cited secondary sources and the note that in-game values are authoritative.
- Team recommendations remain in raw snapshots and are excluded from normalized knowledge.

Check license compatibility before redistributing imported descriptions or images, especially in commercial use.

## Local asset use in Keke Assistant

- The app renders the normalized records and local image files referenced by `local_path`; image paths are restricted to the project's `data/` directory.
- HTML pages under `raw/` are source archives for auditing and re-import only. They contain the source site's original navigation and page resources and are not loaded by the app or copied into the Windows user release.
- `source_url` and `license_url` fields are retained as attribution metadata. They are not used to fetch images or render clickable source links in the app.
- The public user release copies only local image files referenced by its app bundle. Keep the author, source, license, and modification notice when sharing adapted data.
