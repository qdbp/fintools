import click

from fintools.parse_ibkr_qfx import parse_ibkr_qfx


@click.group()
def main() -> None:
    pass


main.add_command(parse_ibkr_qfx)

if __name__ == "__main__":
    main()
