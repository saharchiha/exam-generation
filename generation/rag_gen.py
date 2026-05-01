"""
rag_gen.py — Adaptive RAG Generator for Tunisian Baccalaureate
Architecture: Adaptive RAG + Self-Reflection

Pipeline:
    3 sources run IN PARALLEL:
        ├── Weaviate RAG     (confidence: based on certainty score)
        ├── Web Search       (confidence: based on source trust)
        └── Direct LLM       (confidence: 0.4 baseline)

    → Best confidence score wins
    → LLM generates exercise using winning context
    → Self-Reflection validates output
"""

import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Module imports (graceful degradation)
# ─────────────────────────────────────────────────────────────

try:
    from retrieval.retriever import SemanticRetriever
    WEAVIATE_AVAILABLE = True
    logger.info("✅ SemanticRetriever (Weaviate) imported")
except ImportError as e:
    logger.warning(f"⚠️ Weaviate not available: {e}")
    WEAVIATE_AVAILABLE = False

try:
    from generation.enhanced_bac_search import TunisianBacSearchEngine
    WEB_SEARCH_AVAILABLE = True
    logger.info("✅ TunisianBacSearchEngine (Web Search) imported")
except ImportError as e:
    logger.warning(f"⚠️ Web search not available: {e}")
    WEB_SEARCH_AVAILABLE = False

try:
    from retrieval.reflection import ReflectionManager
    REFLECTION_AVAILABLE = True
    logger.info("✅ ReflectionManager (Self-Reflection) imported")
except ImportError as e:
    logger.warning(f"⚠️ ReflectionManager not available: {e}")
    REFLECTION_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# JSON Parser
# ─────────────────────────────────────────────────────────────

class JSONOutputParser:
    def parse(self, text: str) -> Dict[str, Any]:
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                parts = text.split("```")
                if len(parts) >= 3:
                    text = parts[1].strip()
                    if text.startswith("json"):
                        text = text[4:].strip()
            first = text.find('{')
            last = text.rfind('}')
            if first != -1 and last != -1:
                text = text[first:last + 1]
            return json.loads(text)
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")
            return {"error": "parsing_failed"}


# ─────────────────────────────────────────────────────────────
# Adaptive RAG Generator
# ─────────────────────────────────────────────────────────────

