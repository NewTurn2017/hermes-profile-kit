"""Manifest v2 schema, loader, and validator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ManifestValidationError(ValueError):
    """Raised when manifest.yaml fails schema or semantic validation."""


class TokenSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    provider: str
    wizard: str | None = None
    default: str | None = None          # ← new


class TokensSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: list[TokenSpec] = Field(default_factory=list)
    optional: list[TokenSpec] = Field(default_factory=list)


class RecommendedPlugin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    default: bool = True


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    template: str
    role: str
    model_tier: Literal["haiku", "sonnet", "opus", "openai-codex"]  # ← added openai-codex
    channels: list[str]
    tokens: TokensSection = Field(default_factory=TokensSection)
    recommended_plugins: list[RecommendedPlugin] = Field(default_factory=list)


class Plugin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    upstream_command: str | None = None  # ← was str (non-nullable)
    verified_in_upstream: bool = False
    docs: str | None = None
    install_path: str | None = None      # ← new (kit-local helper path)
    launchd_template: str | None = None  # ← new


class Upstream(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str
    pinned_commit: str
    pinned_version: str
    verified_at: str


class KitMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    license: str


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2, 3]        # ← was Literal[2]
    kit: KitMeta
    upstream: Upstream
    min_hermes_version: str
    profiles: list[Profile]
    plugins: dict[str, Plugin]
    preserve_existing: list[str]
    overwrite_from_template: list[str]

    @model_validator(mode="after")
    def _cross_field(self) -> Manifest:
        from packaging.version import Version

        if Version(self.min_hermes_version) > Version(self.upstream.pinned_version):
            raise ValueError("min_hermes_version must be <= upstream.pinned_version")
        known = set(self.plugins.keys())
        for p in self.profiles:
            for rp in p.recommended_plugins:
                if rp.id not in known:
                    raise ValueError(f"profile {p.name!r} references unknown plugin {rp.id!r}")
        return self


def load_manifest(path: Path) -> Manifest:
    try:
        data = yaml.safe_load(path.read_text())
        return Manifest.model_validate(data)
    except (ValidationError, ValueError, yaml.YAMLError) as e:
        raise ManifestValidationError(str(e)) from e


def migrate_v1_yaml(
    v1_text: str,
    *,
    pinned_commit: str,
    pinned_version: str,
    verified_at: str,
) -> dict[str, Any]:
    """Return a v2 manifest dict built from a v1 manifest YAML string."""
    src = yaml.safe_load(v1_text)
    profiles_out = []
    for p in src.get("profiles", []):
        required = [
            {"key": k, "provider": k.split("_")[0].lower()} for k in p.get("requires_secrets", [])
        ]
        optional = [
            {"key": k, "provider": k.split("_")[0].lower()} for k in p.get("optional_secrets", [])
        ]
        profiles_out.append(
            {
                "name": p["name"],
                "template": p["template"],
                "role": p["role"],
                "model_tier": p["model_tier"],
                "channels": p.get("channels", ["cli"]),
                "tokens": {"required": required, "optional": optional},
                "recommended_plugins": [],
            }
        )
    return {
        "schema_version": 2,
        "kit": {
            "name": src["kit"]["name"],
            "version": "2.0.0",
            "license": src.get("kit", {}).get("license", "MIT"),
        },
        "upstream": {
            "repo": "https://github.com/NousResearch/hermes-agent",
            "pinned_commit": pinned_commit,
            "pinned_version": pinned_version,
            "verified_at": verified_at,
        },
        "min_hermes_version": src.get("min_hermes_version", "0.12.0"),
        "profiles": profiles_out,
        "plugins": {},
        "preserve_existing": [".env"],
        "overwrite_from_template": ["SOUL.md", "config.yaml"],
    }
