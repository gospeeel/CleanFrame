import unittest

from llm.detection.rule_detector import is_suspicious_scene
from llm.legal.retrieval import retrieve_legal_context
from llm.taxonomy import (
    category_label,
    evidence_items,
    normalize_category,
    primary_category_from_evidence,
    score_curated_terms,
)


class TaxonomyTest(unittest.TestCase):
    def test_category_aliases_have_russian_labels(self):
        self.assertEqual(normalize_category("scary"), "fear")
        self.assertEqual(normalize_category("drugs_alcohol"), "substance")
        self.assertEqual(normalize_category("erotic"), "sexual")
        self.assertEqual(category_label("scary"), "Пугающие сцены")

    def test_fight_scene_prefers_violence_over_fear_prediction(self):
        natasha = is_suspicious_scene(
            "Олег выходит из тени и резко хватает незнакомца за рукав. "
            "Завязывается короткая драка, слышен удар, незнакомец падает на пол."
        )

        primary, secondary = primary_category_from_evidence("fear", natasha)

        self.assertEqual(primary, "violence")
        self.assertIn("fear", secondary)

    def test_fear_scene_without_violence_stays_fear(self):
        natasha = is_suspicious_scene(
            "В темном коридоре слышится странный звук. Марине страшно, она видит тень."
        )

        primary, secondary = primary_category_from_evidence("fear", natasha)

        self.assertEqual(primary, "fear")
        self.assertNotIn("violence", secondary)

    def test_neutral_sentence_does_not_match_profanity(self):
        scores, matches = score_curated_terms("Марина спокойно читает письмо и закрывает окно.")

        self.assertEqual(scores["profanity"], 0)
        self.assertEqual(matches["profanity"], [])

    def test_safe_contexts_do_not_raise_risk(self):
        examples = [
            ("Олег ударил по мячу, и игра продолжилась.", "violence"),
            ("Ане страшно опоздать на поезд.", "fear"),
            ("Марина режет торт ножом для торта.", "violence"),
            ("Ты так старалась. Училась кровь из носу. Но результаты тестов не улучшаются.", "violence"),
            ("Этот провал стал ударом по репутации компании.", "violence"),
            ("После отпуска она выглядела кровь с молоком.", "violence"),
            ("Диплом достался ему потом и кровью.", "violence"),
            ("От стыда кровь бросилась ему в голову.", "violence"),
            ("Горячая кровь, я серьёзно.", "violence"),
            ("У меня кровь не холодная, Андрей.", "violence"),
            ("Зачем вам кровь на руках?", "violence"),
            ("Кровь циркулирует через синтетическую пуповину.", "violence"),
            ("Врач назначил анализ крови и проверил группу крови.", "violence"),
            ("Двенадцать грамм попали в кровь.", "violence"),
            ("Словно черная кровь, авиационное топливо сочится из корпуса.", "violence"),
            ("У меня сердце кровью обливается, когда я вижу эти оценки.", "violence"),
            ("Мне страшно интересно, чем закончится эта история.", "fear"),
            ("Главная героиня романа возвращается домой.", "substance"),
            ("У него страсть к музыке и книгам.", "sexual"),
            ("Они решили убить время до поезда.", "violence"),
            ("Ножки стола шатались на неровном полу.", "violence"),
            ("Дети играли с водяным пистолетом во дворе.", "violence"),
            ("Мастер наносит герметик пистолетом для герметика.", "violence"),
            ("Она приклеила декорацию клеевым пистолетом.", "violence"),
            ("На столе лежит строительный пистолет для монтажной пены.", "violence"),
            ("Юмор стал его главным оружием в споре.", "violence"),
            ("Главное оружие актера — голос и пауза.", "violence"),
            ("Он режет хлеб ножом для хлеба.", "violence"),
            ("Дизайнер аккуратно режет бумагу макетным ножом для бумаги.", "violence"),
            ("Театральная труппа приехала на фестиваль.", "violence"),
            ("Это была душевная рана, а не физическая травма.", "violence"),
            ("Психологическая травма детства мешает герою доверять людям.", "violence"),
            ("Какой-то косяк в проекте надо исправить утром.", "substance"),
            ("Косяк рыб прошел вдоль берега.", "substance"),
            ("Голая правда звучала неприятно.", "sexual"),
            ("Голые факты не оставляли места спору.", "sexual"),
            ("Доклад был о сексизме в рекламе.", "sexual"),
            ("Ужасно красиво получилось.", "fear"),
            ("Кошмарно интересно наблюдать за репетицией.", "fear"),
            ("Тони спрашивает: что за паника?", "fear"),
            ("Давайте без паники, у нас есть время.", "fear"),
            ("Не паникуйте, поезд задерживается.", "fear"),
            ("Повода для паники нет.", "fear"),
            ("Какой у тебя номер социального страхования?", "fear"),
            ("Она проверила страховку и страховой полис.", "fear"),
            ("Альпинист отстегнул страховочный трос.", "fear"),
            ("Он весь день бил баклуши вместо работы.", "violence"),
            ("В этом городе жизнь бьет ключом.", "violence"),
            ("Сценарист бьется над задачей уже неделю.", "violence"),
            ("Бьюсь об заклад, она придет вовремя.", "violence"),
            ("После отказа он совсем упал духом.", "violence"),
            ("После кризиса упали продажи и рейтинг.", "violence"),
            ("Мы думали, что серьезно ударили по их бизнесу.", "violence"),
            ("Удары молотка отдавались эхом в мастерской.", "violence"),
            ("Сами столы завалены внутренностями различных приборов.", "violence"),
            ("Две длинные тени ложатся на землю.", "fear"),
            ("Луна отбрасывает красивые тени на поверхность планеты.", "fear"),
            ("Страсть, с которой вы отстаиваете волю народа, заметна всем.", "sexual"),
            ("У него страсть к науке и искусству.", "sexual"),
            ("Ему не хватает ловкости, чтобы собрать коробку аккуратно.", "violence"),
            ("Повсюду, на сколько хватает глаз, видны скалы.", "violence"),
            ("Джейк хватает рюмку и выпивает её к всеобщему веселью.", "violence"),
            ("Мун-Кван схватила телефон, но это еще далеко не конец.", "violence"),
            ("Он смотрит, как копьё падает, вращаясь, в реку.", "violence"),
            ("Мяч падает в грязь мимо намеченной лунки.", "violence"),
            ("Тут взгляд падает на экран поиска цели.", "violence"),
            ("Конни упала в обморок, сойдя с самолета.", "violence"),
            ("Вид у тебя кошмарный.", "fear"),
            ("У тебя что, кошмарные месячные?", "fear"),
            ("Он отощал, под глазами залегли глубокие тени.", "fear"),
            ("Интимность жеста удивляет ее.", "sexual"),
            ("Нео слышит удары собственного сердца.", "violence"),
            ("Отдаленно слышны удары Апока по клавиатуре.", "violence"),
            ("Он прикидывает траекторию удара в направлении чашки.", "violence"),
            ("Норм переводит: Последняя Тень.", "fear"),
            ("Легендарный Наездник Последней Тени идет к ним.", "fear"),
            ("Ее голос действует гипнотически, слова проникают подобно наркотику.", "substance"),
            ("В саду растет декоративный табак с белыми цветами.", "substance"),
            ("Рассада табака стояла у окна.", "substance"),
            ("Я работаю в Управлении по борьбе с наркотиками.", "substance"),
            ("Милый друг спрашивает: борьба с наркотиками?", "substance"),
            ("А наркотикам и алкоголю, просто скажите нет.", "substance"),
            ("Наркотики — это угроза для нашего общества.", "substance"),
            ("В прошлом году возбудили больше уголовных дел по наркотикам.", "substance"),
            ("Все наркотики, что мы найдем, вы сможете конфисковать.", "substance"),
            ("Финальные титры окутаны сексуальной атмосферой песни.", "sexual"),
            ("Контраст между сексуальным рок-н-рольным треком и лицом героини интересен.", "sexual"),
            ("Породистая сука привела щенков.", "profanity"),
            ("Щенята сосали молодую суку.", "profanity"),
        ]

        for text, category in examples:
            with self.subTest(text=text):
                natasha = is_suspicious_scene(text)
                self.assertFalse(natasha["normalized_flags"].get(category, False))

    def test_bloodshot_eyes_are_remapped_without_injury_context(self):
        natasha = is_suspicious_scene("Его глаза налиты кровью.")

        self.assertTrue(natasha["is_suspicious"])
        self.assertFalse(natasha["normalized_flags"].get("violence", False))
        self.assertTrue(natasha["normalized_flags"].get("fear", False))
        self.assertEqual(natasha["matched_terms"].get("fear"), ["глаза налиты кровью"])

    def test_bloodshot_eyes_from_fatigue_are_safe(self):
        natasha = is_suspicious_scene("Его глаза налиты кровью от усталости и бессонницы.")

        self.assertFalse(natasha["is_suspicious"])
        self.assertFalse(natasha["normalized_flags"].get("violence", False))
        self.assertFalse(natasha["normalized_flags"].get("fear", False))

    def test_bloodshot_eyes_with_injury_context_keep_violence(self):
        natasha = is_suspicious_scene("После удара его глаза залиты кровью, лицо разбито.")

        self.assertTrue(natasha["normalized_flags"].get("violence", False))
        self.assertIn("кровь", natasha["matched_terms"].get("violence", []))

    def test_fear_idioms_with_blood_are_fear_not_violence(self):
        examples = [
            "От этого звука кровь стынет в жилах.",
            "Когда дверь скрипнула, у нее волосы дыбом встали.",
        ]

        for text in examples:
            with self.subTest(text=text):
                natasha = is_suspicious_scene(text)
                self.assertFalse(natasha["normalized_flags"].get("violence", False))
                self.assertTrue(natasha["normalized_flags"].get("fear", False))

    def test_literal_high_risk_terms_still_raise_risk(self):
        examples = [
            ("После удара видна кровь и рана.", "violence"),
            ("После удара кровь течет из носа.", "violence"),
            ("Он достал нож и угрожает прохожему.", "violence"),
            ("Он наставляет пистолет на прохожего.", "violence"),
            ("Персонаж находит оружие и готовится стрелять.", "violence"),
            ("На полу лежит труп.", "violence"),
            ("После удара он упал на пол.", "violence"),
            ("Она хватает его за руку, крича и замахиваясь кулаком.", "violence"),
            ("Волк хватает зубами Джейка за руку.", "violence"),
            ("Толпа в панике бежит к выходу.", "fear"),
            ("Его охватывает паника.", "fear"),
            ("Персонаж покупает героин.", "substance"),
            ("Она зажигает сигарету и глубоко затягивается.", "substance"),
            ("Подростки продают наркотики на углу.", "substance"),
            ("Лион привозил наркотики и увозил наличные.", "substance"),
            ("Керосин выделяет наркотик из листьев.", "substance"),
            ("Они прямо обсуждают секс.", "sexual"),
            ("Сексуальная сцена длится несколько минут.", "sexual"),
            ("Он заставляет ее трепетать, как секс-игрушка.", "sexual"),
            ("Герой произносит: сука.", "profanity"),
            ("Он кричит: блядь!", "profanity"),
        ]

        for text, category in examples:
            with self.subTest(text=text):
                natasha = is_suspicious_scene(text)
                self.assertTrue(natasha["normalized_flags"].get(category, False))

    def test_legal_retrieval_uses_evidence_terms(self):
        context = retrieve_legal_context(
            category="violence",
            level=4,
            rating="18+",
            text="После удара видна кровь и рана.",
            evidence=[
                {"matched_term": "кровь", "text": "видна кровь"},
                {"matched_term": "рана", "text": "рана"},
            ],
        )

        self.assertGreaterEqual(len(context), 1)
        self.assertEqual(context[0]["category"], "violence")
        self.assertIn("кровь", context[0]["matched_evidence_terms"])
        self.assertEqual(context[0]["id"], "policy-violence-severe")
        self.assertIn("level", context[0]["retrieval_reason"])
        self.assertIn("evidence", context[0]["retrieval_reason"])

    def test_evidence_snippet_uses_complete_sentence_window(self):
        text = (
            "The family folds pizza boxes at the table. "
            "After the удар, the victim sees blood on the floor. "
            "Neighbors call for help."
        )

        evidence = evidence_items(text, {"violence": ["удар"]})

        self.assertEqual(len(evidence), 1)
        self.assertIn("удар", evidence[0]["text"])
        self.assertTrue(evidence[0]["text"].startswith("The family") or evidence[0]["text"].startswith("After"))
        self.assertFalse(evidence[0]["text"].startswith("fter"))

    def test_legal_retrieval_prefers_level_specific_context(self):
        mild = retrieve_legal_context(
            category="violence",
            level=1,
            rating="6+",
            text="Герой толкает соседа, конфликт сразу прекращается.",
            evidence=[{"matched_term": "толкает", "text": "Герой толкает соседа"}],
            limit=1,
        )
        severe = retrieve_legal_context(
            category="violence",
            level=4,
            rating="18+",
            text="После нападения видны кровь, рана и тяжелые травмы.",
            evidence=[
                {"matched_term": "кровь", "text": "видны кровь и рана"},
                {"matched_term": "рана", "text": "рана"},
            ],
            limit=1,
        )

        self.assertEqual(mild[0]["id"], "policy-violence-mild")
        self.assertEqual(severe[0]["id"], "policy-violence-severe")
        self.assertGreater(severe[0]["retrieval_score"], mild[0]["retrieval_score"])

    def test_legal_retrieval_has_safe_context(self):
        context = retrieve_legal_context(
            category="safe",
            level=0,
            rating="0+",
            text="Друзья спокойно обсуждают учебу и планы на выходные.",
            evidence=[],
            limit=1,
        )

        self.assertEqual(context[0]["id"], "policy-safe-general")
        self.assertEqual(context[0]["policy_version"], "2026-05-28")


if __name__ == "__main__":
    unittest.main()
