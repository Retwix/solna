import express, { Request, Response } from "express";
import { insertFile, getPoolStatus, extractEventFromPath } from "./db";
import photoRoutes from "./routes/photoRoutes";

const app = express();

app.use(express.json());
app.use("/", photoRoutes);

// Enhanced health check endpoint with database status
app.get("/", (_req: Request, res: Response) => {
  try {
    const poolStatus = getPoolStatus();
    res.json({
      status: "healthy",
      message: "Solna API Server is running",
      timestamp: new Date().toISOString(),
      database: {
        pool: poolStatus,
        connected: poolStatus.totalCount > 0,
      },
    });
  } catch (err) {
    console.error("Health check error:", err);
    res.status(503).json({
      status: "unhealthy",
      message: "Service unavailable",
      timestamp: new Date().toISOString(),
      error: "Database connection issue",
    });
  }
});

interface FileChangedRequestBody {
  file: string;
  event: string; // inotify event type (CREATE, MODIFY, etc.)
}

// Enhanced file-changed endpoint with detailed error handling
app.post(
  "/file-changed",
  async (
    req: Request<unknown, unknown, FileChangedRequestBody>,
    res: Response
  ): Promise<void> => {
    const startTime = Date.now();
    const { file, event } = req.body;

    // Input validation
    if (!file || !event) {
      console.warn(
        `⚠️  Invalid request: missing required fields. File: "${file}", Event: "${event}"`
      );
      res.status(400).json({
        error: "Bad Request",
        message: "Both 'file' and 'event' fields are required",
        timestamp: new Date().toISOString(),
      });
      return;
    }

    // Extract the event name from the file path for database storage
    const extractedEventName = extractEventFromPath(file);

    // Log the incoming request with both inotify event and extracted event name
    console.log(
      `📥 File change notification: ${file} (inotify: ${event}, event: ${extractedEventName})`
    );

    try {
      await insertFile(file);

      const duration = Date.now() - startTime;
      console.log(`✅ File metadata stored successfully in ${duration}ms`);

      res.status(200).json({
        success: true,
        message: "File metadata stored",
        data: {
          file,
          inotifyEvent: event,
          extractedEvent: extractedEventName,
          timestamp: new Date().toISOString(),
          processingTime: `${duration}ms`,
        },
      });
    } catch (err) {
      const duration = Date.now() - startTime;

      // Enhanced error logging with categorization
      console.error(`❌ Database insert error after ${duration}ms:`, err);

      let errorMessage = "Internal Server Error";
      let statusCode = 500;

      if (err instanceof Error) {
        console.error(`   Error type: ${err.constructor.name}`);
        console.error(`   Error message: ${err.message}`);

        // Handle specific PostgreSQL errors
        if ("code" in err) {
          const pgError = err as any;
          console.error(`   PostgreSQL error code: ${pgError.code}`);

          switch (pgError.code) {
            case "23505": // Unique violation
              errorMessage = "Duplicate entry detected";
              statusCode = 409;
              break;
            case "23503": // Foreign key violation
              errorMessage = "Referenced record not found";
              statusCode = 400;
              break;
            case "23514": // Check violation
              errorMessage = "Data validation failed";
              statusCode = 400;
              break;
            case "08003": // Connection does not exist
            case "08006": // Connection failure
            case "08001": // Unable to connect
              errorMessage = "Database connection error";
              statusCode = 503;
              break;
            case "57014": // Query canceled
              errorMessage = "Database operation timeout";
              statusCode = 504;
              break;
            default:
              errorMessage = "Database operation failed";
              break;
          }
        }

        // Handle connection timeout errors
        if (
          err.message.includes("timeout") ||
          err.message.includes("ETIMEDOUT")
        ) {
          errorMessage = "Database operation timeout";
          statusCode = 504;
        }
      }

      // Log pool status for debugging
      try {
        const poolStatus = getPoolStatus();
        console.error(`   Pool status: ${JSON.stringify(poolStatus)}`);
      } catch (poolErr) {
        console.error(`   Could not get pool status: ${poolErr}`);
      }

      res.status(statusCode).json({
        error: errorMessage,
        message: "Failed to store file metadata",
        timestamp: new Date().toISOString(),
        processingTime: `${duration}ms`,
        ...(process.env.NODE_ENV === "development" && {
          debug: {
            file,
            inotifyEvent: event,
            extractedEvent: extractedEventName,
            errorType: err instanceof Error ? err.constructor.name : "Unknown",
          },
        }),
      });
    }
  }
);

export default app;
