import re
from typing import List, Tuple


def extract_chunks(markdown_text: str) -> List[Tuple[str, List[str]]]:
    chunks: List[Tuple[str, List[str]]] = []
    header_stack: List[str] = []
    current_chunk: List[str] = []

    for line in markdown_text.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            # Flush current pending chunk
            if current_chunk:
                content = "\n".join(current_chunk).strip()
                if content:
                    chunks.append((content, list(header_stack)))
                current_chunk = []

            level = len(heading_match.group(1))
            heading_title = heading_match.group(2).strip()

            # Adjust stack depth
            header_stack = header_stack[: level - 1]
            header_stack.append(heading_title)
        else:
            current_chunk.append(line)

    # Flush final block
    if current_chunk:
        content = "\n".join(current_chunk).strip()
        if content:
            chunks.append((content, list(header_stack)))

    return chunks