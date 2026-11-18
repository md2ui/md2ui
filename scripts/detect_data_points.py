"""Quick CLI to test DataPointDetector.detect_all on a string."""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[1] / "src"))

from md2ui.pipeline.data_point_detector import DataPointDetector


def main():
    if len(sys.argv) < 2:
        print('Usage: uv run scripts/detect_data_points.py "your text here"')
        sys.exit(1)

    text = " ".join(sys.argv[1:])
    detector = DataPointDetector()
    results = detector.detect_all(text)

    if results:
        for r in results:
            print(
                f"  -> [{r['type']}] '{r['matched']}' = {r['value']} [index: {r['start']}-{r['end']}]"
            )
    else:
        print("  -> No data points found")
    print()


if __name__ == "__main__":
    main()
