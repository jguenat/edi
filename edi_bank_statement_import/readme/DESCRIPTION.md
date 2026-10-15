Plug bank statement file imports into EDI machinery.

This module uses `account_statement_import_file` to process incoming EDI
exchanges. Bank statements can be retrieved through any EDI backend
(webservice, SFTP, local filesystem, etc.). Install an appropriate
statement-format module, such as `account_statement_import_camt`, to parse
your bank's files.
