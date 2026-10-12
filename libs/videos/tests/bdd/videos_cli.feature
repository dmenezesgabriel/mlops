Feature: Produce a video from a YAML concept definition

  `videos` loads concept definitions from `--definitions-dir`, renders each
  narrative beat through the Director pipeline, lints the produced scene
  artifacts, then exits 0 or fails with a named error. These scenarios drive
  the assembled argv → registry → pipeline → artifact-lint loop; only the
  absent `manim` extra is faked (renderer + scene builder), so the linter
  seam that killed real renders under cv2 5.x stays real.

  Scenario: A valid definition produces linted scene previews
    Given a definitions directory with a valid concept "demo_concept"
    When I run "videos" for "demo_concept"
    Then the command exits with code 0
    And stdout shows "Successfully produced video for concept: demo_concept"
    And the artifact "previews/scenes/demo_concept_beat_0.mp4" exists in the output directory
    And the artifact "previews/scenes/demo_concept_beat_0.png" exists in the output directory
    And the artifact "previews/scenes/demo_concept_beat_1.mp4" exists in the output directory

  Scenario: The final quality flag produces the final artifact
    Given a definitions directory with a valid concept "demo_concept"
    When I run "videos" for "demo_concept" at "final" quality
    Then the command exits with code 0
    And the artifact "final/demo_concept.mp4" exists in the output directory

  Scenario: Every definition in the directory produces its own artifacts
    Given a definitions directory with a valid concept "alpha_concept"
    And a definitions directory with a valid concept "beta_concept"
    When I run "videos" for "alpha_concept"
    And I run "videos" for "beta_concept"
    Then every command exits with code 0
    And the artifact "previews/scenes/alpha_concept_beat_0.mp4" exists in the output directory
    And the artifact "previews/scenes/beta_concept_beat_0.mp4" exists in the output directory

  Scenario: A missing definitions directory exits with a named error
    When I run "videos" for "demo_concept" against a missing definitions directory
    Then the command exits with code 1
    And stderr shows "Definitions directory not found"

  Scenario: An unknown concept exits with a named error
    Given a definitions directory with a valid concept "demo_concept"
    When I run "videos" for "ghost_concept"
    Then the command exits with code 1
    And stderr shows "Failed to produce video"
    And stderr shows "Unknown concept"

  Scenario: A scene preview that fails the visual linter fails the produce
    Given a definitions directory with a valid concept "demo_concept"
    And a renderer producing a blank preview image
    When I run "videos" for "demo_concept"
    Then the command exits with code 1
    And stderr shows "Failed to produce video"
    And stderr shows "Visual Linter failed"

  Scenario: A corrupt scene video fails the video linter
    Given a definitions directory with a valid concept "demo_concept"
    And a renderer producing a corrupt scene video
    When I run "videos" for "demo_concept"
    Then the command exits with code 1
    And stderr shows "Failed to produce video"
    And stderr shows "Video Linter failed"
