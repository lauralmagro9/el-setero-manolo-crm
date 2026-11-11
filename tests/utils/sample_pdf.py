"""Write a sample invoice PDF to the path given as first argument (for eyeballing the layout)."""

import sys

from tests.unit.test_invoice_pdf import build_invoice

from crm.services.invoice_pdf import render_invoice_pdf

if __name__ == "__main__":
    with open(sys.argv[1], "wb") as f:
        f.write(render_invoice_pdf(build_invoice()))
