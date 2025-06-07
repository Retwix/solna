import app from "./app";
import { testConnection, closePool, getPoolStatus } from "./db";

const port = process.env.PORT || 3000;

// Enhanced server startup with database connection validation
const startServer = async () => {
  try {
    console.log('🚀 Starting Solna API Server...');
    console.log(`📍 Environment: ${process.env.NODE_ENV || 'development'}`);
    console.log(`🔗 Database URL: ${process.env.DATABASE_URL ? '[CONFIGURED]' : '[NOT SET]'}`);

    // Test database connection before starting the server
    const dbConnected = await testConnection();

    if (!dbConnected) {
      console.error('💥 Failed to connect to database. Server startup aborted.');
      console.error('🔧 Please check:');
      console.error('   - Database service is running (docker-compose up db)');
      console.error('   - DATABASE_URL environment variable is correctly set');
      console.error('   - Network connectivity to database');
      process.exit(1);
    }

    // Log initial pool status
    const poolStatus = getPoolStatus();
    console.log(`📊 Database pool initialized: ${JSON.stringify(poolStatus)}`);

    // Start the Express server
    const server = app.listen(port, () => {
      console.log(`✅ Server running on http://localhost:${port}`);
      console.log('🎯 API Endpoints:');
      console.log('   GET  / - Health check');
      console.log('   POST /file-changed - File change notifications');
      console.log('📡 Ready to receive requests...');
    });

    // Graceful shutdown handling
    const gracefulShutdown = async (signal: string) => {
      console.log(`\n🛑 Received ${signal}. Starting graceful shutdown...`);

      // Stop accepting new connections
      server.close(async (err) => {
        if (err) {
          console.error('❌ Error during server shutdown:', err);
        } else {
          console.log('✅ HTTP server closed');
        }

        try {
          // Close database connections
          await closePool();
          console.log('🎉 Graceful shutdown completed');
          process.exit(0);
        } catch (dbErr) {
          console.error('❌ Error during database shutdown:', dbErr);
          process.exit(1);
        }
      });

      // Force shutdown after 10 seconds
      setTimeout(() => {
        console.error('⏰ Forced shutdown after timeout');
        process.exit(1);
      }, 10000);
    };

    // Register signal handlers for graceful shutdown
    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
    process.on('SIGINT', () => gracefulShutdown('SIGINT'));

    // Handle uncaught exceptions
    process.on('uncaughtException', (err) => {
      console.error('💥 Uncaught Exception:', err);
      gracefulShutdown('UNCAUGHT_EXCEPTION');
    });

    // Handle unhandled promise rejections
    process.on('unhandledRejection', (reason, promise) => {
      console.error('💥 Unhandled Rejection at:', promise, 'reason:', reason);
      gracefulShutdown('UNHANDLED_REJECTION');
    });

  } catch (err) {
    console.error('💥 Failed to start server:', err);
    process.exit(1);
  }
};

// Start the server
startServer();
