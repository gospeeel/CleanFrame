#!/usr/bin/env python3
# rag_law_with_ontology.py
# Интегрированная версия RAG-пайплайна с жёстко прописанной онтологией по ФЗ-436 (статьи 3-11).
# По умолчанию использует cointegrated/rut5-base-multitask (rus T5) — если её нет, можно поменять LLM_MODEL.

import os
import re
import json
from typing import List, Dict, Any
from docx import Document
from sentence_transformers import SentenceTransformer
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from chromadb import PersistentClient

# -------- CONFIG --------
DOCX_PATH = "./example/ФЗ.docx"   # путь к твоему загруженному ФЗ (используется при --build)
CHROMA_DIR = "./chroma_fz436"
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
LLM_MODEL = os.environ.get("RAG_LLM_MODEL", "cointegrated/rut5-base-multitask")
LOAD_IN_8BIT = os.environ.get("LOAD_IN_8BIT", "0") == "1"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ---------- Жёстко прописанная онтология (статьи 3-11 ФЗ-436) ----------
# Для каждого элемента: article, part (может быть None), point (может быть None),
# categories (список), rating (0+/6+/12+/16+/18+), summary, reference
LAW_ONTOLOGY = [
    # Статья 3 — определения (общие) -> general, 0+
    {
        "article": "3", "part": None, "point": None,
        "categories": ["general"], "rating": "0+",
        "summary": "Определяет основные понятия: информация, продукция, влияющая на здоровье и развитие детей, возрастная категория.",
        "reference": "статья 3"
    },
    # Статья 4 — принципы -> general
    {
        "article": "4", "part": None, "point": None,
        "categories": ["general"], "rating": "0+",
        "summary": "Основные принципы защиты детей от вредной информации, приоритет интересов ребёнка.",
        "reference": "статья 4"
    },
    # Статья 5 — классификация (ключевые пункты)
    {
        "article": "5", "part": "2", "point": "1",
        "categories": ["violence", "scary"], "rating": "12+",
        "summary": "Информация, содержащая описание насилия и (или) пугающие сцены без натуралистичных подробностей допускается для 12+.",
        "reference": "статья 5 часть 2 пункт 1"
    },
    {
        "article": "5", "part": "2", "point": "2",
        "categories": ["profanity"], "rating": "16+",
        "summary": "Сведения, содержащие грубую речь и оскорбления в явной форме допускаются в категории 16+ при отсутствии оправдания агрессии.",
        "reference": "статья 5 часть 2 пункт 2"
    },
    {
        "article": "5", "part": "2", "point": "3",
        "categories": ["erotic"], "rating": "18+",
        "summary": "Описание сексуальных отношений и откровенные эротические сцены относятся к категории 18+.",
        "reference": "статья 5 часть 2 пункт 3"
    },
    {
        "article": "5", "part": "2", "point": "4",
        "categories": ["drugs_alcohol"], "rating": "16+",
        "summary": "Материалы, содержащие пропаганду употребления наркотиков и психотропных веществ запрещены для детей; допустимы медицинские/научные ссылки с маркировкой 16+.",
        "reference": "статья 5 часть 2 пункт 4"
    },
    {
        "article": "5", "part": "2", "point": "5",
        "categories": ["scary", "violence"], "rating": "12+",
        "summary": "Материалы с изображением трагедий и смертей допускаются для 12+ при отсутствии подробного натурализма.",
        "reference": "статья 5 часть 2 пункт 5"
    },
    {
        "article": "5", "part": "2", "point": "6",
        "categories": ["profanity"], "rating": "18+",
        "summary": "Нецензурная брань и сцены унижения, способные нанести вред психике детей, относятся к 18+.",
        "reference": "статья 5 часть 2 пункт 6"
    },
    {
        "article": "5", "part": "2", "point": "7",
        "categories": ["erotic", "pornography"], "rating": "18+",
        "summary": "Порнографические материалы и натуралистические сексуальные сцены — только 18+ и запрещены для детей.",
        "reference": "статья 5 часть 2 пункт 7"
    },
    # Статья 6 — запрещённая информация для распространения среди детей (общая)
    {
        "article": "6", "part": None, "point": None,
        "categories": ["violence", "erotic", "drugs_alcohol", "scary", "profanity"], "rating": "18+",
        "summary": "Полный перечень информации, запрещённой для распространения среди детей (порнография, оправдание жестокости, пропаганда наркотиков и т.д.).",
        "reference": "статья 6"
    },
    # Статья 7 — для детей до 6 лет (6+)
    {
        "article": "7", "part": None, "point": None,
        "categories": ["general"], "rating": "6+",
        "summary": "Информация, не вызывающая страха и не содержащая сцен насилия и сексуального содержания, подходит для детей младше 6 лет.",
        "reference": "статья 7"
    },
    # Статья 8 — для детей старше 6 лет (6+)
    {
        "article": "8", "part": None, "point": None,
        "categories": ["violence", "scary"], "rating": "6+",
        "summary": "Короткие, не подробные эпизоды страха/конфликта допустимы для 6+.",
        "reference": "статья 8"
    },
    # Статья 9 — 12+
    {
        "article": "9", "part": None, "point": None,
        "categories": ["violence", "profanity", "scary"], "rating": "12+",
        "summary": "Для 12+ допускаются упоминания насилия без натурализма, отдельные неуничижительные выражения, темы общества.",
        "reference": "статья 9"
    },
    # Статья 10 — 16+
    {
        "article": "10", "part": None, "point": None,
        "categories": ["violence", "erotic", "drugs_alcohol"], "rating": "16+",
        "summary": "Для 16+ допускаются более взрослые темы: небрутальные сцены насилия, упоминание алкоголя, сексуальные отношения без натурализма.",
        "reference": "статья 10"
    },
    # Статья 11 — 18+
    {
        "article": "11", "part": None, "point": None,
        "categories": ["violence", "erotic", "drugs_alcohol", "profanity"], "rating": "18+",
        "summary": "Материалы, предназначенные только для взрослых — 18+. Содержат откровенные сцены, жестокость, наркотики, брань.",
        "reference": "статья 11"
    },
]

