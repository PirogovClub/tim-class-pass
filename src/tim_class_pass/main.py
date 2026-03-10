def main():
    import sys
    from pathlib import Path

    # Ensure project root (containing pipeline/) is on path when running as console script
    if "pipeline" not in sys.modules:
        path = Path(__file__).resolve().parent
        for _ in range(5):
            if (path / "pipeline" / "main.py").exists():
                root = str(path)
                if root not in sys.path:
                    sys.path.insert(0, root)
                break
            path = path.parent
        else:
            path = None

    from pipeline.main import main as pipeline_main
    pipeline_main()


if __name__ == "__main__":
    main()
