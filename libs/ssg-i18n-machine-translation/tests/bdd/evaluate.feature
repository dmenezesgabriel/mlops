Feature: Evaluate machine translation quality gates

  `ssg-i18n-evaluate` compares a translated markdown tree against its
  source tree — and optionally against a translation catalog scored by the
  transformers translator — then exits 0 only when every threshold holds:
  structural parity, fallback rate, wikilink/table integrity, and BLEU.

  Scenario: A faithful translation and catalog pass with a BLEU score
    Given a source tree with a page "guide" containing "A short English page."
    And the translated tree has "guide" containing "Uma página curta."
    And a catalog mapping "The collector gathers quite a few long sentences" to "O coletor reúne várias sentenças longas"
    And the transformers pipeline returns catalog-faithful translations
    When I run "ssg-i18n-evaluate" over the trees
    Then the evaluation exits with code 0
    And the output shows "Evaluation PASSED!"
    And the output shows "BLEU score: 100.0"

  Scenario: A page missing from the translated tree fails
    Given a source tree with a page "guide" containing "A short English page."
    And the translated tree is empty
    When I run "ssg-i18n-evaluate" over the trees
    Then the evaluation exits with code 1
    And the output shows "FAILURES:"
    And the output shows "Missing translated file"

  Scenario: Untranslated English content fails the fallback gate
    Given a source tree with a page "guide" containing "This is a long English sentence here."
    And the translated tree has "guide" containing "This is a long English sentence here."
    When I run "ssg-i18n-evaluate" over the trees
    Then the evaluation exits with code 1
    And the output shows "FAILURES:"
    And the output shows "Fallback rate"

  Scenario: A structurally divergent page fails the evaluation
    Given a source tree with a page "guide" containing two paragraphs "Guide heading text" and "First paragraph text."
    And the translated tree has "guide" containing "Texto do primeiro parágrafo."
    When I run "ssg-i18n-evaluate" over the trees
    Then the evaluation exits with code 1
    And the output shows "FAILURES:"
    And the output shows "STRUCTURE MISMATCH"

  Scenario: A low BLEU score against the catalog fails the gate
    Given a source tree with a page "guide" containing "A short English page."
    And the translated tree has "guide" containing "Uma página curta."
    And a catalog mapping "The collector gathers quite a few long sentences" to "O coletor reúne várias sentenças longas"
    And the transformers pipeline returns the source text unchanged
    When I run "ssg-i18n-evaluate" over the trees with "--min-bleu-score" "99"
    Then the evaluation exits with code 1
    And the output shows "FAILURES:"
    And the output shows "BLEU score"
    And the output shows "below threshold"
