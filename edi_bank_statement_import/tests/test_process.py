# Copyright 2022 Téo Goddet
# @author: Téo Goddet <teo.goddet@gmail.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64
import textwrap
from unittest import mock

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.component.tests.common import TransactionComponentCase


@tagged("post_install", "-at_install")
class TestProcessComponent(AccountTestInvoicingCommon, TransactionComponentCase):
    @classmethod
    def get_default_groups(cls):
        """Grant EDI management rights to the accounting test user."""
        return super().get_default_groups() | cls.env.ref("base_edi.group_edi_manager")

    @classmethod
    def setUpClass(cls):
        """Prepare accounting records and a bank statement EDI backend."""
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context, tracking_disable=True, queue_job__no_delay=True
            )
        )
        cls.journal = cls.company_data["default_journal_bank"]
        cls.backend = cls.env["edi.backend"].create(
            {
                "name": "Bank statement test backend",
                "backend_type_id": cls.env.ref(
                    "edi_bank_statement_import.edi_exchange_backend"
                ).id,
            }
        )
        cls.exc_type = cls.env.ref("edi_bank_statement_import.edi_exchange_type").copy(
            {
                "name": "Test bank statement import",
                "code": "test_bank_statement_import",
                "backend_id": cls.backend.id,
                "advanced_settings_edit": textwrap.dedent(
                    f"""
            components:
                process:
                    usage: input.process.bank.statement
            bank_statement:
                wiz_ctx:
                    random_key: custom
                    journal_id: {cls.journal.id}
            """
                ),
            }
        )
        cls.record = cls.backend.create_record("test_bank_statement_import", {})
        cls.file_content = b"<fake><statement></statement></fake>"
        cls.record._set_file_content(cls.file_content)
        cls.wiz_model = cls.env["account.statement.import"]

    def _create_statement(self, name):
        return self.env["account.bank.statement"].create(
            {
                "name": name,
                "line_ids": [
                    Command.create(
                        {
                            "journal_id": self.journal.id,
                            "date": fields.Date.today(),
                            "payment_ref": name,
                            "amount": 10,
                        }
                    )
                ],
            }
        )

    def test_lookup(self):
        """Resolve the bank statement input component."""
        comp = self.backend._get_component(self.record, "process")
        self.assertEqual(comp._name, "edi.input.bank.statement.process")

    def test_wizard_setup(self):
        """Pass exchange content and configured context to the wizard."""
        comp = self.backend._get_component(self.record, "process")
        wiz = comp._setup_wizard()

        self.assertEqual(wiz._name, self.wiz_model._name)
        self.assertEqual(wiz.env.context["random_key"], "custom")
        self.assertEqual(wiz.env.context["journal_id"], self.journal.id)
        self.assertEqual(
            base64.b64decode(wiz.statement_file),
            self.file_content,
        )
        self.assertEqual(wiz.statement_filename, self.record.exchange_filename)

    def test_wizard_process(self):
        """Forward imported statement IDs to the result handler."""
        comp = self.backend._get_component(self.record, "process")
        statement = self._create_statement("Test Statement")

        def import_single_file(file_data, result):
            self.assertEqual(file_data, self.file_content)
            self.assertEqual(result, {"statement_ids": [], "notifications": []})
            result["statement_ids"].append(statement.id)

        mock1 = mock.patch.object(
            type(self.wiz_model),
            "import_single_file",
            side_effect=import_single_file,
        )
        mock2 = mock.patch.object(type(comp), "_handle_result", return_value=True)
        with mock1 as md_import_single_file, mock2 as md_handle_result:
            self.assertTrue(comp.process())
            md_import_single_file.assert_called_once()
            md_handle_result.assert_called_once_with(
                [statement.id], self.record.exchange_filename
            )

    def test_no_statement(self):
        """Log an import without new statements without linking a record."""
        comp = self.backend._get_component(self.record, "process")
        result = comp._handle_result([], self.record.exchange_filename)

        self.assertEqual(comp.exchange_record.res_id, False)
        self.assertEqual(comp.exchange_record.model, False)
        self.assertEqual(result, True)
        self.assertFalse(comp.exchange_record.related_exchange_ids)
        self.assertTrue(
            any(
                "already imported" in message.body
                for message in self.record.message_ids
            )
        )

    def test_single_statement_result_with_legacy_auto_post(self):
        """Link a statement without calling the removed posting action."""
        statement = self._create_statement("Test Statement")
        self.record.type_id.advanced_settings_edit = textwrap.dedent(
            """
            components:
                process:
                    usage: input.process.bank.statement
            bank_statement:
                auto_post: true
            """
        )

        comp = self.backend._get_component(self.record, "process")
        comp._handle_result([statement.id], self.record.exchange_filename)

        self.assertEqual(comp.exchange_record.res_id, statement.id)
        self.assertEqual(comp.exchange_record.model, "account.bank.statement")
        self.assertEqual(statement.line_ids.move_id.state, "posted")
        self.assertFalse(comp.exchange_record.related_exchange_ids)

    def test_multiple_statement_result(self):
        """Link each imported statement to a processed child exchange."""
        statement1 = self._create_statement("Test Statement 1")
        statement2 = self._create_statement("Test Statement 2")

        comp = self.backend._get_component(self.record, "process")
        comp._handle_result(
            [statement1.id, statement2.id], self.record.exchange_filename
        )

        self.assertEqual(len(comp.exchange_record.related_exchange_ids), 2)
        for child_exch in comp.exchange_record.related_exchange_ids:
            self.assertIn(child_exch.res_id, [statement1.id, statement2.id])
            self.assertEqual(child_exch.model, "account.bank.statement")
            self.assertEqual(child_exch.edi_exchange_state, "input_processed")
            self.assertEqual(child_exch.backend_id, self.backend)
            self.assertEqual(child_exch.type_id, self.exc_type)

        self.assertEqual(statement1.line_ids.move_id.state, "posted")
        self.assertEqual(statement2.line_ids.move_id.state, "posted")
        self.assertFalse(self.record.res_id)
        self.assertEqual(
            len(
                self.record.message_ids.filtered(
                    lambda message: "Multiple Bank Statements created" in message.body
                )
            ),
            1,
        )
