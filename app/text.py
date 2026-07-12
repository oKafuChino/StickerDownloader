from collections.abc import Iterable


def chunk_lines(lines: Iterable[str], *, limit: int = 4000) -> list[str]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    chunks: list[str] = []
    current: list[str] = []
    for line in lines:
        parts = [line[index : index + limit] for index in range(0, len(line), limit)]
        if not parts:
            parts = [""]
        for part in parts:
            candidate = "\n".join([*current, part])
            if current and len(candidate) > limit:
                chunks.append("\n".join(current))
                current = [part]
            else:
                current.append(part)
    if current:
        chunks.append("\n".join(current))
    return chunks

