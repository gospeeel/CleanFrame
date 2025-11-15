import re
import os
import json
from pathlib import Path

from docx import Document
import pdfplumber
import chardet


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def is_scene_header(line: str) -> bool:
    """Определяет, является ли строка заголовком сцены в формате «Васильков»."""
    line = line.strip()
    if not line:
        return False

    # Приводим к единому виду: убираем лишние пробелы, нормализуем тире и точки
    line = re.sub(r'[–—]', '-', line)  # заменяем длинные тире на короткое
    line = re.sub(r'\s+', ' ', line)   # сжимаем множественные пробелы

    # Паттерн для сцен вида: "1-1. ИНТ. ...", "2-5. НАТ. ...", "4-12. 70-е инт. ..."
    pattern = r'^\d+-\d+\.\s*(ИНТ\.|НАТ\.|ИНТЕРЬЕР|ЭКСТЕРЬЕР|INT\.|EXT\.)'
    if re.match(pattern, line, re.IGNORECASE):
        return True

    # Дополнительно: если строка начинается с номера вида "1.", "2.", даже без "ИНТ"
    if re.match(r'^\d+\.\s*\S', line):
        return True

    return False


def is_character_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 50:
        return False
    if not stripped.isupper():
        return False
    # Разрешаем буквы, пробелы, тире, точки, цифры (для "ДЕВУШКА 1")
    if not re.match(r'^[А-ЯЁ\s\-\.0-9]+$', stripped):
        return False
    words = stripped.split()
    if len(words) == 0 or len(words) > 5:
        return False
    # Исключаем очевидные действия
    action_keywords = {'СМЕХ', 'ПАУЗА', 'МОЛЧАНИЕ', 'ЗВУК', 'ТИТР', 'СКЛЕЙКА', 'ПЕРЕХОД'}
    if any(kw in stripped for kw in action_keywords):
        return False
    return True


def extract_text_from_docx(path: str) -> list:
    """Возвращает список строк из .docx."""
    doc = Document(path)
    lines = []
    for para in doc.paragraphs:
        text = para.text
        if text.strip():  # сохраняем даже пустые для структуры, но тут фильтруем
            lines.append(text)
    return lines


def extract_text_from_pdf(path: str) -> list:
    """Возвращает список строк из .pdf с указанием номера страницы."""
    lines_with_page = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=1)
            if text:
                for line in text.split('\n'):
                    if line.strip():
                        lines_with_page.append((line, page_num))
    return lines_with_page


# === ОСНОВНОЙ ПАРСЕР ===

def parse_script_lines(lines_with_page: list) -> dict:
    """
    Принимает список строк (для DOCX: [str]; для PDF: [(str, page)]).
    Возвращает структурированный JSON-совместимый объект.
    """
    scenes = []
    current_scene = None
    last_character = None
    current_action_lines = []
    current_dialogue_lines = []

    # Нормализуем вход: приведём к единому формату [(line, page)]
    if isinstance(lines_with_page[0], str):
        lines_with_page = [(line, None) for line in lines_with_page]

    for raw_line, page in lines_with_page:
        line = raw_line.strip()
        if not line:
            continue

        # Если началась новая сцена — сохраняем предыдущую
        if is_scene_header(line):
            # Сохраняем накопленное действие или реплику перед началом сцены
            if current_action_lines:
                if current_scene:
                    current_scene["elements"].append({
                        "type": "action",
                        "text": " ".join(current_action_lines)
                    })
                current_action_lines = []
            if current_dialogue_lines and last_character and current_scene:
                current_scene["elements"].append({
                    "type": "dialogue",
                    "character": last_character,
                    "text": " ".join(current_dialogue_lines)
                })
                current_dialogue_lines = []
                last_character = None

            # Завершаем текущую сцену
            if current_scene is not None:
                scenes.append(current_scene)

            # Начинаем новую
            current_scene = {
                "scene_id": len(scenes) + 1,
                "page": page,
                "elements": []
            }
            last_character = None
            continue

        # Обработка внутри сцены
        if current_scene is None:
            # Пропускаем всё до первой сцены
            continue

        if is_character_line(line):
            # Сохраняем предыдущее действие
            if current_action_lines:
                current_scene["elements"].append({
                    "type": "action",
                    "text": " ".join(current_action_lines)
                })
                current_action_lines = []

            # Сохраняем предыдущую реплику (если была)
            if current_dialogue_lines and last_character:
                current_scene["elements"].append({
                    "type": "dialogue",
                    "character": last_character,
                    "text": " ".join(current_dialogue_lines)
                })
                current_dialogue_lines = []

            last_character = line
        else:
            # Это либо действие, либо продолжение реплики
            if last_character is not None:
                # Продолжение реплики
                current_dialogue_lines.append(line)
            else:
                # Действие
                current_action_lines.append(line)

    # Финальная очистка после цикла
    if current_scene is not None:
        if current_action_lines:
            current_scene["elements"].append({
                "type": "action",
                "text": " ".join(current_action_lines)
            })
        if current_dialogue_lines and last_character:
            current_scene["elements"].append({
                "type": "dialogue",
                "character": last_character,
                "text": " ".join(current_dialogue_lines)
            })
        scenes.append(current_scene)

    return {"scenes": scenes}


# === ФАСАД ДЛЯ ЗАГРУЗКИ ===

def parse_script(file_path: str) -> dict:
    """Основная функция: принимает путь к .docx или .pdf → возвращает JSON."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    if file_path.suffix.lower() == '.docx':
        lines = extract_text_from_docx(str(file_path))
        return parse_script_lines(lines)
    elif file_path.suffix.lower() == '.pdf':
        lines_with_page = extract_text_from_pdf(str(file_path))
        return parse_script_lines(lines_with_page)
    else:
        raise ValueError("Поддерживаются только .docx и .pdf")


# === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===

if __name__ == "__main__":
    import tkinter
    from tkinter import filedialog

    # Скрываем основное окно tkinter
    root = tkinter.Tk()
    root.withdraw()
    root.attributes('-topmost', True)  # Диалог поверх других окон

    # Открываем диалог выбора файла
    input_file = filedialog.askopenfilename(
        title="Выберите сценарий",
        filetypes=[("Сценарий", "*.docx *.pdf")]
    )

    if not input_file:
        print("Файл не выбран.")
        input("Нажмите Enter для выхода...")
        exit()

    try:
        result = parse_script(input_file)
        output_file = Path(input_file).with_suffix('.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ Успешно! Результат сохранён в:\n{output_file}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        input("Нажмите Enter для выхода...")