class EnhancedRAGGenerator:
    """
    Adaptive RAG Generator — 3 parallel retrieval sources.
    Best confidence score wins and feeds the LLM generation.
    """

    def __init__(self, model_name: str = "openai/gpt-4o"):
        self.llm = self._init_llm(model_name)
        self.json_parser = JSONOutputParser()

        # Source 1: Weaviate RAG
        self.weaviate = None
        if WEAVIATE_AVAILABLE:
            try:
                self.weaviate = SemanticRetriever()
                logger.info("✅ Weaviate RAG ready")
            except Exception as e:
                logger.warning(f"⚠️ Weaviate connection failed: {e}")

        # Source 2: Web Search
        self.web_search = TunisianBacSearchEngine() if WEB_SEARCH_AVAILABLE else None

        # Source 3: Direct LLM — always available via self.llm

        # Self-Reflection
        self.reflection = None
        if REFLECTION_AVAILABLE:
            try:
                self.reflection = ReflectionManager(self.llm)
                logger.info("✅ Self-Reflection ready")
            except Exception as e:
                logger.warning(f"⚠️ ReflectionManager failed: {e}")

        logger.info("✅ EnhancedRAGGenerator (Adaptive RAG) initialized")

    def _init_llm(self, model_name: str) -> ChatOpenAI:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY missing in .env")
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.7,
            max_tokens=2500,
            timeout=45
        )

    # ──────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ──────────────────────────────────────────────────────────

    def generate_exam_question(
            self,
            query: str,
            language: str = "french",
            question_type: str = "exercise",
            difficulty: str = "medium",
            subject: str = "",
            field: str = "sciences",
            exam_type: str = "controle"
    ) -> Dict[str, Any]:
        """Generate a Tunisian Bac exercise using Adaptive RAG pipeline."""
        try:
            try:
                asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        self._run_adaptive_pipeline,
                        query, language, difficulty, subject, field, exam_type
                    )
                    return future.result(timeout=60)
            except RuntimeError:
                return self._run_adaptive_pipeline(
                    query, language, difficulty, subject, field, exam_type
                )
        except Exception as e:
            logger.error(f"generate_exam_question error: {e}")
            return self._make_fallback_response(
                query, language, subject, difficulty, exam_type
            )

    # ──────────────────────────────────────────────────────────
    # ADAPTIVE PIPELINE
    # ──────────────────────────────────────────────────────────

    def _run_adaptive_pipeline(
            self,
            query: str,
            language: str,
            difficulty: str,
            subject: str,
            field: str,
            exam_type: str
    ) -> Dict[str, Any]:
        """
        Run 3 retrieval sources IN PARALLEL.
        Select the one with the highest confidence score.
        Generate exercise with winning context.
        Apply Self-Reflection.
        """
        logger.info(f"🚀 Adaptive RAG | subject={subject} | query={query}")

        # ── Step 1: Parallel retrieval from all 3 sources ─────
        all_results = self._run_parallel_retrieval(
            query, language, subject, field
        )

        for src, (ctx, conf) in all_results.items():
            logger.info(
                f"   [{src}] confidence={conf:.2f} | "
                f"{'empty' if not ctx else f'{len(ctx)} chars'}"
            )

        # ── Step 2: Select best source ─────────────────────────
        best_source, best_context, best_confidence = self._select_best(
            all_results
        )
        logger.info(
            f"🏆 Winner: {best_source} (confidence={best_confidence:.2f})"
        )

        # ── Step 3: Generate exercise ──────────────────────────
        exercise = self._generate_exercise(
            query=query,
            context=best_context,
            language=language,
            difficulty=difficulty,
            subject=subject,
            exam_type=exam_type,
            source=best_source
        )

        # ── Step 4: Self-Reflection ────────────────────────────
        final_confidence = best_confidence
        reflection_result = None

        if self.reflection and best_context:
            try:
                reflection_result = self.reflection.perform_complete_validation(
                    question=exercise.get("question", ""),
                    context=best_context[:1500],
                    language=language,
                    question_type="exercise",
                    retrieval_confidence=best_confidence,
                    generated_answer=exercise.get("correction", "")
                )
                final_confidence = reflection_result.get(
                    "overall_confidence", best_confidence
                )
                logger.info(
                    f"🔍 Self-Reflection: {final_confidence:.2f} | "
                    f"{reflection_result.get('final_decision')}"
                )
            except Exception as e:
                logger.warning(f"⚠️ Self-Reflection failed: {e}")

        return {
            "success": True,
            "query": query,
            "language": language,
            "question_type": "exercise",
            "difficulty": difficulty,
            "generation": exercise,
            "confidence": round(final_confidence, 3),
            "context_source": best_source,
            "reflection": reflection_result,
            "sources_confidence": {
                src: round(conf, 3)
                for src, (_, conf) in all_results.items()
            },
            "model_used": "gpt-4o via OpenRouter"
        }

    # ──────────────────────────────────────────────────────────
    # PARALLEL RETRIEVAL
    # ──────────────────────────────────────────────────────────

    def _run_parallel_retrieval(
            self,
            query: str,
            language: str,
            subject: str,
            field: str
    ) -> Dict[str, Tuple[str, float]]:
        """
        Run all 3 sources simultaneously using ThreadPoolExecutor.
        Returns: { source_name: (context_string, confidence_score) }
        """
        tasks = {
            "weaviate_rag": lambda: self._fetch_weaviate(query, language, subject),
            "web_search":   lambda: self._fetch_web(query, subject, field, language),
            "direct_llm":   lambda: ("", 0.4),
        }

        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(fn): name
                for name, fn in tasks.items()
            }
            for future in as_completed(futures, timeout=30):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.warning(f"⚠️ [{name}] failed: {e}")
                    results[name] = ("", 0.0)

        # Guarantee all keys exist
        for name in tasks:
            if name not in results:
                results[name] = ("", 0.0)

        return results

    def _select_best(
            self,
            results: Dict[str, Tuple[str, float]]
    ) -> Tuple[str, str, float]:
        """
        Select source with highest confidence.
        Penalizes empty context (except direct_llm which is always empty).
        """
        best_source, best_context, best_conf = "direct_llm", "", 0.0

        for source, (context, confidence) in results.items():
            effective = confidence if (context or source == "direct_llm") else 0.0
            if effective > best_conf:
                best_conf = effective
                best_context = context
                best_source = source

        return best_source, best_context, best_conf

    # ──────────────────────────────────────────────────────────
    # SOURCE 1: WEAVIATE RAG
    # ──────────────────────────────────────────────────────────

    def _fetch_weaviate(
            self, query: str, language: str, subject: str
    ) -> Tuple[str, float]:
        if not self.weaviate:
            return "", 0.0
        try:
            filters = {}
            if subject:
                filters["subject"] = subject
            if language:
                filters["language"] = language

            result = self.weaviate.retrieve(
                query=query,
                language=language,
                filters=filters or None
            )

            docs = result.get("retrieved_documents", [])
            total = result.get("total_documents", 0)
            logger.info(f"📚 Weaviate: {len(docs)}/{total} docs")

            if not docs:
                return "", 0.0

            # Build context
            parts = []
            for i, doc in enumerate(docs[:5], 1):
                content = doc.get("content", "")
                subj = doc.get("subject", "")
                year = doc.get("year", "")
                cert = doc.get("certainty", 0)
                parts.append(
                    f"[Doc {i} | {subj} {year} | certainty={cert:.2f}]\n{content}"
                )
            context = "\n\n".join(parts)

            # Confidence = top certainty + small bonus for more docs
            top_cert = docs[0].get("certainty", 0.5)
            bonus = min(len(docs) * 0.05, 0.2)
            confidence = min(top_cert + bonus, 0.95)

            return context, confidence

        except Exception as e:
            logger.error(f"Weaviate fetch error: {e}")
            return "", 0.0

    # ──────────────────────────────────────────────────────────
    # SOURCE 2: WEB SEARCH
    # ──────────────────────────────────────────────────────────

    def _fetch_web(
            self, query: str, subject: str, field: str, language: str
    ) -> Tuple[str, float]:
        if not self.web_search:
            return "", 0.0
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self.web_search.search_real_bac_exams(
                        subject=subject or query,
                        field=field,
                        year="2024",
                        session="principale",
                        language=language,
                        max_results=5
                    )
                )
            finally:
                loop.close()

            if not results:
                return "", 0.0

            parts = []
            for i, exam in enumerate(results[:3], 1):
                title = exam.get("title", f"Exam {i}")
                content = exam.get("content", exam.get("snippet", ""))[:600]
                url = exam.get("url", "")
                parts.append(f"[Source {i} | {title}]\nURL: {url}\n{content}")

            context = "\n\n".join(parts)
            confidence = min(results[0].get("confidence", 0.7), 0.85)

            return context, confidence

        except Exception as e:
            logger.error(f"Web search fetch error: {e}")
            return "", 0.0

    # ──────────────────────────────────────────────────────────
    # STEP 3: GENERATE EXERCISE
    # ──────────────────────────────────────────────────────────

    def _generate_exercise(
            self,
            query: str,
            context: str,
            language: str,
            difficulty: str,
            subject: str,
            exam_type: str,
            source: str
    ) -> Dict[str, Any]:
        num_parts = 2 if exam_type == "controle" else 4

        if context:
            prompt = f"""You are creating a Tunisian Baccalaureate exercise.

RETRIEVED CONTEXT (source: {source}):
{context[:2000]}

Create an AUTHENTIC Tunisian Bac exercise inspired by the context above.
- Subject: {subject} | Language: {language} | Difficulty: {difficulty}
- Type: {"Contrôle 2h" if exam_type == "controle" else "Synthèse 3h"}
- {num_parts} parts (a, b, c...) | Grading: /20 | NO multiple choice

Respond ONLY with valid JSON:
{{
    "title": "Exercise title in {language}",
    "introduction": "Context/data given to student",
    "total_points": 5,
    "parts": [
        {{
            "part": "a",
            "question": "Question in {language}",
            "points": 2,
            "solution": "Step-by-step solution"
        }}
    ]
}}"""
        else:
            prompt = f"""Create an AUTHENTIC Tunisian Baccalaureate exercise from your knowledge.

- Subject: {subject} | Query: {query}
- Language: {language} | Difficulty: {difficulty}
- Type: {"Contrôle 2h" if exam_type == "controle" else "Synthèse 3h"}
- {num_parts} parts | Grading: /20 | NO multiple choice

Respond ONLY with valid JSON:
{{
    "title": "Exercise title in {language}",
    "introduction": "Context/data given to student",
    "total_points": 5,
    "parts": [
        {{
            "part": "a",
            "question": "Question in {language}",
            "points": 2,
            "solution": "Step-by-step solution"
        }}
    ]
}}"""

        try:
            response = self.llm.invoke(prompt)
            exercise = self.json_parser.parse(response.content)

            if exercise and "parts" in exercise and len(exercise.get("parts", [])) >= 1:
                logger.info(f"✅ Exercise: {len(exercise['parts'])} parts generated")
                return self._to_api_format(exercise, subject, language)

            logger.warning("⚠️ Invalid structure — using hardcoded fallback")
            return self._hardcoded_exercise(query, language, subject, exam_type)

        except Exception as e:
            logger.error(f"Exercise generation error: {e}")
            return self._hardcoded_exercise(query, language, subject, exam_type)

    def _to_api_format(self, exercise: Dict, subject: str, language: str) -> Dict:
        parts_text = [
            f"{p.get('part','a')}) {p.get('question','')} ({p.get('points',1)} pt)"
            for p in exercise.get("parts", [])
        ]
        full_q = f"{exercise.get('title', 'Exercise')}\n\n"
        if exercise.get("introduction"):
            full_q += f"{exercise['introduction']}\n\n"
        full_q += "\n\n".join(parts_text)

        correction = "\n\n".join([
            f"{p.get('part','a')}) {p.get('solution','')}"
            for p in exercise.get("parts", [])
        ])

        return {
            "question": full_q,
            "type": "exercise",
            "subject": subject,
            "points": exercise.get("total_points", 5),
            "correction": correction,
            "explanation": correction,
            "parts": exercise.get("parts", []),
            "structure": "multi_part_exercise"
        }

    def _hardcoded_exercise(self, query, language, subject, exam_type) -> Dict:
        return {
            "question": (
                f"Exercice: {query.title()} (5 points)\n\n"
                f"1.a) Partie a (2.5 points)\n"
                f"1.b) Partie b (2.5 points)"
            ),
            "type": "exercise", "subject": subject, "points": 5,
            "correction": "1.a) Solution\n\n1.b) Solution",
            "explanation": "Voir correction",
            "parts": [], "structure": "multi_part_exercise"
        }

    # ──────────────────────────────────────────────────────────
    # FINAL FALLBACK
    # ──────────────────────────────────────────────────────────

    def _make_fallback_response(
            self, query, language, subject, difficulty, exam_type
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "query": query, "language": language,
            "question_type": "exercise", "difficulty": difficulty,
            "generation": self._hardcoded_exercise(
                query, language, subject, exam_type
            ),
            "confidence": 0.3,
            "context_source": "fallback",
            "reflection": None,
            "model_used": "fallback"
        }


# ─────────────────────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────────────────────

def test_adaptive_rag():
    print("🧪 TESTING ADAPTIVE RAG GENERATOR")
    print("=" * 60)
    generator = EnhancedRAGGenerator()
    result = generator.generate_exam_question(
        query="étude de fonctions polynomiales",
        subject="mathématiques",
        field="sciences",
        language="french",
        difficulty="medium",
        exam_type="controle"
    )
    print(f"✅ Success: {result['success']}")
    print(f"🏆 Best source: {result['context_source']}")
    print(f"💯 Final confidence: {result['confidence']}")
    print(f"📊 All sources: {result.get('sources_confidence', {})}")
    if result["success"]:
        print(f"\n📝 Preview:\n{result['generation'].get('question','')[:300]}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_adaptive_rag()
