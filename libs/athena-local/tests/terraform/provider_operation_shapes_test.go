package terraformparity

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"testing"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/athena"
	"github.com/aws/aws-sdk-go-v2/service/athena/types"
)

func loadAWSConfig(t *testing.T) aws.Config {
	t.Helper()
	configuration, err := config.LoadDefaultConfig(
		context.Background(),
		config.WithRegion("us-east-1"),
		config.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider("test", "test", ""),
		),
	)
	if err != nil {
		t.Fatalf("load AWS configuration: %v", err)
	}
	return configuration
}

func newClient(t *testing.T) *athena.Client {
	t.Helper()
	if os.Getenv("AWS_ENDPOINT_URL_ATHENA") == "" {
		t.Skip("AWS_ENDPOINT_URL_ATHENA is required for the live parity test")
	}
	return athena.NewFromConfig(loadAWSConfig(t))
}

func uniqueName(prefix string) string {
	return fmt.Sprintf("%s_%s", prefix, strconv.FormatInt(time.Now().UnixNano(), 10))
}

func requiredEnvironment(t *testing.T, name string) string {
	t.Helper()
	value := os.Getenv(name)
	if value == "" {
		t.Fatalf("%s is required", name)
	}
	return value
}

func requireNoError(t *testing.T, operation string, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("%s: %v", operation, err)
	}
}

func requireEqualString(t *testing.T, member string, actual *string, expected string) {
	t.Helper()
	if actual == nil || *actual != expected {
		t.Fatalf("%s = %v, want %q", member, actual, expected)
	}
}

func requireEqualCatalogType(t *testing.T, member string, actual types.DataCatalogType, expected types.DataCatalogType) {
	t.Helper()
	if actual != expected {
		t.Fatalf("%s = %q, want %q", member, actual, expected)
	}
}

func exerciseWorkGroup(t *testing.T, client *athena.Client, context context.Context) {
	t.Helper()
	name := uniqueName("go_wg")
	_, err := client.CreateWorkGroup(context, &athena.CreateWorkGroupInput{
		Name:          aws.String(name),
		Description:   aws.String("Terraform parity"),
		Configuration: &types.WorkGroupConfiguration{EnforceWorkGroupConfiguration: aws.Bool(true)},
	})
	requireNoError(t, "CreateWorkGroup", err)
	t.Cleanup(func() {
		_, _ = client.DeleteWorkGroup(context, &athena.DeleteWorkGroupInput{WorkGroup: aws.String(name)})
	})

	workgroup, err := client.GetWorkGroup(context, &athena.GetWorkGroupInput{WorkGroup: aws.String(name)})
	requireNoError(t, "GetWorkGroup", err)
	requireEqualString(t, "WorkGroup.Name", workgroup.WorkGroup.Name, name)
	if workgroup.WorkGroup.State != types.WorkGroupStateEnabled {
		t.Fatalf("WorkGroup.State = %q, want ENABLED", workgroup.WorkGroup.State)
	}

	_, err = client.UpdateWorkGroup(context, &athena.UpdateWorkGroupInput{
		WorkGroup:   aws.String(name),
		Description: aws.String("Terraform parity updated"),
		State:       types.WorkGroupStateDisabled,
	})
	requireNoError(t, "UpdateWorkGroup", err)
	workgroup, err = client.GetWorkGroup(context, &athena.GetWorkGroupInput{WorkGroup: aws.String(name)})
	requireNoError(t, "GetWorkGroup after update", err)
	requireEqualString(t, "WorkGroup.Description", workgroup.WorkGroup.Description, "Terraform parity updated")
	if workgroup.WorkGroup.State != types.WorkGroupStateDisabled {
		t.Fatalf("WorkGroup.State = %q, want DISABLED", workgroup.WorkGroup.State)
	}

	_, err = client.DeleteWorkGroup(context, &athena.DeleteWorkGroupInput{WorkGroup: aws.String(name)})
	requireNoError(t, "DeleteWorkGroup", err)
}

func exerciseNamedQuery(t *testing.T, client *athena.Client, context context.Context, database string, workgroup string) {
	t.Helper()
	name := uniqueName("go_named_query")
	created, err := client.CreateNamedQuery(context, &athena.CreateNamedQueryInput{
		Database:    aws.String(database),
		Name:        aws.String(name),
		QueryString: aws.String("SELECT 1"),
		WorkGroup:   aws.String(workgroup),
	})
	requireNoError(t, "CreateNamedQuery", err)
	if created.NamedQueryId == nil {
		t.Fatal("CreateNamedQuery returned no NamedQueryId")
	}
	t.Cleanup(func() {
		_, _ = client.DeleteNamedQuery(context, &athena.DeleteNamedQueryInput{NamedQueryId: created.NamedQueryId})
	})

	query, err := client.GetNamedQuery(context, &athena.GetNamedQueryInput{NamedQueryId: created.NamedQueryId})
	requireNoError(t, "GetNamedQuery", err)
	requireEqualString(t, "NamedQuery.Name", query.NamedQuery.Name, name)
	requireEqualString(t, "NamedQuery.Database", query.NamedQuery.Database, database)
	requireEqualString(t, "NamedQuery.WorkGroup", query.NamedQuery.WorkGroup, workgroup)

	_, err = client.DeleteNamedQuery(context, &athena.DeleteNamedQueryInput{NamedQueryId: created.NamedQueryId})
	requireNoError(t, "DeleteNamedQuery", err)
}

