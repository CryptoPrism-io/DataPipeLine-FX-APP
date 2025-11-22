# GitHub Secrets Setup Guide

This guide explains how to configure GitHub Secrets for the CI/CD workflow to store data in an **external PostgreSQL database**.

---

## Required Secrets

You need to add these secrets to your GitHub repository:

### 1. OANDA API Configuration

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `OANDA_API_KEY` | Your OANDA API token | `abc123xyz...` |
| `OANDA_ENVIRONMENT` | OANDA environment | `demo` or `live` |

### 2. PostgreSQL Database Configuration

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `POSTGRES_HOST` | Database host/endpoint | `mydb.abc123.us-east-1.rds.amazonaws.com` |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_DB` | Database name | `fx_trading_data` |
| `POSTGRES_USER` | Database username | `postgres` or `fx_admin` |
| `POSTGRES_PASSWORD` | Database password | `your_secure_password` |

### 3. Redis Configuration (Optional)

| Secret Name | Description | Example | Required? |
|-------------|-------------|---------|-----------|
| `REDIS_HOST` | Redis host | `redis.example.com` | No (uses localhost) |
| `REDIS_PORT` | Redis port | `6379` | No (uses 6379) |

---

## How to Add Secrets to GitHub

### Step 1: Go to Repository Settings

1. Open your repository: https://github.com/CryptoPrism-io/DataPipeLine-FX-APP
2. Click **Settings** (top menu)
3. In the left sidebar, click **Secrets and variables** → **Actions**

### Step 2: Add Each Secret

For each secret listed above:

1. Click **New repository secret** (green button)
2. Enter the **Name** (exactly as shown in the table)
3. Enter the **Value**
4. Click **Add secret**

---

## Database Setup Options

### Option A: AWS RDS (Recommended for Production)

**Create PostgreSQL Instance:**

```bash
# Via AWS Console:
1. Go to RDS → Create Database
2. Choose PostgreSQL 15
3. Template: Free tier or Production
4. DB instance identifier: fx-trading-db
5. Master username: postgres
6. Master password: <secure_password>
7. DB name: fx_trading_data
8. Public access: Yes (or use VPN)
9. Security group: Allow port 5432 from GitHub IPs

# Get endpoint:
# mydb.abc123.us-east-1.rds.amazonaws.com
```

**GitHub Secrets:**
- `POSTGRES_HOST`: `mydb.abc123.us-east-1.rds.amazonaws.com`
- `POSTGRES_PORT`: `5432`
- `POSTGRES_DB`: `fx_trading_data`
- `POSTGRES_USER`: `postgres`
- `POSTGRES_PASSWORD`: `<your_password>`

### Option B: DigitalOcean Managed Database

**Create Database:**

```bash
# Via DigitalOcean Console:
1. Create → Databases → PostgreSQL
2. Choose region and plan
3. Database name: fx-trading-db
4. Create

# Get connection details from dashboard
```

**GitHub Secrets:**
- `POSTGRES_HOST`: `db-postgresql-nyc1-12345.ondigitalocean.com`
- `POSTGRES_PORT`: `25060`
- `POSTGRES_DB`: `fx_trading_data`
- `POSTGRES_USER`: `doadmin`
- `POSTGRES_PASSWORD`: `<provided_password>`

### Option C: Heroku Postgres

**Create Database:**

```bash
# Using Heroku CLI:
heroku addons:create heroku-postgresql:mini -a your-app

# Get credentials:
heroku pg:credentials:url DATABASE_URL -a your-app
```

**GitHub Secrets:**
- Extract host, port, dbname, user, password from the URL

### Option D: Supabase (Free Tier Available)

**Create Project:**

```bash
# Via Supabase Dashboard:
1. New project → fx-trading-data
2. Database password: <secure_password>
3. Region: Select closest

# Get connection string from Settings → Database
```

**GitHub Secrets:**
- `POSTGRES_HOST`: `db.abc123.supabase.co`
- `POSTGRES_PORT`: `5432`
- `POSTGRES_DB`: `postgres`
- `POSTGRES_USER`: `postgres`
- `POSTGRES_PASSWORD`: `<your_password>`

### Option E: Railway (Free Tier Available)

**Create Database:**

```bash
# Via Railway Dashboard:
1. New Project → PostgreSQL
2. Get connection details from Variables tab
```

---

## Security Considerations

### ✅ Best Practices

1. **Use Strong Passwords**
   - Minimum 16 characters
   - Mix of uppercase, lowercase, numbers, symbols

2. **Restrict Network Access**
   - Whitelist GitHub Actions IP ranges (if possible)
   - Use VPC/private network (AWS RDS, etc.)
   - Enable SSL/TLS encryption

3. **Database User Permissions**
   ```sql
   -- Create dedicated user for GitHub Actions
   CREATE USER github_actions WITH PASSWORD 'secure_password';
   GRANT CONNECT ON DATABASE fx_trading_data TO github_actions;
   GRANT INSERT, SELECT, UPDATE ON ALL TABLES IN SCHEMA public TO github_actions;
   ```

4. **Rotate Secrets Regularly**
   - Change database password every 90 days
   - Update OANDA_API_KEY if compromised

### ⚠️ Security Warnings

- ❌ **Never** commit secrets to git
- ❌ **Never** hardcode passwords in code
- ❌ **Never** expose database publicly without firewall rules
- ✅ **Always** use GitHub Secrets for credentials
- ✅ **Always** use SSL/TLS for database connections
- ✅ **Always** limit database user permissions

---

## Firewall Configuration

### Allow GitHub Actions IPs

If your database has IP whitelisting, add GitHub Actions IP ranges:

**For AWS RDS Security Groups:**
```bash
# Get GitHub Actions IP ranges:
curl https://api.github.com/meta | jq .actions

