# Copyright 2021 AGEPoly - Téo Goddet
# @author: Téo Goddet <teo.goddet@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "EDI Bank statement import",
    "summary": """Plug account_statement_import_file into EDI machinery.""",
    "version": "18.0.1.0.0",
    "development_status": "Alpha",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/edi",
    "author": "AGEPoly,Odoo Community Association (OCA)",
    "maintainers": ["TeoGoddet"],
    "depends": ["edi_oca", "account_statement_import_file"],
    "data": ["data/data.xml"],
    "auto_install": True,
}
