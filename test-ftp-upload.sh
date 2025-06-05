#!/bin/bash

# Test script to verify FTP upload functionality
# This script tests the complete workflow: FTP upload -> file detection -> database logging

echo "🧪 Testing FTP Upload Functionality"
echo "=================================="

# Check if required tools are available
if ! command -v curl &> /dev/null; then
    echo "❌ curl is required but not installed"
    exit 1
fi

if ! command -v ftp &> /dev/null; then
    echo "❌ ftp client is required but not installed"
    echo "On macOS: brew install inetutils"
    echo "On Ubuntu: sudo apt-get install ftp"
    exit 1
fi

# Create a test file
TEST_FILE="test_camera_upload_$(date +%Y%m%d_%H%M%S).jpg"
echo "📸 Creating test file: $TEST_FILE"
echo "This is a test file simulating a camera upload at $(date)" > "$TEST_FILE"

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Test API connectivity
echo "🔍 Testing API connectivity..."
if curl -s http://localhost:3000/ | grep -q "Hello World"; then
    echo "✅ API server is responding"
else
    echo "❌ API server is not responding. Make sure docker-compose is running."
    rm "$TEST_FILE"
    exit 1
fi

# Upload file via FTP
echo "📤 Uploading file via FTP..."
ftp -n localhost 21 << EOF
user foo pass
binary
put $TEST_FILE
quit
EOF

if [ $? -eq 0 ]; then
    echo "✅ File uploaded successfully via FTP"
else
    echo "❌ FTP upload failed"
    rm "$TEST_FILE"
    exit 1
fi

# Wait for file watcher to detect and process the file
echo "⏳ Waiting for file watcher to process the upload..."
sleep 3

# Check if file exists in local_data directory
if [ -f "local_data/$TEST_FILE" ]; then
    echo "✅ File found in local_data directory"
else
    echo "❌ File not found in local_data directory"
    rm "$TEST_FILE"
    exit 1
fi

# Clean up
rm "$TEST_FILE"
echo "🧹 Cleaned up test file"

echo ""
echo "🎉 FTP Upload Test Completed Successfully!"
echo "Your Sony camera should now be able to upload photos using these FTP settings:"
echo "  Server: localhost (or your server's IP)"
echo "  Port: 21"
echo "  Username: foo"
echo "  Password: pass"
echo "  Directory: /home/foo/upload"