func exerciseDataCatalog(t *testing.T, client *athena.Client, context context.Context) {
	t.Helper()
	name := uniqueName("go_catalog")
	created, err := client.CreateDataCatalog(context, &athena.CreateDataCatalogInput{
		Name:        aws.String(name),
		Type:        types.DataCatalogTypeLambda,
		Description: aws.String("Terraform parity catalog"),
		Parameters:  map[string]string{"function": "arn:aws:lambda:us-east-1:123456789012:function:one"},
	})
	requireNoError(t, "CreateDataCatalog", err)
	requireEqualString(t, "CreateDataCatalog.Name", created.DataCatalog.Name, name)
	t.Cleanup(func() {
		_, _ = client.DeleteDataCatalog(context, &athena.DeleteDataCatalogInput{Name: aws.String(name)})
	})

	catalog, err := client.GetDataCatalog(context, &athena.GetDataCatalogInput{Name: aws.String(name)})
	requireNoError(t, "GetDataCatalog", err)
	requireEqualCatalogType(t, "DataCatalog.Type", catalog.DataCatalog.Type, types.DataCatalogTypeLambda)

	_, err = client.UpdateDataCatalog(context, &athena.UpdateDataCatalogInput{
		Name:        aws.String(name),
		Type:        types.DataCatalogTypeLambda,
		Description: aws.String("Terraform parity catalog updated"),
		Parameters:  map[string]string{"function": "arn:aws:lambda:us-east-1:123456789012:function:two"},
	})
	requireNoError(t, "UpdateDataCatalog", err)
	catalog, err = client.GetDataCatalog(context, &athena.GetDataCatalogInput{Name: aws.String(name)})
	requireNoError(t, "GetDataCatalog after update", err)
	requireEqualString(t, "DataCatalog.Description", catalog.DataCatalog.Description, "Terraform parity catalog updated")

	deleted, err := client.DeleteDataCatalog(context, &athena.DeleteDataCatalogInput{Name: aws.String(name)})
	requireNoError(t, "DeleteDataCatalog", err)
	requireEqualString(t, "DeleteDataCatalog.Name", deleted.DataCatalog.Name, name)
}

func exercisePreparedStatement(t *testing.T, client *athena.Client, context context.Context, workgroup string) {
	t.Helper()
	name := uniqueName("go_statement")
	_, err := client.CreatePreparedStatement(context, &athena.CreatePreparedStatementInput{
		StatementName:  aws.String(name),
		WorkGroup:      aws.String(workgroup),
		QueryStatement: aws.String("SELECT ?"),
		Description:    aws.String("Terraform parity statement"),
	})
	requireNoError(t, "CreatePreparedStatement", err)
	t.Cleanup(func() {
		_, _ = client.DeletePreparedStatement(context, &athena.DeletePreparedStatementInput{StatementName: aws.String(name), WorkGroup: aws.String(workgroup)})
	})

	statement, err := client.GetPreparedStatement(context, &athena.GetPreparedStatementInput{StatementName: aws.String(name), WorkGroup: aws.String(workgroup)})
	requireNoError(t, "GetPreparedStatement", err)
	requireEqualString(t, "PreparedStatement.StatementName", statement.PreparedStatement.StatementName, name)
	requireEqualString(t, "PreparedStatement.QueryStatement", statement.PreparedStatement.QueryStatement, "SELECT ?")

	_, err = client.UpdatePreparedStatement(context, &athena.UpdatePreparedStatementInput{
		StatementName:  aws.String(name),
		WorkGroup:      aws.String(workgroup),
		QueryStatement: aws.String("SELECT ? + 1"),
		Description:    aws.String("Terraform parity statement updated"),
	})
	requireNoError(t, "UpdatePreparedStatement", err)
	statement, err = client.GetPreparedStatement(context, &athena.GetPreparedStatementInput{StatementName: aws.String(name), WorkGroup: aws.String(workgroup)})
	requireNoError(t, "GetPreparedStatement after update", err)
	requireEqualString(t, "PreparedStatement.QueryStatement", statement.PreparedStatement.QueryStatement, "SELECT ? + 1")

	_, err = client.DeletePreparedStatement(context, &athena.DeletePreparedStatementInput{StatementName: aws.String(name), WorkGroup: aws.String(workgroup)})
	requireNoError(t, "DeletePreparedStatement", err)
}

