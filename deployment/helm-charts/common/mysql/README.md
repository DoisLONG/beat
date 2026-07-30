# mysql

Helm chart for deploying Redis Vector DB service.

## Install the Chart

To install the chart, run the following:

```console
cd ${GenAIInfro_repo}/helm-charts/common
helm install mysql mysql
```

## Verify

To verify the installation, run the command `kubectl get pod` to make sure all the mysql pods are runinng.

Then run the command `kubectl port-forward svc/mysql 3306:3306` to expose the mysql service for access.

Open another terminal and run the command `mysqladmin ping -uroot -p${MYSQL_PASSWORD}` to access the mysql db.

## Values

| Key                          | Type   | Default               | Description            |
| ---------------------------- | ------ | --------------------- | ---------------------- |
| image.repository             | string | `"mysql"` |                        |
| image.tag                    | string | `"8.0.39"`          |                        |
| service.port | string | `"3306"`              | The mysql port |
