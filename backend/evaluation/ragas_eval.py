"""
RAGAS evaluation script for the pronunciation history RAG pipeline.

Usage:
    python evaluation/ragas_eval.py

Requires:
    - ragas
    - langchain-openai
    - Running PostgreSQL with session_patterns data
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.db.database import SessionLocal
from app.db.models import SessionPattern, SessionHistory
from app.core.embedding import get_embedding, build_pattern_text, extract_transcript_mismatches


def build_eval_dataset(user_id: int, n_samples: int = 10):
    """
    평가 데이터셋 구성.
    각 샘플 = {question, answer, contexts, ground_truth}
    """
    db = SessionLocal()
    try:
        sessions = (
            db.query(SessionHistory)
            .filter(SessionHistory.user_id == user_id)
            .order_by(SessionHistory.created_at.desc())
            .limit(n_samples + 5)
            .all()
        )

        if len(sessions) < 2:
            print("Need at least 2 sessions for evaluation.")
            return None

        questions, answers, contexts_list = [], [], []

        for session in sessions[:n_samples]:
            mismatches = extract_transcript_mismatches(
                session.target_text or "",
                session.user_transcript or "",
            )
            pattern_text = build_pattern_text(
                session.improvements or [],
                mismatches,
                session.score or 0,
            )
            query_vector = get_embedding(pattern_text)

            # 유사 패턴 검색
            similar = db.execute(
                """
                SELECT sp.pattern_text
                FROM session_patterns sp
                WHERE sp.user_id = :user_id
                  AND sp.session_id != :current_id
                ORDER BY sp.embedding <=> :query_vec
                LIMIT 5
                """,
                {
                    "query_vec": str(query_vector),
                    "user_id": user_id,
                    "current_id": session.id,
                },
            ).fetchall()

            retrieved_contexts = [row[0] for row in similar]
            if not retrieved_contexts:
                continue

            question = f"What pronunciation patterns should I focus on? Current issues: {pattern_text}"

            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an encouraging English pronunciation coach. "
                            "Based on retrieved past sessions, identify recurring patterns "
                            "and give specific, actionable advice. Be concise (3-5 sentences)."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Current session:\n{pattern_text}\n\n"
                            f"Similar past sessions:\n" + "\n".join(retrieved_contexts) +
                            "\n\nWhat recurring patterns do you see and what should this learner focus on?"
                        ),
                    },
                ],
            )
            answer = response.choices[0].message.content

            questions.append(question)
            answers.append(answer)
            contexts_list.append(retrieved_contexts)

        if not questions:
            print("No valid samples generated.")
            return None

        return Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
        })

    finally:
        db.close()


def run_evaluation(user_id: int):
    print(f"Building eval dataset for user_id={user_id}...")
    dataset = build_eval_dataset(user_id)
    if dataset is None:
        return

    print(f"Evaluating {len(dataset)} samples with RAGAS...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    results = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=llm,
        embeddings=embeddings,
    )

    print("\n=== RAGAS Evaluation Results ===")
    print(f"Faithfulness:      {results['faithfulness']:.3f}")
    print(f"Answer Relevancy:  {results['answer_relevancy']:.3f}")
    print(f"Context Precision: {results['context_precision']:.3f}")
    return results


if __name__ == "__main__":
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_evaluation(user_id)