func startDdl(t *testing.T, client *athena.Client, context context.Context, query string, outputLocation string, workgroup string) string {
	t.Helper()
	started, err := client.StartQueryExecution(context, &athena.StartQueryExecutionInput{
		QueryString:         aws.String(query),
		ResultConfiguration: &types.ResultConfiguration{OutputLocation: aws.String(outputLocation)},
		WorkGroup:           aws.String(workgroup),
	})
	requireNoError(t, "StartQueryExecution "+query, err)
	if started.QueryExecutionId == nil {
		t.Fatalf("StartQueryExecution %s returned no QueryExecutionId", query)
	}
	return *started.QueryExecutionId
}

func waitForSuccess(t *testing.T, client *athena.Client, context context.Context, queryID string) {
	t.Helper()
	deadline := time.Now().Add(30 * time.Second)
	for time.Now().Before(deadline) {
		response, err := client.GetQueryExecution(context, &athena.GetQueryExecutionInput{QueryExecutionId: aws.String(queryID)})
		requireNoError(t, "GetQueryExecution "+queryID, err)
		if response.QueryExecution == nil || response.QueryExecution.Status == nil {
			t.Fatalf("GetQueryExecution %s returned no status", queryID)
		}
		state := response.QueryExecution.Status.State
		if state == types.QueryExecutionStateSucceeded {
			return
		}
		if state == types.QueryExecutionStateFailed || state == types.QueryExecutionStateCancelled {
			t.Fatalf("query %s reached %s: %s", queryID, state, aws.ToString(response.QueryExecution.Status.StateChangeReason))
		}
		time.Sleep(100 * time.Millisecond)
	}
	t.Fatalf("query %s did not succeed within 30s", queryID)
}

func readDdlResults(t *testing.T, client *athena.Client, context context.Context, queryID string) {
	t.Helper()
	results, err := client.GetQueryResults(context, &athena.GetQueryResultsInput{QueryExecutionId: aws.String(queryID)})
	requireNoError(t, "GetQueryResults "+queryID, err)
	if results.ResultSet == nil {
		t.Fatalf("GetQueryResults %s returned no ResultSet", queryID)
	}
}

func exerciseDatabase(t *testing.T, client *athena.Client, context context.Context) {
	t.Helper()
	outputLocation := requiredEnvironment(t, "ATHENA_PROVIDER_OUTPUT_LOCATION")
	workgroup := requiredEnvironment(t, "ATHENA_PROVIDER_WORKGROUP")
	name := uniqueName("go_database")
	createID := startDdl(t, client, context, fmt.Sprintf("create database `%s`;", name), outputLocation, workgroup)
	waitForSuccess(t, client, context, createID)
	readDdlResults(t, client, context, createID)

	_, err := client.GetDatabase(context, &athena.GetDatabaseInput{CatalogName: aws.String("AwsDataCatalog"), DatabaseName: aws.String(name)})
	requireNoError(t, "GetDatabase", err)
	dropped := false
	t.Cleanup(func() {
		if dropped {
			return
		}
		_, _ = client.StartQueryExecution(context, &athena.StartQueryExecutionInput{
			QueryString:         aws.String(fmt.Sprintf("drop database `%s`;", name)),
			ResultConfiguration: &types.ResultConfiguration{OutputLocation: aws.String(outputLocation)},
			WorkGroup:           aws.String(workgroup),
		})
	})

	dropID := startDdl(t, client, context, fmt.Sprintf("drop database `%s`;", name), outputLocation, workgroup)
	waitForSuccess(t, client, context, dropID)
	dropped = true
	readDdlResults(t, client, context, dropID)
}

func TestProviderOperationShapes(t *testing.T) {
	if os.Getenv("AWS_ENDPOINT_URL_ATHENA") == "" {
		t.Skip("AWS_ENDPOINT_URL_ATHENA is required for the live parity test")
	}
	client := newClient(t)
	context := context.Background()
	workgroup := requiredEnvironment(t, "ATHENA_PROVIDER_WORKGROUP")
	database := requiredEnvironment(t, "ATHENA_PROVIDER_DATABASE")
	exerciseWorkGroup(t, client, context)
	exerciseNamedQuery(t, client, context, database, workgroup)
	exerciseDataCatalog(t, client, context)
	exercisePreparedStatement(t, client, context, workgroup)
	exerciseDatabase(t, client, context)
}
