import logging
import os
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import quote
import re
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import json

load_dotenv()
logger = logging.getLogger(__name__)


class TunisianBacSearchEngine:
    """
    Search and extract REAL Tunisian Baccalaureate exams from the web.
    Used as the RAG retrieval source — replaces Weaviate when local data is insufficient.
    """

    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cx = os.getenv("GOOGLE_CX")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Known Tunisian education websites
        self.trusted_sources = [
            'devoir.tn',
            'bacweb.tn',
            'education.gov.tn',
            'bac.tn',
            'devoirs.tn',
            'epreuvebac.tn'
        ]

    async def search_real_bac_exams(
            self,
            subject: str,
            field: str,
            year: str,
            session: str,
            language: str,
            max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for REAL Tunisian Baccalaureate exams online"""
        try:
            query = self._build_bac_query(subject, field, year, session, language)
            logger.info(f"🔍 Searching for real Tunisian Bac exams: {query}")

            search_results = await self._google_search_bac(query, max_results)

            if not search_results:
                logger.warning("No Google results, trying broader query...")
                alt_query = f"bac tunisie {subject} sujet corrigé pdf"
                search_results = await self._google_search_bac(alt_query, max_results)

            exam_contents = []
            for result in search_results[:3]:
                content = await self._extract_exam_content(result['url'])
                if content:
                    exam_contents.append({
                        'title': result['title'],
                        'url': result['url'],
                        'content': content,
                        'snippet': result['snippet'],
                        'confidence': result['confidence']
                    })

            logger.info(f"✅ Found {len(exam_contents)} real exam contents")
            return exam_contents

        except Exception as e:
            logger.error(f"Error searching real bac exams: {e}")
            return []

    def _build_bac_query(self, subject, field, year, session, language) -> str:
        """Build optimized search query for Tunisian Bac"""
        subject_map = {
            'mathématiques': 'mathématiques', 'mathematics': 'mathématiques', 'math': 'mathématiques',
            'physique': 'sciences physiques', 'physics': 'sciences physiques',
            'chimie': 'sciences physiques', 'chemistry': 'sciences physiques',
            'svt': 'sciences de la vie et de la terre', 'biology': 'sciences de la vie et de la terre',
            'philosophie': 'philosophie', 'philosophy': 'philosophie',
            'français': 'français', 'french': 'français',
            'arabe': 'arabe', 'arabic': 'arabe',
            'anglais': 'anglais', 'english': 'anglais'
        }
        subject_clean = subject_map.get(subject.lower(), subject)
        return f'bac tunisie {year} {session} {subject_clean} sujet corrigé'

    async def _google_search_bac(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Google specifically for Tunisian Bac content"""
        try:
            if not self.google_api_key or not self.google_cx:
                logger.error("❌ GOOGLE_API_KEY or GOOGLE_CX not set in .env")
                return []

            site_restriction = ' OR '.join([f'site:{site}' for site in self.trusted_sources])
            enhanced_query = f'{query} ({site_restriction}) filetype:pdf OR exercice OR sujet'

            params = {
                'key': self.google_api_key,
                'cx': self.google_cx,
                'q': enhanced_query,
                'num': min(max_results, 10),
                'lr': 'lang_fr',
                'gl': 'tn'
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params=params
                )

                if response.status_code != 200:
                    logger.warning(f"Google API returned status {response.status_code}")
                    return []

                data = response.json()
                results = []

                for item in data.get('items', [])[:max_results]:
                    url = item.get('link', '')
                    is_trusted = any(source in url for source in self.trusted_sources)
                    is_pdf = url.lower().endswith('.pdf')
                    confidence = 0.95 if (is_trusted and is_pdf) else 0.85 if is_trusted else 0.7

                    results.append({
                        'title': item.get('title', ''),
                        'snippet': item.get('snippet', ''),
                        'url': url,
                        'is_pdf': is_pdf,
                        'is_trusted': is_trusted,
                        'confidence': confidence
                    })

                results.sort(key=lambda x: x['confidence'], reverse=True)

                if results:
                    logger.info(f"✅ Google found {len(results)} Tunisian Bac results")
                return results

        except Exception as e:
            logger.error(f"Google Bac search failed: {e}")
            return []

    async def _extract_exam_content(self, url: str) -> Optional[str]:
        """Extract exam content from webpage or PDF"""
        try:
            if url.lower().endswith('.pdf'):
                return await self._extract_pdf_content(url)
            else:
                return await self._extract_html_content(url)
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None

    async def _extract_html_content(self, url: str) -> Optional[str]:
        """Extract exam content from HTML page"""
        try:
            async with httpx.AsyncClient(
                timeout=15.0, headers=self.headers, follow_redirects=True
            ) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.text, 'html.parser')

                # Remove scripts and styles
                for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()

                # Extract main content
                content_selectors = [
                    'article', '.exam-content', '.sujet', '.exercice',
                    '.content', 'main', '#content', '.post-content'
                ]
                for selector in content_selectors:
                    element = soup.select_one(selector)
                    if element:
                        text = element.get_text(separator='\n', strip=True)
                        if len(text) > 200:
                            return text[:2000]

                # Fallback: all paragraphs
                paragraphs = soup.find_all('p')
                text = '\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
                return text[:2000] if len(text) > 100 else None

        except Exception as e:
            logger.error(f"HTML extraction failed for {url}: {e}")
            return None

    async def _extract_pdf_content(self, url: str) -> Optional[str]:
        """Download and extract text from PDF"""
        try:
            async with httpx.AsyncClient(
                timeout=30.0, headers=self.headers, follow_redirects=True
            ) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None

                # Try PyPDF2
                try:
                    import io
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(response.content))
                    text = ""
                    for page_num in range(min(3, len(pdf_reader.pages))):
                        text += pdf_reader.pages[page_num].extract_text() + "\n"
                    return text[:2000] if text.strip() else None
                except ImportError:
                    logger.warning("PyPDF2 not installed — cannot extract PDF content")
                    return f"[PDF available at: {url}]"

        except Exception as e:
            logger.error(f"PDF extraction failed for {url}: {e}")
            return None


