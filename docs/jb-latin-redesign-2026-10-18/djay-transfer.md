# djay transfer design and device verification

## Purpose and boundary

JB’s destination is a practical djay library on iPad. This is a design and test plan for 15,000 tracks and later changes, not an implemented device integration or proof that JB, Finder, Music, Files, and djay work together on Poy’s devices.

Preserve one stable staged audio copy per track, originals and their names, and a broad Genre plus detailed browsing value without duplicating audio into every style folder. Export multiple style memberships as categories or metadata when supported; otherwise use one user-chosen broad-family location and retain detailed styles in the catalogue and tags.

Use this route order only after its device test passes.

1. **Direct USB-C cable through Finder Files** is the first bulk candidate. It is the least ambiguous when the receiving iPad app or container supports File Sharing and djay can index the received media.
2. **Wireless SMB through Files** is the preferred local-network candidate after cable. It is a manual, observable workflow, not a background sync promise.
3. **Apple Music sync** remains a compatibility fallback for Poy’s current workflow when its category behavior works in djay.
4. **OneLibrary on USB** is an optional desktop-djay alternative, never the default route merely because it exists.
5. **AirDrop and iCloud Drive** are optional small-update conveniences only. They have no 15,000-track performance or cost guarantee and must never be enabled automatically.

A route is not “working” merely because files arrive; it must pass the checks below.

## Export preparation and states

The Export view creates a durable job before transfer. It calculates selected tracks, missing media, changed files, output bytes, target size, free space, profile revision, and filename collisions. It uses stable staging paths and never renames originals or changes their folder tree. NFC-normalize output names only when required, retain a collision suffix, and show the resulting path in the preview.

The manifest stores source identity, output checksum, profile revision, relative staging path, bytes, media status, and destination status. It permits incremental preparation without copying unchanged files. A tag-only revision prepares only selected changed files. An unavailable source is **Missing media**; a changed source or staged file is **Stale** and needs a fresh preview.

Use these distinct states throughout Export, Activity, the track drawer, and restore history:

| State | Meaning | Permitted transition |
|---|---|---|
| **Draft** | Selection or profile is being edited; no staged output exists. | Preview → Prepared. |
| **Prepared** | JB created and verified staged output plus a manifest. It makes no claim about an iPad. | User marks transfer attempt → Transferred (user-confirmed) or Transfer unverified. |
| **Transferred (user-confirmed)** | The user says completed staged files reached the intended iPad location. JB has no device API evidence. | Device test → Verified in djay, Failed, or remains user-confirmed. |
| **Transfer unverified** | Copy was initiated, a browser/Finder action opened, or a destination is unknown. | User confirmation or device test; it must never become Verified automatically. |
| **Verified in djay** | A dated device-test record proves the declared verification scope: named sample or complete export. | A retag, changed file, or route/profile change returns affected tracks to Prepared. |
| **Failed / Missing media / Stale** | A visible reason blocks completion. | Retry from the affected earlier state. |

“Verified in djay” must record route, iPad and djay version, profile revision, tester, date, sample size, tested search fields, playback result, and whether verification covered a sample or every file. It never means a full transfer succeeded unless every requested file was checked. The Activity view separates export bytes prepared from user-confirmed transfer and device verification; its labels must not say “synced” for any of these states.

## Metadata profiles and copy discipline

The default profile writes a single standard broad Genre and preserves the raw existing Comment as an observed value. It shows a field-by-field diff before writing any copy. It does not overwrite originals in this plan. For category access such as Salsa Romántica, the evaluation profile is **djay extended Genre** on staged copies only: one CSV string containing the parent and qualified style, for example `Salsa, Salsa Romántica`. It preserves the source broad Genre and raw Comments in the manifest and preview. This candidate follows an Algoriddim community recommendation to prefer CSV Genre over repeated ID3 values; its actual iPad mapping must still be tested. It does not promise arbitrary custom frames or M3U compatibility.

A source file appears once in staging. The profile must not make a second audio copy for Timba, Salsa room, or a saved filter. Category membership lives in JB and, where supported, metadata or a destination collection. A folder fallback uses one selected broad-family folder only. The preflight makes copies and extra storage explicit.

## Route A — direct USB-C cable bulk test

Apple documents Finder file transfer only for apps that support File Sharing. Therefore the first test determines whether the intended receiving container is visible in Finder and whether djay can index media from that location; do not assume a Files-visible location belongs to djay.

1. In Export, select the **Direct cable** route, the default profile, and 20 disposable representative copies. Review missing-media and byte estimates, then prepare the job.
2. Connect the unlocked iPad to the Mac by USB-C and open Finder. Locate the device and inspect its Files/File Sharing area. If the selected app or destination is absent, stop this route as unsupported rather than copying into an arbitrary container.
3. Copy only the prepared stable staging directory. Eject only after Finder reports completion. Record the copy as **Transferred (user-confirmed)**; cable completion is not djay verification.
4. In djay, add or index the received files using its supported Files or My Collection workflow. Run the device checks. If index references originals rather than importing a copy, keep the source in the expected reachable location.

Finder has no documented safe JB-controlled delta-sync API. Later updates repeat the prepared changed-file list through the same observed user action. A cable disconnect creates an incomplete transfer: mark the attempt failed or unverified, compare the manifest again, and retry only missing or changed outputs. Never infer success from opening Finder.

