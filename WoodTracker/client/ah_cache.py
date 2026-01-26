import json
from pathlib import Path
from datetime import datetime, timezone
print(">>> AH_CACHE FILE EXECUTED <<<")
class AHCache:
    def __init__(self, path: Path, ttl_seconds=1800):
        self.path = path
        self.ttl = ttl_seconds
        self.data = None

    def load(self):
        if not self.path.exists():
            self.data = None
            return None

        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        return self.data

    def is_valid(self) -> bool:
        if not self.data:
            return False

        meta = self.data.get("meta", {})
        last_refresh = meta.get("last_refresh")
        if not last_refresh:
            return False

        last = datetime.fromisoformat(
            last_refresh.replace("Z", "+00:00")
        )
        age = (datetime.now(timezone.utc) - last).total_seconds()
        return age < self.ttl

    def save(self, components: dict, decors: dict):
        payload = {
            "meta": {
                "region": "EU",
                "realm": "Dalaran",
                "last_refresh": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                "ttl_seconds": self.ttl,
            },
            "components": components,
            "decors": decors,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.data = payload

