import torch
import torch.nn as nn
import torch.nn.functional as F


class CrossAttention(nn.Module):
    """Cross-attention block for aligning features from two branches.

    `query` is a feature map that gets *enriched* with information from
    `context` (a feature map of the other branch): every spatial position
    of the query attends over all positions of the context.

        query   (B, C, H,  W )
        context (B, C, H', W')   ->   output (B, C, H, W)

    The block is a pre-norm transformer decoder layer without the
    self-attention part: cross-attention + residual, then a small FFN +
    residual. Learnable 2D position embeddings (`pos_size`) are added to
    the attention inputs only, so tokens know *where* they are without
    polluting the residual stream. The output projections are zero-
    initialised, so at the start of training the block is the identity and
    the network behaves like plain multi-scale fusion; the attention is
    learned gradually.
    """

    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        pos_size: int = None,
        dropout: float = 0.0,
        mlp_ratio: float = 2.0
    ):
        super().__init__()

        assert dim % num_heads == 0, "dim must be divisible by num_heads"

        self.dim = dim
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.attn_dropout = dropout

        self.norm_q = nn.LayerNorm(dim)
        self.norm_kv = nn.LayerNorm(dim)

        self.to_q = nn.Linear(dim, dim)
        self.to_kv = nn.Linear(dim, dim * 2)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(dropout)

        self.norm_ffn = nn.LayerNorm(dim)
        hidden = int(dim * mlp_ratio)
        self.ffn = nn.Sequential(
            nn.Linear(dim, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, dim),
            nn.Dropout(dropout)
        )

        if pos_size:
            self.pos = nn.Parameter(torch.zeros(1, dim, pos_size, pos_size))
            nn.init.trunc_normal_(self.pos, std=0.02)
        else:
            self.pos = None

        # Identity at initialisation (see class docstring)
        nn.init.zeros_(self.proj.weight)
        nn.init.zeros_(self.proj.bias)
        nn.init.zeros_(self.ffn[3].weight)
        nn.init.zeros_(self.ffn[3].bias)

    @staticmethod
    def _to_tokens(x: torch.Tensor) -> torch.Tensor:
        # (B, C, H, W) -> (B, H*W, C)
        return x.flatten(2).transpose(1, 2)

    def _with_pos(self, x: torch.Tensor) -> torch.Tensor:

        if self.pos is None:
            return x

        height, width = x.shape[-2:]

        pos = self.pos

        if pos.shape[-2:] != (height, width):
            pos = F.interpolate(
                pos,
                size=(height, width),
                mode="bilinear",
                align_corners=False
            )

        return x + pos

    def forward(self, query: torch.Tensor, context: torch.Tensor):

        batch, channels, height, width = query.shape

        q_residual = self._to_tokens(query)

        q_tokens = self.norm_q(self._to_tokens(self._with_pos(query)))
        kv_tokens = self.norm_kv(self._to_tokens(self._with_pos(context)))

        q = self.to_q(q_tokens)
        k, v = self.to_kv(kv_tokens).chunk(2, dim=-1)

        def split_heads(t):
            # (B, N, C) -> (B, heads, N, head_dim)
            return t.view(batch, -1, self.num_heads, self.head_dim).transpose(1, 2)

        attended = F.scaled_dot_product_attention(
            split_heads(q),
            split_heads(k),
            split_heads(v),
            dropout_p=self.attn_dropout if self.training else 0.0
        )

        attended = attended.transpose(1, 2).reshape(batch, -1, channels)

        x = q_residual + self.proj_drop(self.proj(attended))

        x = x + self.ffn(self.norm_ffn(x))

        # (B, H*W, C) -> (B, C, H, W)
        return x.transpose(1, 2).reshape(batch, channels, height, width)
