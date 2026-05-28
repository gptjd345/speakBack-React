from langdetect import detect, LangDetectException


def is_english(text: str) -> bool:
    try:
        return detect(text.strip()) == "en"
    except LangDetectException:
        return False
