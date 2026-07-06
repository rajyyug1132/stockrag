"""Offline RAG evaluation harness (Ragas).

Runs the full ask() pipeline over a QA dataset and scores it with Ragas.
The judge LLM is Gemini (needs GEMINI_API_KEY); embeddings are the local
bge model, so only judging calls leave the machine.

Usage:
    uv run python eval/run_eval.py --subset smoke              # 8 questions (CI)
    uv run python eval/run_eval.py --subset golden             # full set
    uv run python eval/run_eval.py --subset smoke --llm gemini # generation via Gemini too (CI has no Ollama)

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
    "answer_relevancy": 0.70,
    "llm_context_precision_with_reference": 0.60,
}
# context_recall is reported but not gated: recall against a hand-written
# reference is noisy for long filing answers.


def load_dataset(subset: str) -> list[dict]:
    path = EVAL_DIR / f"{subset}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", choices=["smoke", "golden"], default="smoke")
    parser.add_argument("--llm", default=None, help="Generation LLM provider: ollama (default) or gemini")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between questions (API rate limits)")
    args = parser.parse_args()

    from stockrag.config import settings

    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY is required (Ragas judge). Set it in .env or the environment.")
        return 2

    from langchain_google_genai import ChatGoogleGenerativeAI
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

    from stockrag.rag.answer import ask
    from stockrag.rag.embed import get_embeddings

    rows = load_dataset(args.subset)
    print(f"Running pipeline over {len(rows)} questions (subset={args.subset}, llm={args.llm or 'default'})...")

    samples: list[SingleTurnSample] = []
    for i, row in enumerate(rows, start=1):
        result = ask(row["question"], row["ticker"], llm_provider=args.llm)
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

    judge = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=0.0,
            google_api_key=settings.gemini_api_key,
        )
    )
    embeddings = LangchainEmbeddingsWrapper(get_embeddings())

    print("Scoring with Ragas (Gemini judge, max_workers=1 for free-tier RPM)...")
    result = evaluate(
        EvaluationDataset(samples=samples),
        metrics=[Faithfulness(), AnswerRelevancy(), LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=judge,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=1),
    )

    scores = {metric: float(value) for metric, value in result._repr_dict.items()}
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
