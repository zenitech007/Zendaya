from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pydantic import BaseModel

class HealthCache(BaseModel):
    """Thread-safe health check cache"""
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.min
    ttl: timedelta = timedelta(seconds=10)

    def is_valid(self) -> bool:
        return (
            self.data is not None and 
            (datetime.utcnow() - self.timestamp) < self.ttl
        )