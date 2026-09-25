package terraformparity

import (
	"context"
	"os"
	"testing"

	"github.com/aws/aws-sdk-go-v2/service/athena"
	"github.com/aws/aws-sdk-go-v2/service/glue"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

func TestEndpointRouting(t *testing.T) {
	if os.Getenv("AWS_ENDPOINT_URL_ATHENA") == "" {
		t.Skip("AWS_ENDPOINT_URL_ATHENA is required for the endpoint routing test")
	}
	context := context.Background()
	configuration := loadAWSConfig(t)

	_, err := athena.NewFromConfig(configuration).ListWorkGroups(context, &athena.ListWorkGroupsInput{})
	requireNoError(t, "route Athena", err)
	_, err = s3.NewFromConfig(configuration).ListBuckets(context, &s3.ListBucketsInput{})
	requireNoError(t, "route S3", err)
	_, err = glue.NewFromConfig(configuration).GetDatabases(context, &glue.GetDatabasesInput{})
	requireNoError(t, "route Glue", err)
}
