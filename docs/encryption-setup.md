# =============================================================================
# Database Encryption Setup Instructions
# =============================================================================

## Prerequisites
1. Backup your database before proceeding
2. Ensure all services are stopped

## Step 1: Generate SSL Certificates

Run the certificate generation script:
```powershell
python scripts/gen_certs.py
```

This will create:
- `certs/server.key` (Private key)
- `certs/server.crt` (Certificate)

## Step 2: Configure Security Key

Add a strong encryption key to your `.env` file:

```bash
# Generate a key (PowerShell)
$key = -join ((48..57) + (65..70) | Get-Random -Count 64 | ForEach-Object {[char]$_})
Write-Host "SECURITY_KEY=$key"
```

Or use OpenSSL if available:
```bash
openssl rand -hex 32
```

Add to `.env`:
```
SECURITY_KEY=your_generated_64_character_hex_key_here
```

⚠️ **CRITICAL**: Store this key securely. If lost, all encrypted data will be unrecoverable.

## Step 3: Database Migration

### Option A: Fresh Database (Recommended for Development)

1. Stop all services:
```powershell
docker-compose down
```

2. Remove old database volume:
```powershell
docker volume rm admin_system_core_postgres_data
```

3. Start services with new schema:
```powershell
docker-compose up -d
```

The new schema with encryption will be created automatically.

### Option B: Production Migration (With Existing Data)

⚠️ **NOTE**: The migration script for existing data is complex and requires careful execution. 

Due to the schema changes (adding `email_hash`, `line_user_id_hash` columns and changing column types), you would need to:

1. Export existing data
2. Drop and recreate tables with new schema
3. Re-import data with encryption

For production systems, we recommend:
- Schedule a maintenance window
- Backup your database
- Test the migration in a staging environment first
- Contact your database administrator

## Step 4: Verify Encryption

After starting the services, verify encryption is working:

```powershell
# Check SSL connection
docker exec -it hsib-sop-db psql -U postgres -d hsib_sop_bot -c "SELECT * FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
```

You should see `ssl = t` (true).

## Step 5: Test the Application

1. Start the application
2. Try to authenticate via the chatbot
3. Check the database directly to confirm data is encrypted:

```powershell
docker exec -it hsib-sop-db psql -U postgres -d hsib_sop_bot -c "SELECT email, line_user_id FROM users LIMIT 1;"
```

The values should appear as hex-encoded encrypted data, not plaintext.

## Troubleshooting

### SSL Connection Failed
- Check that certificates exist in `certs/` directory
- Verify file permissions
- Check PostgreSQL logs: `docker-compose logs db`

### Encryption Key Error
- Verify `SECURITY_KEY` is set in `.env`
- Ensure it's exactly 64 hex characters (32 bytes)
- Restart the application after adding the key

### Database Schema Errors
- For fresh start: Drop the volume and recreate
- For migration: Ensure backup exists before proceeding

## Security Best Practices

1. **Key Rotation**: Plan for periodic key rotation (advanced topic)
2. **Backup Strategy**: Backup both database AND the `SECURITY_KEY`
3. **Access Control**: Limit access to `.env` file and production servers
4. **Monitoring**: Monitor for encryption/decryption errors in logs
