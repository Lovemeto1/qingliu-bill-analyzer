"""Export installed Python package license files for desktop distributions."""

from __future__ import annotations

import argparse
from importlib import metadata
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


LICENSE_NAMES = ("license", "licence", "copying", "notice", "copyright")
ROOT_PACKAGES = (
    "streamlit",
    "pandas",
    "openpyxl",
    "plotly",
    "pywebview",
    "pyinstaller",
)


def is_license_file(path: Path) -> bool:
    name = path.name.lower()
    return any(token in name for token in LICENSE_NAMES)


def desktop_distributions() -> list[metadata.Distribution]:
    installed = {
        canonicalize_name(distribution.metadata.get("Name") or ""): distribution
        for distribution in metadata.distributions()
        if distribution.metadata.get("Name")
    }
    environment = default_environment()
    environment["extra"] = ""
    pending = [canonicalize_name(name) for name in ROOT_PACKAGES]
    selected: dict[str, metadata.Distribution] = {}

    while pending:
        name = pending.pop()
        if name in selected:
            continue
        distribution = installed.get(name)
        if distribution is None:
            raise RuntimeError(f"Required desktop distribution is not installed: {name}")
        selected[name] = distribution

        for requirement_text in distribution.requires or []:
            try:
                requirement = Requirement(requirement_text)
            except InvalidRequirement:
                continue
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency in installed and dependency not in selected:
                pending.append(dependency)

    return sorted(
        selected.values(),
        key=lambda distribution: (distribution.metadata.get("Name") or "").lower(),
    )


def export_licenses(output_path: Path) -> int:
    sections: list[str] = []
    seen: set[tuple[str, str]] = set()

    for distribution in desktop_distributions():
        name = distribution.metadata.get("Name") or "Unknown package"
        version = distribution.version
        key = (name.lower(), version)
        if key in seen:
            continue
        seen.add(key)

        license_texts: list[tuple[str, str]] = []
        for relative_path in distribution.files or []:
            path = Path(str(relative_path))
            if not is_license_file(path):
                continue
            located = distribution.locate_file(relative_path)
            try:
                text = Path(located).read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            if text:
                license_texts.append((str(path), text))

        if not license_texts:
            declared = (
                distribution.metadata.get("License-Expression")
                or distribution.metadata.get("License")
                or "No bundled license file was found; consult the package metadata."
            )
            license_texts.append(("Package metadata", declared.strip()))

        sections.append("=" * 78)
        sections.append(f"{name} {version}")
        sections.append("=" * 78)
        for filename, text in license_texts:
            sections.extend((f"\n--- {filename} ---\n", text, ""))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sections), encoding="utf-8")
    return len(seen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count = export_licenses(args.output.resolve())
    print(f"Exported license information for {count} installed distributions.")


if __name__ == "__main__":
    main()
