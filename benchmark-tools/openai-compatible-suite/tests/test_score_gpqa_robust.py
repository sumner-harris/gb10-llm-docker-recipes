import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "score_gpqa_robust.py"
SPEC = importlib.util.spec_from_file_location("score_gpqa_robust", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExtractAnswerTests(unittest.TestCase):
    def assertExtracts(self, expected, text, method=None):
        result = MODULE.extract_answer(text)
        self.assertEqual(expected, result["answer"])
        if method:
            self.assertEqual(method, result["method"])

    def test_enumerated_options_do_not_override_final_choice(self):
        self.assertExtracts("C", "(A) alpha (B) beta (C) gamma (D) delta\nTherefore C)", "choice_format")

    def test_chemical_z_does_not_override_choice(self):
        self.assertExtracts("A", "The correct structure is A) (Z)-but-2-ene.", "choice_format")

    def test_bare_boxed_letter(self):
        self.assertExtracts("D", "Thus the result is \\boxed{D}.", "boxed")

    def test_answer_colon_has_priority_over_box_and_mentions(self):
        self.assertExtracts("B", "Earlier I considered \\boxed{A}; final **Answer**: **B**.", "answer_colon")

    def test_last_explicit_final_answer_wins_within_primary_tier(self):
        self.assertExtracts("C", "Answer: A. Correction—Answer: C.", "answer_colon")

    def test_ambiguous_mentions_use_explicit_correct(self):
        self.assertExtracts("B", "A and C are tempting, but B is the correct answer.", "explicit_correct")

    def test_non_letter_box_is_not_an_answer(self):
        self.assertIsNone(MODULE.extract_answer(r"The expression is \\boxed{(1+n v)/(n+v)}")["answer"])

    def test_restricts_to_gpqa_a_through_d(self):
        self.assertIsNone(MODULE.extract_answer("Answer: Z")["answer"])


if __name__ == "__main__":
    unittest.main()
