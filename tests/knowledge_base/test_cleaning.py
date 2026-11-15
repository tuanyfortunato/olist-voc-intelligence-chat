from src.knowledge_base.cleaning import (
    clean_text,
    has_letters,
    join_title_and_message,
    to_embedding_text,
)


def test_clean_text_normalizes_spaces_and_keeps_words():
    assert clean_text("  Péssimo\n\nproduto,   não   chegou ") == "Péssimo produto, não chegou"


def test_clean_text_removes_zero_width_and_control_chars():
    assert clean_text("Muito​ bom\x07﻿") == "Muito bom"


def test_clean_text_keeps_emojis():
    assert clean_text("Amei 😍") == "Amei 😍"


def test_embedding_text_converts_emojis_and_smileys():
    assert to_embedding_text("👍👍👍") == "aprovado aprovado aprovado"
    assert to_embedding_text("Muito bom :)") == "Muito bom satisfeito"
    assert to_embedding_text("Chegou quebrado 😡") == "Chegou quebrado irritado"
    assert to_embedding_text("Não gostei :(") == "Não gostei insatisfeito"
    assert to_embedding_text("Entrega rápida :D") == "Entrega rápida feliz"


def test_embedding_text_converts_most_frequent_emoji():
    assert to_embedding_text("Parabéns 👏👏") == "Parabéns palmas palmas"


def test_embedding_text_drops_skin_tone_and_variation_selector():
    assert to_embedding_text("Top 👍🏽") == "Top aprovado"
    assert to_embedding_text("Amei ❤️") == "Amei amei"


def test_embedding_text_keeps_ambiguous_emojis():
    assert to_embedding_text("Entrega rápida 😂") == "Entrega rápida 😂"


def test_smiley_inside_text_is_not_converted():
    assert to_embedding_text("Horário 10:00 (manhã)") == "Horário 10:00 (manhã)"


def test_has_letters():
    assert not has_letters("...")
    assert not has_letters("10")
    assert not has_letters("100%")
    assert not has_letters("👎")
    assert has_letters(to_embedding_text("👎"))
    assert has_letters("Não")


def test_join_title_and_message():
    assert join_title_and_message(None, "Chegou rápido") == "Chegou rápido"
    assert join_title_and_message("   ", "Chegou rápido") == "Chegou rápido"
    assert join_title_and_message("Ótimo", "Chegou rápido") == "Ótimo. Chegou rápido"
    assert join_title_and_message("Péssimo!", "Não chegou") == "Péssimo! Não chegou"
