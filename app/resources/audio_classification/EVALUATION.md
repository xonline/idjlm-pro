# Audio benchmark data boundary

The benchmark command consumes a local JSONL manifest and never uploads audio.
It must only name files the evaluator is allowed to decode locally. Do not add
user-library paths to a committed manifest.

`MTG-Jamendo` is a possible source for licensed public audio and broad negative
examples, after checking each selected recording's licence and the intended use.
Its public genre tags do not establish Salsa, Bachata, or Kizomba ground truth.
Do not relabel it by title, artist, or an LLM. A small target-family evaluation
set still needs lawful recordings, documented provenance, and independent human
adjudication. Keep artist/album/recording/remix groups in exactly one split.

The Zenodo Salsa Dataset record `13120822` offers a small 322.6 MB audio-fragment archive and beat annotations, but its record does not establish release rights or target-family/style gold labels in this project. Treat it as a candidate smoke/positive-source only after a licence review; do not distribute it, use it as a precision benchmark, or infer Bachata/Kizomba coverage from it. The Latin Music Database exposes feature vectors rather than redistributable audio, so it is unsuitable for this CLAP audio proof.

No public corpus is shipped by IDJLM and this repository makes no accuracy claim
until a frozen, lawfully sourced held-out set has been evaluated.

## Implementation smoke, not a quality result

On 2026-11-10 the pinned `laion/clap-htsat-unfused` revision
`8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a` ran locally on this Linux host
against a generated 10-second, 48 kHz mono sine-wave WAV. The first inference
in one process took 10.901 seconds, the next took 2.764 seconds, and the
process peak RSS was 1,457,368 KB. The install-and-first-run command took
21.91 seconds and peaked at 1,468,964 KB. This proves the adapter, download
verification, decoding and CPU inference path only. It is not an M3 benchmark,
Latin-music evaluation, memory target, or model-selection result.

The installed checkpoint is an Apache-2.0 generic CLAP baseline, not the
selected production music model. Compare it against the separately documented
music-and-speech CLAP candidate on the same grouped, held-out Latin set before
selecting a model or enabling any family for more than review suggestions.
