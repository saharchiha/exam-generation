import re
import os
import json
from typing import Dict, List

def extract_metadata_from_text(text: str) -> Dict[str, str]:
    """
    Extracts metadata (subject, year, session, section) from exam text.
    Supports multilingual content (French, Arabic, English).
    """

    metadata = {
        "subject": "unknown",
        "year": "unknown",
        "session": "unknown",
        "section": "unknown",
        "language": "unknown"
    }

    text_lower = text.lower()

    # ---------- LANGUAGE DETECTION ----------
    if re.search(r"[\u0600-\u06FF]", text):  # Arabic Unicode range
        metadata["language"] = "Arabic"
    elif re.search(r"[éèàùç]", text_lower):
        metadata["language"] = "French"
    else:
        metadata["language"] = "English"

    # ---------- SUBJECT DETECTION ----------
    subject_map = {
        # English → canonical
        "math": "Mathematics",
        "mathematics": "Mathematics",
        "physics": "Physics",
        "chemistry": "Chemistry",
        "biology": "Biology",
        "philosophy": "Philosophy",
        "history": "History",
        "geography": "Geography",
        "arabic": "Arabic",
        "french": "French",
        "english": "English",
        "computer science": "Informatics",
        "informatics": "Informatics",
        "economics": "Economics",
        "management": "Management",

        # French equivalents
        "mathématiques": "Mathematics",
        "physique": "Physics",
        "chimie": "Chemistry",
        "biologie": "Biology",
        "philosophie": "Philosophy",
        "histoire": "History",
        "géographie": "Geography",
        "arabe": "Arabic",
        "français": "French",
        "anglais": "English",
        "informatique": "Informatics",
        "économie": "Economics",
        "gestion": "Management",

        # Arabic equivalents (transliterated & native)
        "رياضيات": "Mathematics",
        "فيزياء": "Physics",
        "كيمياء": "Chemistry",
        "علوم": "Biology",
        "فلسفة": "Philosophy",
        "تاريخ": "History",
        "جغرافيا": "Geography",
        "عربية": "Arabic",
        "فرنسية": "French",
        "انجليزية": "English",
        "اعلامية": "Informatics",
        "اقتصاد": "Economics",
        "تصرف": "Management"
    }

    for key, canonical in subject_map.items():
        if re.search(rf"\b{key}\b", text_lower):
            metadata["subject"] = canonical
            break

    # ---------- YEAR DETECTION ----------
    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        metadata["year"] = year_match.group(1)

    # ---------- SESSION DETECTION ----------
    session_map = {
        # English
        "main": "Main",
        "retake": "Retake",
        "june": "June",
        # French
        "session principale": "Main",
        "session de contrôle": "Retake",
        "juin": "June",
        # Arabic
        "الدورة الرئيسية": "Main",
        "دورة المراقبة": "Retake"
    }

    for key, canonical in session_map.items():
        if key in text_lower:
            metadata["session"] = canonical
            break

    # ---------- SECTION DETECTION ----------
    section_map = {
        # English/French
        "math": "Mathématiques",
        "mathématiques": "Mathématiques",
        "scientifique": "Sciences Expérimentales",
        "sciences": "Sciences Expérimentales",
        "lettres": "Lettres",
        "literature": "Lettres",
        "économie": "Économie et Gestion",
        "économie et gestion": "Économie et Gestion",
        "gestion": "Économie et Gestion",
        "technique": "Sciences Techniques",
        "technologique": "Sciences Techniques",
        "informatique": "Informatique",
        "computer": "Informatique",
        "sport": "Sport",
        # Arabic
        "شعبة الرياضيات": "Mathématiques",
        "شعبة العلوم": "Sciences Expérimentales",
        "شعبة الآداب": "Lettres",
        "شعبة الاقتصاد": "Économie et Gestion",
        "شعبة التقنية": "Sciences Techniques",
        "شعبة الإعلامية": "Informatique",
        "شعبة الرياضة": "Sport"
    }

    for key, canonical in section_map.items():
        if key in text_lower:
            metadata["section"] = canonical
            break

    return metadata


def enrich_chunks_with_metadata(chunks: List[str], base_text: str) -> List[Dict]:
    """
    Adds extracted multilingual metadata to each chunk.
    """
    metadata = extract_metadata_from_text(base_text)
    return [{"text": chunk, "metadata": metadata} for chunk in chunks]


def save_enriched_chunks(input_dir: str, output_dir: str):
    """
    Reads raw text files, chunks them, and enriches with multilingual metadata.
    """
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if not filename.endswith(".txt"):
            continue

        path = os.path.join(input_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        from embeddings.chunker import chunk_exam_data
        chunks_path = os.path.join(output_dir, f"{filename}_chunks.json")
        chunk_exam_data(path, output_dir)

        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        enriched = enrich_chunks_with_metadata(chunks, content)
        enriched_file = os.path.join(output_dir, f"{filename}_enriched.json")

        with open(enriched_file, "w", encoding="utf-8") as out:
            json.dump(enriched, out, ensure_ascii=False, indent=2)

        print(f"✅ Enriched {filename} with multilingual metadata (subject, section, session, year, language)")