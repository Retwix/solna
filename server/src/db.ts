import { Pool, PoolClient } from "pg";
import { randomUUID } from "crypto";
import path from "path";

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
    console.log("🔍 Testing database connection...");

    // Get a client from the pool
    client = await pool.connect();

    // Test the connection with a simple query
    const result = await client.query("SELECT 1 as test, NOW() as timestamp");

    if (result.rows.length > 0) {
      console.log("✅ Database connection successful");
      console.log(
        `📊 Connection test result: ${JSON.stringify(result.rows[0])}`
      );
      return true;
    } else {
      console.error("❌ Database connection test failed: No rows returned");
      return false;
    }
  } catch (err) {
    console.error("❌ Database connection failed:", err);

    // Log specific error details for debugging
    if (err instanceof Error) {
      console.error(`   Error name: ${err.name}`);
      console.error(`   Error message: ${err.message}`);
      if ("code" in err) {
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
    console.log("🔄 Closing database connection pool...");
    await pool.end();
    console.log("✅ Database connection pool closed successfully");
  } catch (err) {
    console.error("❌ Error closing database connection pool:", err);
    throw err;
  }
};

/**
 * Extracts the event name from a file path.
 * Expected path format: /home/foo/upload/[event-name]/filename.ext
 * If no event folder is present, returns "default"
 *
 * @param filePath - The full file path
 * @returns The extracted event name
 */
export const extractEventFromPath = (filePath: string): string => {
  try {
    // Normalize the path and remove leading/trailing slashes
    const normalizedPath = path.normalize(filePath).replace(/^\/+|\/+$/g, "");

    // Split the path into segments
    const pathSegments = normalizedPath.split(path.sep);

    // Expected structure: home/foo/upload/[event-name]/filename.ext
    // Find the upload directory index
    const uploadIndex = pathSegments.findIndex(
      (segment) => segment === "upload"
    );

    if (uploadIndex === -1) {
      console.warn(`⚠️  Upload directory not found in path: ${filePath}`);
      return "default";
    }

    // Check if there's an event folder after the upload directory
    const eventIndex = uploadIndex + 1;
    if (eventIndex < pathSegments.length - 1) {
      // There's a folder between upload and the filename
      const eventName = pathSegments[eventIndex];

      // Validate event name (basic sanitization)
      if (
        eventName &&
        eventName.length > 0 &&
        eventName !== "." &&
        eventName !== ".."
      ) {
        console.log(
          `📁 Extracted event name: "${eventName}" from path: ${filePath}`
        );
        return eventName;
      }
    }

    // No event folder found, file is directly in upload directory
    console.log(
      `📁 No event folder found in path: ${filePath}, using default event`
    );
    return "default";
  } catch (err) {
    console.error(`❌ Error extracting event from path "${filePath}":`, err);
    return "default";
  }
};

export const insertFile = async (filePath: string) => {
  const uuid = randomUUID();
  const now = new Date();

  // Extract event name from the file path
  const eventName = extractEventFromPath(filePath);

  const query = `
    INSERT INTO uploaded_files (id, filename, event, created_at)
    VALUES ($1, $2, $3, $4)
  `;

  console.log(`📝 Processing file: ${filePath} -> Event: ${eventName}`);

  try {
    await pool.query(query, [uuid, filePath, eventName, now]);
    console.log(
      `📝 File metadata inserted: ${filePath} (${eventName}) with ID: ${uuid}`
    );
  } catch (err) {
    // Re-throw with additional context for better error handling upstream
    console.error("❌ Database insert operation failed:", err);
    throw err;
  }
};

export default pool;
