"""Tests for the helpers shared by the agents."""

from datetime import date

from crm.services.agents.utils import calendar_hint, match_score, normalize_text


class TestNormalizeText:
    """Tests for normalize_text."""

    def test_0_drops_accents_case_and_punctuation(self):
        """Accents, capitals, punctuation and repeated spaces disappear."""
        assert normalize_text("  Frutería  ÑU, S.L. ") == "fruteria nu s l"

    def test_1_none_is_empty(self):
        """None becomes an empty string."""
        assert normalize_text(None) == ""


class TestMatchScore:
    """Tests for match_score."""

    def test_0_exact_match_ignores_accents(self):
        """'garcia' matches 'García' exactly."""
        assert match_score("garcia", "García") == 1.0

    def test_1_all_query_words_inside_candidate(self):
        """A first name alone matches the full name with a high score."""
        assert match_score("Alberto", "Alberto García") == 0.95

    def test_2_typo_still_scores_high(self):
        """A one-letter typo is still a good match."""
        assert match_score("Rebosuelos", "Rebozuelos") > 0.85

    def test_3_unrelated_text_scores_low(self):
        """Different words do not match."""
        assert match_score("chantarelas", "Boletus edulis") < 0.5

    def test_4_empty_values_score_zero(self):
        """Nothing matches an empty text."""
        assert match_score("", "Boletus") == 0.0
        assert match_score("Boletus", None) == 0.0

    def test_5_misspelt_word_matches_one_word_of_a_longer_name(self):
        """'rebosuelos' finds 'Rebozuelos frescos'; a different word still does not."""
        assert match_score("rebosuelos", "Rebozuelos frescos") >= 0.7
        assert match_score("boletus", "Rebozuelos frescos") < 0.7


    def test_6_candidate_named_inside_a_longer_query(self):
        """A company name inside a phrase scores higher than a lone first name inside it."""
        assert match_score("Marta del Bar Y", "Bar Y") > match_score("Marta del Bar Y", "Marta") > 0.7


class TestCalendarHint:
    """Tests for calendar_hint."""

    def test_0_lists_weekday_and_iso_date_from_today(self):
        """Thursday 2026-11-12 is followed by Friday 2026-11-13, for the number of days asked."""
        lines = calendar_hint(date(2026, 11, 12), 3).splitlines()
        assert lines == ["- jueves 2026-11-12", "- viernes 2026-11-13", "- sábado 2026-11-14"]

