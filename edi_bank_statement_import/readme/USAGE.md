For each bank/bank account, you need to create an exchange type.
You can use the supplied **Bank Statement Import** exchange type as a template.
Set the direction to **Input** and select **Component Handler for EDI** as the
processor, including on existing exchange types migrated from Odoo 14.

On your exchange type, go to advanced settings and add the following:

    [...]
    components:
        process:
            usage: input.process.bank.statement

Odoo 18 automatically posts bank transactions when they are imported.
Statements no longer have a separate posting action. The old
`bank_statement.auto_post` setting has no effect and can be removed from
existing exchange types; setting it to `false` does not keep transactions
in draft.

You may also specify some context for the bank statement import wizard:

    [...]
    bank_statement:
        wiz_ctx:
            journal_id: 5

Use `journal_id` to select a bank journal when the file does not identify
the bank account. With `account_statement_import_sheet_file` installed,
you can also select a sheet mapping:

    [...]
    bank_statement:
        wiz_ctx:
            default_sheet_mapping_id: 5

Replace these example IDs with the IDs of your own records.

A single imported statement is linked directly to the exchange. If the file
creates several statements, each is linked to a child exchange. Files containing
only previously imported transactions are logged on the exchange without
creating new statements. Import errors remain errors in the EDI workflow.