## Route B — wireless local SMB test

This route is a proposed composition of Apple’s File Sharing and Files “Connect to Server” features, so it needs real-device validation. It is useful only while the Mac is awake, reachable on the local network, and deliberately sharing an export-only folder.

1. Poy enables macOS File Sharing or uses an existing approved share, limited to the JB staged-export folder and a permitted macOS account. JB never stores macOS credentials or runs a new Flask LAN music server.
2. On iPad, use Files **Connect to Server** with that registered account, browse the export-only share, and copy completed prepared files into one stable **On My iPad** directory.
3. Add or index those local files in djay, then execute the device checks. Record the route as wireless SMB and the exact destination directory in the verification evidence.

This is not automatic sync, does not run against a sleeping Mac, and has no claimed failover from cable. A network interruption leaves the job unverified until the manifest and files are reconciled manually. The incremental manifest limits the next copy to prepared differences; it does not grant Finder or Files an undocumented delta API.

## Route C — Apple Music compatibility fallback

Use this only when the existing Poy workflow remains usable in djay. Finder can sync Music over cable or, after initial cable pairing, Wi-Fi; Apple notes Wi-Fi sync can be slower. iCloud Sync Library can disable Finder Music syncing. JB must never change that setting, replace the Music database, or claim that refreshing Music sends files to an iPad.

Prepare a 20-copy job, import it using Poy’s existing Music workflow, perform the chosen cable or Wi-Fi sync action, and then check the iPad’s **Local Music** and any relevant djay source separately. Algoriddim staff state that Local Music reads the Music database rather than raw ID3, so both initial import and a retag of an already imported track are required. A successful Mac Music refresh is not a device-sync result.

## Route D — optional OneLibrary USB test

OneLibrary is worth comparing only if Mac djay is available and its supported desktop export fits Poy’s workflow. djay documents iOS OneLibrary as read-only: iOS can browse USB content or import a playlist and copy files to internal storage. Do not write private djay databases or OneLibrary files. Test initial import, retagged content, Genre, detailed browsing value, playback, and duplicate/cue behavior. It is not the default wireless or cable recommendation.

## Required device acceptance test

Run each eligible route with 20 disposable copies before bulk use. Include Salsa, Bachata, Kizomba, a fourth-wave example, mixed supported file formats, a detailed Comment, a no-comment track, a multi-style candidate, and an already-imported track whose staged copy is retagged. The test record must cover:

- initial import or index, subsequent changed-file transfer, and a retag of an already imported item;
- Genre browsing, search, filters, and the detailed browsing value (Comments are not documented as a djay search field, so record the actual result);
- direct playback offline in airplane mode after the route reports complete, including files previously held in cloud storage;
- duplicate paths, duplicate track entries, and preservation of existing cues or playlist references where applicable;
- cable unplug or network loss during transfer, manifest reconciliation, retry of only missing files, and no false “synced” label;
- source/original preservation, stable staging path, collision handling, byte/free-space estimate, and a visible field diff;
- djay availability, device version, and subscription applicability. No purchase is a prerequisite for this plan.

Only then may Phase 0 choose a route for a larger staged batch. If Comments are not browsable or searchable, test the `djay extended Genre` profile on copies. If it fails, keep the detailed taxonomy in JB and select another supported browsing path rather than silently collapsing labels.

## Existing-code crosswalk and product guardrails

The existing Sync Center is only an export launcher. `app/static/modules/sync-center.js:75-87` stores a local “Last Sync” timestamp, and lines 212-222 write it after `window.open()` succeeds. It cannot prove that a file reached an iPad. `app/routes/applescript_routes.py:8-35` calls Music `refresh`; it does not command a device sync. Existing M3U routes emit desktop absolute paths (`app/routes/export_routes.py:13-20`), so they are not portable iPad transfer evidence. These audit facts remain unchanged; the planned Export and Activity contract replaces their misleading presentation rather than treating them as an integration.

## Sources

- [Apple: transfer files between a Mac and iPhone or iPad](https://support.apple.com/en-ca/119585)
- [Apple: sync content between Mac and iPhone or iPad](https://support.apple.com/en-hk/guide/mac-help/mchlada1d602/mac) and [Sync Library availability](https://support.apple.com/en-ie/guide/mac-help/mchl923c1147/27/mac/27)
- [Apple: connect iPad Files to a server](https://support.apple.com/en-ie/guide/ipad/ipad8139864c/ipados) and [macOS File Sharing](https://support.apple.com/en-au/guide/mac-help/mh17131/mac)
- [djay iOS: external tracks](https://help.algoriddim.com/user-manual/djay-ios/music-library/advanced/adding-external-tracks), [My Collection](https://help.algoriddim.com/user-manual/djay-ios/music-library/my-collection), and [searching](https://help.algoriddim.com/user-manual/djay-ios/music-library/searching)
- [djay iOS: OneLibrary](https://help.algoriddim.com/user-manual/djay-ios/music-library/advanced/onelibrary), [djay iCloud limits](https://help.algoriddim.com/topic/using-djay/icloud), and [Algoriddim staff Genre note](https://community.algoriddim.com/t/read-multiple-genre-tags-in-local-music/42053)
