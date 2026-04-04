from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Track:
    # Identity
    id: str
    file_path: str

    # Existing ID3 tags
    existing_title: Optional[str] = None
    existing_artist: Optional[str] = None
    existing_album: Optional[str] = None
    existing_genre: Optional[str] = None
    existing_year: Optional[int] = None

    # Audio analysis
    bpm: Optional[float] = None
    key: Optional[str] = None  # Camelot
    energy: Optional[int] = None  # 1-10

    # AI classification
    classified_genre: Optional[str] = None
    classified_subgenre: Optional[str] = None
    classification_confidence: Optional[float] = None

    # Spotify enrichment
    spotify_artist_genres: list = field(default_factory=list)
    spotify_year: Optional[int] = None

    # Review state
    approved: bool = False
    skipped: bool = False

    # User overrides
    override_genre: Optional[str] = None
    override_subgenre: Optional[str] = None
    override_bpm: Optional[float] = None
    override_key: Optional[str] = None
    override_year: Optional[int] = None

    # Write state
    tags_written: bool = False

    @property
    def final_genre(self) -> Optional[str]:
        return self.override_genre or self.classified_genre

    @property
    def final_subgenre(self) -> Optional[str]:
        return self.override_subgenre or self.classified_subgenre

    @property
    def final_bpm(self) -> Optional[float]:
        return self.override_bpm or self.bpm

    @property
    def final_key(self) -> Optional[str]:
        return self.override_key or self.key

    @property
    def final_year(self) -> Optional[int]:
        return self.override_year or self.spotify_year or self.existing_year

    def to_dict(self) -> dict:
        return asdict(self)
