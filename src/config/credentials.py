"""
Central credentials loader for MillionTwigs.

Reads all API keys and passwords from environment variables (or a .env file).
Every data module imports from here — credentials are never hardcoded.

Quick setup:
    cp .env.example .env          # copy the template
    nano .env                     # fill in your real values
    python -m src.config.credentials  # verify all credentials

See docs/credentials_guide.md for step-by-step registration instructions.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Load .env file automatically if python-dotenv is installed
try:
    from dotenv import load_dotenv
    _ENV_FILE = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(_ENV_FILE)
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False


# ── Credential dataclasses ─────────────────────────────────────────────────────

@dataclass
class GEECredentials:
    """Google Earth Engine credentials.

    How to get:
      1. Register: https://code.earthengine.google.com/register
      2. Run once: earthengine authenticate
      3. Set GEE_PROJECT to your Google Cloud project ID
    """
    project: Optional[str] = field(
        default_factory=lambda: os.environ.get("GEE_PROJECT")
    )

    def validate(self) -> None:
        if not self.project:
            raise CredentialError(
                "GEE_PROJECT",
                "Google Earth Engine project ID",
                "https://code.earthengine.google.com/register",
                extra=(
                    "After registering, run in terminal:\n"
                    "  earthengine authenticate\n"
                    "Then set GEE_PROJECT=your-cloud-project-id in .env"
                ),
            )


@dataclass
class CopernicusCredentials:
    """Copernicus Dataspace credentials for Sentinel-2 downloads.

    How to get:
      Register free at: https://dataspace.copernicus.eu
    """
    user: Optional[str] = field(
        default_factory=lambda: os.environ.get("COPERNICUS_USER")
    )
    password: Optional[str] = field(
        default_factory=lambda: os.environ.get("COPERNICUS_PASSWORD")
    )

    def validate(self) -> None:
        if not self.user:
            raise CredentialError(
                "COPERNICUS_USER",
                "Copernicus Dataspace email",
                "https://dataspace.copernicus.eu",
            )
        if not self.password:
            raise CredentialError(
                "COPERNICUS_PASSWORD",
                "Copernicus Dataspace password",
                "https://dataspace.copernicus.eu",
            )


@dataclass
class USGSCredentials:
    """USGS EarthExplorer credentials for Landsat downloads.

    How to get:
      Register free at: https://ers.cr.usgs.gov/register
    """
    username: Optional[str] = field(
        default_factory=lambda: os.environ.get("LANDSATXPLORE_USERNAME")
    )
    password: Optional[str] = field(
        default_factory=lambda: os.environ.get("LANDSATXPLORE_PASSWORD")
    )

    def validate(self) -> None:
        if not self.username:
            raise CredentialError(
                "LANDSATXPLORE_USERNAME",
                "USGS EarthExplorer username",
                "https://ers.cr.usgs.gov/register",
            )
        if not self.password:
            raise CredentialError(
                "LANDSATXPLORE_PASSWORD",
                "USGS EarthExplorer password",
                "https://ers.cr.usgs.gov/register",
            )


@dataclass
class NASACredentials:
    """NASA Earthdata credentials for GEDI and MODIS.

    How to get:
      Register free at: https://urs.earthdata.nasa.gov/users/new
    """
    username: Optional[str] = field(
        default_factory=lambda: os.environ.get("EARTHDATA_USERNAME")
    )
    password: Optional[str] = field(
        default_factory=lambda: os.environ.get("EARTHDATA_PASSWORD")
    )

    def validate(self) -> None:
        if not self.username:
            raise CredentialError(
                "EARTHDATA_USERNAME",
                "NASA Earthdata username",
                "https://urs.earthdata.nasa.gov/users/new",
            )
        if not self.password:
            raise CredentialError(
                "EARTHDATA_PASSWORD",
                "NASA Earthdata password",
                "https://urs.earthdata.nasa.gov/users/new",
            )


@dataclass
class BhuvanCredentials:
    """ISRO Bhuvan / NRSC credentials.

    How to get:
      Register at: https://bhuvan-app1.nrsc.gov.in/mda/
      Approval takes 1–3 working days.
      See docs/credentials_guide.md §1A for full steps.
    """
    user: Optional[str] = field(
        default_factory=lambda: os.environ.get("BHUVAN_USER")
    )
    password: Optional[str] = field(
        default_factory=lambda: os.environ.get("BHUVAN_PASSWORD")
    )

    def validate(self) -> None:
        if not self.user:
            raise CredentialError(
                "BHUVAN_USER",
                "ISRO Bhuvan registered email",
                "https://bhuvan-app1.nrsc.gov.in/mda/",
                extra=(
                    "Registration takes 1–3 working days.\n"
                    "See docs/credentials_guide.md section 1A for detailed steps.\n"
                    "Use institutional email (IIT/ISRO/Univ) for faster approval."
                ),
            )
        if not self.password:
            raise CredentialError(
                "BHUVAN_PASSWORD",
                "ISRO Bhuvan password",
                "https://bhuvan-app1.nrsc.gov.in/mda/",
            )


# ── Error class ────────────────────────────────────────────────────────────────

class CredentialError(EnvironmentError):
    """Raised when a required credential is missing or invalid."""

    def __init__(
        self,
        env_var: str,
        description: str,
        registration_url: str,
        extra: str = "",
    ) -> None:
        self.env_var = env_var
        self.description = description
        self.registration_url = registration_url
        lines = [
            f"\n{'='*60}",
            f"  Missing credential: {env_var}",
            f"  Required for: {description}",
            f"",
            f"  How to fix:",
            f"  1. Register (free) at: {registration_url}",
            f"  2. Add to your .env file:",
            f"       {env_var}=<your_value>",
            f"",
            f"  Full setup guide: docs/credentials_guide.md",
        ]
        if extra:
            lines += ["", f"  Note: {extra}"]
        lines.append("=" * 60)
        super().__init__("\n".join(lines))


# ── Convenience accessors ──────────────────────────────────────────────────────

def get_gee() -> GEECredentials:
    """Return validated GEE credentials."""
    creds = GEECredentials()
    creds.validate()
    return creds


def get_copernicus() -> CopernicusCredentials:
    """Return validated Copernicus credentials."""
    creds = CopernicusCredentials()
    creds.validate()
    return creds


def get_usgs() -> USGSCredentials:
    """Return validated USGS credentials."""
    creds = USGSCredentials()
    creds.validate()
    return creds


def get_nasa() -> NASACredentials:
    """Return validated NASA Earthdata credentials."""
    creds = NASACredentials()
    creds.validate()
    return creds


def get_bhuvan() -> BhuvanCredentials:
    """Return validated ISRO Bhuvan credentials."""
    creds = BhuvanCredentials()
    creds.validate()
    return creds


# ── Status check (run directly: python -m src.config.credentials) ─────────────

def check_all() -> dict:
    """Check which credentials are configured. Returns a status dict."""
    checks = {
        "GEE_PROJECT":             os.environ.get("GEE_PROJECT"),
        "COPERNICUS_USER":         os.environ.get("COPERNICUS_USER"),
        "COPERNICUS_PASSWORD":     os.environ.get("COPERNICUS_PASSWORD"),
        "LANDSATXPLORE_USERNAME":  os.environ.get("LANDSATXPLORE_USERNAME"),
        "LANDSATXPLORE_PASSWORD":  os.environ.get("LANDSATXPLORE_PASSWORD"),
        "EARTHDATA_USERNAME":      os.environ.get("EARTHDATA_USERNAME"),
        "EARTHDATA_PASSWORD":      os.environ.get("EARTHDATA_PASSWORD"),
        "BHUVAN_USER":             os.environ.get("BHUVAN_USER"),
        "BHUVAN_PASSWORD":         os.environ.get("BHUVAN_PASSWORD"),
    }
    return {k: ("✅ set" if v else "❌ missing") for k, v in checks.items()}


if __name__ == "__main__":
    print("\nMillionTwigs — Credential Status Check")
    print("=" * 45)
    if not _DOTENV_AVAILABLE:
        print("⚠  python-dotenv not installed — install it to load .env automatically:")
        print("   pip install python-dotenv\n")

    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        print(f"📄 .env file found: {env_file}\n")
    else:
        print(f"⚠  No .env file found. Copy the template:\n   cp .env.example .env\n")

    status = check_all()
    max_len = max(len(k) for k in status)
    for key, state in status.items():
        print(f"  {key:<{max_len}}  {state}")

    missing = [k for k, v in status.items() if "missing" in v]
    print()
    if missing:
        print(f"⚠  {len(missing)} credential(s) missing.")
        print("   See docs/credentials_guide.md for registration instructions.")
    else:
        print("✅ All credentials configured.")
    print()
