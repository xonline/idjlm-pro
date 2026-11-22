# DJ tagging competitor refresh

Checked 10 November 2026. Comparison boundary: the 18 October 2026 Latin classifier audit. This refresh checks current public product documentation and release dates. It does not test the products, infer their private algorithms, or treat their marketing claims as measured accuracy.

## What changed since 18 October

I found no dated post-18 October release from Tagami, OneTagger, or a relevant audio tagger that proves a new Latin genre-classification capability. OneTagger’s official release page still lists 1.7.0, released 3 August 2023. Its currently documented Quick Tag is useful manual tagging, not audio genre inference.

Tagami’s broad update is real, but its public announcement is dated 11 September 2026, before the previous audit. The current product has a free tier and one-time Pro purchase; the announcement says the former 14-day trial and save limit were removed. Do not describe these as changes since 18 October. Lexicon published October and November 2026 workflow tips after the previous audit. Those posts reinforce existing behavior, especially cleaning title and artist metadata before database lookup. They do not announce a Latin classifier or a new genre model.

Choon is a useful comparator omitted from the October audit, but its dated getting-started article is 16 April 2026, also before the cutoff. It is new to this comparison, not new since the prior audit.

No current source supports “perfect” or effortless Latin classification. Choon itself says its AI is not perfect and describes human review. Product feature claims below are not independent accuracy evidence.

## Current products and what they prove

