# Copyright 2021 AGEPoly - Téo Goddet
# @author: Téo Goddet <teo.goddet@gmail.>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64

from odoo.addons.component.core import Component


class EDIExchangeBankStatementInput(Component):
    """Process bank statements."""

    _name = "edi.input.bank.statement.process"
    _inherit = "edi.component.input.mixin"
    _usage = "input.process.bank.statement"

    def __init__(self, work_context):
        super().__init__(work_context)
        self.settings = self.type_settings.get("bank_statement", {})

    def process(self):
        """Import the exchange file and link the resulting bank statements."""
        wiz = self._setup_wizard()
        result = {
            "statement_ids": [],
            "notifications": [],
        }

        file_data = base64.b64decode(wiz.statement_file)
        wiz.import_single_file(file_data, result)

        return self._handle_result(result["statement_ids"], wiz.statement_filename)

    def _handle_result(self, statement_ids, filename):
        if not statement_ids:
            # EDI operators may not have chatter write access on exchanges.
            self.exchange_record.sudo().message_post(
                body=self.env._(
                    "You have already imported this file (%s) or this file "
                    "only contains already imported transactions.",
                    filename,
                )
            )
            return True

        if len(statement_ids) == 1:
            self._handle_single_result(self.exchange_record, statement_ids[0])
            return True
        else:
            for statement_id in statement_ids:
                child_exchange = self.exchange_record.create(
                    {
                        "type_id": self.exchange_record.type_id.id,
                        "backend_id": self.exchange_record.backend_id.id,
                        "edi_exchange_state": "input_processed",
                        "parent_id": self.exchange_record.id,
                    }
                )
                self._handle_single_result(child_exchange, statement_id)
            # EDI operators may not have chatter write access on exchanges.
            self.exchange_record.sudo().message_post(
                body=self.env._(
                    "Multiple Bank Statements created (See child exchanges)"
                )
            )
            return True

    def _handle_single_result(self, exchange_record, statement_id):
        statement = self.env["account.bank.statement"].browse(statement_id)
        # Statement lines are posted by Odoo when the importer creates them.
        # EDI operators may not have chatter write access on exchanges.
        exchange_record.sudo().message_post(
            body=self.env._("Bank Statement %s created", statement.display_name)
        )
        exchange_record._set_related_record(statement)

    def _setup_wizard(self):
        """Init a `account.statement.import` instance for current record."""
        wiz_ctx = self.settings.get("wiz_ctx", {})

        wiz_model = "account.statement.import"
        wiz_vals = {
            "statement_filename": self.exchange_record.exchange_filename,
            "statement_file": self.exchange_record._get_file_content(binary=False),
        }
        # Automated EDI users may not have access to the accounting import wizard.
        wiz = self.env[wiz_model].with_context(**wiz_ctx).sudo().create(wiz_vals)

        return wiz