# Add to security group:
# Inbound Rules → PostgreSQL (5432) → Source: <GitHub_IP_ranges>
```

**For DigitalOcean/Heroku:**
- Most managed databases allow access from anywhere (0.0.0.0/0)
- Use strong passwords and SSL/TLS instead

---

## Testing Database Connection

### Test Locally First

```bash
# Install PostgreSQL client
sudo apt-get install postgresql-client

# Test connection
psql -h <POSTGRES_HOST> -U <POSTGRES_USER> -d <POSTGRES_DB> -c "SELECT version();"

# Initialize schema
psql -h <POSTGRES_HOST> -U <POSTGRES_USER> -d <POSTGRES_DB> -f database/schema.sql
```

### Test in GitHub Actions

After adding secrets:

1. Go to **Actions** tab
2. Click **CI/CD Pipeline**
3. Click **Run workflow**
4. Watch the logs for:
   - ✓ Database connection successful
   - ✓ Schema initialized
   - ✓ Data fetch completed
   - ✓ Data verification complete

---

## Monitoring Database Growth

The workflow will accumulate data over time:

**Expected Growth:**

| Time Period | Candles | Volatility | Correlations | Total Size |
|-------------|---------|------------|--------------|------------|
| 1 day | 480 | 480 | 190 | ~500 KB |
| 1 week | 3,360 | 3,360 | 1,330 | ~3 MB |
| 1 month | 14,400 | 14,400 | 5,700 | ~15 MB |
| 1 year | 175,200 | 175,200 | 69,350 | ~175 MB |

**Database Maintenance:**

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('fx_trading_data'));

-- Check table sizes
SELECT
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Clean old data (optional - keeps 1 year)
DELETE FROM oanda_candles WHERE time < NOW() - INTERVAL '365 days';
DELETE FROM volatility_metrics WHERE time < NOW() - INTERVAL '365 days';
DELETE FROM correlation_matrix WHERE time < NOW() - INTERVAL '365 days';
```

---

## Troubleshooting

### Error: "could not connect to server"

**Cause:** Database not accessible from GitHub Actions

**Solutions:**
1. Check `POSTGRES_HOST` is correct (external IP/hostname)
2. Verify firewall allows GitHub Actions IPs
3. Ensure database is publicly accessible (or use VPN)

### Error: "password authentication failed"

**Cause:** Incorrect credentials

**Solutions:**
1. Verify `POSTGRES_USER` and `POSTGRES_PASSWORD` are correct
2. Check database user has correct permissions
3. Test connection locally with same credentials

### Error: "database does not exist"

**Cause:** Database name doesn't exist

**Solutions:**
1. Create database: `CREATE DATABASE fx_trading_data;`
2. Verify `POSTGRES_DB` secret matches actual database name

### Error: "permission denied for table"

**Cause:** Database user lacks permissions

**Solutions:**
```sql
-- Grant permissions to user
GRANT ALL PRIVILEGES ON DATABASE fx_trading_data TO <DB_USER>;
GRANT ALL ON ALL TABLES IN SCHEMA public TO <DB_USER>;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO <DB_USER>;
```

---

## Summary Checklist

Before running the workflow:

- [ ] External PostgreSQL database created
- [ ] Database is accessible from internet (or GitHub IPs whitelisted)
- [ ] Database schema initialized (or workflow will do it)
- [ ] All required secrets added to GitHub:
  - [ ] `OANDA_API_KEY`
  - [ ] `POSTGRES_HOST`
  - [ ] `POSTGRES_DB`
  - [ ] `POSTGRES_USER`
  - [ ] `POSTGRES_PASSWORD`
  - [ ] `POSTGRES_PORT`
- [ ] Connection tested locally
- [ ] Firewall rules configured (if applicable)

**Once complete, trigger the workflow and data will persist in your external database!** 🎉

---

## Cost Estimates

### Free Tier Options

| Provider | Free Tier | Limits |
|----------|-----------|--------|
| **Supabase** | ✅ Yes | 500 MB, 2 GB bandwidth/month |
| **Railway** | ✅ Yes | 500 MB, $5 credit/month |
| **Heroku** | ⚠️ Limited | Mini plan $5/month |
| **AWS RDS** | ✅ Yes (12 months) | 20 GB, 750 hours/month |
| **DigitalOcean** | ❌ No | $15/month minimum |

### Paid Options (Recommended for Production)

| Provider | Cost | Storage |
|----------|------|---------|
| **AWS RDS (db.t3.micro)** | ~$15/month | 20 GB |
| **DigitalOcean Managed** | $15/month | 10 GB |
| **Heroku Standard** | $50/month | 64 GB |

---

**Need help?** Check the workflow logs in GitHub Actions for detailed error messages.
