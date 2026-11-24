from dataclasses import asdict, dataclass


@dataclass
class SigmaConfig:
    # 12 x 832-wide decoder blocks with a 4x feed-forward layer.
    # This is approximately 100M parameters with the 259-token byte vocabulary.
    vocab_size: int = 259
    d_model: int = 832
    n_layers: int = 12
    n_heads: int = 13
    ffn_dim: int = 3328
    max_seq_len: int = 1024
    dropout: float = 0.0

    def to_dict(self):
        return asdict(self)
