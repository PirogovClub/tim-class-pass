"""
List MLX models and/or run health check on the configured server.
Host from env: MLX_SERVICE_BASE_URL, LOCAL_MLX_SERVER, or LOCAL_OLLAMA_SERVER.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from helpers.clients import mlx_client


def main() -> None:
    parser = argparse.ArgumentParser(description="MLX server: list models or health check")
    parser.add_argument("--health", action="store_true", help="Only run health check (GET /health)")
    parser.add_argument("--host", default=None, help="Override host (e.g. http://192.168.1.5:11434)")
    args = parser.parse_args()

    host = mlx_client.normalize_mlx_host(args.host)
    print(f"Host: {host}")

    if args.health:
        try:
            health = mlx_client.health_check(host=args.host)
            print("Health: OK")
            for k, v in health.items():
                print(f"  {k}: {v}")
        except Exception as e:
            print(f"Health check failed: {e}")
            sys.exit(1)
        return

    try:
        models = mlx_client.list_models(host=args.host)
    except Exception as e:
        print(f"Error listing models: {e}")
        print("Check that the MLX service is running on that host.")
        sys.exit(1)
    print(f"Models: {len(models)}")
    for m in models:
        print(f"  {m}")


if __name__ == "__main__":
    main()
