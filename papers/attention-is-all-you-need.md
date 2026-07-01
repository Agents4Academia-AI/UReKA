---
title: Attention Is All You Need
type: paper
created: 2026-07-01
authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin]
year: 2017
related_papers: []
related_concepts: []
sources:
  - ../sources/zotero_attention_is_all_you_need.md
  - ../notes/obsidian_attention_is_all_you_need.md
  - ../notes/zotero_attention_is_all_you_need/annotations.md
---

# Attention Is All You Need

## My Notes & Annotations

Introduces the Transformer, a sequence transduction architecture built entirely
on [[self-attention]], dispensing with recurrence and convolutions entirely.
Relies on [[multi-head-attention]] to jointly attend to information from
different representation subspaces, paired with [[positional-encoding]] since
the model has no inherent notion of token order.

Key components:
- [[scaled-dot-product-attention]] — the core attention mechanism, scaled by
  $\sqrt{d_k}$ to stabilize gradients
- [[encoder-decoder-architecture]] — stacked layers of self-attention and
  feed-forward sublayers
- [[layer-normalization]] and residual connections around each sublayer
- [[feed-forward-networks]] applied position-wise

Trained on WMT 2014 En-De and En-Fr translation tasks, outperforming prior
[[recurrent-neural-networks]] and [[convolutional-seq2seq]] approaches while
being significantly more parallelizable.

> [!note] Worth revisiting the ablations on number of attention heads — seems like there's a sweet spot before returns diminish.

> [!question] How does this compare to [[sparse-attention]] variants for long-context tasks?

Related: [[bert]], [[gpt]], [[vision-transformer]]

## Summary

**The Transformer is a sequence transduction architecture built entirely on
attention mechanisms, dispensing with recurrence and convolutions while
achieving state-of-the-art translation quality at a fraction of prior training
cost.**

Dominant sequence transduction models had relied on recurrent or convolutional
encoder–decoder networks, with the best variants connecting encoder and decoder
through an attention mechanism ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
The paper proposes replacing recurrence and convolution outright with a network
that draws global dependencies between input and output positions using
attention alone. This makes the computation far more parallelizable, since the
sequential dependency chain of recurrent models — where hidden state $h_t$ is a
function of $h_{t-1}$ — is removed ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

On the WMT 2014 English-to-German task the model reaches **28.4 BLEU**,
improving over prior best results (including ensembles) by more than 2 BLEU; on
English-to-French it sets a new single-model state of the art of **41.0 BLEU**
after 3.5 days of training on eight P100 GPUs — a small fraction of the training
cost of competing models ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

> [!note]
> "This is a very good paper - I think this will be very influential to all of ML" — typed note on page 1, alongside the abstract.

## Key Contributions

- The **Transformer**, the first sequence transduction model relying entirely
  on self-attention to compute representations of its input and output, without
  sequence-aligned RNNs or convolution ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
- **Scaled dot-product attention**, a fast, memory-efficient attention function
  implementable as matrix multiplication, with a scaling factor that stabilizes
  gradients for large key dimension ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
- **Multi-head attention**, which lets the model jointly attend to information
  from different representation subspaces at different positions ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
- A **parameter-free sinusoidal positional encoding** that injects order
  information into an otherwise permutation-agnostic model ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
- New state-of-the-art BLEU on WMT 2014 En-De and En-Fr at substantially
  reduced training cost, demonstrating superior parallelizability ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

## Methodology

### Encoder–decoder architecture

The Transformer keeps the standard encoder–decoder structure: the encoder maps
an input sequence $(x_1, \dots, x_n)$ to continuous representations
$\mathbf{z} = (z_1, \dots, z_n)$, and the decoder generates an output sequence
$(y_1, \dots, y_m)$ one symbol at a time, auto-regressively consuming previously
generated symbols ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

Both stacks use $N = 6$ identical layers. Each **encoder** layer has two
sub-layers — a multi-head self-attention mechanism and a position-wise
fully connected feed-forward network. Each **decoder** layer inserts a third
sub-layer performing multi-head attention over the encoder output. Every
sub-layer is wrapped in a residual connection followed by layer normalization:

$$\text{output} = \text{LayerNorm}(x + \text{Sublayer}(x))$$

To support these residual connections, all sub-layers and the embedding layers
produce outputs of dimension $d_{\text{model}} = 512$ ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
The decoder's self-attention is **masked** — future positions are set to
$-\infty$ before the softmax — so predictions for position $i$ depend only on
known outputs at positions less than $i$, preserving the auto-regressive
property ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

