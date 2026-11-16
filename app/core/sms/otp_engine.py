"""In-memory cryptographic OTP generator and verification manager."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.core.utils.phone import normalize_ethiopian_phone


@dataclass
class _OtpRecord:
    phone: str
    code_hash: str
    expires_at: float
    attempts: int = 0
    max_attempts: int = 5
    is_verified: bool = False


class OtpEngine:
    """Internal engine managing OTP generation, hashing, expiration, and verification."""

    def __init__(self) -> None:
        self._records: dict[str, _OtpRecord] = {}  # key: verification_id

    def generate_otp(
        self,
        phone: str,
        length: int = 6,
        ttl_seconds: int = 300,
    ) -> tuple[str, str]:
        """Generate a secure numeric OTP and return (plain_code, verification_id)."""
        normalized = normalize_ethiopian_phone(phone)
        # Generate numeric code with leading zeros preserved
        upper_bound = 10**length
        code_int = secrets.randbelow(upper_bound)
        plain_code = f"{code_int:0{length}d}"

        verification_id = str(uuid4())
        code_hash = hashlib.sha256(plain_code.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc).timestamp() + ttl_seconds

        self._records[verification_id] = _OtpRecord(
            phone=normalized,
            code_hash=code_hash,
            expires_at=expires_at,
        )

        self._cleanup_expired()
        return plain_code, verification_id

    def verify_otp(
        self,
        phone: str,
        code: str,
        verification_id: str | None = None,
    ) -> bool:
        """Verify an OTP code for a given phone or verification_id."""
        normalized = normalize_ethiopian_phone(phone)
        now = datetime.now(timezone.utc).timestamp()
        target_id = verification_id

        # If verification_id is not provided, find most recent active record for phone
        if not target_id:
            matching_ids = [
                vid for vid, r in self._records.items()
                if r.phone == normalized and r.expires_at > now and not r.is_verified
            ]
            if not matching_ids:
                return False
            # Sort by expiration (newest first)
            target_id = max(matching_ids, key=lambda vid: self._records[vid].expires_at)

        record = self._records.get(target_id)
        if not record:
            return False

        if record.phone != normalized or record.expires_at <= now or record.is_verified:
            return False

        record.attempts += 1
        if record.attempts > record.max_attempts:
            # Exceeded maximum attempts - invalidate
            self._records.pop(target_id, None)
            return False

        input_hash = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()
        if secrets.compare_digest(input_hash, record.code_hash):
            record.is_verified = True
            return True

        return False

    def is_verified(self, verification_id: str) -> bool:
        """Check if a verification record was successfully verified."""
        record = self._records.get(verification_id)
        if not record:
            return False
        now = datetime.now(timezone.utc).timestamp()
        return record.is_verified and record.expires_at > now

    def _cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        expired_ids = [vid for vid, r in self._records.items() if r.expires_at <= now]
        for vid in expired_ids:
            self._records.pop(vid, None)

    def clear(self) -> None:
        """Clear all records (used in tests)."""
        self._records.clear()


_global_otp_engine = OtpEngine()


def get_otp_engine() -> OtpEngine:
    return _global_otp_engine