class EnhancedBacExamGenerator:
    """
    Full exam generator: searches real Tunisian Bac exams online,
    then generates an authentic exam based on the retrieved content.
    """

    def __init__(self, model_name: str = "openai/gpt-4o"):
        self.search_engine = TunisianBacSearchEngine()
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY missing in .env")

        self.llm = ChatOpenAI(
            model=model_name,
            openai_api_key=openrouter_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.7,
            max_tokens=2500
        )

    async def generate_authentic_exam(
            self,
            subject: str,
            field: str,
            year: str,
            session: str,
            language: str,
            num_questions: int = 4,
            difficulty: str = "medium"
    ) -> Dict[str, Any]:
        """Generate an authentic Tunisian Bac exam using web RAG"""
        try:
            # Step 1: Search for real exam examples
            real_exams = await self.search_engine.search_real_bac_exams(
                subject=subject, field=field, year=year,
                session=session, language=language, max_results=5
            )

            # Step 2: Generate based on results
            if real_exams:
                context = "\n\n".join([
                    f"Source: {e['title']}\n{e['content'][:600]}"
                    for e in real_exams[:3]
                ])
                exam = await self._generate_from_real_exams(
                    context, subject, field, language,
                    num_questions, difficulty, real_exams
                )
                source_type = "real_web_rag"
            else:
                exam = await self._generate_from_knowledge(
                    subject, field, language, num_questions, difficulty
                )
                source_type = "knowledge"

            return {
                "success": True,
                "source_type": source_type,
                "sources": real_exams[:3] if real_exams else [],
                "exam": exam
            }

        except Exception as e:
            logger.error(f"generate_authentic_exam error: {e}")
            return {
                "success": False,
                "error": str(e),
                "exam": self._create_fallback_exam(subject, field, language, num_questions)
            }

    async def _generate_from_real_exams(
            self, context, subject, field, language,
            num_questions, difficulty, real_exam_sources
    ) -> Dict[str, Any]:
        """Generate exam based on REAL web examples"""
        prompt = f"""You are creating a Tunisian Baccalaureate exam based on REAL exam examples.

REAL EXAM EXAMPLES FROM TUNISIA:
{context}

Create an AUTHENTIC Tunisian Baccalaureate exam that mimics the structure above.
- Subject: {subject} | Field: {field} | Language: {language}
- Exercises: {num_questions} | Difficulty: {difficulty}
- Grading: 0-20 points | Duration: 3 hours
- NO simple multiple choice — use complex open-ended problems with parts a, b, c...

Respond ONLY with valid JSON:
{{
    "exam_title": "Baccalauréat Tunisien - {subject}",
    "subject": "{subject}",
    "field": "{field}",
    "language": "{language}",
    "total_duration": "3 heures",
    "total_points": 20,
    "exercises": [
        {{
            "exercise_number": 1,
            "title": "Exercise title",
            "points": 5,
            "parts": [
                {{"part": "a", "question": "Question text", "points": 2}},
                {{"part": "b", "question": "Question text", "points": 3}}
            ],
            "correction": {{"part_a": "Solution a", "part_b": "Solution b"}}
        }}
    ],
    "sources_used": {[s['url'] for s in real_exam_sources[:2]]}
}}"""

        try:
            response = self.llm.invoke(prompt)
            result = self._parse_json_response(response.content)
            if result and 'exercises' in result:
                return result
            return self._create_fallback_exam(subject, field, language, num_questions)
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return self._create_fallback_exam(subject, field, language, num_questions)

    async def _generate_from_knowledge(
            self, subject, field, language, num_questions, difficulty
    ) -> Dict[str, Any]:
        """Generate exam from LLM knowledge when no web results found"""
        prompt = f"""Create an AUTHENTIC Tunisian Baccalaureate exam.
Subject: {subject} | Field: {field} | Language: {language}
Exercises: {num_questions} | Difficulty: {difficulty}
Grading: 0-20 | Duration: 3h | Complex multi-part exercises only.
Respond ONLY with valid JSON with exercises array."""

        try:
            response = self.llm.invoke(prompt)
            result = self._parse_json_response(response.content)
            return result or self._create_fallback_exam(subject, field, language, num_questions)
        except Exception as e:
            logger.error(f"Knowledge generation error: {e}")
            return self._create_fallback_exam(subject, field, language, num_questions)

    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """Parse JSON from LLM response"""
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end != -1:
                text = text[start:end + 1]
            return json.loads(text)
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")
            return None

    def _create_fallback_exam(self, subject, field, language, num_questions) -> Dict[str, Any]:
        """Basic fallback exam structure"""
        return {
            "exam_title": f"Baccalauréat Tunisien - {subject.title()}",
            "subject": subject, "field": field, "language": language,
            "total_duration": "3 heures", "total_points": 20,
            "exercises": [
                {
                    "exercise_number": i + 1,
                    "title": f"Exercice {i + 1}" if language == "french" else f"Exercise {i + 1}",
                    "points": 20 // num_questions,
                    "parts": [{"part": "a", "question": f"Question {i+1}a about {subject}", "points": 5}],
                    "correction": {"part_a": "Detailed solution here"}
                } for i in range(num_questions)
            ],
            "note": "Fallback exam — web search returned no results"
        }


# Test
async def test_real_bac_search():
    print("🧪 TESTING REAL TUNISIAN BAC EXAM SEARCH")
    print("=" * 60)

    generator = EnhancedBacExamGenerator()
    result = await generator.generate_authentic_exam(
        subject="mathématiques", field="sciences",
        year="2024", session="principale",
        language="french", num_questions=4, difficulty="medium"
    )

    print(f"✅ Success: {result['success']}")
    print(f"📚 Source type: {result.get('source_type')}")
    print(f"🔗 Sources found: {len(result.get('sources', []))}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_real_bac_search())
