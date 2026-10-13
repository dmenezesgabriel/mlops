## 09_boundaries

| feature | status | detail | latency_ms |
|---|---|---|---|
| syntax error rejected at submit → InvalidRequestException 400 | PASS | InvalidRequestException (400): Exception parsing query: line 1:1: mismatched input 'SELEC'. Expecting: 'ALTER', |  |
| missing OutputLocation on primary → InvalidRequestException 400 | PASS | InvalidRequestException (400): OutputLocation is required: pass ResultConfiguration.OutputLocation or configure |  |
| unknown workgroup rejected at submit → 400 | PASS | InvalidRequestException (400): WorkGroup nb09-no-such does not exist |  |
| disabled workgroup rejects StartQueryExecution → 400 | PASS | InvalidRequestException (400): WorkGroup nb09-dis-b68b48e8 is disabled |  |
| unknown QueryExecutionContext.Catalog → 400 | PASS | InvalidRequestException (400): DataCatalog nb09-no-such-cat does not exist |  |
| non-GLUE catalog rejects query execution → 400 | PASS | InvalidRequestException (400): DataCatalog nb09-cat-b68b48e8 is of type LAMBDA; only GLUE catalogs execute quer |  |
| missing-table SELECT → FAILED with Trino's reason verbatim | PASS | a730ab31-95cf-48be-8c59-f0bf2e59a729 FAILED: line 1:15: Table 'hive.nb09_b68b48e8.missing_table' does not exist | 336.658 |
| duplicate-column CTAS → FAILED with Trino's reason verbatim | PASS | adcdc2d0-1e49-4236-bccd-7218aa5f8bab FAILED: line 1:1: Column name 'a' specified more than once | 328.053 |
| GetQueryResults on a FAILED execution → empty Rows | PASS | adcdc2d0-1e49-4236-bccd-7218aa5f8bab answered Rows=[] |  |
| GetQueryResults on a QUEUED/RUNNING execution → 400 | PASS | InvalidRequestException (400): Query has not yet finished. Current state: RUNNING |  |
| in-flight execution unwound via StopQueryExecution | PASS | 5a176be0-789c-4dbc-bc42-a755ca1951d6 → CANCELLED |  |
| StatementName pattern violation → 400 before the lookup | PASS | InvalidRequestException (400): StatementName must match pattern '[a-zA-Z_][a-zA-Z0-9_@:]{1,256}', got 'nb09-bad |  |
| missing prepared statement → ResourceNotFoundException 404 | PASS | ResourceNotFoundException (404): PreparedStatement nb09_nosuch_b68b48e8 does not exist in workgroup primary |  |
| unknown QueryExecutionId → InvalidRequestException 400 | PASS | InvalidRequestException (400): QueryExecution 00000000-0000-0000-0000-000000000000 does not exist |  |
| out-of-scope ops (session/calculation/DPU/notebook) → shaped 400 | PASS | ListSessions → InvalidRequestException; StartCalculationExecution → InvalidRequestException; ListApplicationDPUSizes → InvalidRequestException; CreateNotebook → InvalidRequestException |  |
