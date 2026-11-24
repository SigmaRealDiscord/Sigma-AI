"""Small, dependency-free UTF-8 byte tokenizer used by Sigma-0.1B v0.

Every Unicode language can be represented. This is a deliberately simple
first tokenizer; a learned multilingual BPE tokenizer can replace it later.
"""

BOS = 256
EOS = 257
PAD = 258
VOCAB_SIZE = 259


class SigmaTokenizer:
    vocab_size = VOCAB_SIZE

    def encode(self, text: str, add_special_tokens: bool = True) -> list[int]:
        ids = list(text.encode("utf-8", errors="replace"))
        return ([BOS] + ids + [EOS]) if add_special_tokens else ids

    def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
        data = bytearray()
        for token in ids:
            if token < 256:
                data.append(token)
            elif not skip_special_tokens and token in (BOS, EOS, PAD):
                data.extend({BOS: b"<BOS>", EOS: b"<EOS>", PAD: b"<PAD>"}[token])
        return data.decode("utf-8", errors="replace")
