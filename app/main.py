import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import os
import sys
from datetime import datetime
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S'
)
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generation.rag_gen import EnhancedRAGGenerator

app = FastAPI(title="Tunisian Baccalaureate Exam Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize enhanced generator
logger.info("Initializing Enhanced RAG Generator...")
rag_generator = EnhancedRAGGenerator()
logger.info("✅ Enhanced generator initialized successfully")

# Store generated exams
exam_storage = {}


class ExamRequest(BaseModel):
    field: str
    subject: str
    language: str
    type: str  # 'controle' ou 'synthese'
    session: str
    difficulty: str
    num_questions: int
    themes: Optional[str] = ""
    lycee: Optional[str] = ""
    professeur: Optional[str] = ""


class ExamResponse(BaseModel):
    exam_id: str
    status: str
    message: str
    exam_content: Optional[dict] = None


def _validate_question(question: Dict) -> bool:
    """RELAXED validation - accept more questions"""
    try:
        if not question.get("question"):
            return False
        return True
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


def _enhance_question_quality(question: Dict, subject: str, language: str) -> Dict:
    """Enhance question to match Tunisian bac style"""
    if not question.get("subject"):
        question["subject"] = subject
    if not question.get("points"):
        question["points"] = 5
    return question


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Générateur de Devoirs - Baccalauréat Tunisien",
        "version": "3.0.0 - Format Tunisien Authentique",
        "status": "running",
        "features": [
            "Génération de devoirs de contrôle (2h)",
            "Génération de devoirs de synthèse (3h)",
            "Format authentique tunisien",
            "Thèmes personnalisables",
            "Support multilingue (Français/Arabe/Anglais)"
        ],
        "endpoints": {
            "generate": "/api/generate-exam",
            "download": "/api/download-exam/{exam_id}",
            "get_exam": "/api/exam/{exam_id}"
        }
    }


