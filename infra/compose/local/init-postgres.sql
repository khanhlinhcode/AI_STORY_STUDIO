CREATE DATABASE mlflow_db;
CREATE DATABASE n8n_db;

\connect studio
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\connect mlflow_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

\connect n8n_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

