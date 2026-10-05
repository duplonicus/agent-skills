import csv
import io


def export_orders(orders, delimiter=","):
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter)
    writer.writerow(["id", "customer", "total"])
    for o in orders:
        writer.writerow([o["id"], o["customer"], o["total"]])
    return ("﻿" + buf.getvalue()).encode("utf-8")
