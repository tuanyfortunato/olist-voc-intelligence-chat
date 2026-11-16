from src.themes.taxonomy import SECTOR_IDS, SECTORS, THEME_IDS, THEMES, themes_of_sector


def test_ids_are_unique_and_every_theme_has_a_sector():
    assert len(THEME_IDS) == len(THEMES)
    assert len(SECTOR_IDS) == len(SECTORS)
    assert all(theme.sector in SECTOR_IDS for theme in THEMES)


def test_every_sector_has_themes_and_strengths_are_praise():
    for sector in SECTORS:
        assert themes_of_sector(sector.id)
    assert {theme.polarity for theme in THEMES if theme.sector == "fortes"} == {"elogio"}
