from pathlib import Path

from common.inventory import InventoryProfile, build_inventory


PROFILE = InventoryProfile(
    repo="carbon",
    expected_ref="origin/v1.0-rc",
    analysis_surfaces=(
        "crates",
        "datasources",
        "decoders",
        "examples",
        "metrics",
        "packages",
    ),
    build_commands=(
        "cargo build --workspace",
        "pnpm install --frozen-lockfile",
        "pnpm build",
    ),
    test_commands=(
        "cargo test --workspace",
        "pnpm test",
    ),
    notes=(
        "Treat Carbon as a Rust-first monorepo with meaningful boundaries across crates, packages, metrics, and top-level workspace surfaces.",
        "TypeScript tooling is concentrated under packages/* and driven by pnpm/turbo.",
    ),
)


def inventory(repo_root: Path) -> dict:
    return build_inventory(repo_root, PROFILE)
