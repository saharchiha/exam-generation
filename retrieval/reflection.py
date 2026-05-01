# reflection.py
import logging
import json
import re
import os
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class JSONOutputParser:
    """Parse LLM output as JSON with enhanced error handling"""

    def parse(self, text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response with multiple fallback strategies"""
        try:
            text = text.strip()

            # Remove markdown code blocks
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()

            # Enhanced JSON extraction with better error handling
            cleaned_text = self._extract_and_clean_json(text)

            # Parse the cleaned JSON
            return json.loads(cleaned_text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Raw text was: {text[:500]}...")
            return {"error": f"JSON parsing failed: {e}", "raw_text": text}
        except Exception as e:
            logger.error(f"Unexpected error in JSON parsing: {e}")
            return {"error": f"Unexpected parsing error: {e}", "raw_text": text}

    def _extract_and_clean_json(self, text: str) -> str:
        """Extract and clean JSON from text with enhanced handling"""
        # Try to find JSON object pattern
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)

        if matches:
            # Return the first valid JSON object
            for match in matches:
                try:
                    # Test if it's valid JSON
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue

        # If no valid JSON found, try to fix common issues
        return self._fix_common_json_issues(text)

    def _fix_common_json_issues(self, text: str) -> str:
        """Fix common JSON formatting issues"""
        # Fix unescaped quotes within strings
        text = re.sub(r'(?<!\\)"', '"', text)

        # Fix trailing commas
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        # Fix missing quotes around keys
        text = re.sub(r'(\w+):', r'"\1":', text)

        return text


class SelfReflectionValidator:
    """
    Handles self-reflection and validation of generated exam questions
    with enhanced quality checks and confidence scoring
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.json_parser = JSONOutputParser()

    def validate_question_quality(self,
                                  question: str,
                                  context: str,
                                  language: str,
                                  question_type: str = "multiple_choice") -> Dict[str, Any]:
        """
        Validate the quality, accuracy, and relevance of a generated question
        """
        try:
            prompt = self._create_validation_prompt(question_type)

            formatted_prompt = prompt.format(
                question=question,
                context=context[:2000],  # Limit context length
                language=language,
                question_type=question_type
            )

            response = self.llm.invoke(formatted_prompt)
            result = self.json_parser.parse(response.content)

            # Handle parsing errors gracefully
            if "error" in result:
                logger.warning("Validation parsing failed, using default validation")
                return self._get_default_validation()

            # Enhance result with additional metrics
            enhanced_result = self._enhance_validation_result(result, question, context)
            return enhanced_result

        except Exception as e:
            logger.error(f"Error in question validation: {e}")
            return self._get_default_validation()

    def validate_answer_accuracy(self,
                                 question: str,
                                 generated_answer: str,
                                 context: str,
                                 language: str) -> Dict[str, Any]:
        """
        Validate the accuracy of generated answers against context
        """
        try:
            prompt = ChatPromptTemplate.from_template("""
You are an expert educational validator. Analyze the accuracy and factual correctness of an answer.

QUESTION: {question}
GENERATED ANSWER: {generated_answer}
CONTEXT FROM DATABASE: {context}
LANGUAGE: {language}

CRITICAL: Respond with ONLY valid JSON. No explanatory text.

Provide this EXACT JSON structure:
{{
    "is_factually_correct": true,
    "confidence_score": 0.85,
    "factual_errors": [],
    "missing_information": [],
    "context_alignment": "high|medium|low",
    "suggested_improvements": [],
    "overall_accuracy": "high|medium|low"
}}

Consider:
1. Is the answer factually correct based on the context?
2. Does it contain any hallucinations or invented information?
3. Is all relevant information from context included?
4. Is the answer complete and comprehensive?
5. Does it align with educational standards?

Respond with ONLY the JSON object.
""")

            response = self.llm.invoke(prompt.format(
                question=question,
                generated_answer=generated_answer,
                context=context[:1500],
                language=language
            ))

            result = self.json_parser.parse(response.content)

            if "error" in result:
                return {
                    "is_factually_correct": True,  # Default to true to avoid blocking
                    "confidence_score": 0.5,
                    "factual_errors": ["Validation parsing failed"],
                    "missing_information": [],
                    "context_alignment": "unknown",
                    "suggested_improvements": ["Manual review recommended"],
                    "overall_accuracy": "unknown"
                }

            return result

        except Exception as e:
            logger.error(f"Error in answer validation: {e}")
            return {
                "is_factually_correct": True,
                "confidence_score": 0.3,
                "factual_errors": ["Validation process failed"],
                "missing_information": [],
                "context_alignment": "unknown",
                "suggested_improvements": ["System validation error"],
                "overall_accuracy": "unknown"
            }

    def calculate_overall_confidence(self,
                                     quality_validation: Dict[str, Any],
                                     answer_validation: Dict[str, Any],
                                     retrieval_confidence: float) -> float:
        """
        Calculate overall confidence score combining multiple validation metrics
        """
        try:
            # Quality validation confidence (40% weight)
            quality_conf = quality_validation.get("confidence_score", 0.5)
            quality_weight = 0.4

            # Answer accuracy confidence (30% weight)
            answer_conf = answer_validation.get("confidence_score", 0.5)
            answer_weight = 0.3

            # Retrieval confidence (30% weight)
            retrieval_weight = 0.3

            # Calculate weighted average
            overall_confidence = (
                    quality_conf * quality_weight +
                    answer_conf * answer_weight +
                    retrieval_confidence * retrieval_weight
            )

            # Apply penalties for issues found
            if quality_validation.get("issues_found"):
                overall_confidence *= 0.8

            if answer_validation.get("factual_errors"):
                overall_confidence *= 0.7

            # Ensure confidence is within bounds
            return max(0.1, min(1.0, overall_confidence))

        except Exception as e:
            logger.error(f"Error calculating overall confidence: {e}")
            return 0.5  # Default confidence

    def _create_validation_prompt(self, question_type: str) -> ChatPromptTemplate:
        """Create validation prompt based on question type"""

        base_template = """
You are an expert educational validator. Analyze the exam question for quality, accuracy, and educational value.

QUESTION TO VALIDATE:
{question}

CONTEXT FROM EXAM DATABASE:
{context}

LANGUAGE: {language}
QUESTION TYPE: {question_type}

CRITICAL: Respond with ONLY valid JSON. No explanatory text before or after.

Provide this EXACT JSON structure:
{{
    "is_valid": true,
    "confidence_score": 0.85,
    "issues_found": [],
    "suggestions": [],
    "relevance_to_context": "high|medium|low",
    "educational_value": "high|medium|low",
    "clarity": "high|medium|low",
    "difficulty_match": "high|medium|low",
    "bias_check": "none|minor|significant"
}}

Validation Criteria:
1. FACTUAL ACCURACY: Is the question factually correct based on context?
2. CLARITY: Is the question clear and unambiguous?
3. RELEVANCE: Does it align with context examples?
4. EDUCATIONAL VALUE: Does it test appropriate knowledge/skills?
5. DIFFICULTY: Is the difficulty level appropriate?
6. BIAS: Is the question free from bias or cultural insensitivity?
7. ORIGINALITY: Is it sufficiently different from context examples?

Respond with ONLY the JSON object.
"""

        # Type-specific additions
        if question_type == "multiple_choice":
            base_template += """
For multiple choice questions specifically check:
- All options are plausible but distinct
- Only one clearly correct answer
- No trick questions or ambiguous phrasing
- Options are parallel in structure and length
"""
        elif question_type == "open_ended":
            base_template += """
For open-ended questions specifically check:
- Clear evaluation criteria are implied
- Requires critical thinking, not just recall
- Appropriate scope for expected answer length
"""
        elif question_type == "essay":
            base_template += """
For essay questions specifically check:
- Prompts deep analysis, not just summary
- Clear focus and scope
- Appropriate for expected writing level
"""

        return ChatPromptTemplate.from_template(base_template)

    def _enhance_validation_result(self,
                                   result: Dict[str, Any],
                                   question: str,
                                   context: str) -> Dict[str, Any]:
        """Enhance validation result with additional metrics"""

        # Calculate automatic metrics
        question_length = len(question)
        context_length = len(context)

        # Add complexity score based on question length and structure
        complexity_score = min(1.0, question_length / 500)  # Normalize

        # Add context utilization score
        context_utilization = min(1.0, len(context) / 1000) if context else 0

        enhanced_result = result.copy()
        enhanced_result.update({
            "automatic_metrics": {
                "question_complexity": round(complexity_score, 3),
                "context_utilization": round(context_utilization, 3),
                "question_length": question_length,
                "context_reference_length": context_length
            },
            "validation_timestamp": self._get_timestamp()
        })

        return enhanced_result

    def _get_default_validation(self) -> Dict[str, Any]:
        """Return default validation result when validation fails"""
        return {
            "is_valid": True,  # Default to valid to avoid blocking generation
            "confidence_score": 0.5,
            "issues_found": ["Validation process failed"],
            "suggestions": ["Manual review recommended"],
            "relevance_to_context": "unknown",
            "educational_value": "medium",
            "clarity": "medium",
            "difficulty_match": "unknown",
            "bias_check": "unknown"
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp for validation tracking"""
        from datetime import datetime
        return datetime.now().isoformat()


class ReflectionManager:
    """
    Main manager for all reflection and validation operations
    """

    def __init__(self, llm: ChatOpenAI):
        self.validator = SelfReflectionValidator(llm)
        logger.info("ReflectionManager initialized")

    def perform_complete_validation(self,
                                    question: str,
                                    context: str,
                                    language: str,
                                    question_type: str,
                                    retrieval_confidence: float,
                                    generated_answer: str = None) -> Dict[str, Any]:
        """
        Perform complete validation including question quality and answer accuracy
        """
        try:
            # Validate question quality
            quality_validation = self.validator.validate_question_quality(
                question=question,
                context=context,
                language=language,
                question_type=question_type
            )

            # Validate answer accuracy if provided
            answer_validation = {}
            if generated_answer:
                answer_validation = self.validator.validate_answer_accuracy(
                    question=question,
                    generated_answer=generated_answer,
                    context=context,
                    language=language
                )
            else:
                # Create default answer validation
                answer_validation = {
                    "is_factually_correct": True,
                    "confidence_score": 0.7,
                    "factual_errors": [],
                    "missing_information": [],
                    "context_alignment": "unknown",
                    "overall_accuracy": "unknown"
                }

            # Calculate overall confidence
            overall_confidence = self.validator.calculate_overall_confidence(
                quality_validation=quality_validation,
                answer_validation=answer_validation,
                retrieval_confidence=retrieval_confidence
            )

            # Compile comprehensive results
            validation_result = {
                "success": True,
                "overall_confidence": round(overall_confidence, 3),
                "quality_validation": quality_validation,
                "answer_validation": answer_validation,
                "retrieval_confidence": retrieval_confidence,
                "final_decision": self._make_final_decision(quality_validation, answer_validation, overall_confidence),
                "recommendations": self._generate_recommendations(quality_validation, answer_validation)
            }

            logger.info(f"Complete validation completed with confidence: {overall_confidence:.3f}")
            return validation_result

        except Exception as e:
            logger.error(f"Error in complete validation: {e}")
            return {
                "success": False,
                "error": str(e),
                "overall_confidence": 0.3,
                "final_decision": "manual_review_required"
            }

    def _make_final_decision(self,
                             quality_validation: Dict[str, Any],
                             answer_validation: Dict[str, Any],
                             overall_confidence: float) -> str:
        """Make final decision about question validity"""

        # Check critical failures
        if not quality_validation.get("is_valid", True):
            return "reject"

        if not answer_validation.get("is_factually_correct", True):
            return "reject"

        # Check confidence thresholds
        if overall_confidence >= 0.8:
            return "accept"
        elif overall_confidence >= 0.6:
            return "accept_with_review"
        else:
            return "manual_review_required"

    def _generate_recommendations(self,
                                  quality_validation: Dict[str, Any],
                                  answer_validation: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on validation results"""
        recommendations = []

        # Add quality recommendations
        quality_issues = quality_validation.get("issues_found", [])
        if quality_issues:
            recommendations.append(f"Address quality issues: {', '.join(quality_issues[:3])}")

        quality_suggestions = quality_validation.get("suggestions", [])
        if quality_suggestions:
            recommendations.extend(quality_suggestions[:2])

        # Add accuracy recommendations
        factual_errors = answer_validation.get("factual_errors", [])
        if factual_errors:
            recommendations.append(f"Fix factual errors: {', '.join(factual_errors[:2])}")

        missing_info = answer_validation.get("missing_information", [])
        if missing_info:
            recommendations.append(f"Add missing information: {', '.join(missing_info[:2])}")

        # Ensure we have at least one recommendation
        if not recommendations:
            recommendations.append("Question meets quality standards")

        return recommendations[:5]  # Limit to top 5 recommendations


# Utility function to create reflection manager
def create_reflection_manager(model_name: str = "openai/gpt-4o", api_key: str = None) -> ReflectionManager:
    """Create a reflection manager with the specified LLM"""
    llm = ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.1,  # Low temperature for consistent validation
        max_tokens=1000,
        timeout=30
    )

    return ReflectionManager(llm)


# Test function
def test_reflection_system():
    """Test the reflection system"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    print("🧪 TESTING REFLECTION SYSTEM")
    print("=" * 50)

    try:
        # Load API key from .env
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY missing in .env")

        reflection_manager = create_reflection_manager(api_key=api_key)

        # Test data
        test_question = "Quelle est la dérivée de la fonction f(x) = 3x^2 + 2x - 5?"
        test_context = "Document 1: Calculus basics - Derivatives measure rate of change. The derivative of x^n is n*x^(n-1)."
        test_language = "french"
        test_retrieval_confidence = 0.75

        print("Testing question validation...")
        result = reflection_manager.perform_complete_validation(
            question=test_question,
            context=test_context,
            language=test_language,
            question_type="multiple_choice",
            retrieval_confidence=test_retrieval_confidence
        )

        print(f"✅ Validation successful: {result['success']}")
        print(f"🎯 Overall confidence: {result['overall_confidence']}")
        print(f"📋 Final decision: {result['final_decision']}")
        print(f"💡 Recommendations: {result['recommendations']}")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_reflection_system()