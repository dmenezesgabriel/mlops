Feature: Inline GetQueryResults pagination (AR-3)

  Inline result reads page the cached terminal page with MaxResults and an
  opaque NextToken. The header row appears only on the first page, and the
  token disappears once no rows remain — the exact contract botocore's
  get_query_results paginator (wrangler's `_fetch_api_result` path,
  awswrangler/athena/_read.py:335-384) relies on to merge pages back.

  Scenario: rows page across MaxResults boundaries
    Given a SUCCEEDED query result with 5 rows
    When GetQueryResults requests MaxResults 2
    Then the page has the header and 2 data rows and a NextToken
    When GetQueryResults continues with the NextToken and MaxResults 2
    Then the page has 2 data rows and a NextToken
    When GetQueryResults continues with the NextToken and MaxResults 2
    Then the page has 1 data row and no NextToken

  Scenario: out-of-range MaxResults is rejected
    Given a SUCCEEDED query result with 1 row
    When GetQueryResults requests MaxResults 1001
    Then the request fails with InvalidRequestException naming "1001"

  Scenario: an undecodable NextToken is rejected
    Given a SUCCEEDED query result with 1 row
    When GetQueryResults requests NextToken "nonsense"
    Then the request fails with InvalidRequestException "Invalid NextToken"