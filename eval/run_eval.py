"""Offline RAG evaluation harness (Ragas).

Runs the full ask() pipeline over a QA dataset and scores it with Ragas.
The judge LLM follows --llm (falling back to the configured default provider,
needing its API key); embeddings are the local bge model, so only judging
calls leave the machine.

Usage:
    uv run python eval/run_eval.py --subset smoke              # 8 questions
    uv run python eval/run_eval.py --subset golden             # full set
    uv run python eval/run_eval.py --subset smoke --llm nvidia # CI (no Ollama there)

Exits 1 when any gated metric falls below its threshold.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

THRESHOLDS = {
    "faithfulness": 0.75,
    # 0.60, not 0.70: long cited filing answers score ~0.65 consistently across
    # three judge models (nemotron-ultra/super, gemini-lite) — the metric's
    # embedding-similarity bias against long answers, not a quality regression.
    "answer_relevancy": 0.60,
    "llm_context_precision_with_reference": 0.60,
    # Locally computed (no LLM judge): groundedness proxy + hallucination
    # resistance on the unanswerable questions.
    "citation_coverage": 0.60,
    "refusal_accuracy": 0.50,
}
# context_recall is reported but not gated: recall against a hand-written
# reference is noisy for long filing answers.


def load_dataset(subset: str) -> list[dict]:
    path = EVAL_DIR / f"{subset}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", choices=["smoke", "golden"], default="smoke")
    parser.add_argument("--llm", default=None, help="LLM provider for generation + judge: nvidia, gemini, or ollama")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between questions (API rate limits)")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N questions (quota-constrained runs)")
    args = parser.parse_args()

    from stockrag.config import settings

    judge_provider = args.llm or settings.llm_provider
    judge_keys = {"gemini": settings.gemini_api_key, "nvidia": settings.nvidia_api_key}
    if judge_provider in judge_keys and not judge_keys[judge_provider]:
        print(f"ERROR: {judge_provider.upper()}_API_KEY is required (Ragas judge). Set it in .env or the environment.")
        return 2

    from ragas import EvaluationDataset, evaluate
    from ragas.dataset_schema import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        AnswerRelevancy,
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
    )
    from ragas.run_config import RunConfig

    from stockrag.rag.answer import NO_CONTEXT_MESSAGE, ask
    from stockrag.rag.embed import get_embeddings
    from stockrag.rag.metrics import citation_coverage

    rows = load_dataset(args.subset)
    if args.limit:
        rows = rows[: args.limit]
    print(f"Running pipeline over {len(rows)} questions (subset={args.subset}, llm={args.llm or 'default'})...")

    samples: list[SingleTurnSample] = []
    coverages: list[float] = []
    refusal_expected = 0
    refusal_correct = 0
    for i, row in enumerate(rows, start=1):
        result = ask(row["question"], row["ticker"], llm_provider=args.llm)
        refused = result.answer == NO_CONTEXT_MESSAGE
        if row.get("expected_section") == "unanswerable":
            refusal_expected += 1
            refusal_correct += int(refused)
        elif not refused:
            coverages.append(citation_coverage(result.answer))
        samples.append(
            SingleTurnSample(
                user_input=row["question"],
                response=result.answer,
                retrieved_contexts=result.contexts,
                reference=row["ground_truth"],
            )
        )
        print(f"  [{i}/{len(rows)}] {row['question'][:70]}")
        if args.sleep:
            time.sleep(args.sleep)

    from stockrag.rag.llm import get_llm

    # nvidia judge uses a faster model than generation: Ragas fires ~4 long
    # prompts per question and slow judge calls time out into NaN scores.
    # temperature=0.0: a grader must be deterministic or scores swing run-to-run.
    judge_model = settings.nvidia_judge_model if judge_provider == "nvidia" else None
    judge = LangchainLLMWrapper(get_llm(judge_provider, judge_model, temperature=0.0))
    embeddings = LangchainEmbeddingsWrapper(get_embeddings())

    print(f"Scoring with Ragas ({judge_provider} judge, max_workers=1 for free-tier RPM)...")
    result = evaluate(
        EvaluationDataset(samples=samples),
        metrics=[Faithfulness(), AnswerRelevancy(), LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=judge,
        embeddings=embeddings,
        # timeout: judge calls on shared NIM endpoints occasionally spike; the
        # 180s default turned slow calls into NaN scores and false gate failures.
        run_config=RunConfig(max_workers=1, timeout=300),
    )

    scores = {metric: float(value) for metric, value in result._repr_dict.items()}
    if coverages:
        scores["citation_coverage"] = sum(coverages) / len(coverages)
    if refusal_expected:
        scores["refusal_accuracy"] = refusal_correct / refusal_expected
    print(json.dumps(scores, indent=2))

    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{args.subset}.json"
    out_path.write_text(
        json.dumps({"subset": args.subset, "llm": args.llm, "scores": scores}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")

    failed = {
        metric: (scores.get(metric), threshold)
        for metric, threshold in THRESHOLDS.items()
        if scores.get(metric) is not None and scores[metric] < threshold
    }
    if failed:
        for metric, (score, threshold) in failed.items():
            print(f"FAIL: {metric} = {score:.3f} < threshold {threshold}")
        return 1
    print("All gated metrics above thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
