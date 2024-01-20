from datetime import datetime
from decimal import Decimal
from pathlib import Path

import click
from lxml.etree import Element
from ofxtools import OFXTree


def write_atm_line(element: Element) -> str:
    amt = Decimal(element.find(".//TRNAMT").text)
    memo = "(".join(element.find(".//MEMO").text.split("(")[:-1]).strip()
    date = datetime.strptime(element.find(".//DTPOSTED").text[:8], "%Y%m%d").date()  # noqa: DTZ007

    return f'{date.isoformat()},"{memo}",{amt:.2f}'


@click.command()
@click.argument("fn", type=Path)
def parse_ibkr_qfx(fn: Path) -> None:
    """
    Parses the raw IBKR QFX file FN into a split representation, factoring out
    mastercard transactions to a separate CSV file.
    """

    out_qfx_fn = fn.parent.joinpath(fn.stem + ".out.qfx")
    out_csv_fn = fn.parent.joinpath(fn.stem + ".csv")

    with fn.open("rb") as f:
        parser = OFXTree()
        tree = parser.parse(f)

    transactions = []

    for tran in tree.findall(".//INVBANKTRAN"):
        ttype = tran.find("./STMTTRN/TRNTYPE").text
        if ttype == "ATM":
            transactions.append(write_atm_line(tran))
            tran.find(".//MEMO").text = "MasterCard Transaction"

    with fn.open() as f_in, out_qfx_fn.open("wb") as f_out:
        # copy header
        f_out.write("".join(f_in.readlines()[:9]).encode("utf-8"))
        parser.write(f_out)

    out_csv_fn.write_text("\n".join(transactions))
