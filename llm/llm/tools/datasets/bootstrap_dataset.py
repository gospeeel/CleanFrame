import argparse
import json
import random
from pathlib import Path

from llm.legal.policy import calculate_simple_rating, fallback_recommendation


CATEGORIES = {
    "safe": {
        0: [
            "{hero} помогает {target} донести сумку до двери.",
            "Друзья обсуждают планы на выходные и смеются над безобидной шуткой.",
            "{hero} ударил по мячу, и игра продолжилась без конфликта.",
            "В темном зале гаснет свет, но это оказывается началом спектакля.",
            "На столе стоит бокал сока, герои спокойно ужинают.",
            "Персонажи обнимаются после долгой разлуки без интимного подтекста.",
            "{hero} говорит, что ему страшно опоздать на поезд.",
            "Учитель просит класс соблюдать тишину и открыть учебники.",
        ],
    },
    "violence": {
        1: [
            "{hero} толкает {target}, и конфликт быстро останавливают.",
            "{hero} замахивается, но удар выглядит условно и без последствий.",
            "В споре {hero} грубо хватает {target} за рукав.",
        ],
        2: [
            "{hero} ударяет {target}, тот падает и поднимается через несколько секунд.",
            "В драке {hero} сбивает {target} с ног, окружающие разнимают их.",
            "{hero} получает несильную травму во время короткой потасовки.",
        ],
        3: [
            "{hero} наносит несколько ударов, {target} остается на полу и тяжело дышит.",
            "Сцена драки затягивается, слышны крики, видны следы травм.",
            "{hero} угрожает оружием и применяет силу против беззащитного персонажа.",
        ],
        4: [
            "Камера подробно показывает тяжелые последствия нападения и страдания жертвы.",
            "{hero} жестоко расправляется с {target}, сцена описана натуралистично.",
            "После нападения на полу остаются явные следы крови и тяжелых травм.",
        ],
    },
    "profanity": {
        1: [
            "{hero} раздраженно бросает грубое оскорбление без нецензурных слов.",
            "Персонажи спорят, один использует резкую, но не обсценную лексику.",
            "{hero} грубо обзывает {target}, после чего сразу извиняется.",
        ],
        2: [
            "В диалоге звучит завуалированная брань и несколько грубых выражений.",
            "{hero} в ярости произносит непристойную фразу, частично заглушенную шумом.",
            "Ссора сопровождается повторяющимися грубыми репликами.",
        ],
        3: [
            "{hero} несколько раз использует обсценную лексику в адрес {target}.",
            "Перепалка строится на агрессивной брани и унижениях.",
            "В сцене звучит продолжительная нецензурная тирада.",
        ],
        4: [
            "Диалог почти полностью состоит из жесткой обсценной брани и унижений.",
            "{hero} произносит крайне грубую нецензурную речь с сексуализированными оскорблениями.",
            "Сцена содержит многократную ненормативную лексику без смягчения.",
        ],
    },
    "substance": {
        1: [
            "На столе стоит бокал вина, но употребление не акцентируется.",
            "{hero} отказывается от предложенного алкоголя и уходит.",
            "В кадре мелькает сигарета, сцена не задерживается на этом.",
        ],
        2: [
            "{hero} выпивает на вечеринке, после чего ведет себя шумно.",
            "Персонажи обсуждают алкоголь и показывают последствия опьянения.",
            "{hero} курит в напряженной сцене, это не выглядит привлекательным.",
        ],
        3: [
            "Сцена подробно показывает употребление запрещенного вещества и состояние персонажа.",
            "{hero} убеждает {target} попробовать наркотик, последствия показаны тревожно.",
            "Персонаж теряет контроль после употребления, сцена длительная и заметная.",
        ],
        4: [
            "Сценарий подробно описывает приготовление и употребление наркотика.",
            "Употребление вещества показано как желанное и привлекательное без осуждения.",
            "Герои обсуждают способы достать наркотики и демонстрируют процесс употребления.",
        ],
    },
    "fear": {
        1: [
            "В темном коридоре слышится странный звук, но опасность не подтверждается.",
            "{hero} пугается тени и быстро понимает, что это безобидный предмет.",
            "Сцена создает легкое напряжение без угроз и страшных образов.",
        ],
        2: [
            "{hero} идет по заброшенному дому, слышит шаги и видит пугающий силуэт.",
            "В комнате внезапно гаснет свет, персонаж кричит от страха.",
            "Сцена содержит тревожную погоню и резкий испуг.",
        ],
        3: [
            "{hero} видит жуткую фигуру, которая преследует его несколько минут.",
            "Сцена кошмара подробно описывает страх, крики и ощущение угрозы.",
            "Персонаж оказывается заперт в мрачном помещении с пугающими звуками.",
        ],
        4: [
            "Сцена содержит натуралистичный хоррор-образ и длительную панику персонажа.",
            "Пугающее существо подробно описано крупным планом, персонажи в истерике.",
            "Кошмарная сцена соединяет ужас, травмы и безысходность.",
        ],
    },
    "sexual": {
        1: [
            "{hero} и {target} флиртуют, сцена остается невинной.",
            "Персонажи обнимаются и целуются без интимных подробностей.",
            "В диалоге есть легкий романтический намек без сексуального описания.",
        ],
        2: [
            "Сцена содержит продолжительный поцелуй и намек на близость за кадром.",
            "{hero} и {target} обсуждают интимные отношения без деталей.",
            "Романтическая сцена становится более взрослой, но без прямого описания.",
        ],
        3: [
            "Сцена описывает интимную близость через недвусмысленные детали, без натурализма.",
            "Персонажи говорят о сексуальном опыте прямо и подробно.",
            "Сценарий делает явный акцент на эротическом подтексте сцены.",
        ],
        4: [
            "Сцена подробно описывает сексуальное действие и физические детали.",
            "Диалог содержит откровенные сексуальные реплики и прямые описания.",
            "Эпизод строится вокруг детализированной интимной сцены.",
        ],
    },
}

