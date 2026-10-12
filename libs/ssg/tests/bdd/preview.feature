Feature: Preview server rebuilds and serves edited content

  `ssg preview` builds the site, serves the output directory over HTTP, and
  rebuilds affected pages when sources change on disk. `--collection`
  scopes the build, the index, and the watched directories to the named
  collection.

  Scenario: An edited page is rebuilt and served during preview
    Given a site
    And a "docs" collection with a page "overview" showing "version one"
    When I run "ssg preview" for the site
    Then the served "docs/overview.html" shows "version one"
    When I edit the "overview" source to "version two"
    Then the served "docs/overview.html" shows "version two"

  Scenario: A selected collection is the only one served
    Given a site
    And a "docs" collection with a page "overview" showing "docs overview"
    And a "blog" collection with a page "post" showing "blog post"
    When I run "ssg preview" for the site with "--collection" "docs"
    Then the served "docs/overview.html" shows "docs overview"
    And the page "blog/post.html" is not served
    And the served index lists "Docs Collection" and not "Blog Collection"