# Упорядочение рейтингов по строгости
RATING_ORDER = ["0+", "6+", "12+", "16+", "18+"]
RATING_TO_INDEX = {r: i for i, r in enumerate(RATING_ORDER)}

# ---------- Utility: parse docx into articles (unchanged) ----------
def extract_articles(docx_path: str) -> List[Dict[str, str]]:
    doc = Document(docx_path)
    articles = []
    cur_title = None
    cur_text = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if re.match(r"^Статья\s+\d+", text):
            if cur_title is not None:
                articles.append({"title": cur_title, "text": " ".join(cur_text)})
            cur_title = text
            cur_text = []
        else:
            cur_text.append(text)
    if cur_title is not None:
        articles.append({"title": cur_title, "text": " ".join(cur_text)})
    return articles

# ---------- Build or load Chroma index (unchanged logic) ----------
def build_or_load_chroma(docx_path: str = DOCX_PATH,
                         chroma_dir: str = CHROMA_DIR,
                         embedding_model_name: str = EMBEDDING_MODEL_NAME):
    emb = SentenceTransformer(embedding_model_name)
    client = PersistentClient(path=chroma_dir)
    try:
        coll = client.get_collection("fz436")
    except Exception:
        coll = client.create_collection("fz436")

    if coll.count() == 0:
        print("Building Chroma index from docx...")
        articles = extract_articles(docx_path)
        ids, docs, metadatas, embeddings = [], [], [], []
        # для каждого чанкa просто индексируем весь текст статьи
        for i, a in enumerate(articles):
            title = a["title"]
            doc_text = a["text"]
            emb_vec = emb.encode(doc_text).tolist()
            ids.append(f"art_{i}_{re.sub(r'\\s+','_', title)[:60]}")
            docs.append(doc_text)
            # метаданные минимальны — названия статьи
            meta = {"title": title}
            metadatas.append(meta)
            embeddings.append(emb_vec)
        coll.add(
            documents=docs,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        print(f"✅ Indexed {len(docs)} law chunks into Chroma at {chroma_dir}")
    else:
        print("✅ Chroma index already exists, using it.")
    return client, coll

# ---------- LLM init (Seq2Seq for RuT5) ----------
def init_llm(model_name: str = LLM_MODEL):
    print(f"Loading LLM {model_name} on {DEVICE} (8bit={LOAD_IN_8BIT}) ...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
        kwargs = {"torch_dtype": torch.float32, "device_map": None}
        if LOAD_IN_8BIT:
            kwargs["load_in_8bit"] = True
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name, **kwargs).to(DEVICE)
        model.eval()
        return tokenizer, model
    except Exception as e:
        print("⚠️ Ошибка при загрузке LLM:", e)
        # fallback: используем более лёгкую публичную модель (если желаешь — менять)
        fallback = "google/flan-t5-small"
        print("➡️ Переключаюсь на fallback модель:", fallback)
        tokenizer = AutoTokenizer.from_pretrained(fallback, use_fast=False)
        model = AutoModelForSeq2SeqLM.from_pretrained(fallback).to(DEVICE)
        model.eval()
        return tokenizer, model

# ---------- Ontology helpers ----------
def get_articles_by_category(category: str) -> List[Dict[str, Any]]:
    return [a for a in LAW_ONTOLOGY if category in a["categories"]]

def get_relevant_law_context(active_categories: List[str]) -> List[str]:
    """
    Возвращает читаемый список ссылок/описаний по онтологии для активных категорий.
    """
    out = []
    seen = set()
    for cat in active_categories:
        arts = get_articles_by_category(cat)
        for a in arts:
            ref = a.get("reference")
            if ref and ref not in seen:
                seen.add(ref)
                out.append(f"{ref}: {a.get('summary')} (рейтинг {a.get('rating')})")
    return out

# ---------- Build prompt ----------
PROMPT_TEMPLATE = """Ты — эксперт по применению Федерального закона №436-ФЗ «О защите детей от информации, причиняющей вред их здоровью и (или) развитию».

Задача: используя контекст из закона и результаты автоматических детекторов, определи возрастной рейтинг для данной сцены и приведи юридическое обоснование.

ДАНО:
1) Текст сцены:
\"\"\"{scene_text}\"\"\"

2) Результаты детекторов:
{category_lines}

3) Триггерные слова:
{triggers_text}

4) Юридический контекст (из онтологии и/или извлечений):
{law_context}

ОТВЕТ:
Верни строго только JSON в формате:
{{
  "rating": "<0+|6+|12+|16+|18+|uncertain>",
  "reason": "<краткое юридическое обоснование>",
  "references": ["статья X часть Y пункт Z", "..."], 
  "recommendation": "<рекомендация для автора>",
  "confidence": <число от 0 до 1>
}}

Если не уверен — верни "rating": "uncertain" и объясни почему в поле reason.
Отвечай на русском. Никаких дополнительных слов вне JSON.
"""

def build_prompt(scene_text: str, category_scores: Dict[str, float], triggers: Dict[str, List[str]], law_context: List[str]):
    category_lines = "\n".join([f"- {cat}: prob={prob:.3f}" for cat, prob in category_scores.items()])
    triggers_text = json.dumps(triggers, ensure_ascii=False, indent=2)
    ctx_text = "\n".join(law_context) if law_context else "— нет релевантного юридического контекста."
    return PROMPT_TEMPLATE.format(
        scene_text=scene_text,
        category_lines=category_lines,
        triggers_text=triggers_text,
        law_context=ctx_text
    )

# ---------- Utility: compute final rating given detected categories ----------
def select_strictest_rating(detected_categories: List[str]) -> str:
    """
    Берём все рейтинги, соответствующие категориям, и выбираем максимально строгий (по RATING_ORDER).
    Если нет релевантных категорий — возвращает "uncertain".
    """
    ratings_found = []
    for cat in detected_categories:
        arts = get_articles_by_category(cat)
        for a in arts:
            r = a.get("rating")
            if r:
                ratings_found.append(r)
    if not ratings_found:
        return "uncertain"
    # выбрать самый строгий
    idx = max(RATING_TO_INDEX.get(r, 0) for r in ratings_found)
    return RATING_ORDER[idx]

# ---------- Query function (интегрированная) ----------
def query_rag(scene_text: str, category_scores: Dict[str, float], triggers: Dict[str, List[str]],
              client=None, coll=None, tokenizer=None, model=None, top_k:int=5) -> Dict[str, Any]:
    # ensure chroma
    if client is None or coll is None:
        client, coll = build_or_load_chroma()

    # active categories by threshold
    active_cats = [c for c, p in category_scores.items() if p >= 0.25]
    if not active_cats:
        active_cats = ["general"]

    # get ontology-based law context
    law_ctx = get_relevant_law_context(active_cats)

    # retrieve similar chunks from Chroma (optional helper context)
    docs = []
    try:
        query_text = scene_text[:1000]
        results = coll.query(query_texts=[query_text], n_results=top_k)
        docs = results.get("documents", [[]])[0]
    except Exception:
        docs = []

    # combine contexts
    combined_context = law_ctx.copy()
    for d in docs:
        # короткие выдержки
        combined_context.append((d[:600] + "...") if d else "")

    prompt = build_prompt(scene_text, category_scores, triggers, combined_context)

    if tokenizer is None or model is None:
        tokenizer, model = init_llm()

    # generation (Seq2Seq)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=256, do_sample=False)
    text = tokenizer.decode(out[0], skip_special_tokens=True)

    # try to parse JSON
    json_part = None
    try:
        jstart = text.find("{")
        jend = text.rfind("}")
        if jstart != -1 and jend != -1 and jend > jstart:
            json_str = text[jstart:jend+1]
            parsed = json.loads(json_str)
            json_part = parsed
        else:
            json_part = {"raw": text}
    except Exception:
        json_part = {"raw": text}

    # post-process: enforce choices, confidence
    # confidence: берем max prob из detectors (если есть)
    confidence = 0.0
    if isinstance(category_scores, dict) and category_scores:
        confidence = float(max(category_scores.values()))

    # if model returned rating but it's not one of allowed, try to compute from ontology
    rating = json_part.get("rating") if isinstance(json_part, dict) else None
    if rating not in RATING_ORDER and rating != "uncertain":
        # compute based on ontology
        rating_calc = select_strictest_rating(active_cats)
        if rating_calc != "uncertain":
            json_part["rating"] = rating_calc
        else:
            json_part["rating"] = "uncertain"

    # if no rating at all, compute strictly
    if "rating" not in json_part:
        json_part["rating"] = select_strictest_rating(active_cats)

    # attach references if missing (take from ontology)
    if isinstance(json_part, dict) and ("references" not in json_part or not json_part.get("references")):
        refs = []
        for cat in active_cats:
            arts = get_articles_by_category(cat)
            for a in arts:
                if a.get("reference") and a.get("reference") not in refs:
                    refs.append(a.get("reference"))
        if refs:
            json_part["references"] = refs

    # if still no references and rating != uncertain, leave as is; if uncertain, keep empty refs
    json_part["confidence"] = round(float(confidence), 3) if isinstance(confidence, (float, int)) else 0.0

    # add debug info
    json_part["_debug"] = {
        "prompt_snippet": prompt[:1000],
        "llm_raw": text[:2000],
        "retrieved_docs": docs,
        "ontology_context": law_ctx,
        "active_categories": active_cats
    }
    return json_part

# ---------- Batch processing helper (как раньше) ----------
def process_json(input_json_path: str, output_json_path: str,
                 client=None, coll=None, tokenizer=None, model=None):
    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if client is None or coll is None:
        client, coll = build_or_load_chroma()
    if tokenizer is None or model is None:
        tokenizer, model = init_llm()

    for scene in data.get("scenes", []):
        for element in scene.get("elements", []):
            category_scores = element.get("rubert_scores", {})
            triggers = element.get("triggers", {})
            if not isinstance(category_scores, dict):
                continue
            rag_result = query_rag(
                scene_text=element.get("text", ""),
                category_scores=category_scores,
                triggers=triggers,
                client=client, coll=coll, tokenizer=tokenizer, model=model
            )
            element["rag"] = rag_result

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved with RAG results to", output_json_path)

# ---------- CLI ----------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RAG + onto for ФЗ-436 (build/query/process)")
    parser.add_argument("--build", action="store_true", help="Build Chroma index from DOCX")
    parser.add_argument("--query", nargs=1, metavar=("SCENE_TXT"), help="Quick test: query a single scene text")
    parser.add_argument("--process", nargs=2, metavar=("INPUT_JSON","OUTPUT_JSON"), help="Process JSON produced by predict_rubert")
    args = parser.parse_args()

    if args.build:
        build_or_load_chroma()
    elif args.query:
        client, coll = build_or_load_chroma()
        tokenizer, model = init_llm()
        scene = args.query[0]
        # dummy detector scores & triggers for quick test (adjust as you like)
        scores = {"violence": 0.9, "profanity": 0.6, "erotic": 0.0, "drugs_alcohol": 0.02, "scary": 0.1}
        triggers = {"violence": ["ударил"], "profanity": ["дурак"]}
        res = query_rag(scene, scores, triggers, client=client, coll=coll, tokenizer=tokenizer, model=model)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.process:
        input_j, output_j = args.process
        client, coll = build_or_load_chroma()
        tokenizer, model = init_llm()
        process_json(input_j, output_j, client=client, coll=coll, tokenizer=tokenizer, model=model)
    else:
        print("Run --help for usage. Examples:\n  python rag_law_with_ontology.py --build\n  python rag_law_with_ontology.py --query \"...\"")
