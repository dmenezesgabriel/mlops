# Monitoring

Continuous monitoring is essential to ensure that models remain accurate over time as production data distributions change. 

In this stage, we compare the features of incoming production request traffic against our training baseline to calculate **feature drift** and monitor operational and performance metrics.

Below is the latest generated model performance and feature drift report:

{{ include_source("reports/monitoring.md") }}
