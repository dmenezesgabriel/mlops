from pathlib import Path


class YellowTaxiTripPreprocessor:
    """Clean raw trip records and aggregate them into hourly trip counts.

    Stub left for the specialization exercises — calls raise
    NotImplementedError.

    Example:
        YellowTaxiTripPreprocessor().preprocess(Path("data/raw"), Path("data/interim"))
    """

    def preprocess(self, raw_directory: Path, output_directory: Path) -> Path:
        raise NotImplementedError(
            "YellowTaxiTripPreprocessor.preprocess is not implemented"
        )
