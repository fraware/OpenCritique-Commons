"""Structural types for the optional torch/transformers surface used by hf_local.

These Protocols describe only the attributes and call shapes exercised by
``opencritique_runners.hf_local``. They keep core typing green when the
``[live-openreviewer]`` extra is not installed.
"""

from __future__ import annotations

from typing import Any, Protocol


class TorchCuda(Protocol):
    def is_available(self) -> bool: ...


class TorchModule(Protocol):
    cuda: TorchCuda
    bfloat16: Any


class TensorLike(Protocol):
    def to(self, device: Any, /) -> TensorLike: ...

    @property
    def shape(self) -> Any: ...

    def __getitem__(self, item: Any) -> Any: ...


class HFTokenizer(Protocol):
    def apply_chat_template(
        self,
        conversation: Any,
        *,
        add_generation_prompt: bool = ...,
        return_tensors: str | None = ...,
    ) -> TensorLike: ...

    def decode(
        self,
        token_ids: Any,
        *,
        skip_special_tokens: bool = ...,
    ) -> str: ...


class HFTokenizerFactory(Protocol):
    def from_pretrained(self, pretrained_model_name_or_path: str, /) -> HFTokenizer: ...


class HFCausalLM(Protocol):
    device: Any

    def generate(
        self,
        *,
        input_ids: Any,
        max_new_tokens: int,
        do_sample: bool,
        temperature: float,
        top_p: float,
    ) -> TensorLike: ...


class HFCausalLMFactory(Protocol):
    def from_pretrained(
        self,
        pretrained_model_name_or_path: str,
        /,
        *,
        torch_dtype: Any = ...,
        device_map: str | None = ...,
    ) -> HFCausalLM: ...


class TransformersModule(Protocol):
    AutoModelForCausalLM: HFCausalLMFactory
    AutoTokenizer: HFTokenizerFactory
