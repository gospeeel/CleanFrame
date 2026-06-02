from yargy import rule, or_, Parser
from yargy.predicates import normalized
from llm.semantic_expansion import load_expanded_lexicons
from llm.taxonomy import ambiguous_context_adjustments, normalize_category, safe_context_categories, score_curated_terms
import json, os, sys, glob
from typing import Dict, Any


# -------------------------
# 📦 ЗАГРУЗКА РАСШИРЕННЫХ СЛОВАРЕЙ 
# -------------------------
lexicons = load_expanded_lexicons()

def get_words(cat, key):
    return set(lexicons.get(cat, {}).get(key, []))

# -------------------------
# 🔢 СЛОВАРИ
# -------------------------
VIOLENCE_VERBS = get_words("violence", "verbs")
VIOLENCE_NOUNS = get_words("violence", "nouns")
VIOLENCE_IDIOMS = set(lexicons.get("violence", {}).get("idioms", []))

PROFANITY_WORDS = get_words("profanity", "words")
PROFANITY_EUPHEMISMS = get_words("profanity", "euphemisms")

DRUGS_ALCOHOL = get_words("drugs_alcohol", "words")
DRUGS_IDIOMS = set(lexicons.get("drugs_alcohol", {}).get("idioms", []))

EROTIC_WORDS = get_words("erotic", "words")
EROTIC_IDIOMS = set(lexicons.get("erotic", {}).get("idioms", []))

SCARY_WORDS = get_words("scary", "words")
SCARY_IDIOMS = set(lexicons.get("scary", {}).get("idioms", []))

# -------------------------
# 🧠 ПОСТРОЕНИЕ ПРАВИЛ
# -------------------------
def make_verb_noun_rules(verbs, nouns):
    rules = []
    for v in verbs:
        for n in nouns:
            rules.append(rule(normalized(v), normalized(n).optional()))
        rules.append(rule(normalized(v)))
    for n in nouns:
        rules.append(rule(normalized(n)))
    return rules

def make_word_rules(words):
    return [rule(normalized(word)) for word in words]

def make_idiom_rules(phrases):
    rules = []
    for phrase in phrases:
        tokens = phrase.split()
        token_predicates = [normalized(token) for token in tokens]
        rules.append(rule(*token_predicates))
    return rules

def build_category_rule(words=None, idioms=None, verbs=None, nouns=None):
    all_rules = []
    if words:
        all_rules.extend(make_word_rules(words))
    if idioms:
        all_rules.extend(make_idiom_rules(idioms))
    if verbs and nouns:
        all_rules.extend(make_verb_noun_rules(verbs, nouns))
    return rule(or_(*all_rules)) if all_rules else None



# -------------------------
# 🧩 ПАРСЕРЫ
# -------------------------
RULES = {
    'violence': build_category_rule(words=VIOLENCE_VERBS | VIOLENCE_NOUNS, idioms=VIOLENCE_IDIOMS),
    'profanity': build_category_rule(words=PROFANITY_WORDS | PROFANITY_EUPHEMISMS),
    'drugs_alcohol': build_category_rule(words=DRUGS_ALCOHOL, idioms=DRUGS_IDIOMS),
    'erotic': build_category_rule(words=EROTIC_WORDS, idioms=EROTIC_IDIOMS),
    'scary': build_category_rule(words=SCARY_WORDS, idioms=SCARY_IDIOMS)
}

parsers = {cat: Parser(category_rule) for cat, category_rule in RULES.items() if category_rule is not None}

# -------------------------
# 🔍 АНАЛИЗ
# -------------------------
def is_suspicious_scene(text: str) -> dict:
    text = text.lower()
    flags = {category: False for category in RULES}
    curated_scores, matched_terms = score_curated_terms(text)
    ambiguous_adjustments = ambiguous_context_adjustments(text)
    suppressed_categories = safe_context_categories(text) | set(ambiguous_adjustments.get("suppress", set()))

    for category, parser in parsers.items():
        matches = list(parser.findall(text))
        normalized_category = normalize_category(category)
        flags[category] = (
            normalized_category not in suppressed_categories
            and (len(matches) > 0 or curated_scores.get(normalized_category, 0.0) > 0)
        )

    normalized_scores = {category: 0.0 for category in curated_scores}
    normalized_matches = {category: [] for category in curated_scores}
    for category, is_active in flags.items():
        normalized_category = normalize_category(category)
        if normalized_category in suppressed_categories:
            continue
        if is_active:
            normalized_scores[normalized_category] += 1.0
        normalized_scores[normalized_category] += curated_scores.get(normalized_category, 0.0)
        normalized_matches[normalized_category].extend(matched_terms.get(normalized_category, []))

    for category, score in ambiguous_adjustments.get("boosts", {}).items():
        normalized_category = normalize_category(category)
        normalized_scores[normalized_category] += float(score)
    for category, terms in ambiguous_adjustments.get("matches", {}).items():
        normalized_category = normalize_category(category)
        normalized_matches[normalized_category].extend(str(term) for term in terms)

    normalized_flags = {
        category: score > 0
        for category, score in normalized_scores.items()
    }

    return {
        'is_suspicious': any(flags.values()) or any(normalized_flags.values()),
        'flags': flags,
        'normalized_flags': normalized_flags,
        'category_scores': normalized_scores,
        'matched_terms': {
            category: sorted(set(terms))
            for category, terms in normalized_matches.items()
            if terms
        }
    }

def analyze_parsed_script(parsed_script: Dict[str, Any]) -> Dict[str, Any]:
    for scene in parsed_script.get("scenes", []):
        for element in scene.get("elements", []):
            if "text" in element:
                element["natasha_flags"] = is_suspicious_scene(element["text"])
    return parsed_script

def analyze_script_from_json_file(json_path: str, output_path: str = None) -> Dict[str, Any]:
    with open(json_path, 'r', encoding='utf-8') as f:
        parsed = json.load(f)
    analyzed = analyze_parsed_script(parsed)
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analyzed, f, ensure_ascii=False, indent=2)
    return analyzed

# -------------------------
# 🚀 ТОЧКА ВХОДА
# -------------------------
if __name__ == "__main__":
    INPUT_FOLDER = "example"
    OUTPUT_SUFFIX = "_natasha"

    if not os.path.isdir(INPUT_FOLDER):
        print(f"❌ Папка '{INPUT_FOLDER}' не найдена.")
        sys.exit(1)

    json_files = glob.glob(os.path.join(INPUT_FOLDER, "*.json"))
    if not json_files:
        print(f"❌ Нет JSON-файлов в '{INPUT_FOLDER}'.")
        sys.exit(1)

    print(f"📁 Найдено {len(json_files)} JSON-файлов.")
    for input_path in json_files:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}{OUTPUT_SUFFIX}{ext}"
        try:
            result = analyze_script_from_json_file(input_path, output_path)
            total_elements = sum(len(s["elements"]) for s in result["scenes"])
            suspicious_count = sum(
                1 for s in result["scenes"] for e in s["elements"]
                if e.get("natasha_flags", {}).get("is_suspicious")
            )
            print(f"✅ {os.path.basename(input_path)}: {suspicious_count}/{total_elements} подозрительных.")
        except Exception as e:
            print(f"❌ Ошибка {input_path}: {e}")