HEROES = ["Аня", "Игорь", "капитан", "подросток", "следователь", "Марина", "Олег", "героиня"]
TARGETS = ["друга", "незнакомца", "соперника", "охранника", "соседа", "прохожего", "брата"]
PLACES = ["в подъезде", "на кухне", "в школе", "в клубе", "в лесу", "на вокзале", "в квартире"]
TONES = ["сдержанно", "напряженно", "резко", "тихо", "в панике", "после паузы"]


def enrich_text(template: str, rnd: random.Random) -> str:
    text = template.format(
        hero=rnd.choice(HEROES),
        target=rnd.choice(TARGETS),
        place=rnd.choice(PLACES),
        tone=rnd.choice(TONES),
    )
    prefix = rnd.choice(["", "{place} ", "{tone} ", "{place} {tone} "]).format(
        place=rnd.choice(PLACES),
        tone=rnd.choice(TONES),
    )
    suffix = rnd.choice([
        "",
        " Камера фиксирует реакцию окружающих.",
        " Сцена занимает несколько реплик.",
        " После этого действие переходит к следующей сцене.",
        " Важно, что эпизод влияет на общий тон истории.",
    ])
    return f"{prefix}{text}{suffix}".strip()


def build_examples(samples_per_bucket: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)
    examples = []
    for category, levels in CATEGORIES.items():
        for level, templates in levels.items():
            for index in range(samples_per_bucket):
                text = enrich_text(rnd.choice(templates), rnd)
                rating = "0+" if category == "safe" else calculate_simple_rating(category, level)
                examples.append({
                    "id": f"silver-{category}-{level}-{index + 1:04d}",
                    "text": text,
                    "category": category,
                    "level": level,
                    "rating": rating,
                    "source": "synthetic_silver",
                    "element_type": rnd.choice(["action", "dialogue"]),
                    "needs_human_review": True,
                    "recommendation": fallback_recommendation(category, level),
                })

    rnd.shuffle(examples)
    return examples


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def split_examples(examples: list[dict], train_ratio: float, validation_ratio: float):
    train_end = int(len(examples) * train_ratio)
    validation_end = train_end + int(len(examples) * validation_ratio)
    return {
        "train": examples[:train_end],
        "validation": examples[train_end:validation_end],
        "test": examples[validation_end:],
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a balanced synthetic silver dataset for ML_WINK.")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/silver"))
    parser.add_argument("--samples-per-bucket", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--validation-ratio", type=float, default=0.15)
    return parser.parse_args()


def main():
    args = parse_args()
    examples = build_examples(samples_per_bucket=args.samples_per_bucket, seed=args.seed)
    splits = split_examples(examples, args.train_ratio, args.validation_ratio)
    for split_name, rows in splits.items():
        write_jsonl(args.output_dir / f"{split_name}.jsonl", rows)

    manifest = {
        "dataset_type": "synthetic_silver",
        "warning": "Not a human-labeled golden dataset. Use for bootstrap, regression checks, and weak pretraining only.",
        "seed": args.seed,
        "samples_per_bucket": args.samples_per_bucket,
        "total": len(examples),
        "splits": {name: len(rows) for name, rows in splits.items()},
        "categories": sorted(CATEGORIES.keys()),
        "levels": [0, 1, 2, 3, 4],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
