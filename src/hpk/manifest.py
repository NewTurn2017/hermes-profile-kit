"""Manifest v2 schema, loader, and validator."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ManifestValidationError(ValueError):
    """Raised when manifest.yaml fails schema or semantic validation."""


class TokenSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    provider: str
    wizard: str | None = None


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
    model_tier: Literal["haiku", "sonnet", "opus"]
    channels: list[str]
    tokens: TokensSection = Field(default_factory=TokensSection)
    recommended_plugins: list[RecommendedPlugin] = Field(default_factory=list)


class Plugin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    upstream_command: str
    verified_in_upstream: bool = False
    docs: str | None = None


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
    schema_version: Literal[2]
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
