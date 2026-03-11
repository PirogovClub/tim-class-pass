def main():
    import sys
    from pathlib import Path

    if "pipeline" not in sys.modules:
        path = Path(__file__).resolve().parent
        for _ in range(5):
            if (path / "pipeline" / "usage_report.py").exists():
                root = str(path)
                if root not in sys.path:
                    sys.path.insert(0, root)
                break
            path = path.parent
        else:
            path = None

    from pipeline.usage_report import main as usage_report_main

    usage_report_main()


if __name__ == "__main__":
    main()
