"""Optional Hugging Face local runner for Llama-OpenReviewer-8B.

Requires ``pip install -e ".[live-openreviewer]"`` and a GPU-capable host for
practical inference. This path does **not** use ``OPENAI_API_KEY`` /
``OPENCRITIQUE_BYOK_API_KEY``.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import cast

from .hf_stack_types import (
    HFCausalLMFactory,
    HFTokenizerFactory,
    TorchModule,
    TransformersModule,
)
from .openreviewer import (
    DEFAULT_VENUE_TEMPLATE,
    OPENREVIEWER_HF_MODEL_ID,
    OpenReviewerLiveExport,
    live_export_from_generated_markdown,
)

# Mirrors the Space app.py review-field block (ICLR-style sections).
_DEFAULT_REVIEW_FIELDS = """## Summary
Briefly summarize the paper and its contributions.

## Strengths
A substantive assessment of the strengths of the paper.

## Weaknesses
A substantive assessment of the weaknesses of the paper.

## Questions
Please list questions and suggestions for the authors.

## Rating
Please provide an overall score for this submission. Choose from:
1, 3, 5, 6, 8, or 10.
"""

_SYSTEM_PROMPT = """You are an expert reviewer for AI conferences.
Write reviews in markdown format containing the following sections:

# Review

{review_fields}

Your response must only contain the review in markdown format with sections as defined above.
"""

_USER_PROMPT = """Review the following paper:

{paper_text}
"""


class OpenReviewerHFUnavailableError(RuntimeError):
    """Raised when the optional HF stack is missing or unusable."""


def _require_hf_stack() -> tuple[TorchModule, tuple[HFCausalLMFactory, HFTokenizerFactory]]:
    try:
        torch_mod = cast(TorchModule, importlib.import_module("torch"))
        transformers_mod = cast(
            TransformersModule, importlib.import_module("transformers")
        )
    except ImportError as exc:  # pragma: no cover - exercised via mocked tests
        raise OpenReviewerHFUnavailableError(
            "OpenReviewer HF local runner requires the [live-openreviewer] extra "
            "(transformers + torch). OpenAI/BYOK API keys do not substitute for this. "
            "Install with: pip install -e \".[live-openreviewer]\" "
            "and use a GPU host, or import a Space export via "
            "`opencritique runners openreviewer --from-export`."
        ) from exc
    return torch_mod, (
        transformers_mod.AutoModelForCausalLM,
        transformers_mod.AutoTokenizer,
    )


def gpu_status_message(torch_mod: TorchModule) -> str:
    if torch_mod.cuda.is_available():
        return "CUDA available"
    return (
        "CUDA not available — Llama-OpenReviewer-8B local runs typically need a GPU; "
        "CPU-only inference is unsupported by this runner"
    )


def run_openreviewer_hf_local(
    manuscript: Path,
    *,
    model_id: str = OPENREVIEWER_HF_MODEL_ID,
    venue_template: str = DEFAULT_VENUE_TEMPLATE,
    max_new_tokens: int = 4096,
    allow_cpu: bool = False,
) -> OpenReviewerLiveExport:
    """Generate a review from a local markdown/text manuscript via HF weights.

    Downloads model weights on first use when the extra is installed. CI must not
    exercise this path with network/GPU; use import mode + mocks instead.
    """
    manuscript = manuscript.resolve()
    if not manuscript.is_file():
        raise FileNotFoundError(f"manuscript not found: {manuscript}")

    torch_mod, (auto_model_cls, auto_tokenizer_cls) = _require_hf_stack()
    status = gpu_status_message(torch_mod)
    if "not available" in status and not allow_cpu:
        raise OpenReviewerHFUnavailableError(
            f"{status}. Pass allow_cpu=True only for explicit operator override "
            "(not recommended). Prefer GPU or --from-export import mode."
        )

    paper_text = manuscript.read_text(encoding="utf-8").strip()
    if len(paper_text) < 200:
        raise ValueError("manuscript text too short for OpenReviewer local generation")

    tokenizer = auto_tokenizer_cls.from_pretrained(model_id)
    model = auto_model_cls.from_pretrained(
        model_id,
        torch_dtype=getattr(torch_mod, "bfloat16", None),
        device_map="auto",
    )
    messages = [
        {
            "role": "system",
            "content": _SYSTEM_PROMPT.format(review_fields=_DEFAULT_REVIEW_FIELDS),
        },
        {"role": "user", "content": _USER_PROMPT.format(paper_text=paper_text)},
    ]
    input_ids = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to(model.device)
    output_ids = model.generate(
        input_ids=input_ids,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=0.6,
        top_p=0.9,
    )
    generated = tokenizer.decode(
        output_ids[0][input_ids.shape[-1] :],
        skip_special_tokens=True,
    ).replace("<|eot_id|>", "").strip()

    return live_export_from_generated_markdown(
        generated,
        venue_template=venue_template,
        model_id=model_id,
        notes=(
            f"HF local generation with {model_id}. {status}. "
            "Not powered by OpenAI/BYOK credentials."
        ),
    )
