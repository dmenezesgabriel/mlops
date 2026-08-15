# Machine Learning Specialization — Course Organizer

Study notes and lab notebooks for the DeepLearning.AI Machine Learning
Specialization, grouped by course and week.

## Courses

- **Course 1 — Supervised Machine Learning: Regression and Classification**
  notes in `docs/lessons/01_supervised_machine_learning/`,
  notebooks in `notebooks/01_supervised_machine_learning/`
- **Course 2 — Advanced Learning Algorithms**
  notes in `docs/lessons/02_advanced_learning_algorithms/`,
  notebooks in `notebooks/02_advanced_learning_algorithms/`
- **Course 3 — Unsupervised Learning, Recommenders, Reinforcement Learning**
  notes in `docs/lessons/03_unsupervised_learning_recommenders_rl/`,
  notebooks in `notebooks/03_unsupervised_learning_recommenders_rl/`

Each `week_XX.md` file lists the week's lesson topics; fill in your own notes
below the stubs.

## Commands

```bash
make collect PROJECT=ml_specialization
make preprocess PROJECT=ml_specialization
make features PROJECT=ml_specialization
make train PROJECT=ml_specialization
make evaluate PROJECT=ml_specialization
```

Scaffolded with `make scaffold PROJECT=ml_specialization`. The pipeline stubs,
configs, feature repo, and MLflow tracking exist per the monorepo template even
though the primary use is note and notebook organization.
