from export import export_orders

ORDERS = [{"id": 1, "customer": "Zoë Müller", "total": "19.90"}]


def test_export_has_header():
    assert export_orders(ORDERS).decode("utf-8-sig").splitlines()[0] == "id,customer,total"


def test_export_opens_in_excel_with_accents():
    # Excel only detects UTF-8 when the file starts with a byte order mark.
    assert export_orders(ORDERS).startswith(b"\xef\xbb\xbf")


def test_export_custom_delimiter():
    assert b"1;Zo" in export_orders(ORDERS, delimiter=";")
