# Dataset Storage and Blind-Test Policy

## Folder layout

`	ext
data/
├── source_archives/
│   ├── train/
│   └── blind_test/
├── raw/
│   ├── train/
│   └── blind_test/
│       └── public/
├── private/
│   └── blind_test_ground_truth/
├── reference/
│   ├── train_pack/
│   └── blind_test_pack/
├── interim/
├── processed/
└── manifests/
`

## Rules

- source_archives/ preserves original ZIP files.
- aw/train/ is the only raw source allowed for training.
- aw/blind_test/public/ is used for final prediction only.
- private/blind_test_ground_truth/ is evaluation-only.
- eference/ stores dictionaries, assumptions, reports, and pack scripts.
- interim/ stores temporary transformed data.
- processed/ stores final model-ready features.
- Large/private datasets are ignored by Git.
- Dataset manifests record file hashes and sizes for reproducibility.