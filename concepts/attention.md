---
title: Attention
type: concept
created: 2026-07-01
topic: attention
related_concepts: []
related_papers: [attention-is-all-you-need]
sources:
  - ../sources/zotero_attention_is_all_you_need.md
  - ../notes/obsidian_attention_is_all_you_need.md
  - ../notes/zotero_attention_is_all_you_need/annotations.md
---

# Attention

## My Notes & Annotations

Relies on [[multi-head-attention]] to jointly attend to information from
different representation subspaces, paired with [[positional-encoding]] since
the model has no inherent notion of token order. The core mechanism is
[[scaled-dot-product-attention]], scaled by $\sqrt{d_k}$ to stabilize gradients.

> [!note] Worth revisiting the ablations on number of attention heads — seems like there's a sweet spot before returns diminish.

> [!question] How does this compare to [[sparse-attention]] variants for long-context tasks?

> [!note]
> "This is a very good paper - I think this will be very influential to all of ML" — typed note on page 1, alongside the abstract that first frames attention as sufficient on its own.

## Summary

**Attention is a mechanism that maps a query and a set of key–value pairs to an
output computed as a weighted sum of the values, where each value's weight is a
compatibility function of the query with the corresponding key.**

Attention mechanisms let a model draw dependencies between positions in a
sequence without regard to their distance, and had become an integral part of
compelling sequence modeling and transduction models ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
Historically they were used *in conjunction with* recurrent networks; the
Transformer's central claim is that attention is sufficient on its own —
**the Transformer is the first transduction model relying entirely on
self-attention to compute representations of its input and output without using
sequence-aligned RNNs or convolution** ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

Removing recurrence in favor of attention makes computation far more
parallelizable, since attention relates any two positions in a constant number
of operations rather than through a sequential chain of hidden states ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

## Scaled dot-product attention

The particular attention function used in the Transformer is **scaled
dot-product attention**. With queries and keys of dimension $d_k$ and values of
dimension $d_v$, packed row-wise into matrices $Q$, $K$, $V$:

$$\text{Attention}(Q, K, V) = \text{softmax}\!\left(\frac{QK^{\top}}{\sqrt{d_k}}\right)V$$

The dot products of the query with all keys are divided by $\sqrt{d_k}$ and
passed through a softmax to obtain the weights on the values ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
The two most common compatibility functions are **additive attention** (a
feed-forward net with one hidden layer) and **dot-product (multiplicative)
attention**; the latter is chosen because it can be implemented with highly
optimized matrix multiplication, making it much faster and more space-efficient ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

The scaling factor addresses a specific failure mode. If the components of $q$
and $k$ are independent random variables with mean $0$ and variance $1$, their
dot product $q \cdot k = \sum_{i=1}^{d_k} q_i k_i$ has mean $0$ and variance
$d_k$. For large $d_k$ these products grow in magnitude, pushing the softmax
into regions of vanishingly small gradient; dividing by $\sqrt{d_k}$ counteracts
this ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
Without scaling, additive attention outperforms dot-product attention for large
$d_k$ ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

## Multi-head attention

Rather than a single attention function over $d_{\text{model}}$-dimensional
keys, values and queries, **multi-head attention** projects them $h$ times with
different learned linear projections to $d_k$, $d_k$ and $d_v$ dimensions,
applies attention in parallel, then concatenates and projects the results:

$$\text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)\,W^{O}$$
$$\text{head}_i = \text{Attention}(QW_i^{Q},\, KW_i^{K},\, VW_i^{V})$$

with $W_i^{Q} \in \mathbb{R}^{d_{\text{model}} \times d_k}$,
$W_i^{K} \in \mathbb{R}^{d_{\text{model}} \times d_k}$,
$W_i^{V} \in \mathbb{R}^{d_{\text{model}} \times d_v}$ and
$W^{O} \in \mathbb{R}^{hd_v \times d_{\text{model}}}$ ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
Multi-head attention lets the model **jointly attend to information from
different representation subspaces at different positions**, which a single
attention head inhibits through averaging ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
The Transformer uses $h = 8$ heads with $d_k = d_v = d_{\text{model}}/h = 64$,
so that the reduced per-head dimension keeps the total cost close to that of
single-head attention at full dimensionality ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

> [!note]
> Ablation section (§6.2 / Table 3) marked in red ink — single-head attention is 0.9 BLEU worse than the best setting, while too many heads also degrades quality, which is the "sweet spot in $h$" flagged in the personal note above.

## Self-attention and why it is used

**Self-attention** (also called intra-attention) is an attention mechanism
relating different positions of a single sequence in order to compute a
representation of that sequence ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
The motivation for preferring it over recurrent and convolutional layers rests
on three desiderata — per-layer computational complexity, the amount of
computation that can be parallelized, and the maximum path length between
long-range dependencies (shorter paths make long-range dependencies easier to
learn):

| Layer type | Complexity per layer | Sequential ops | Max path length |
|---|---|---|---|
| Self-Attention | $O(n^2 \cdot d)$ | $O(1)$ | $O(1)$ |
| Recurrent | $O(n \cdot d^2)$ | $O(n)$ | $O(n)$ |
| Convolutional | $O(k \cdot n \cdot d^2)$ | $O(1)$ | $O(\log_k(n))$ |
| Self-Attention (restricted) | $O(r \cdot n \cdot d)$ | $O(1)$ | $O(n/r)$ |

A self-attention layer connects all positions with a constant number of
sequentially executed operations, whereas a recurrent layer requires $O(n)$;
self-attention is also faster than a recurrent layer when the sequence length
$n$ is smaller than the representation dimensionality $d$ — the common case for
sentence representations ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
As a side benefit, individual attention heads appear to learn distinct,
interpretable syntactic and semantic behaviors ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

> [!note]
> §4 "Why Self-Attention" (pp. 6–7) marked in red ink — the reader emphasized the complexity / path-length argument for choosing self-attention.

## Applications of attention

The Transformer uses multi-head attention in three distinct ways ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)):

- **Encoder–decoder attention** — queries come from the previous decoder layer,
  and the memory keys and values come from the encoder output, so every decoder
  position can attend over all positions of the input sequence.
- **Encoder self-attention** — all keys, values and queries come from the same
  place (the previous encoder layer), so each position attends to all positions
  of that layer.
- **Masked decoder self-attention** — each position attends only to positions up
  to and including itself; illegal (future) connections are masked by setting
  them to $-\infty$ before the softmax, preserving the auto-regressive property.

> [!note]
> The multi-head self-attention sub-layers of §3 Model Architecture (Figure 1, the $N=6$ encoder/decoder stacks) are marked in red ink on page 3 — flagged as the core of how attention is wired into the model.

## Related Concepts

- [Attention Is All You Need](../papers/attention-is-all-you-need.md) — the paper that introduces the mechanisms described here
- [[self-attention]] — attention relating positions within a single sequence
- [[scaled-dot-product-attention]] — the specific compatibility function used
- [[multi-head-attention]] — parallel attention over projected subspaces
- [[positional-encoding]] — supplies order information attention alone lacks
- [[sparse-attention]] — sibling variant for long-context efficiency (open question in notes)

## Sources

- [Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md) — objective paper text; source of all mechanism definitions and equations
- [Obsidian note](../notes/obsidian_attention_is_all_you_need.md) — personal notes on the mechanism and open questions
- [Zotero annotations](../notes/zotero_attention_is_all_you_need/annotations.md) — significance note and red-ink section markers
