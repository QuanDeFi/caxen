from pathlib import Path

from common.inventory import InventoryProfile, build_inventory


PROFILE = InventoryProfile(
    repo="yellowstone-vixen",
    expected_ref=None,
    analysis_surfaces=(
        "crates",
        "examples",
        "tests",
        "docs",
    ),
    build_commands=(
        "cargo build --workspace",
    ),
    test_commands=(
        "cargo test --workspace",
        "cd tests/proc-macro-events && cargo test",
    ),
    notes=(
        "Treat Yellowstone Vixen as a Rust workspace with important crate, test, example, and documentation surfaces.",
        "Examples and tests are important because the repo documents extension patterns through runnable pipelines and fixtures.",
    ),
)


def inventory(repo_root: Path) -> dict:
    return build_inventory(repo_root, PROFILE)
