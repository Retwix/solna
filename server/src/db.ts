import { Pool, PoolClient } from "pg";
import { randomUUID } from "crypto";

// Enhanced connection pool configuration for production reliability
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20, // Maximum number of clients in the pool
  idleTimeoutMillis: 30000, // Close idle clients after 30 seconds
  connectionTimeoutMillis: 2000, // Return an error after 2 seconds if connection could not be established
  statement_timeout: 30000, // Maximum time to wait for a query to complete (30 seconds)
  query_timeout: 30000, // Maximum time to wait for a query to complete (30 seconds)
});

// Database connection health check function
export const testConnection = async (): Promise<boolean> => {
  let client: PoolClient | null = null;

  try {
    console.log('🔍 Testing database connection...');

    // Get a client from the pool
    client = await pool.connect();

    // Test the connection with a simple query
    const result = await client.query('SELECT 1 as test, NOW() as timestamp');

    if (result.rows.length > 0) {
      console.log('✅ Database connection successful');
      console.log(`📊 Connection test result: ${JSON.stringify(result.rows[0])}`);
      return true;
    } else {
      console.error('❌ Database connection test failed: No rows returned');
      return false;
    }
  } catch (err) {
    console.error('❌ Database connection failed:', err);

    // Log specific error details for debugging
    if (err instanceof Error) {
      console.error(`   Error name: ${err.name}`);
      console.error(`   Error message: ${err.message}`);
      if ('code' in err) {
        console.error(`   Error code: ${err.code}`);
      }
    }

    return false;
  } finally {
    // Always release the client back to the pool
    if (client) {
      client.release();
    }
  }
};

// Get pool status for monitoring
export const getPoolStatus = () => {
  return {
    totalCount: pool.totalCount,
    idleCount: pool.idleCount,
    waitingCount: pool.waitingCount,
  };
};

// Graceful shutdown function
export const closePool = async (): Promise<void> => {
  try {
    console.log('🔄 Closing database connection pool...');
    await pool.end();
    console.log('✅ Database connection pool closed successfully');
  } catch (err) {
    console.error('❌ Error closing database connection pool:', err);
    throw err;
  }
};

export const insertFile = async (file: string, event: string) => {
  const uuid = randomUUID();
  const now = new Date();

  const query = `
    INSERT INTO uploaded_files (id, filename, event, created_at)
    VALUES ($1, $2, $3, $4)
  `;

  try {
    await pool.query(query, [uuid, file, event, now]);
    console.log(`📝 File metadata inserted: ${file} (${event}) with ID: ${uuid}`);
  } catch (err) {
    // Re-throw with additional context for better error handling upstream
    console.error('❌ Database insert operation failed:', err);
    throw err;
  }
};
