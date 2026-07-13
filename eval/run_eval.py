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

# Deterministic gates — regex/counting on the answers, no LLM judge. These are
# the merge-blocking thresholds: on a frozen fixture they give the same result
# every run, so CI can't fail at random.
DETERMINISTIC_THRESHOLDS = {
    "citation_coverage": 0.60,  # groundedness proxy
    "refusal_accuracy": 0.50,   # hallucination resistance on unanswerable Qs
}
# Judge-computed metrics: reported for visibility but NOT merge-gated. They call
# a live shared LLM endpoint and swing run-to-run (faithfulness 0.86 -> 0.0 on
# identical input), so gating on them makes CI a coin flip. Check them manually.
ADVISORY_METRICS = ("faithfulness", "answer_relevancy", "llm_context_precision_with_reference", "context_recall")


def load_dataset(subset: str) -> list[dict]:
    path = EVAL_DIR / f"{subset}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", choices=["smoke", "golden"], default="smoke")
    parser.add_argument("--llm", default=None, help="LLM provider for generation + judge: nvidia, gemini, or ollama")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between questions (API rate limits)")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N questions (quota-constrained runs)")
    parser.add_argument("--freeze", metavar="PATH", help="Generate answers and write them to a fixture, then exit (no judging).")
    parser.add_argument("--frozen", metavar="PATH", help="Load answers from a fixture instead of generating (reproducible CI).")
    parser.add_argument("--no-judge", action="store_true", help="Skip the LLM judge; gate only on deterministic metrics.")
    args = parser.parse_args()

    from stockrag.config import settings

    judge_provider = args.llm or settings.llm_provider
    judge_keys = {"gemini": settings.gemini_api_key, "nvidia": settings.nvidia_api_key}
    # Key needed only when we actually call the endpoint: generating (not frozen)
    # or judging (not --no-judge). Frozen + no-judge runs offline.
    need_key = not (args.frozen and args.no_judge)
    if need_key and judge_provider in judge_keys and not judge_keys[judge_provider]:
        print(f"ERROR: {judge_provider.upper()}_API_KEY is required. Set it in .env or the environment.")
        return 2

    from stockrag.rag.metrics import citation_coverage

    # --- answers: generate live, or load a frozen fixture ---
    if args.frozen:
        answers = json.loads(Path(args.frozen).read_text(encoding="utf-8"))
        print(f"Loaded {len(answers)} frozen answers from {args.frozen}")
    else:
        from stockrag.rag.answer import ask

        rows = load_dataset(args.subset)
        if args.limit:
            rows = rows[: args.limit]
        print(f"Generating over {len(rows)} questions (subset={args.subset}, llm={args.llm or 'default'})...")
        answers = []
        for i, row in enumerate(rows, start=1):
            result = ask(row["question"], row["ticker"], llm_provider=args.llm)
            answers.append(
                {
                    "question": row["question"],
                    "ticker": row["ticker"],
                    "ground_truth": row["ground_truth"],
                    "expected_section": row.get("expected_section"),
                    "answer": result.answer,
                    "contexts": result.contexts,
                }
            )
            print(f"  [{i}/{len(rows)}] {row['question'][:70]}")
            if args.sleep:
                time.sleep(args.sleep)

    if args.freeze:
        Path(args.freeze).write_text(json.dumps(answers, indent=2), encoding="utf-8")
        print(f"Wrote fixture: {args.freeze} ({len(answers)} answers)")
        return 0

    from stockrag.rag.answer import NO_CONTEXT_MESSAGE

    # --- deterministic metrics (regex/counting on the answers; no LLM judge) ---
    coverages: list[float] = []
    refusal_expected = 0
    refusal_correct = 0
    for a in answers:
        refused = a["answer"] == NO_CONTEXT_MESSAGE
        if a.get("expected_section") == "unanswerable":
            refusal_expected += 1
            refusal_correct += int(refused)
        elif not refused:
            coverages.append(citation_coverage(a["answer"]))

    scores: dict[str, float] = {}
    if coverages:
        scores["citation_coverage"] = sum(coverages) / len(coverages)
    if refusal_expected:
        scores["refusal_accuracy"] = refusal_correct / refusal_expected

    # --- advisory judge metrics (not merge-gated) ---
    if not args.no_judge:
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

        from stockrag.rag.embed import get_embeddings
        from stockrag.rag.llm import get_llm

        samples = [
            SingleTurnSample(
                user_input=a["question"],
                response=a["answer"],
                retrieved_contexts=a["contexts"],
                reference=a["ground_truth"],
            )
            for a in answers
        ]
        # temperature=0.0: a grader must be deterministic or scores swing run-to-run.
        judge_model = settings.nvidia_judge_model if judge_provider == "nvidia" else None
        judge = LangchainLLMWrapper(get_llm(judge_provider, judge_model, temperature=0.0))
        print(f"Scoring advisory metrics with Ragas ({judge_provider} judge)...")
        result = evaluate(
            EvaluationDataset(samples=samples),
            metrics=[Faithfulness(), AnswerRelevancy(), LLMContextPrecisionWithReference(), LLMContextRecall()],
            llm=judge,
            embeddings=LangchainEmbeddingsWrapper(get_embeddings()),
            run_config=RunConfig(max_workers=1, timeout=300),
        )
        scores.update({metric: float(value) for metric, value in result._repr_dict.items()})

    print(json.dumps(scores, indent=2))
    advisory = {m: scores[m] for m in ADVISORY_METRICS if m in scores}
    if advisory:
        print("Advisory (not gated): " + ", ".join(f"{k}={v:.3f}" for k, v in advisory.items()))

    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{args.subset}.json"
    out_path.write_text(
        json.dumps({"subset": args.subset, "llm": args.llm, "frozen": bool(args.frozen), "scores": scores}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")

    failed = {
        metric: (scores.get(metric), threshold)
        for metric, threshold in DETERMINISTIC_THRESHOLDS.items()
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
