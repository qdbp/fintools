from datetime import datetime
from pathlib import Path

import click
import pandas as pd
from quiffen import Account, AccountType, Category, Qif, Split, Transaction


@click.command()
@click.argument("amz_path", type=Path)
@click.argument("start", type=click.DateTime())
@click.argument("end", type=click.DateTime())
@click.option("--out", "out_fn", type=Path, default=Path("amz.qif"))
def construct_qif_from_amz_csv(amz_path: Path, start: datetime, end: datetime, out_fn: Path) -> None:
    df = pd.read_csv(amz_path)
    df["dt"] = pd.to_datetime(df["Order Date"])

    df = df[df["dt"].dt.to_pydatetime() >= start]
    df = df[df["dt"].dt.to_pydatetime() <= end]
    df = df[df["Order Status"] == "Closed"]

    df = df.sort_values("dt")
    df["Total Discounts"] = df["Total Discounts"].apply(lambda it: float(it.strip("'")))

    out = Qif()

    cat_tax = Category(name="Need").add_child("Tax").add_child("Sales")
    cat_ship = Category(name="Need").add_child("Services").add_child("Shipping+Postage")
    cat_unk = Category(name="Unknown")

    # we don't write any account info, so we just use a dummy account
    qif_acc = Account(name="Dummy")
    out.add_account(qif_acc)

    for oid, odf in df.groupby("Order ID", as_index=True):
        account = odf["Payment Instrument Type"].iloc[0]
        tr_date = odf["dt"].iloc[0].to_pydatetime()

        # skip suspect orders, these will need to be manually entered
        # TODO maybe we can do something with these?
        if "Not Available" in account or "Gift" in account:
            continue

        # create a split for each item in the order, at the given date; agglomerate tax into a separate
        # 1. base transaction
        splits = [
            Split(
                account=qif_acc,
                amount=-(row["Unit Price"] * row["Quantity"]) - row["Total Discounts"],
                date=row["dt"],
                category=cat_unk,
                memo=row["Product Name"],
            )
            for _, row in odf.iterrows()
        ]
        tax_amt = (odf["Unit Price Tax"] * odf["Quantity"]).sum()
        if tax_amt > 0:
            splits.append(
                # tax split
                Split(
                    account=qif_acc,
                    amount=-tax_amt.sum(),
                    category=cat_tax,
                    memo="Tax",
                ),
            )
        # TODO might not be quite right if we have multiple shipments?
        shipping_amt = odf["Shipping Charge"].sum()
        if shipping_amt > 0:
            # shipping split
            splits.append(
                Split(
                    account=qif_acc,
                    amount=-shipping_amt,
                    category=cat_ship,
                    memo="Shipping",
                ),
            )
        total = sum(s.amount for s in splits)
        tr = Transaction(
            memo=f"Amazon order {oid} on {tr_date} (fintools import)",
            date=tr_date,
            amount=total,
            splits=splits,
        )
        qif_acc.add_transaction(tr, header=AccountType.CREDIT_CARD)

    out_fn.unlink(missing_ok=True)
    # strip out account info, this just makes moneydance add dummy accounts.
    lines = out.to_qif().splitlines()[4:-1]
    out_fn.write_text("\n".join(lines))
