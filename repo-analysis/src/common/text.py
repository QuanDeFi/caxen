from __future__ import annotations

from typing import List


def tokenize(query: str) -> List[str]:
    tokens = []
    for raw_token in query.replace("::", " ").replace("/", " ").replace("-", " ").replace(".", " ").split():
        normalized = "".join(char for char in raw_token.lower() if char.isalnum() or char == "_")
        if normalized:
            tokens.append(normalized)
    return tokens