> [!note]
> Section §3 Model Architecture (including Figure 1, the $N=6$ encoder/decoder stacks, residual connections and layer normalization) is marked in red ink on page 3 — flagged as core reading.

### Scaled dot-product attention

An attention function maps a query and a set of key–value pairs to an output
computed as a weighted sum of the values, where each weight is a compatibility
function of the query with the corresponding key ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
With queries and keys of dimension $d_k$ and values of dimension $d_v$, packed
into matrices $Q$, $K$, $V$:

$$\text{Attention}(Q, K, V) = \text{softmax}\!\left(\frac{QK^{\top}}{\sqrt{d_k}}\right)V$$

Dot-product attention is chosen over additive attention because it can be
implemented with highly optimized matrix multiplication, making it much faster
and more space-efficient ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
The scaling by $\tfrac{1}{\sqrt{d_k}}$ counteracts a specific failure mode: if
the components of $q$ and $k$ are independent with mean $0$ and variance $1$,
their dot product $q \cdot k = \sum_{i=1}^{d_k} q_i k_i$ has mean $0$ and
variance $d_k$; for large $d_k$ these products grow in magnitude and push the
softmax into regions of vanishingly small gradient ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

### Multi-head attention

Rather than a single attention function over $d_{\text{model}}$-dimensional
keys, values and queries, the model linearly projects them $h$ times with
learned projections to $d_k$, $d_k$ and $d_v$ dimensions, applies attention in
parallel, then concatenates and projects the results:

$$\text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)\,W^{O}$$
$$\text{head}_i = \text{Attention}(QW_i^{Q},\, KW_i^{K},\, VW_i^{V})$$

with projection matrices $W_i^{Q} \in \mathbb{R}^{d_{\text{model}} \times d_k}$,
$W_i^{K} \in \mathbb{R}^{d_{\text{model}} \times d_k}$,
$W_i^{V} \in \mathbb{R}^{d_{\text{model}} \times d_v}$ and
$W^{O} \in \mathbb{R}^{hd_v \times d_{\text{model}}}$. The work uses $h = 8$
heads with $d_k = d_v = d_{\text{model}}/h = 64$, so the total cost is similar
to single-head attention at full dimensionality ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
Multi-head attention lets the model jointly attend to information from different
representation subspaces at different positions, which a single head inhibits
through averaging ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

Attention is applied in three ways: **encoder–decoder attention** (queries from
the decoder, keys/values from the encoder output, letting every decoder position
attend over the whole input), **encoder self-attention**, and **masked decoder
self-attention** ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

### Position-wise feed-forward networks

Each layer also contains a feed-forward network applied identically to each
position — two linear transformations with a ReLU in between:

$$\text{FFN}(x) = \max(0,\, xW_1 + b_1)\,W_2 + b_2$$

The input/output dimensionality is $d_{\text{model}} = 512$ and the inner layer
has $d_{ff} = 2048$; parameters differ from layer to layer ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

### Positional encoding

Because the model has no recurrence or convolution, positional information is
injected by adding sinusoidal **positional encodings** to the input embeddings:

$$PE_{(pos,\, 2i)} = \sin\!\left(\frac{pos}{10000^{2i/d_{\text{model}}}}\right), \qquad
PE_{(pos,\, 2i+1)} = \cos\!\left(\frac{pos}{10000^{2i/d_{\text{model}}}}\right)$$

where $pos$ is the position and $i$ the dimension, giving wavelengths in a
geometric progression from $2\pi$ to $10000 \cdot 2\pi$. This form was chosen
because for any fixed offset $k$, $PE_{pos+k}$ is a linear function of
$PE_{pos}$, and it may let the model extrapolate to longer sequences than seen
in training. Learned positional embeddings gave nearly identical results ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

### Training

Training used the WMT 2014 English–German dataset (~4.5M sentence pairs,
byte-pair encoding, ~37000 shared tokens) and the larger English–French dataset
(36M sentences, 32000 word-piece vocabulary), on one machine with 8 NVIDIA P100
GPUs — base models for 100,000 steps (~12 hours), big models for 300,000 steps
(3.5 days) ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
The Adam optimizer ($\beta_1 = 0.9$, $\beta_2 = 0.98$, $\epsilon = 10^{-9}$)
was used with a warmup-then-decay schedule:

