"""Chart metadata models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Maintainer:
    name: str = ""
    email: str = ""
    url: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> Maintainer:
        return cls(
            name=d.get("name", ""),
            email=d.get("email", ""),
            url=d.get("url", ""),
        )


@dataclass
class ChartDependency:
    name: str = ""
    version: str = ""
    repository: str = ""
    condition: str = ""
    alias: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> ChartDependency:
        return cls(
            name=d.get("name", ""),
            version=d.get("version", ""),
            repository=d.get("repository", ""),
            condition=d.get("condition", ""),
            alias=d.get("alias", ""),
        )


@dataclass
class ChartMetadata:
    name: str = ""
    version: str = ""
    app_version: str = ""
    description: str = ""
    api_version: str = ""
    chart_type: str = ""
    home: str = ""
    icon: str = ""
    keywords: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    maintainers: list[Maintainer] = field(default_factory=list)
    dependencies: list[ChartDependency] = field(default_factory=list)
    annotations: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> ChartMetadata:
        if not d:
            return cls()
        return cls(
            name=d.get("name", ""),
            version=d.get("version", ""),
            app_version=d.get("appVersion", ""),
            description=d.get("description", ""),
            api_version=d.get("apiVersion", ""),
            chart_type=d.get("type", ""),
            home=d.get("home", ""),
            icon=d.get("icon", ""),
            keywords=d.get("keywords", []),
            sources=d.get("sources", []),
            maintainers=[Maintainer.from_dict(m) for m in d.get("maintainers", [])],
            dependencies=[ChartDependency.from_dict(dep) for dep in d.get("dependencies", [])],
            annotations=d.get("annotations", {}),
        )