@app.post("/api/generate-exam", response_model=ExamResponse)
async def generate_exam(request: ExamRequest):
    """Generate Tunisian baccalaureate exam (Contrôle or Synthèse)"""
    logger.info(f"🎓 Generating Tunisian Bac Exam: {request.subject} ({request.field})")
    logger.info(f"   Type: {request.type.upper()}, Language: {request.language}")
    logger.info(f"   Exercises: {request.num_questions}, Themes: {request.themes or 'Auto'}")
    logger.info(f"   Lycée: {request.lycee or 'Non spécifié'}, Prof: {request.professeur or 'Non spécifié'}")

    try:
        exam_id = str(uuid.uuid4())
        logger.info(f"🆔 Exam ID: {exam_id}")

        # Parse themes
        themes_list = []
        if request.themes:
            themes_list = [t.strip() for t in request.themes.split(',') if t.strip()]
            logger.info(f"📚 Themes specified: {themes_list}")

        # Build intelligent queries for each exercise
        base_queries = _generate_exercise_queries(
            subject=request.subject,
            num_exercises=request.num_questions,
            difficulty=request.difficulty,
            themes=themes_list,
            exam_type=request.type
        )

        # CORRECTION 1: S'assurer qu'on a exactement num_questions queries
        if len(base_queries) < request.num_questions:
            logger.warning(f"⚠️ Only {len(base_queries)} queries generated, padding to {request.num_questions}")
            while len(base_queries) < request.num_questions:
                base_queries.append(base_queries[0])  # Duplicate queries if needed

        all_exercises = []
        generation_stats = {
            "rag_success": 0,
            "web_search_used": 0,
            "fallback_used": 0,
            "total_attempted": request.num_questions
        }

        # CORRECTION 2: Générer TOUS les exercices demandés
        for i in range(request.num_questions):
            query = base_queries[i] if i < len(base_queries) else base_queries[0]
            logger.info(f"🔍 Generating exercise {i + 1}/{request.num_questions}...")
            logger.info(f"   Query: {query}")

            try:
                result = rag_generator.generate_exam_question(
                    query=query,
                    language=request.language,
                    question_type="exercise",
                    difficulty=request.difficulty,
                    subject=request.subject,
                    field=request.field,
                    exam_type=request.type
                )

                if result.get("success"):
                    generation = result.get("generation", {})

                    enhanced_exercise = _enhance_question_quality(
                        question=generation,
                        subject=request.subject,
                        language=request.language
                    )

                    if _validate_question(enhanced_exercise):
                        exercise_data = {
                            "exercise_number": i + 1,
                            "text": enhanced_exercise.get("question", ""),
                            "type": "exercise",
                            "points": 5,
                            "correction": enhanced_exercise.get("correction", ""),
                            "parts": enhanced_exercise.get("parts", []),
                            "confidence": result.get("confidence", 0.7)
                        }

                        all_exercises.append(exercise_data)

                        context_source = result.get("context_source", "unknown")
                        if context_source == "rag":
                            generation_stats["rag_success"] += 1
                        elif context_source == "web_search":
                            generation_stats["web_search_used"] += 1
                        else:
                            generation_stats["fallback_used"] += 1

                        logger.info(f"   ✅ Exercise {i + 1} generated (source: {context_source})")
                    else:
                        logger.warning(f"   ⚠️ Exercise {i + 1} failed validation")
                else:
                    logger.warning(f"   ⚠️ Failed to generate exercise {i + 1}")

            except Exception as e:
                logger.error(f"   ❌ Error generating exercise {i + 1}: {e}")
                continue

        # Ensure we have at least some exercises
        if len(all_exercises) == 0:
            logger.error("❌ No exercises generated successfully!")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate any valid exercises. Please try again."
            )

        # Determine duration based on type
        duration = "2 heures" if request.type == "controle" else "3 heures"

        # Create exam content in Tunisian format
        exam_content = {
            "exam_title": f"Devoir de {request.type.capitalize()}",
            "subject": request.subject,
            "field": request.field,
            "language": request.language,
            "type": request.type,
            "session": request.session,
            "difficulty": request.difficulty,
            "duration": duration,
            "themes": themes_list,
            "exercises": all_exercises,
            "total_points": 20,
            # CORRECTION 3: Stocker les infos lycée et professeur
            "lycee": request.lycee or "Lycée Pilote",
            "professeur": request.professeur or "[Nom du professeur]",
            "generation_info": {
                "model_used": "gpt-4o via OpenRouter",
                "exercises_generated": len(all_exercises),
                "exercises_requested": request.num_questions,
                "success_rate": len(all_exercises) / request.num_questions,
                "avg_confidence": sum(e["confidence"] for e in all_exercises) / len(all_exercises),
                "rag_success": generation_stats["rag_success"],
                "web_search_used": generation_stats["web_search_used"],
                "fallback_used": generation_stats["fallback_used"]
            }
        }

        # Store exam
        exam_storage[exam_id] = {
            "content": exam_content,
            "metadata": {
                "field": request.field,
                "subject": request.subject,
                "language": request.language,
                "type": request.type,
                "session": request.session,
                "difficulty": request.difficulty,
                "num_questions": request.num_questions,
                "themes": request.themes,
                "lycee": request.lycee,
                "professeur": request.professeur,
                "generated_at": datetime.now().isoformat()
            }
        }

        logger.info(f"✅ Exam {exam_id} generated successfully!")
        logger.info(f"📊 Stats: RAG={generation_stats['rag_success']}, "
                    f"Web={generation_stats['web_search_used']}, "
                    f"Fallback={generation_stats['fallback_used']}")

        return ExamResponse(
            exam_id=exam_id,
            status="success",
            message=f"Generated {len(all_exercises)} exercises successfully",
            exam_content=exam_content
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Critical error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _generate_exercise_queries(
        subject: str,
        num_exercises: int,
        difficulty: str,
        themes: List[str],
        exam_type: str
) -> List[str]:
    """Generate DIVERSE queries for exercise generation based on themes"""
    topic_templates = {
        "mathématiques": [
            "étude complète de fonctions",
            "calcul de limites et continuité",
            "dérivées et applications",
            "primitives et intégrales",
            "suites numériques et convergence",
            "nombres complexes",
            "probabilités et statistiques",
            "géométrie dans l'espace",
            "équations différentielles"
        ],
        "physique": [
            "mécanique et mouvement",
            "circuits électriques",
            "ondes et vibrations",
            "optique géométrique",
            "thermodynamique",
            "électromagnétisme"
        ],
        "sciences": [
            "génétique et hérédité",
            "biologie cellulaire",
            "physiologie",
            "écologie",
            "géologie"
        ]
    }

    queries = []

    # If themes are specified, use them
    if themes:
        for i, theme in enumerate(themes[:num_exercises]):
            complexity = "exercice détaillé" if exam_type == "synthese" else "exercice court"
            queries.append(f"{theme} {complexity} niveau baccalauréat tunisien")

        # CORRECTION 4: Si pas assez de thèmes, générer des thèmes supplémentaires
        while len(queries) < num_exercises:
            queries.append(f"{themes[0]} exercice varié niveau baccalauréat tunisien")
    else:
        # Auto-generate diverse queries
        subject_lower = subject.lower()
        topics = []

        for key, topic_list in topic_templates.items():
            if key in subject_lower or subject_lower in key:
                topics = topic_list
                break

        if not topics:
            topics = [f"{subject} - exercice {i + 1}" for i in range(num_exercises)]

        # Generate queries with variation
        import random
        for i in range(num_exercises):
            topic = topics[i % len(topics)]
            complexity = "exercice complet avec plusieurs parties" if exam_type == "synthese" else "exercice ciblé"
            queries.append(f"{topic} {complexity} niveau baccalauréat tunisien")

    logger.info(f"📚 Generated {len(queries)} exercise queries")
    return queries


@app.get("/api/download-exam/{exam_id}")
async def download_exam(exam_id: str):
    """Generate and download PDF in Tunisian format"""
    logger.info(f"📥 Download request: {exam_id}")

    try:
        if exam_id not in exam_storage:
            raise HTTPException(status_code=404, detail="Exam not found")

        exam_data = exam_storage[exam_id]
        pdf_path = generate_tunisian_pdf(exam_id, exam_data)

        return FileResponse(
            path=pdf_path,
            filename=f"devoir_{exam_data['metadata']['type']}_{exam_id[:8]}.pdf",
            media_type="application/pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/exam/{exam_id}")
async def get_exam(exam_id: str):
    """Retrieve exam details"""
    if exam_id not in exam_storage:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam_storage[exam_id]


def generate_tunisian_pdf(exam_id: str, exam_data: dict) -> str:
    """Generate PDF in AUTHENTIC Tunisian Baccalaureate format"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        from reportlab.lib import colors

        output_dir = "generated_exams"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"exam_{exam_id}.pdf")

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()

        metadata = exam_data['metadata']
        content = exam_data['content']
        exam_type = metadata.get('type', 'controle')

        # CORRECTION 5: Utiliser les valeurs du metadata (qui contient lycée et professeur)
        lycee_name = content.get('lycee') or metadata.get('lycee') or "Lycée Pilote"
        prof_name = content.get('professeur') or metadata.get('professeur') or "[Nom du professeur]"

        # ==================== EN-TÊTE TUNISIEN ====================
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=11,
            alignment=TA_LEFT,
            spaceAfter=6
        )

        # Ligne 1: Lycée (gauche) et Date (droite)
        header_table = Table([
            [
                Paragraph(f"<b>{lycee_name}</b>", header_style),
                Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}",
                          ParagraphStyle('HeaderRight', parent=header_style, alignment=TA_RIGHT))
            ]
        ], colWidths=[9 * cm, 9 * cm])

        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        story.append(header_table)

        # Ligne 2: Prof et Classe
        info_table = Table([
            [
                Paragraph(f"<b>Prof:</b> {prof_name}", header_style),
                Paragraph(f"<b>Classe:</b> 4ème {metadata['field'].title()}",
                          ParagraphStyle('InfoRight', parent=header_style, alignment=TA_RIGHT))
            ]
        ], colWidths=[9 * cm, 9 * cm])

        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))

        story.append(info_table)
        story.append(Spacer(1, 0.3 * cm))

        # ==================== TITRE PRINCIPAL ====================
        title_style = ParagraphStyle(
            'TunisianTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        exam_type_display = "Devoir de Contrôle" if exam_type == "controle" else "Devoir de Synthèse"
        title = f"{exam_type_display} - {metadata['subject'].title()}"
        story.append(Paragraph(title, title_style))

        # Durée
        duration_style = ParagraphStyle(
            'Duration',
            parent=styles['Normal'],
            fontSize=11,
            alignment=TA_CENTER,
            spaceAfter=12
        )
        story.append(Paragraph(f"<b>Durée:</b> {content.get('duration', '2 heures')}", duration_style))

        story.append(Spacer(1, 0.5 * cm))

        # ==================== EXERCICES ====================
        exercise_title_style = ParagraphStyle(
            'ExerciseTitle',
            parent=styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceAfter=8,
            alignment=TA_LEFT
        )

        exercise_text_style = ParagraphStyle(
            'ExerciseText',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=10,
            alignment=TA_JUSTIFY,
            leading=14
        )

        if 'exercises' in content:
            for ex in content['exercises']:
                # Titre de l'exercice
                ex_title = f"EXERCICE N°{ex['exercise_number']} : ({ex['points']} points)"
                story.append(Paragraph(ex_title, exercise_title_style))

                # Texte de l'exercice
                story.append(Paragraph(ex['text'], exercise_text_style))

                story.append(Spacer(1, 0.5 * cm))

        # ==================== PAGE CORRECTION ====================
        story.append(PageBreak())

        correction_title_style = ParagraphStyle(
            'CorrectionTitle',
            parent=styles['Heading1'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph("<b>CORRIGÉ</b>", correction_title_style))
        story.append(Spacer(1, 0.5 * cm))

        correction_style = ParagraphStyle(
            'Correction',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=10,
            alignment=TA_JUSTIFY,
            leading=13
        )

        if 'exercises' in content:
            for ex in content['exercises']:
                # Titre exercice
                story.append(Paragraph(f"<b>EXERCICE N°{ex['exercise_number']}:</b>", exercise_title_style))

                # Correction
                if ex.get('correction'):
                    story.append(Paragraph(ex['correction'], correction_style))

                story.append(Spacer(1, 0.4 * cm))

        # Build PDF
        doc.build(story)
        logger.info(f"✅ PDF generated: {pdf_path}")
        return pdf_path

    except ImportError as e:
        logger.warning(f"⚠️ reportlab not available: {e}, creating text file")
        return _create_text_file(exam_id, exam_data)
    except Exception as e:
        logger.error(f"❌ PDF generation error: {e}", exc_info=True)
        return _create_text_file(exam_id, exam_data)


def _create_text_file(exam_id: str, exam_data: dict) -> str:
    """Fallback: Create text file in Tunisian format"""
    output_dir = "generated_exams"
    os.makedirs(output_dir, exist_ok=True)
    txt_path = os.path.join(output_dir, f"exam_{exam_id}.txt")

    with open(txt_path, 'w', encoding='utf-8') as f:
        metadata = exam_data['metadata']
        content = exam_data['content']

        # CORRECTION 6: Utiliser les bonnes valeurs pour lycée et prof
        lycee_name = content.get('lycee') or metadata.get('lycee') or "Lycée Pilote"
        prof_name = content.get('professeur') or metadata.get('professeur') or "[Nom du professeur]"

        # En-tête
        f.write(f"{lycee_name}                                    Date: {datetime.now().strftime('%d/%m/%Y')}\n")
        f.write(f"Prof: {prof_name}                       Classe: 4ème {metadata['field'].title()}\n\n")

        exam_type_display = "Devoir de Contrôle" if metadata['type'] == "controle" else "Devoir de Synthèse"
        f.write(f"                    {exam_type_display} - {metadata['subject'].title()}\n")
        f.write(f"                    Durée: {content.get('duration', '2 heures')}\n")
        f.write("=" * 80 + "\n\n")

        # Exercices
        if 'exercises' in content:
            for ex in content['exercises']:
                f.write(f"EXERCICE N°{ex['exercise_number']} : ({ex['points']} points)\n")
                f.write(f"{ex['text']}\n\n")
                f.write("-" * 80 + "\n\n")

        # Correction
        f.write("\n" + "=" * 80 + "\n")
        f.write("                              CORRIGÉ\n")
        f.write("=" * 80 + "\n\n")

        if 'exercises' in content:
            for ex in content['exercises']:
                f.write(f"EXERCICE N°{ex['exercise_number']}:\n")
                if ex.get('correction'):
                    f.write(f"{ex['correction']}\n")
                f.write("\n" + "-" * 80 + "\n\n")

    logger.info(f"✅ Text file created: {txt_path}")
    return txt_path


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Tunisian Baccalaureate Exam Generator API...")
    logger.info("🌐 Server: http://127.0.0.1:8000")
    logger.info("📖 Docs: http://127.0.0.1:8000/docs")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")