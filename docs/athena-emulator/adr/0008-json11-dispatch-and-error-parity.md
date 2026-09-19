# ADR-0008 — JSON 1.1 dispatch and botocore-parity errors; no moto internals

- Status: Accepted
- Date: 2026-09-19

## Context

The Athena protocol is AWS JSON 1.1: `protocol=json`, `jsonVersion=1.1`, 70
operations, all `POST /`, dispatch via the `X-Amz-Target:
Athena_2017_05_18.<Operation>` header — from the canonical model
`research_repos/aws-cli/awscli/botocore/data/athena/2017-05-18/service-2.json`
(byte-identical to the installed botocore model; verified shapes equal).
moto shows the reference shapes of dispatch and error serialization:
- `X-Amz-Target` split in `research_repos/moto/moto/core/responses.py:462-464`;
  request parsing from the service model via botocore parsers (`:468`).
- Errors: body `{"__type": "<ShapeName>", "message": "<msg>"}` from
  `research_repos/moto/moto/core/exceptions.py:100`; header
  `X-Amzn-Errortype: <ShapeName>` and JSON-encoding of `__type` from
  `research_repos/moto/moto/core/serialize.py:492,538`.
- Exception metadata (shape names + `httpStatusCode`) is in `service-2.json`:
  `InvalidRequestException` 400, `ResourceNotFoundException` 404,
  `TooManyRequestsException` 429, `InternalServerException` 500,
  `MetadataException`, `SessionAlreadyExistsException`,
  `TooManyRequestsException`.

## Decision

- `athena-local` implements its own FastAPI application with **a single
  `POST /` route** that dispatches `X-Amz-Target` through an operation
  registry generated/verified against `service-2.json` — no reuse of moto
  response/model machinery (which is coupled to moto's server).
- Request/response schemas are explicit, typed dataclasses checked against the
  model (both direction + optionality); unknown targets → `InvalidRequestException`
  400 with the target name in the message.
- Errors serialize exactly as botocore expects:
  `{"__type": "<ExceptionShapeName>", "message": "<message>"}` + `X-Amzn-Errortype`
  header, correct HTTP status from the model's `httpStatusCode`.
- `GetQueryResults` before completion raises Athena's exact 400:
  `InvalidRequestException` `"Query has not yet finished. Current state: <state>"`
  (ADR-0009; verified real-Athena behavior).

## Consequences

- Zero coupling to moto internals: we can evolve dispatch freely and stay
  black-box compatible.
- Botocore/stubs accept every response byte-for-byte; awswrangler's error
  sniffing (`InvalidRequestException` + `"Exception parsing query"` /
  `"extraneous input"` at `awswrangler/athena/_utils.py:888-898`) must keep
  matching after our error text mapping from Trino errors.