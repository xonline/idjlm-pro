from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Track:
    # Identity
    file_path: str
    filename: str

    # Existing ID3 tags (read from file)
    existing_title: Optional[str] = None
    existing_artist: Optional[str] = None
    existing_album: Optional[str] = None
    existing_year: Optional[str] = None
    existing_genre: Optional[str] = None
    existing_comment: Optional[str] = None
    existing_bpm: Optional[str] = None
    existing_key: Optional[str] = None

    # Audio analysis (librosa)
    analyzed_bpm: Optional[float] = None
    analyzed_key: Optional[str] = None       # Camelot notation e.g. "8B"
    analyzed_energy: Optional[int] = None    # 1-10
    waveform_data: Optional[list] = None     # 60 normalised amplitude points (0.0–1.0)
    bpm_corrected: bool = False              # True if BPM was half/doubled for correction
    bpm_confidence: Optional[int] = None     # 0-100
    key_confidence: Optional[int] = None     # 0-100
    analysis_done: bool = False

    # AI classification
    proposed_genre: Optional[str] = None
    proposed_subgenre: Optional[str] = None
    confidence: Optional[int] = None          # 0-100
    reasoning: Optional[str] = None
    classification_done: bool = False

    # Spotify enrichment
    spotify_title: Optional[str] = None
    spotify_artist: Optional[str] = None
    spotify_year: Optional[str] = None
    spotify_genres: list = field(default_factory=list)
    album_art_url: Optional[str] = None      # Album art URL from Spotify
    enrichment_done: bool = False

    # Review state: "pending" | "approved" | "skipped" | "edited"
    review_status: str = "pending"

    # User overrides (set during review)
    override_genre: Optional[str] = None
    override_subgenre: Optional[str] = None
    override_bpm: Optional[str] = None
    override_key: Optional[str] = None
    override_year: Optional[str] = None
    override_comment: Optional[str] = None

    # Write state
    tags_written: bool = False
    error: Optional[str] = None

    # Duplicate detection
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None       # file_path of the original track

    # Setlist
    setlist_position: Optional[int] = None

    # Approval learning
    approval_logged: bool = False

    # Latin music analysis
    clave_pattern: Optional[str] = None      # "2-3", "3-2", or None
    clave_confidence: Optional[int] = None   # 0-100
    suggested_cues: Optional[list] = None    # [{label, position_sec, type}]
    latin_analysis_done: bool = False

    # Vocal / Instrumental detection
    vocal_flag: Optional[str] = None          # "vocal", "instrumental", "mostly_instrumental"
    vocal_confidence: Optional[int] = None    # 0-100

    # Tempo category (per dance style)
    tempo_category: Optional[str] = None      # "slow", "medium", "fast"

    # Key accuracy
    key_mismatch: Optional[bool] = None       # True if analyzed_key differs significantly from final_key
    key_mismatch_detail: Optional[str] = None # e.g. "Stored: 8A, Detected: 7B"

    def to_dict(self) -> dict:
        d = asdict(self)
        # asdict() only serialises dataclass fields — add @property values explicitly
        d['display_title'] = self.display_title
        d['display_artist'] = self.display_artist
        d['final_genre'] = self.final_genre
        d['final_subgenre'] = self.final_subgenre
        d['final_bpm'] = self.final_bpm
        d['final_key'] = self.final_key
        d['final_year'] = self.final_year
        d['final_comment'] = self.final_comment
        return d

    @property
    def display_title(self) -> str:
        return self.existing_title or self.spotify_title or self.filename

    @property
    def display_artist(self) -> str:
        return self.existing_artist or self.spotify_artist or "Unknown"

    @property
    def final_genre(self) -> Optional[str]:
        return self.override_genre or self.proposed_genre or self.existing_genre

    @property
    def final_subgenre(self) -> Optional[str]:
        return self.override_subgenre or self.proposed_subgenre

    @property
    def final_bpm(self) -> Optional[str]:
        if self.override_bpm:
            return self.override_bpm
        if self.analyzed_bpm:
            return str(round(self.analyzed_bpm))
        return self.existing_bpm

    @property
    def final_key(self) -> Optional[str]:
        return self.override_key or self.analyzed_key or self.existing_key

    @property
    def final_year(self) -> Optional[str]:
        return self.override_year or self.existing_year or self.spotify_year

    @property
    def final_comment(self) -> Optional[str]:
        return self.override_comment or self.proposed_subgenre or self.existing_comment