$$lrate = d_{\text{model}}^{-0.5} \cdot \min\!\left(step\_num^{-0.5},\; step\_num \cdot warmup\_steps^{-1.5}\right)$$

with $warmup\_steps = 4000$ ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
Regularization combined residual dropout ($P_{drop} = 0.1$ for the base model)
and label smoothing ($\epsilon_{ls} = 0.1$), the latter hurting perplexity but
improving accuracy and BLEU ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

> [!note]
> Sections §5 Training / §5.1–§5.2 and Table 2 (the BLEU comparison against ByteNet, GNMT, ConvS2S and MoE) are marked in red ink on page 7 — the reader tracked the headline results.

## Important Concepts

- [[self-attention]] (intra-attention) — relating different positions of a
  single sequence to compute its representation
- [[scaled-dot-product-attention]] — the core compatibility function, scaled by
  $\sqrt{d_k}$
- [[multi-head-attention]] — parallel attention over projected subspaces
- [[positional-encoding]] — sinusoidal injection of token order
- [[encoder-decoder-architecture]] — the stacked-layer backbone
- [[layer-normalization]] and residual connections
- [[feed-forward-networks]] — position-wise transformations

## Connections to Related Work

The Transformer builds on the encoder–decoder attention lineage of Bahdanau et
al. and sequence-to-sequence learning, while removing the recurrence they relied
on ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
It positions itself against the parallel-computation convolutional models
(Extended Neural GPU, ByteNet, ConvS2S), where the number of operations relating
two positions grows with distance — linearly for ConvS2S, logarithmically for
ByteNet — whereas self-attention reduces this to a constant number of operations
(at the cost of reduced effective resolution, counteracted by multi-head
attention) ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

The **Why Self-Attention** analysis compares layer types on three desiderata —
per-layer complexity, parallelizable computation, and maximum path length
between long-range dependencies:

| Layer type | Complexity per layer | Sequential ops | Max path length |
|---|---|---|---|
| Self-Attention | $O(n^2 \cdot d)$ | $O(1)$ | $O(1)$ |
| Recurrent | $O(n \cdot d^2)$ | $O(n)$ | $O(n)$ |
| Convolutional | $O(k \cdot n \cdot d^2)$ | $O(1)$ | $O(\log_k(n))$ |
| Self-Attention (restricted) | $O(r \cdot n \cdot d)$ | $O(1)$ | $O(n/r)$ |

Self-attention connects all positions with a constant number of sequential
operations, and is faster than a recurrent layer when the sequence length $n$ is
smaller than the representation dimensionality $d$ — the common case for
sentence representations ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
As a side benefit, individual attention heads appear to learn distinct,
interpretable syntactic and semantic behaviors ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

> [!note]
> The comparison of self-attention against recurrent and convolutional layers (§4 Why Self-Attention, spanning pages 6–7) is marked in red ink — the reader emphasized the complexity/path-length argument.

Follow-on work builds directly on this architecture — see [[bert]], [[gpt]] and
[[vision-transformer]] noted above.

## Limitations & Open Questions

- Self-attention's per-layer complexity is $O(n^2 \cdot d)$, quadratic in
  sequence length; for very long sequences the authors suggest **restricted
  self-attention** over a neighborhood of size $r$ (raising max path length to
  $O(n/r)$) as future work ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
- Reducing multi-head attention to a single head costs 0.9 BLEU, while too many
  heads also degrades quality — implying a sweet spot in $h$ ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
- Reducing the attention key size $d_k$ hurts quality, suggesting dot-product
  compatibility may be too simple and a more sophisticated compatibility
  function could help ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).
- The authors flag extending the Transformer to non-text modalities (images,
  audio, video) and making generation less sequential as open directions ([Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md)).

> [!note]
> The §6.2 Model Variations ablations (Table 3 — varying $N$, $d_{\text{model}}$, $d_{ff}$, $h$, $d_k$, $d_v$, dropout, label smoothing) and the §7 Conclusion are marked in red ink on page 9 — this connects to the "sweet spot" question raised in the Obsidian note above.

## Sources

- [Attention Is All You Need](../sources/zotero_attention_is_all_you_need.md) — objective paper text (abstract through references)
- [Obsidian note](../notes/obsidian_attention_is_all_you_need.md) — personal summary, component notes, and open questions
- [Zotero annotations](../notes/zotero_attention_is_all_you_need/annotations.md) — typed significance note and red-ink section markers
