from dotenv import load_dotenv

from eagent.cli import run_cli

load_dotenv()


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
