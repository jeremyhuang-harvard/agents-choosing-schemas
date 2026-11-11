"""Subject-model backends. MockEngine is for plumbing tests only; its output is NOT evidence."""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field

MOCK_WARNING = "MOCK ENGINE OUTPUT - NOT EVIDENCE"
DEFAULT_MODEL = "mlx-community/Qwen3-8B-4bit"


class MockEngine:
    name = "mock"
    model_id = "mock"

    def config(self) -> dict:
        return {"engine": "mock", "warning": MOCK_WARNING}

    def generate(self, prompt: str, seed: int) -> str:
        rng = random.Random(seed)
        facts = re.findall(r"^- (.*)$", prompt, flags=re.M)
        think = f"<think>\n[{MOCK_WARNING}] I see {len(facts)} facts. " + " ".join(facts) + "\n</think>\n\n"
        return think + str(int(rng.uniform(5, 300)))

    def generate_stream(self, jobs, batch_size: int = 8):
        for key, prompt in jobs:
            yield key, self.generate(prompt, hash(key) & 0xFFFF)


@dataclass
class MLXEngine:
    """Qwen3 via mlx-lm with thinking enabled. Sampling follows Qwen's recommended thinking-mode settings."""
    model_id: str = DEFAULT_MODEL
    max_tokens: int = 8192
    temp: float = 0.6
    top_p: float = 0.95
    top_k: int = 20
    enable_thinking: bool = True
    batch_seed: int = 0
    name: str = "mlx"
    _model: object = field(default=None, repr=False)
    _tok: object = field(default=None, repr=False)

    def config(self) -> dict:
        import mlx_lm
        return {"engine": "mlx", "model_id": self.model_id, "mlx_lm_version": mlx_lm.__version__,
                "max_tokens": self.max_tokens, "temp": self.temp, "top_p": self.top_p, "top_k": self.top_k,
                "enable_thinking": self.enable_thinking}

    def _load(self) -> None:
        if self._model is None:
            import mlx.core as mx
            from mlx_lm import load
            # Share the GPU politely with other MLX jobs: keep freed buffers out of the cache.
            mx.set_cache_limit(512 * 1024**2)
            self._model, self._tok = load(self.model_id)

    def generate(self, prompt: str, seed: int) -> str:
        import mlx.core as mx
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler
        self._load()
        chat = self._tok.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True,
            enable_thinking=self.enable_thinking)
        mx.random.seed(seed)
        return generate(self._model, self._tok, chat, max_tokens=self.max_tokens,
                        sampler=make_sampler(temp=self.temp, top_p=self.top_p, top_k=self.top_k),
                        verbose=False)

    def generate_stream(self, jobs, batch_size: int = 8):
        """Continuous batching. `jobs` is an iterable of (key, prompt). Yields (key, raw_text) as each finishes.

        Every prompt is an independent sequence with its own KV cache; prompts never see each other.
        Sampling settings are identical to `generate`; randomness is per-batch rather than per-call seed.
        """
        import mlx.core as mx
        from mlx_lm.generate import BatchGenerator
        from mlx_lm.sample_utils import make_sampler
        self._load()
        mx.random.seed(self.batch_seed)
        jobs = iter(jobs)
        sampler = make_sampler(temp=self.temp, top_p=self.top_p, top_k=self.top_k)
        gen = BatchGenerator(self._model, stop_tokens=[[t] for t in self._tok.eos_token_ids], sampler=sampler,
                             completion_batch_size=batch_size, prefill_batch_size=batch_size)
        uid_key: dict = {}
        toks: dict = {}

        def feed(n: int) -> None:
            batch = []
            for _ in range(n):
                try:
                    batch.append(next(jobs))
                except StopIteration:
                    break
            if not batch:
                return
            ids = [self._tok.apply_chat_template([{"role": "user", "content": p}], add_generation_prompt=True,
                                                 enable_thinking=self.enable_thinking) for _, p in batch]
            uids = gen.insert(ids, [self.max_tokens] * len(ids))
            for uid, (key, _) in zip(uids, batch):
                uid_key[uid] = key
                toks[uid] = []

        feed(batch_size)
        try:
            while uid_key:
                responses = gen.next_generated()
                if not responses:
                    break
                for r in responses:
                    if r.finish_reason != "stop":
                        toks[r.uid].append(r.token)
                    if r.finish_reason is not None:
                        text = self._tok.decode(toks.pop(r.uid))
                        key = uid_key.pop(r.uid)
                        feed(1)
                        yield key, text
        finally:
            gen.close()
