"""Limpeza dos comentários e conversão dos emojis.

A limpeza é mínima de propósito: o modelo de embeddings entende a frase
natural, e remover palavras como "não" inverteria o sentido. Os emojis só são
trocados por palavras no texto que vira embedding; o texto mostrado ao gestor
mantém o que o cliente escreveu.
"""

import re

# Emojis mais frequentes na base e a palavra que entra no lugar de cada um.
# 😂, 🤔 e 💥 ficam de fora porque podem ser elogio ou crítica.
EMOJI_WORDS = {
    "👍": "aprovado",
    "🤙": "aprovado",
    "👎": "reprovado",
    "👌": "ótimo",
    "👏": "palmas",
    "🌟": "excelente",
    "🔝": "excelente",
    "😡": "irritado",
    "😠": "irritado",
    "😤": "irritado",
    "😞": "decepcionado",
    "😔": "decepcionado",
    "😢": "triste",
    "😭": "triste",
    "😍": "adorei",
    "🥰": "adorei",
    "😘": "adorei",
    "❤": "amei",
    "💖": "amei",
    "💓": "amei",
    "😊": "satisfeito",
    "🙂": "satisfeito",
    "☺": "satisfeito",
    "😉": "satisfeito",
    "🤗": "satisfeito",
    "😀": "feliz",
    "😁": "feliz",
    "😃": "feliz",
    "😄": "feliz",
    "😆": "feliz",
    "🙏": "obrigado",
}

# Carinhas de texto, só quando não estão coladas em letras ou números
SMILEY_WORDS = {
    ":)": "satisfeito",
    ":-)": "satisfeito",
    "=)": "satisfeito",
    ";)": "satisfeito",
    ";-)": "satisfeito",
    ":(": "insatisfeito",
    ":-(": "insatisfeito",
    ":D": "feliz",
    "=D": "feliz",
}
SMILEY_PATTERN = re.compile(r"(?<!\w)(" + "|".join(re.escape(s) for s in SMILEY_WORDS) + r")(?!\w)")

# Caracteres invisíveis que aparecem em textos colados de outros lugares
INVISIBLE_PATTERN = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​﻿]")

# Modificadores de tom de pele, seletor de variação e junção de emojis:
# só mudam a aparência do emoji anterior e saem do texto do embedding
EMOJI_MODIFIERS_PATTERN = re.compile(r"[\U0001F3FB-\U0001F3FF️‍]")

LETTER_PATTERN = re.compile(r"[A-Za-zÀ-ÿ]")


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text: str) -> str:
    """Texto mostrado ao gestor: sem caracteres invisíveis e com espaços normalizados."""
    return normalize_spaces(INVISIBLE_PATTERN.sub("", text))


def to_embedding_text(text: str) -> str:
    """Texto que vira embedding: limpo e com os emojis e as carinhas trocados por palavras."""
    text = EMOJI_MODIFIERS_PATTERN.sub("", clean_text(text))
    text = SMILEY_PATTERN.sub(lambda match: f" {SMILEY_WORDS[match.group(1)]} ", text)
    text = "".join(f" {EMOJI_WORDS[char]} " if char in EMOJI_WORDS else char for char in text)
    return normalize_spaces(text)


def has_letters(text: str) -> bool:
    return bool(LETTER_PATTERN.search(text))


def join_title_and_message(title: str | None, message: str) -> str:
    """Junta título e mensagem, com um ponto no meio se o título não terminar em pontuação."""
    if title is None or not title.strip():
        return message
    title = title.strip()
    separator = " " if title[-1] in ".!?" else ". "
    return f"{title}{separator}{message}"
