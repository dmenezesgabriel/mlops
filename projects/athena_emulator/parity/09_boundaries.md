## 09_boundaries

| feature | status | detail | latency_ms |
|---|---|---|---|
| syntax error rejected at submit → InvalidRequestException 400 | PASS | InvalidRequestException (400): Exception parsing query: line 1:1: mismatched input 'SELEC'. Expecting: 'ALTER', |  |
| missing OutputLocation on primary → InvalidRequestException 400 | PASS | InvalidRequestException (400): OutputLocation is required: pass ResultConfiguration.OutputLocation or configure |  |
| unknown workgroup rejected at submit → 400 | PASS | InvalidRequestException (400): WorkGroup nb09-no-such does not exist |  |
| disabled workgroup rejects StartQueryExecution → 400 | PASS | InvalidRequestException (400): WorkGroup nb09-dis-55d59221 is disabled |  |
| unknown QueryExecutionContext.Catalog → 400 | PASS | InvalidRequestException (400): DataCatalog nb09-no-such-cat does not exist |  |
| non-GLUE catalog rejects query execution → 400 | PASS | InvalidRequestException (400): DataCatalog nb09-cat-55d59221 is of type LAMBDA; only GLUE catalogs execute quer |  |
| missing-table SELECT → FAILED with Trino's reason verbatim | PASS | 7aa09899-9d54-4342-96e2-e252fe377c4b FAILED: line 1:15: Table 'hive.nb09_55d59221.missing_table' does not exist | 356.32 |
| duplicate-column CTAS → FAILED with Trino's reason verbatim | PASS | 6edfcb63-8ac9-4238-9961-3b06ecbadb2e FAILED: line 1:1: Column name 'a' specified more than once | 43.0784 |
| GetQueryResults on a FAILED execution → empty Rows | PASS | 6edfcb63-8ac9-4238-9961-3b06ecbadb2e answered Rows=[] |  |
| GetQueryResults on a QUEUED/RUNNING execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| in-flight execution unwound via StopQueryExecution | PASS | c9dd4011-f2b3-4509-a1ee-5df57f64343f → CANCELLED |  |
| StatementName pattern violation → 400 before the lookup | PASS | InvalidRequestException (400): StatementName must match pattern '[a-zA-Z_][a-zA-Z0-9_@:]{1,256}', got 'nb09-bad |  |
| missing prepared statement → ResourceNotFoundException 404 | PASS | ResourceNotFoundException (404): PreparedStatement nb09_nosuch_55d59221 does not exist in workgroup primary |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400): QueryExecution 00000000-0000-0000-0000-000000000000 does not exist |  |
| out-of-scope ops (session/calculation/DPU/notebook) → shaped 400 | PASS | ListSessions → InvalidRequestException; StartCalculationExecution → InvalidRequestException; ListApplicationDPUSizes → InvalidRequestException; CreateNotebook → InvalidRequestException |  |
