from dataclasses import dataclass


@dataclass
class VideoInfo:
    title: str
    author: str
    duration_seconds: int
    views: int
    url: str

    @property
    def duration(self) -> str:
        minutes, seconds = divmod(self.duration_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            return f"{hours}:{minutes:02}:{seconds:02}"

        return f"{minutes}:{seconds:02}"

    @property
    def readable_views(self) -> str:
        if self.views >= 1_000_000_000:
            return f"{self.views / 1_000_000_000:.1f}B"

        if self.views >= 1_000_000:
            return f"{self.views / 1_000_000:.1f}M"

        if self.views >= 1_000:
            return f"{self.views / 1_000:.1f}K"

        return str(self.views)