| Product | Current documented capability | Relevance and limit |
|---|---|---|
| [Tagami](https://tagami.au/) | Keyboard-first Genre and Comment keyword tagging; multi-tag filtering and saved presets; bulk edits; inline edits; zoomable waveform playback; tag finder against MusicBrainz and iTunes with an unsaved review table; playlist generation and export. Its current page also describes cue/loop tools and bulk actions. | Strong reference for fast tagging, auditioning, filters, and review-before-save. Tag finder retrieves metadata from named sources; it does not prove audio-based Salsa or subgenre recognition. The 11 September community update documents new waveform, cue/loop, playlist, filter-panel, and export features, but predates the October audit. [Dated announcement](https://community.algoriddim.com/t/tagami-toolkit-app-for-djs-huge-update/43211). |
| [OneTagger](https://onetagger.github.io/) | Auto Tag matches metadata to Beatport, Traxsource, Juno, Discogs, iTunes, MusicBrainz, Beatsource, and Spotify, with Shazam identification. Spotify Audio Features are fetched using ISRC or exact-match lookup. Quick Tag applies a user-defined Energy, Mood, Genre, or other palette with keyboard shortcuts. | It is an open-source metadata lookup and manual tagging reference, not an audio classifier for niche Latin styles. The [official release list](https://github.com/Marekkon5/onetagger/releases) still shows 1.7.0, dated 3 August 2023. Do not mistake Spotify-derived features or a user palette for verified Salsa labels. |
| [Lexicon](https://www.lexicondj.com/manual/all) | Genre Cleanup maps inconsistent genres and can lock protected values. Find Tags & Album Art retrieves Genre, Year, Label, Album, Energy, Danceability, Popularity, and Happiness from SonoVault using existing artist/title metadata; its manual says title/artist quality affects matching. It can keep main Genre in the Genre field and put subgenres in Custom Tags. Custom Tags can be category-based, searched, combined as OR within a category and AND across categories, and mapped to Comment or DJ-app fields. | Good references for genre cleanup, locks, multiple category filters, and explicit field mapping. Lookup is database/release matching, not evidence of acoustic Latin recognition. The [November 2026 tip](https://www.lexicondj.com/blog/tips-drop-november-2026) was posted after the cutoff and repeats the need to clean titles before lookup; it does not document a new classification feature. |
| [Choon](https://choon.app/how-it-works) | A Mac companion produces Genre, Region, Era, and Vibe tags from a user-selected vocabulary. Its documentation says it uses metadata and music-database context, while the Mac app also analyzes tempo, energy, and tonal qualities. It shows confidence per tag, allows batch selection and review, and syncs to Rekordbox My Tag. It sends track metadata for tagging; the product says audio files remain on the Mac. | Useful patterns for user-controlled labels, separate tag dimensions, confidence display, and batch review. Its [dated setup guide](https://choon.app/blog/getting-started-with-choon) is from 16 April 2026. The docs do not show an independently measured Latin benchmark, named Salsa/Bachata/Kizomba taxonomy, offline classification, or proof that tempo/energy/tonality establishes genre. Treat its workflow as a pattern, not an accuracy result. |

These products separate two jobs that IDJLM must not conflate: proposing or retrieving a value and making that value fast to browse, correct, and export. The first needs evidence and evaluation. The second can borrow tested interaction patterns now.

## OneTagger screenshot palette: exact transcription

The two supplied screenshots show unchecked options beneath two headings. These strings are transcribed as displayed, including lowercase spelling, punctuation, and spacing. They are user palette values, not a validated taxonomy or track assignments.

**Salsa**

`classica` · `cubana` · `dura / brava` · `latin jazz` · `mambo` · `romantica` · `timba` · `tropical` · `afro` · `instrumental`

**Salsa Rhythm**

`boogaloo` · `charanga` · `english,fusion` · `guaguanco` · `guajira` · `on1` · `pachanga` · `rumba` · `son` · `swap` · `live` · `choke` · `tempo changed` · `????` · `descasgar` · `cumbia` · `breaks`

Screenshot 1 shows the Salsa list and the beginning of Salsa Rhythm. Screenshot 2 shows the Salsa Rhythm list continuing from `boogaloo`.

Keep these strings unchanged in any palette import or alias mapping until the source Comment format is inspected. In particular, do not split `english,fusion`; the screenshot presents it as one checkbox label. Do not reinterpret `swap`, `????`, `descasgar`, `on1`, or `tempo changed` without the user’s definition. The headings are palette groups, not proof that all child values are music subgenres. The values visibly mix possible styles, rhythm or arrangement cues, dance use, production, language, instrumentation or vocal status, and unexplained personal shorthand. A selected checkbox could make a displayed label relevant, but these screenshots show the boxes unchecked; they do not establish a tag on any track.

## Small additions for the implementation

Prioritize these workflow additions. They improve speed and user trust without expanding the classification model’s claims.

1. **Import personal palettes as raw vocabulary.** Let the user choose a source such as the OneTagger palette or an inspected Comment value. Preserve exact text, group, and delimiter. Show proposed mappings to internal axes as a separate review. Unmapped values remain valid personal tags. Do not convert the palette into training labels.
2. **Keep tagging and auditioning keyboard-friendly.** Let a listener move through selected tracks, play or seek the relevant section, apply several personal tags, and continue to the next track without losing selection. Reuse the project’s current player and waveform where they work. A waveform is a navigation aid, not classification evidence by itself.
3. **Make category filters reusable.** Support multi-select within an axis and stacked filters across axes, then save the result as a Library view or playlist rule. Show the logic plainly, such as “Salsa Romántica OR Salsa Dura, AND live.” Preserve raw personal palette categories separately from classifier axes.
4. **Review each proposed field with its evidence.** Show family, style, dance use, production/version, and vocal language separately. Each axis can be known, uncertain, mixed, or unsupported independently. Show source, model version, and calibrated confidence or an honest uncertainty label. A reliable family result can stand when style abstains.
5. **Preview exact writes before batch approval.** Show original Genre and raw Comment beside the proposed values, selected files and fields, profile mapping, and conflicts. Keep original comments intact. Require one confirmation for that displayed batch, then write and verify each file with recoverable backup.
6. **Use online metadata lookup only as an optional evidence source.** Clean artist/title fields first, show source and match candidates, and preserve existing values unless the user accepts a proposed field change. Do not make cloud lookup a prerequisite for local audio classification.

Keep cue/loop editing, artwork generation, paid database services, direct DJ-database sync, and added mobile features out of this classification milestone. Tagami and Lexicon prove those are product areas; they do not make them requirements for accurate Latin tagging.

## djay and Comment export caution

The official [djay iOS search guide](https://help.algoriddim.com/user-manual/djay-ios/music-library/searching) documents filters including Genre but does not list Comment. The [Files source guide](https://help.algoriddim.com/user-manual/djay-ios/music-library/advanced/adding-external-tracks) says Files tracks are not searchable in that source and reference their original location; items must be local when played. [My Collection](https://help.algoriddim.com/user-manual/djay-ios/music-library/my-collection) indexes added tracks rather than copying or moving them. The docs also describe availability/subscription requirements for external-track access. Do not promise that transferring a file makes detailed comments searchable in djay.

Keep broad standard Genre plus the preserved raw Comment as the default export profile. On disposable copies, test a reversible “extended Genre” profile that writes one CSV Genre string such as `Salsa, Salsa Romántica`, while retaining the original Genre and Comment values in IDJLM and the write ledger. Algoriddim staff have recommended a single-string CSV Genre rather than repeated ID3 Genre values, but only device testing can confirm it works for the user’s version. Verify that imported tracks are added to My Collection and that the desired detail is visible and discoverable. Do not certify an export route from copy completion alone.

## Sources checked

- Tagami current [product page](https://tagami.au/) and dated [11 September 2026 feature announcement](https://community.algoriddim.com/t/tagami-toolkit-app-for-djs-huge-update/43211).
- OneTagger [official product page](https://onetagger.github.io/) and [official release history](https://github.com/Marekkon5/onetagger/releases).
- Lexicon official [Find Tags & Album Art](https://www.lexicondj.com/manual/find-tags-and-album-art), [Genre Cleanup](https://www.lexicondj.com/manual/genre-cleanup), [Custom Tags](https://www.lexicondj.com/manual/tags), and [Field Mappings](https://www.lexicondj.com/manual/field-mappings) manuals, plus its dated [October](https://www.lexicondj.com/blog/tips-drop-october-2026) and [November 2026](https://www.lexicondj.com/blog/tips-drop-november-2026) tips.
- Choon [How It Works](https://choon.app/how-it-works), [Mac download and requirements](https://choon.app/download), and dated [16 April 2026 setup guide](https://choon.app/blog/getting-started-with-choon).
- Screenshots supplied 10 November 2026: `/home/ubuntu/upload/Screenshot 2026-11-10 at 3.35.35 am.png` and `/home/ubuntu/upload/Screenshot 2026-11-10 at 3.35.41 am.png`.
