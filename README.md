docker exec -u root -it airflow@9efd71ca9624 /bin/bash
chmod -R 777 /opt/airflow/logs
chmod -R 777 /opt/airflow/dags
chmod -R 777 /opt/airflow/plugins
chmod -R 777 /opt/airflow/bitrix_to_postgres
