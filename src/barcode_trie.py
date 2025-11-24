from typing import Dict, List


class TrieNode:
    __slots__ = ("children", "terminal")

    def __init__(self) -> None:
        self.children: Dict[str, "TrieNode"] = {}
        self.terminal: bool = False


class Trie:
    """Minimal trie for barcode Hamming search.

    Interface:
      - insert(seq: str)
      - find_all_hamming_conflicts(seq: str, distance: int) -> List[str]
    """

    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, seq: str) -> None:
        node = self.root
        for ch in seq:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.terminal = True

    def find_all_hamming_conflicts(self, seq: str, distance: int) -> List[str]:
        """Return all barcodes in the trie within given Hamming distance.

        This is a naive depth first search over the trie that tracks remaining
        mismatches. Fine for moderate library sizes.
        """
        results: List[str] = []

        def dfs(node: TrieNode, pos: int, mismatches_left: int, prefix: List[str]) -> None:
            if pos == len(seq):
                if node.terminal and mismatches_left >= 0:
                    results.append("".join(prefix))
                return

            target_ch = seq[pos]
            for ch, child in node.children.items():
                new_mismatches = mismatches_left - (0 if ch == target_ch else 1)
                if new_mismatches < 0:
                    continue
                prefix.append(ch)
                dfs(child, pos + 1, new_mismatches, prefix)
                prefix.pop()

        dfs(self.root, 0, distance, [])
        return results
