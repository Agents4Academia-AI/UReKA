---
type: obsidian_note
title: Attention Is All You Need
source_links:
  - /Users/user/.../Attention Is All You Need.md
concepts_mentioned: [self-attention, multi-head-attention, positional-encoding, scaled-dot-product-attention, encoder-decoder-architecture, layer-normalization, feed-forward-networks, recurrent-neural-networks, convolutional-seq2seq, sparse-attention, bert, gpt, vision-transformer]
---

## Content

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
